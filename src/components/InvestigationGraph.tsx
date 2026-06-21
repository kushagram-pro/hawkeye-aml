import ForceGraph2D from "react-force-graph-2d";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { downloadReport } from "../services/api";
import { AccountNode, InvestigationResult, TransactionEdge } from "../types";

interface GraphNode extends AccountNode {
  color: string;
  val: number;
  dimmed: boolean;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  amount: number;
  color: string;
  flagged: boolean;
  particles: number;
  width: number;
}

interface InvestigationGraphProps {
  result: InvestigationResult | null;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  loading?: boolean;
  reportScenarioId?: string | null;
}

const REPLAY_STEP_MS: Record<number, number> = {
  1: 600,
  2: 300,
  4: 150
};

function getNodeColor(node: AccountNode) {
  if ((node.riskScore ?? 0) >= 85) return "#f1554c";
  if ((node.riskScore ?? 0) >= 60) return "#fb923c";
  if ((node.riskScore ?? 0) >= 30) return "#f5a524";
  if (node.watchlistNote) return "#a78bfa";
  return "#4f7fff";
}

function mapNode(node: AccountNode, dimmed: boolean): GraphNode {
  return {
    ...node,
    color: getNodeColor(node),
    val: 1.5 + ((node.riskScore ?? 8) / 18),
    dimmed
  };
}

function mapLink(edge: TransactionEdge, state: "future" | "revealed" | "justRevealed"): GraphLink {
  if (state === "future") {
    return {
      source: edge.from,
      target: edge.to,
      amount: edge.amount,
      color: "rgba(148, 163, 184, 0.07)",
      flagged: false,
      particles: 0,
      width: 0.6
    };
  }

  if (state === "justRevealed") {
    return {
      source: edge.from,
      target: edge.to,
      amount: edge.amount,
      color: "rgba(245, 158, 11, 0.95)",
      flagged: Boolean(edge.flagged),
      particles: 7,
      width: 3
    };
  }

  return {
    source: edge.from,
    target: edge.to,
    amount: edge.amount,
    color: edge.flagged ? "rgba(220, 38, 38, 0.85)" : "rgba(100, 116, 139, 0.35)",
    flagged: Boolean(edge.flagged),
    particles: edge.flagged ? 4 : 0,
    width: edge.flagged ? 2.4 : 1
  };
}

export function InvestigationGraph({
  result,
  selectedNodeId,
  onSelectNode,
  loading,
  reportScenarioId
}: InvestigationGraphProps) {
  const graphRef = useRef<any>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 540 });
  const [downloadingReport, setDownloadingReport] = useState(false);

  const transactions = result?.graph.transactions ?? [];
  const totalSteps = transactions.length;

  const rankedTransactions = useMemo(
    () => [...transactions].sort((left, right) => new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()),
    [transactions]
  );

  const revealRank = useMemo(() => {
    const rank = new Map<string, number>();
    rankedTransactions.forEach((edge, index) => rank.set(edge.id, index));
    return rank;
  }, [rankedTransactions]);

  const [replayStep, setReplayStep] = useState(totalSteps);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 2 | 4>(2);
  const isReplaying = replayStep < totalSteps;

  // A fresh investigation result means a brand-new transaction set - drop any
  // in-progress replay state from the previous run rather than carrying its
  // step index (which may now be out of range) into the new graph.
  useEffect(() => {
    setReplayStep(transactions.length);
    setIsPlaying(false);
  }, [result?.scenario.id, result?.generatedAt, transactions.length]);

  useEffect(() => {
    if (!isPlaying) {
      return;
    }
    if (replayStep >= totalSteps) {
      setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => setReplayStep((current) => Math.min(current + 1, totalSteps)), REPLAY_STEP_MS[speed]);
    return () => clearTimeout(timer);
  }, [isPlaying, replayStep, totalSteps, speed]);

  const handlePlayPause = () => {
    if (!isPlaying && replayStep >= totalSteps) {
      setReplayStep(0);
    }
    setIsPlaying((current) => !current);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setReplayStep(0);
  };

  const handleShowAll = () => {
    setIsPlaying(false);
    setReplayStep(totalSteps);
  };

  const asOfLabel = (() => {
    if (!isReplaying) {
      return "Full graph";
    }
    if (replayStep === 0) {
      return "Before first transaction";
    }
    return `As of ${rankedTransactions[replayStep - 1].timestamp}`;
  })();

  const handleDownloadReport = async () => {
    if (!reportScenarioId) {
      return;
    }
    setDownloadingReport(true);
    try {
      await downloadReport(reportScenarioId);
    } catch {
      // best-effort - the report endpoint already surfaces a 404 if nothing has completed yet
    } finally {
      setDownloadingReport(false);
    }
  };

  // The canvas div only mounts once `result` is set (it's behind the empty-state
  // early return below), so a plain ref + mount-only useEffect would miss it - a
  // callback ref fires every time the node actually mounts/unmounts instead.
  const setContainerRef = useCallback((node: HTMLDivElement | null) => {
    resizeObserverRef.current?.disconnect();
    resizeObserverRef.current = null;

    if (!node) {
      return;
    }

    const updateDimensions = () => {
      const width = node.clientWidth;
      const height = window.innerWidth < 960 ? 420 : 560;
      if (width > 0) {
        setDimensions((current) => (current.width === width && current.height === height ? current : { width, height }));
      }
    };

    updateDimensions();
    const observer = new ResizeObserver(updateDimensions);
    observer.observe(node);
    resizeObserverRef.current = observer;
  }, []);

  useEffect(() => {
    if (graphRef.current && result) {
      graphRef.current.d3ReheatSimulation();
    }
  }, [result, dimensions]);

  // zoomToFit needs the simulation's final node positions, not just a fixed
  // delay after reheat - onEngineStop fires exactly when the physics engine
  // settles, whether that's from a new result or a container resize.
  const handleEngineStop = useCallback(() => {
    graphRef.current?.zoomToFit(400, 60);
  }, []);

  if (!result) {
    return (
      <section className="panel graph-shell empty-state">
        <div className="section-heading">
          <span className="eyebrow">Money Trail Graph</span>
          <h2>Force-directed network</h2>
        </div>
        {loading ? (
          <div className="loading-state">
            <span className="spinner" />
            <p>Running the 4-agent pipeline...</p>
          </div>
        ) : (
          <p>Pick a scenario and run the pipeline to render the investigation graph.</p>
        )}
      </section>
    );
  }

  const touchedAccountIds = new Set<string>();
  const links = transactions.map((edge) => {
    const rank = revealRank.get(edge.id) ?? 0;
    const state = !isReplaying ? "revealed" : rank >= replayStep ? "future" : rank === replayStep - 1 ? "justRevealed" : "revealed";
    if (state !== "future") {
      touchedAccountIds.add(edge.from);
      touchedAccountIds.add(edge.to);
    }
    return mapLink(edge, state);
  });
  const nodes = result.graph.accounts.map((account) => mapNode(account, isReplaying && !touchedAccountIds.has(account.id)));

  return (
    <section className="panel graph-shell">
      <div className="section-heading graph-header">
        <div>
          <span className="eyebrow">Money Trail Graph</span>
          <h2>Force-directed network</h2>
        </div>
        <div className="graph-header-actions">
          {reportScenarioId ? (
            <button
              type="button"
              className="ghost-button"
              onClick={handleDownloadReport}
              disabled={downloadingReport}
            >
              {downloadingReport ? "Preparing..." : "Download report"}
            </button>
          ) : null}
          <button className="ghost-button" type="button" onClick={() => onSelectNode(null)}>
            Clear focus
          </button>
        </div>
      </div>

      <div className="legend-row">
        <span><i className="legend-dot low" />Normal</span>
        <span><i className="legend-dot medium" />Elevated</span>
        <span><i className="legend-dot high" />High risk</span>
        <span><i className="legend-dot watchlist" />Watchlist hit</span>
        <span><i className="legend-line" />Flagged transfer path</span>
      </div>

      {totalSteps > 0 ? (
        <div className="replay-bar">
          <div className="replay-controls">
            <button type="button" className="ghost-button" onClick={handlePlayPause}>
              {isPlaying ? "Pause" : replayStep >= totalSteps ? "Replay" : "Play"}
            </button>
            <button type="button" className="ghost-button" onClick={handleReset} disabled={replayStep === 0 && !isPlaying}>
              Reset
            </button>
            <button type="button" className="ghost-button" onClick={handleShowAll} disabled={!isReplaying}>
              Show all
            </button>
            <div className="replay-speed">
              {([1, 2, 4] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`replay-speed-button ${speed === option ? "active" : ""}`}
                  onClick={() => setSpeed(option)}
                >
                  {option}x
                </button>
              ))}
            </div>
          </div>
          <input
            type="range"
            className="replay-slider"
            min={0}
            max={totalSteps}
            value={replayStep}
            onChange={(event) => {
              setIsPlaying(false);
              setReplayStep(Number(event.target.value));
            }}
          />
          <div className="replay-meta">
            <span>{asOfLabel}</span>
            <span>
              {Math.min(replayStep, totalSteps)} / {totalSteps} transactions
            </span>
          </div>
        </div>
      ) : null}

      <div className="graph-canvas" ref={setContainerRef}>
        {loading ? (
          <div className="loading-overlay">
            <span className="spinner" />
            <p>Refreshing investigation...</p>
          </div>
        ) : null}

        <ForceGraph2D
          ref={graphRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={{ nodes, links }}
          backgroundColor="rgba(255, 255, 255, 0)"
          cooldownTicks={80}
          onEngineStop={handleEngineStop}
          linkDirectionalParticles={(link) => (link as GraphLink).particles}
          linkDirectionalParticleWidth={(link) => ((link as GraphLink).particles >= 6 ? 3 : 2)}
          linkDirectionalParticleSpeed={(link) => ((link as GraphLink).particles >= 6 ? 0.014 : 0.007)}
          linkWidth={(link) => (link as GraphLink).width}
          linkColor={(link) => (link as GraphLink).color}
          nodeRelSize={7}
          onNodeClick={(node) => onSelectNode((node as GraphNode).id)}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const typedNode = node as GraphNode;
            const label = typedNode.label;
            const fontSize = 12 / globalScale;
            const isSelected = typedNode.id === selectedNodeId;

            ctx.beginPath();
            ctx.arc(typedNode.x ?? 0, typedNode.y ?? 0, typedNode.val * (isSelected ? 1.4 : 1), 0, 2 * Math.PI);
            ctx.fillStyle = typedNode.dimmed ? "rgba(148, 163, 184, 0.35)" : typedNode.color;
            ctx.shadowColor = typedNode.color;
            ctx.shadowBlur = isSelected ? 12 : 0;
            ctx.fill();
            ctx.shadowBlur = 0;

            if (typedNode.flags.length > 0 && !typedNode.dimmed) {
              ctx.beginPath();
              ctx.arc(typedNode.x ?? 0, typedNode.y ?? 0, typedNode.val + 4, 0, 2 * Math.PI);
              ctx.strokeStyle = "rgba(241, 245, 249, 0.7)";
              ctx.lineWidth = 1.5;
              ctx.stroke();
            }

            ctx.font = `${fontSize}px "Inter", sans-serif`;
            ctx.fillStyle = typedNode.dimmed ? "rgba(226, 232, 240, 0.4)" : "#f1f5f9";
            ctx.fillText(label, (typedNode.x ?? 0) + 8, (typedNode.y ?? 0) - 8);
          }}
        />
      </div>
    </section>
  );
}
