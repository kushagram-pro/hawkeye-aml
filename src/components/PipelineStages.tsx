import { StageStatus } from "../types";

interface PipelineStagesProps {
  stages: StageStatus[];
  elapsedMs?: number;
}

function formatStageSummary(key: StageStatus["key"], summary: Record<string, unknown>): string[] {
  const lines: string[] = [];

  if (key === "ingestion") {
    if (typeof summary.account_count === "number") {
      lines.push(`${summary.account_count} accounts normalized`);
    }
    if (typeof summary.transaction_count === "number") {
      lines.push(`${summary.transaction_count} transactions ingested`);
    }
  } else if (key === "detection") {
    const patternsFound = summary.patterns_found;
    if (typeof patternsFound === "number") {
      lines.push(patternsFound > 0 ? `${patternsFound} pattern(s) confirmed` : "No suspicious patterns confirmed");
    }
    const byType = summary.pattern_types as Record<string, number> | undefined;
    if (byType && Object.keys(byType).length > 0) {
      lines.push(
        Object.entries(byType)
          .map(([type, count]) => `${type.replace(/_/g, " ")} ×${count}`)
          .join(", ")
      );
    }
  } else if (key === "scoring") {
    if (typeof summary.average_risk_score === "number") {
      lines.push(`Average risk score: ${summary.average_risk_score}`);
    }
    if (typeof summary.highest_risk_score === "number") {
      lines.push(`Highest risk score: ${summary.highest_risk_score}`);
    }
    if (typeof summary.high_confidence_count === "number") {
      lines.push(`${summary.high_confidence_count} high-confidence pattern(s)`);
    }
  } else if (key === "narrative") {
    if (typeof summary.narratives_generated === "number") {
      lines.push(`${summary.narratives_generated} narrative(s) generated`);
    }
  }

  return lines;
}

export function PipelineStages({ stages, elapsedMs }: PipelineStagesProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <span className="eyebrow">Pipeline Status</span>
        <h2>Agent progress</h2>
      </div>

      <div className="stage-list">
        {stages.map((stage, index) => {
          const summaryLines =
            stage.status === "done" && stage.summary ? formatStageSummary(stage.key, stage.summary) : [];

          return (
            <div key={stage.key} className={`stage-card ${stage.status}`}>
              <div className="stage-marker">{index + 1}</div>
              <div>
                <div className="stage-title-row">
                  <h3>{stage.label}</h3>
                  <span className={`stage-badge ${stage.status}`}>{stage.status}</span>
                </div>
                <p>{stage.detail}</p>
                {summaryLines.length > 0 ? (
                  <ul className="stage-summary">
                    {summaryLines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <div className="metric-strip">
        <div>
          <span className="metric-label">Runtime</span>
          <strong>{elapsedMs ? `${(elapsedMs / 1000).toFixed(1)}s` : "--"}</strong>
        </div>
        <div>
          <span className="metric-label">Target</span>
          <strong>{"< 120s"}</strong>
        </div>
      </div>
    </section>
  );
}
