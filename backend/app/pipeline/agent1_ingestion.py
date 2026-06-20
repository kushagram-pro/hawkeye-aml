from app.schemas import Account, InvestigationGraph, Transaction


def ingest(scenario_id: str, raw_transactions: list[dict]) -> InvestigationGraph:
    """Deterministic normalization: raw transaction records -> account graph with aggregates."""
    transactions = [Transaction(**t) for t in raw_transactions]

    accounts: dict[str, Account] = {}
    counterparties: dict[str, set[str]] = {}

    def get_account(account_id: str) -> Account:
        if account_id not in accounts:
            accounts[account_id] = Account(id=account_id)
            counterparties[account_id] = set()
        return accounts[account_id]

    for tx in transactions:
        sender = get_account(tx.from_account)
        receiver = get_account(tx.to_account)

        sender.total_out += tx.amount
        sender.transaction_count += 1
        counterparties[tx.from_account].add(tx.to_account)

        receiver.total_in += tx.amount
        receiver.transaction_count += 1
        counterparties[tx.to_account].add(tx.from_account)

    for account_id, account in accounts.items():
        account.unique_counterparties = len(counterparties[account_id])

    return InvestigationGraph(
        scenario_id=scenario_id,
        accounts=list(accounts.values()),
        transactions=transactions,
        flagged_patterns=[],
    )
