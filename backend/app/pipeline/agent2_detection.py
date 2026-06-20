from collections import defaultdict
from datetime import datetime, timedelta

from app.llm_client import call_llm
from app.schemas import Account, FlaggedPattern, InvestigationGraph, Transaction

STRUCTURING_THRESHOLD = 50_000
STRUCTURING_MIN_TRANSFERS = 4
STRUCTURING_WINDOW = timedelta(hours=48)

LAYERING_MIN_HOPS = 4
LAYERING_WINDOW = timedelta(days=5)
LAYERING_AMOUNT_TOLERANCE = 0.3

MULE_MIN_FANOUT = 5
MULE_CASHOUT_RATIO = 0.8

SYSTEM_PROMPT = (
    "You are an AML (anti-money-laundering) investigator analyzing a candidate "
    "transaction sub-graph that a rule engine has already flagged as structurally "
    "suspicious. Decide whether the pattern genuinely matches the given pattern_type, "
    "and explain WHY the structure is suspicious in investigator terms (not just "
    "restating the rule that matched it). Respond with strict JSON: "
    '{"confirmed": true|false, "reasoning": "2-3 sentences"}'
)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _find_structuring_candidates(transactions: list[Transaction]) -> list[list[Transaction]]:
    by_receiver: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        if tx.amount < STRUCTURING_THRESHOLD:
            by_receiver[tx.to_account].append(tx)

    best_per_receiver: dict[str, list[Transaction]] = {}
    for receiver, txs in by_receiver.items():
        txs_sorted = sorted(txs, key=lambda t: _parse(t.timestamp))
        n = len(txs_sorted)
        for i in range(n):
            window_txs = [txs_sorted[i]]
            for j in range(i + 1, n):
                if _parse(txs_sorted[j].timestamp) - _parse(txs_sorted[i].timestamp) <= STRUCTURING_WINDOW:
                    window_txs.append(txs_sorted[j])
                else:
                    break
            senders = {t.from_account for t in window_txs}
            if len(window_txs) >= STRUCTURING_MIN_TRANSFERS and len(senders) >= STRUCTURING_MIN_TRANSFERS:
                if receiver not in best_per_receiver or len(window_txs) > len(best_per_receiver[receiver]):
                    best_per_receiver[receiver] = window_txs

    return list(best_per_receiver.values())


def _extend_chain(
    chain: list[Transaction],
    outgoing_by_account: dict[str, list[Transaction]],
    used_accounts: set[str],
) -> list[list[Transaction]]:
    last_tx = chain[-1]
    receiver = last_tx.to_account
    if len(chain) >= 6:
        return [chain]

    candidates = [
        tx
        for tx in outgoing_by_account.get(receiver, [])
        if tx.to_account not in used_accounts
        and _parse(tx.timestamp) > _parse(last_tx.timestamp)
        and _parse(tx.timestamp) - _parse(last_tx.timestamp) <= LAYERING_WINDOW
        and abs(tx.amount - last_tx.amount) / last_tx.amount <= LAYERING_AMOUNT_TOLERANCE
    ]
    if not candidates:
        return [chain]

    results = []
    for candidate in candidates:
        results.extend(
            _extend_chain(chain + [candidate], outgoing_by_account, used_accounts | {candidate.to_account})
        )
    return results


def _find_layering_candidates(transactions: list[Transaction]) -> list[list[Transaction]]:
    outgoing_by_account: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        outgoing_by_account[tx.from_account].append(tx)

    chains: list[list[Transaction]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    for tx in transactions:
        full_chains = _extend_chain([tx], outgoing_by_account, {tx.from_account, tx.to_account})
        for chain in full_chains:
            if len(chain) >= LAYERING_MIN_HOPS:
                signature = tuple([chain[0].from_account] + [t.to_account for t in chain])
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    chains.append(chain)

    # Drop chains that are just a tail/sub-chain of a longer chain already found,
    # so a single seeded chain doesn't surface as multiple overlapping flags.
    chains.sort(key=len, reverse=True)
    maximal_chains: list[list[Transaction]] = []
    accepted_signatures: list[tuple[str, ...]] = []
    for chain in chains:
        signature = tuple([chain[0].from_account] + [t.to_account for t in chain])
        if any(
            signature == accepted[i : i + len(signature)]
            for accepted in accepted_signatures
            for i in range(len(accepted) - len(signature) + 1)
        ):
            continue
        accepted_signatures.append(signature)
        maximal_chains.append(chain)
    return maximal_chains


def _find_mule_network_candidates(
    transactions: list[Transaction], accounts_index: dict[str, Account]
) -> list[dict]:
    by_sender: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        by_sender[tx.from_account].append(tx)

    candidates = []
    for source, txs in by_sender.items():
        receivers = {t.to_account for t in txs}
        if len(receivers) < MULE_MIN_FANOUT:
            continue
        mule_accounts = []
        for receiver in receivers:
            account = accounts_index.get(receiver)
            if account and account.total_in > 0 and (account.total_out / account.total_in) >= MULE_CASHOUT_RATIO:
                mule_accounts.append(receiver)
        if len(mule_accounts) >= MULE_MIN_FANOUT:
            candidates.append(
                {
                    "source": source,
                    "mules": mule_accounts,
                    "transactions": [t for t in txs if t.to_account in mule_accounts],
                }
            )
    return candidates


async def _confirm_with_llm(pattern_type: str, accounts_involved: list[str], txs: list[Transaction]) -> dict:
    user_prompt = (
        f"pattern_type candidate: {pattern_type}\n"
        f"accounts_involved: {accounts_involved}\n"
        f"transactions: {[t.model_dump() for t in txs]}"
    )
    try:
        return await call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception:
        # Demo-safety: if the LLM is unreachable, trust the rule engine rather than dropping the flag.
        return {"confirmed": True, "reasoning": f"Rule engine flagged a {pattern_type} pattern (LLM unavailable)."}


async def detect_patterns(graph: InvestigationGraph) -> list[FlaggedPattern]:
    accounts_index = {a.id: a for a in graph.accounts}
    flagged: list[FlaggedPattern] = []

    for txs in _find_structuring_candidates(graph.transactions):
        receiver = txs[0].to_account
        accounts_involved = [receiver] + sorted({t.from_account for t in txs})
        result = await _confirm_with_llm("structuring", accounts_involved, txs)
        if result.get("confirmed", True):
            flagged.append(
                FlaggedPattern(
                    pattern_type="structuring",
                    accounts_involved=accounts_involved,
                    reasoning=result.get("reasoning", ""),
                )
            )

    for chain in _find_layering_candidates(graph.transactions):
        accounts_involved = [chain[0].from_account] + [t.to_account for t in chain]
        result = await _confirm_with_llm("layering", accounts_involved, chain)
        if result.get("confirmed", True):
            flagged.append(
                FlaggedPattern(
                    pattern_type="layering",
                    accounts_involved=accounts_involved,
                    reasoning=result.get("reasoning", ""),
                )
            )

    for candidate in _find_mule_network_candidates(graph.transactions, accounts_index):
        accounts_involved = [candidate["source"]] + candidate["mules"]
        result = await _confirm_with_llm("mule_network", accounts_involved, candidate["transactions"])
        if result.get("confirmed", True):
            flagged.append(
                FlaggedPattern(
                    pattern_type="mule_network",
                    accounts_involved=accounts_involved,
                    reasoning=result.get("reasoning", ""),
                )
            )

    return flagged
