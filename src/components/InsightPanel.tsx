import { InvestigationResult } from "../types";

interface InsightPanelProps {
  result: InvestigationResult | null;
  selectedNodeId: string | null;
}

function confidenceTone(confidence?: string | null) {
  if (confidence === "high") return "high";
  if (confidence === "medium") return "medium";
  return "low";
}

export function InsightPanel({ result, selectedNodeId }: InsightPanelProps) {
  if (!result) {
    return (
      <section className="panel insight-panel empty-state">
        <div className="section-heading">
          <span className="eyebrow">Investigation Detail</span>
          <h2>Analyst narrative</h2>
        </div>
        <p>Account-level explanations will appear here after an investigation run.</p>
      </section>
    );
  }

  const selectedNode = result.graph.accounts.find((account) => account.id === selectedNodeId) ?? null;
  const selectedPattern =
    result.graph.flaggedPatterns.find((pattern) => selectedNode && pattern.accountsInvolved.includes(selectedNode.id)) ??
    result.graph.flaggedPatterns[0] ??
    null;

  return (
    <section className="panel insight-panel">
      <div className="section-heading">
        <span className="eyebrow">Investigation Detail</span>
        <h2>{selectedNode ? `Account ${selectedNode.label}` : "Pattern narrative"}</h2>
      </div>

      {selectedNode ? (
        <>
          <div className="insight-topline">
            <span className="risk-score">{selectedNode.riskScore ?? 0}</span>
            <div>
              <p className="metric-label">Risk Score</p>
              <span className={`confidence-badge ${confidenceTone(selectedNode.confidence)}`}>
                {selectedNode.confidence ?? "low"} confidence
              </span>
            </div>
          </div>

          <div className="detail-grid">
            <div>
              <span className="metric-label">Total In</span>
              <strong>Rs. {selectedNode.totalIn.toLocaleString()}</strong>
            </div>
            <div>
              <span className="metric-label">Total Out</span>
              <strong>Rs. {selectedNode.totalOut.toLocaleString()}</strong>
            </div>
            <div>
              <span className="metric-label">Transactions</span>
              <strong>{selectedNode.transactionCount}</strong>
            </div>
            <div>
              <span className="metric-label">Counterparties</span>
              <strong>{selectedNode.uniqueCounterparties}</strong>
            </div>
          </div>
        </>
      ) : null}

      {selectedPattern ? (
        <>
          <div className="tag-row">
            <span className="pattern-tag">{selectedPattern.patternType.replace("_", " ")}</span>
            <span className={`confidence-badge ${confidenceTone(selectedPattern.confidence)}`}>
              {selectedPattern.confidence} confidence
            </span>
          </div>
          <p className="narrative-copy">{selectedPattern.narrative}</p>
          <div className="involved-accounts">
            <span className="metric-label">Accounts involved</span>
            <div className="account-chip-row">
              {selectedPattern.accountsInvolved.map((accountId) => (
                <span className="account-chip" key={accountId}>
                  {accountId}
                </span>
              ))}
            </div>
          </div>
        </>
      ) : (
        <p>No suspicious pattern explanation was returned for this investigation.</p>
      )}
    </section>
  );
}
