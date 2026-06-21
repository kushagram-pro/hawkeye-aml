import { useEffect, useState } from "react";
import { AuditTrail } from "./components/AuditTrail";
import { ChatPanel } from "./components/ChatPanel";
import { InvestigationGraph } from "./components/InvestigationGraph";
import { InsightPanel } from "./components/InsightPanel";
import { PipelineStages } from "./components/PipelineStages";
import { ScenarioPicker } from "./components/ScenarioPicker";
import { SummaryCards } from "./components/SummaryCards";
import { UploadPanel } from "./components/UploadPanel";
import { deleteScenario, fetchScenarios, logout, runInvestigation } from "./services/api";
import { InvestigationResult, Scenario, StageStatus } from "./types";

const initialStages: StageStatus[] = [
  { key: "ingestion", label: "Agent 1: Ingestion", status: "idle", detail: "Waiting for a scenario run." },
  { key: "watchlist", label: "Agent 1B: Watchlist Screening", status: "idle", detail: "Repeat-offender lookup not started." },
  { key: "detection", label: "Agent 2: Pattern Detection", status: "idle", detail: "Rule and reasoning stage not started." },
  { key: "adversarial", label: "Agent 2B: Adversarial Review", status: "idle", detail: "Skeptical second pass not started." },
  { key: "scoring", label: "Agent 3: Risk Scoring", status: "idle", detail: "Score factors will appear after investigation." },
  { key: "memory", label: "Agent 3B: Case Memory", status: "idle", detail: "Precedent lookup not started." },
  { key: "narrative", label: "Agent 4: Narrative & Next Steps", status: "idle", detail: "Narratives will be generated after suspicious paths are found." }
];

interface DashboardProps {
  onLogout: () => void;
}

export function Dashboard({ onLogout }: DashboardProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [stages, setStages] = useState(initialStages.map((stage) => ({ ...stage })));
  const [auditRefreshToken, setAuditRefreshToken] = useState(0);

  useEffect(() => {
    void (async () => {
      const loadedScenarios = await fetchScenarios();
      setScenarios(loadedScenarios);
      setSelectedScenarioId((current) => current || loadedScenarios[0]?.id || "");
    })();
  }, []);

  const markRunningTimeline = () => {
    setStages((current) =>
      current.map((stage, index) => ({
        ...stage,
        status: index === 0 ? "running" : "idle",
        detail:
          index === 0
            ? "Normalizing transactions into a connected account graph..."
            : initialStages[index].detail
      }))
    );
  };

  const handleRun = async (scenarioIdOverride?: string) => {
    const scenarioId = scenarioIdOverride ?? selectedScenarioId;
    if (!scenarioId) {
      return;
    }

    setLoading(true);
    setSelectedNodeId(null);
    markRunningTimeline();

    try {
      const investigation = await runInvestigation(scenarioId, setStages);
      setResult(investigation);
      setStages(investigation.stages);

      const topFlaggedAccount =
        [...investigation.graph.accounts]
          .filter((account) => account.flags.length > 0)
          .sort((left, right) => (right.riskScore ?? 0) - (left.riskScore ?? 0))[0] ?? null;

      setSelectedNodeId(topFlaggedAccount?.id ?? null);
      if (!investigation.usedMockData) {
        setAuditRefreshToken((current) => current + 1);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUploaded = async (scenarioId: string) => {
    const loadedScenarios = await fetchScenarios();
    setScenarios(loadedScenarios);
    setSelectedScenarioId(scenarioId);
    await handleRun(scenarioId);
  };

  const handleDeleteScenario = async (scenarioId: string) => {
    await deleteScenario(scenarioId);
    const loadedScenarios = await fetchScenarios();
    setScenarios(loadedScenarios);

    if (selectedScenarioId === scenarioId) {
      setSelectedScenarioId(loadedScenarios[0]?.id || "");
    }
    if (result?.scenario.id === scenarioId) {
      setResult(null);
      setSelectedNodeId(null);
    }
  };

  const handleLogout = async () => {
    await logout();
    onLogout();
  };

  return (
    <div className="app-shell">
      <div className="backdrop backdrop-left" />
      <div className="backdrop backdrop-right" />

      <div className="topbar">
        <span className="topbar-brand">HawkEye AML</span>
        <button type="button" className="ghost-button" onClick={handleLogout}>
          Log out
        </button>
      </div>

      <header className="hero">
        <div>
          <span className="hero-kicker">AI-Powered AML Investigation</span>
          <h1>Trace suspicious money movement with an explainable 4-agent workflow.</h1>
          <p className="hero-copy">
            Hawkeye AML turns raw transactions into a live investigation graph, ranked risk signals,
            and plain-language narratives that judges can understand instantly.
          </p>
        </div>

        <div className="hero-panel panel">
          <span className="metric-label">Demo promise</span>
          <strong>Load a scenario, run the pipeline, and inspect the exact suspicious trail.</strong>
          <p>
            Built for a hackathon flow: fast startup, high-contrast visuals, and a mock-data fallback
            so the demo still lands even if the backend is cold.
          </p>
        </div>
      </header>

      <main className="layout">
        <ScenarioPicker
          scenarios={scenarios}
          selectedScenarioId={selectedScenarioId}
          onSelect={setSelectedScenarioId}
          onRun={() => handleRun()}
          onDelete={handleDeleteScenario}
          loading={loading}
        />

        <UploadPanel onUploaded={handleUploaded} disabled={loading} />

        {result?.usedMockData ? (
          <div className="status-banner warning" role="status">
            Backend unreachable — showing demo data so the walkthrough still works.
          </div>
        ) : null}

        {result?.graph.executiveSummary ? (
          <div className="status-banner summary" role="status">
            <span className="metric-label">Executive Summary</span>
            <p>{result.graph.executiveSummary}</p>
          </div>
        ) : null}

        <SummaryCards result={result} />

        <div className="content-grid">
          <div className="main-column">
            <InvestigationGraph
              result={result}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              loading={loading}
              reportScenarioId={result && !result.usedMockData ? result.scenario.id : null}
            />
            <PipelineStages stages={result?.stages ?? stages} elapsedMs={result?.elapsedMs} />
            <AuditTrail
              scenarioId={result && !result.usedMockData ? result.scenario.id : null}
              refreshToken={auditRefreshToken}
            />
          </div>

          <div className="side-column">
            <InsightPanel result={result} selectedNodeId={selectedNodeId} />
            <ChatPanel
              key={result && !result.usedMockData ? `${result.scenario.id}-${result.generatedAt}` : "none"}
              scenarioId={result && !result.usedMockData ? result.scenario.id : null}
              onAsked={() => setAuditRefreshToken((current) => current + 1)}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
