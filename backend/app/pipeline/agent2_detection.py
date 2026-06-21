import asyncio
import re
from collections import defaultdict
from datetime import datetime, timedelta

from app.llm_client import call_llm
from app.pipeline.anomaly import select_anomaly_candidates
from app.schemas import Account, FlaggedPattern, InvestigationGraph, Transaction

STRUCTURING_THRESHOLD = 50_000
STRUCTURING_MIN_TRANSFERS = 4
STRUCTURING_WINDOW = timedelta(hours=48)

LAYERING_MIN_HOPS = 4
LAYERING_WINDOW = timedelta(days=5)
LAYERING_AMOUNT_TOLERANCE = 0.3

MULE_MIN_FANOUT = 5
MULE_CASHOUT_RATIO = 0.8

CIRCULAR_MIN_HOPS = 3
CIRCULAR_MAX_HOPS = 6
CIRCULAR_WINDOW = timedelta(days=7)
CIRCULAR_AMOUNT_TOLERANCE = 0.35

SYSTEM_PROMPT = (
    "You are a financial crime analyst AI assisting an AML investigation platform. "
    "You will be given ONE candidate suspicious pattern, already detected by a "
    "deterministic rule engine, along with the transactions involved. The candidate's "
    "pattern_type will be one of: structuring (many sub-threshold transfers converging "
    "on one account), layering (a one-way chain of intermediary accounts), mule_network "
    "(one source fanning out to many cash-out accounts), or circular_flow (funds routed "
    "through a chain of accounts that loops back to the original sender, i.e. "
    "round-tripping). Your job is NOT to find new patterns from scratch - it is to: "
    "1. Confirm whether this candidate genuinely matches its labeled pattern_type, "
    "or reject it as a false positive. "
    "2. Explain, in technical terms, exactly why it does or doesn't match. "
    "3. Note any additional suspicious detail visible in the provided transactions "
    "that the rule engine didn't capture (only from the given data - never invent "
    "accounts or transactions not present in the input). All monetary amounts in this "
    "data are in Indian Rupees - if you cite any amount, write it as 'Rs. <amount>', "
    "never '$' or 'USD'. "
    "Respond with strict JSON only: "
    '{"confirmed": true|false, "reasoning": "2-3 sentences", "additional_notes": "string or null"}'
)

GENERAL_ANOMALY_SYSTEM_PROMPT = (
    "You are a financial crime analyst AI with no fixed list of known scam types. "
    "You will be given ONE account's transaction activity plus a set of generic "
    "statistical anomaly signals (z-scores and ratios) that a monitoring system "
    "computed without reference to any specific fraud typology - it does not know "
    "or care whether this looks like structuring, layering, a mule network, or "
    "something else entirely. Decide: "
    "1. Whether this account's behavior is genuinely consistent with a financial "
    "scam, fraud, or money-laundering activity, or whether it is unusual but "
    "explainable as legitimate (e.g. a payroll, merchant, or aggregator account). "
    "Be skeptical - most statistical outliers are not fraud. "
    "2. If, and only if, you believe it is suspicious, invent a short snake_case "
    "label describing the specific behavior you actually observe. Do not force-fit "
    "it into structuring, layering, mule_network, or circular_flow if it looks "
    "genuinely different - name the real behavior (e.g. 'shell_company_passthrough', "
    "'wash_trading', 'dormant_account_velocity_spike', 'invoice_fraud_round_amounts'). "
    "3. Explain your reasoning citing the actual signals and transactions given. "
    "Never invent accounts or transactions not present in the input. All monetary "
    "amounts in this data are in Indian Rupees - if you cite any amount, write it as "
    "'Rs. <amount>', never '$' or 'USD'. "
    "Respond with strict JSON only: "
    '{"confirmed": true|false, "pattern_label": "snake_case_string or null", '
    '"reasoning": "2-3 sentences", "additional_notes": "string or null"}'
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


def _extend_cycle(
    chain: list[Transaction],
    outgoing_by_account: dict[str, list[Transaction]],
    origin: str,
) -> list[list[Transaction]]:
    """Walk forward from `chain`, looking for a path that returns to `origin`
    (round-tripping / circular fund flow) rather than terminating at a new account."""
    last_tx = chain[-1]
    receiver = last_tx.to_account
    visited = {t.from_account for t in chain} | {t.to_account for t in chain}

    if len(chain) >= CIRCULAR_MAX_HOPS:
        return []

    closures: list[list[Transaction]] = []
    for tx in outgoing_by_account.get(receiver, []):
        if _parse(tx.timestamp) <= _parse(last_tx.timestamp):
            continue
        if _parse(tx.timestamp) - _parse(last_tx.timestamp) > CIRCULAR_WINDOW:
            continue
        if abs(tx.amount - last_tx.amount) / last_tx.amount > CIRCULAR_AMOUNT_TOLERANCE:
            continue

        if tx.to_account == origin:
            if len(chain) + 1 >= CIRCULAR_MIN_HOPS:
                closures.append(chain + [tx])
            continue

        if tx.to_account in visited:
            continue

        closures.extend(_extend_cycle(chain + [tx], outgoing_by_account, origin))

    return closures


def _find_circular_flow_candidates(transactions: list[Transaction]) -> list[list[Transaction]]:
    """Detect closed loops where funds are passed through a chain of accounts and
    routed back to the originating account - round-tripping used to recycle funds
    or disguise their source, distinct from one-way layering chains."""
    outgoing_by_account: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        outgoing_by_account[tx.from_account].append(tx)
    for txs in outgoing_by_account.values():
        txs.sort(key=lambda t: _parse(t.timestamp))

    cycles: list[list[Transaction]] = []
    seen_signatures: set[tuple[tuple[str, str, str], ...]] = set()
    for tx in transactions:
        origin = tx.from_account
        for cycle in _extend_cycle([tx], outgoing_by_account, origin):
            # Identify a cycle by its actual transactions (account + timestamp), not just
            # the account sequence, so repeated rounds through the same ring at different
            # times are each kept as distinct candidates.
            signature = tuple((t.from_account, t.to_account, t.timestamp) for t in cycle)
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                cycles.append(cycle)

    return cycles


async def _confirm_with_llm(pattern_type: str, accounts_involved: list[str], txs: list[Transaction]) -> dict:
    user_prompt = (
        f"pattern_type candidate: {pattern_type}\n"
        f"accounts_involved: {accounts_involved}\n"
        f"transactions: {[t.model_dump() for t in txs]}"
    )
    try:
        return await call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception:
        return {"confirmed": True, "reasoning": f"Rule engine flagged a {pattern_type} pattern (LLM unavailable)."}


async def _confirm_general_anomaly(account_id: str, signals: dict, txs: list[Transaction]) -> dict:
    user_prompt = (
        f"account: {account_id}\n"
        f"anomaly_signals: {signals}\n"
        f"transactions: {[t.model_dump() for t in txs]}"
    )
    try:
        return await call_llm(GENERAL_ANOMALY_SYSTEM_PROMPT, user_prompt)
    except Exception:
        # Unlike the named detectors, a generic statistical outlier hasn't already
        # passed a crime-specific rule - without the LLM to judge it, fail closed
        # (don't flag) rather than assuming it's fraud.
        return {"confirmed": False}


def _sanitize_label(label: str | None) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return cleaned or "unclassified_anomaly"


async def detect_patterns(graph: InvestigationGraph) -> list[FlaggedPattern]:
    accounts_index = {a.id: a for a in graph.accounts}

    raw_candidates: list[tuple[str, list[str], list[Transaction]]] = []

    for txs in _find_structuring_candidates(graph.transactions):
        receiver = txs[0].to_account
        accounts_involved = [receiver] + sorted({t.from_account for t in txs})
        raw_candidates.append(("structuring", accounts_involved, txs))

    for chain in _find_layering_candidates(graph.transactions):
        accounts_involved = [chain[0].from_account] + [t.to_account for t in chain]
        raw_candidates.append(("layering", accounts_involved, chain))

    for candidate in _find_mule_network_candidates(graph.transactions, accounts_index):
        accounts_involved = [candidate["source"]] + candidate["mules"]
        raw_candidates.append(("mule_network", accounts_involved, candidate["transactions"]))

    for cycle in _find_circular_flow_candidates(graph.transactions):
        ordered = [cycle[0].from_account] + [t.to_account for t in cycle]
        accounts_involved = list(dict.fromkeys(ordered))  # de-dupe, preserve order (loop repeats the origin)
        raw_candidates.append(("circular_flow", accounts_involved, cycle))

    flagged: list[FlaggedPattern] = []

    if raw_candidates:
        # Each candidate is reasoned over independently, so confirm them concurrently
        # instead of awaiting one LLM round-trip at a time.
        results = await asyncio.gather(
            *(
                _confirm_with_llm(pattern_type, accounts_involved, txs)
                for pattern_type, accounts_involved, txs in raw_candidates
            )
        )
        for (pattern_type, accounts_involved, _txs), result in zip(raw_candidates, results):
            if result.get("confirmed", True):
                flagged.append(
                    FlaggedPattern(
                        pattern_type=pattern_type,
                        accounts_involved=accounts_involved,
                        reasoning=result.get("reasoning", ""),
                        additional_notes=result.get("additional_notes"),
                    )
                )

    # General catch-all pass: statistically anomalous accounts that none of the
    # named detectors above caught. The rule layer here is generic (z-scores and
    # ratios that apply to any account), so it never needs a new detector for a
    # new scam shape - the LLM decides whether it's fraud and names it.
    already_considered = {account_id for _, accounts_involved, _ in raw_candidates for account_id in accounts_involved}
    general_candidates = select_anomaly_candidates(graph, exclude_accounts=already_considered)

    if general_candidates:
        general_results = await asyncio.gather(
            *(
                _confirm_general_anomaly(candidate["account_id"], candidate["signals"], candidate["transactions"])
                for candidate in general_candidates
            )
        )
        for candidate, result in zip(general_candidates, general_results):
            if result.get("confirmed"):
                involved = {candidate["account_id"]}
                for tx in candidate["transactions"]:
                    involved.add(tx.from_account)
                    involved.add(tx.to_account)
                flagged.append(
                    FlaggedPattern(
                        pattern_type=_sanitize_label(result.get("pattern_label")),
                        accounts_involved=sorted(involved),
                        reasoning=result.get("reasoning", ""),
                        additional_notes=result.get("additional_notes"),
                    )
                )

    return flagged
