import { Scenario } from "../types";

interface ScenarioPickerProps {
  scenarios: Scenario[];
  selectedScenarioId: string;
  onSelect: (scenarioId: string) => void;
  onRun: () => void;
  onDelete: (scenarioId: string) => void;
  loading: boolean;
}

export function ScenarioPicker({
  scenarios,
  selectedScenarioId,
  onSelect,
  onRun,
  onDelete,
  loading
}: ScenarioPickerProps) {
  return (
    <section className="panel scenario-panel">
      <div className="section-heading">
        <span className="eyebrow">Scenario Control</span>
        <h2>Launch an investigation run</h2>
      </div>

      <div className="scenario-grid">
        {scenarios.map((scenario) => {
          const active = scenario.id === selectedScenarioId;

          return (
            <div
              key={scenario.id}
              className={`scenario-card${active ? " active" : ""}`}
              onClick={() => onSelect(scenario.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  onSelect(scenario.id);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="scenario-title-row">
                <h3>{scenario.name}</h3>
                <div className="scenario-title-actions">
                  <span className="transaction-pill">{scenario.transactionCount} txns</span>
                  {scenario.deletable ? (
                    <button
                      type="button"
                      className="scenario-delete-button"
                      title="Delete this dataset"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(scenario.id);
                      }}
                    >
                      ×
                    </button>
                  ) : null}
                </div>
              </div>
              <p>{scenario.description}</p>
              <div className="tag-row">
                {scenario.seededPatterns.map((pattern) => (
                  <span key={pattern} className="pattern-tag">
                    {pattern.replace("_", " ")}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="cta-row">
        <button className="run-button" onClick={onRun} type="button" disabled={loading || !selectedScenarioId}>
          {loading ? "Running Investigation..." : "Run 4-Agent Pipeline"}
        </button>
        <p className="helper-text">
          The UI auto-falls back to demo-safe mock results if the backend is unavailable.
        </p>
      </div>
    </section>
  );
}
