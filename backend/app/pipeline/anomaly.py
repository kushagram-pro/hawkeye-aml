"""Generic, crime-type-agnostic anomaly scoring.

Unlike the specific detectors in agent2_detection.py (structuring, layering,
mule_network, circular_flow), this module encodes no knowledge of any particular
scam shape. It only computes statistics that generalize to any kind of unusual
account behavior: how far an account's amounts/velocity/connectivity deviate from
the rest of the graph, how much it behaves like a pass-through conduit, and how
often its amounts look fabricated (suspiciously round numbers).

The point is that when a new fraud typology shows up that none of the named
detectors catch, this module still surfaces the accounts behind it as outliers -
without anyone writing a new rule function for it. Classifying *what* the outlier
actually is gets delegated to an open-ended LLM call (see _confirm_general_anomaly
in agent2_detection.py), not to more code here.
"""

import statistics
from collections import defaultdict

from app.schemas import Account, InvestigationGraph, Transaction

ROUND_AMOUNT_BASES = (100, 500, 1000, 5000, 10000)


def _safe_mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _safe_stdev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _zscore(value: float, mean: float, stdev: float) -> float:
    return (value - mean) / stdev if stdev > 0 else 0.0


def _is_round_amount(amount: float) -> bool:
    return any(amount >= base and amount % base == 0 for base in ROUND_AMOUNT_BASES)


def compute_account_signals(graph: InvestigationGraph) -> dict[str, dict]:
    accounts = graph.accounts
    if not accounts:
        return {}

    tx_by_account: dict[str, list[Transaction]] = defaultdict(list)
    for tx in graph.transactions:
        tx_by_account[tx.from_account].append(tx)
        tx_by_account[tx.to_account].append(tx)

    avg_amounts = [a.total_in + a.total_out for a in accounts if a.transaction_count > 0]
    velocities = [a.transaction_count for a in accounts]
    degrees = [a.unique_counterparties for a in accounts]

    amt_mean, amt_stdev = _safe_mean(avg_amounts), _safe_stdev(avg_amounts)
    vel_mean, vel_stdev = _safe_mean(velocities), _safe_stdev(velocities)
    deg_mean, deg_stdev = _safe_mean(degrees), _safe_stdev(degrees)

    signals: dict[str, dict] = {}
    for account in accounts:
        txs = tx_by_account.get(account.id, [])
        total_flow = account.total_in + account.total_out

        round_ratio = sum(1 for t in txs if _is_round_amount(t.amount)) / len(txs) if txs else 0.0
        passthrough_ratio = (
            min(account.total_in, account.total_out) / max(account.total_in, account.total_out)
            if max(account.total_in, account.total_out) > 0
            else 0.0
        )
        concentration = (
            account.transaction_count / account.unique_counterparties
            if account.unique_counterparties > 0
            else float(account.transaction_count)
        )

        amount_z = _zscore(total_flow, amt_mean, amt_stdev)
        velocity_z = _zscore(account.transaction_count, vel_mean, vel_stdev)
        degree_z = _zscore(account.unique_counterparties, deg_mean, deg_stdev)

        composite_score = (
            abs(amount_z) * 0.3
            + abs(velocity_z) * 0.25
            + abs(degree_z) * 0.15
            + passthrough_ratio * 1.5
            + round_ratio * 1.0
            + min(concentration, 10) * 0.1
        )

        signals[account.id] = {
            "amount_zscore": round(amount_z, 2),
            "velocity_zscore": round(velocity_z, 2),
            "degree_zscore": round(degree_z, 2),
            "passthrough_ratio": round(passthrough_ratio, 2),
            "round_amount_ratio": round(round_ratio, 2),
            "counterparty_concentration": round(concentration, 2),
            "composite_score": round(composite_score, 3),
        }

    return signals


def select_anomaly_candidates(
    graph: InvestigationGraph,
    exclude_accounts: set[str],
    top_k: int = 5,
    min_score: float = 1.2,
) -> list[dict]:
    """Top-K outlier accounts not already covered by a specific detector, each
    paired with its own transactions so the LLM can judge them in isolation."""
    signals = compute_account_signals(graph)

    tx_by_account: dict[str, list[Transaction]] = defaultdict(list)
    for tx in graph.transactions:
        tx_by_account[tx.from_account].append(tx)
        tx_by_account[tx.to_account].append(tx)

    ranked = sorted(
        (
            (account_id, sig)
            for account_id, sig in signals.items()
            if account_id not in exclude_accounts and sig["composite_score"] >= min_score
        ),
        key=lambda item: item[1]["composite_score"],
        reverse=True,
    )[:top_k]

    return [
        {"account_id": account_id, "signals": sig, "transactions": tx_by_account.get(account_id, [])}
        for account_id, sig in ranked
    ]
