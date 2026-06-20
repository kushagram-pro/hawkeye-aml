import { InvestigationResult } from "../types";

interface SummaryCardsProps {
  result: InvestigationResult | null;
}

export function SummaryCards({ result }: SummaryCardsProps) {
  if (!result) {
    return null;
  }

  const flaggedAccounts = result.graph.accounts.filter((account) => account.flags.length > 0);
  const highestRisk = [...flaggedAccounts].sort((left, right) => (right.riskScore ?? 0) - (left.riskScore ?? 0))[0];

  return (
    <section className="summary-grid">
      <article className="panel summary-card">
        <span className="metric-label">Flagged Patterns</span>
        <strong>{result.graph.flaggedPatterns.length}</strong>
        <p>Seeded suspicious structures surfaced by the detection and narrative agents.</p>
      </article>

      <article className="panel summary-card">
        <span className="metric-label">Flagged Accounts</span>
        <strong>{flaggedAccounts.length}</strong>
        <p>Accounts with one or more suspicious labels in the investigation graph.</p>
      </article>

      <article className="panel summary-card">
        <span className="metric-label">Highest Risk</span>
        <strong>{highestRisk ? `${highestRisk.label} · ${highestRisk.riskScore}` : "--"}</strong>
        <p>The account currently prioritized for analyst escalation.</p>
      </article>
    </section>
  );
}
