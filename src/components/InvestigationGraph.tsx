import ForceGraph2D from "react-force-graph-2d";
import { useCallback, useEffect, useRef, useState } from "react";
import { downloadReport } from "../services/api";
import { AccountNode, InvestigationResult, TransactionEdge } from "../types";

interface GraphNode extends AccountNode {
  color: string;
  val: number;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  amount: number;
  color: string;
  flagged: boolean;
}

interface InvestigationGraphProps {
  result: InvestigationResult | null;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  loading?: boolean;
  reportScenarioId?: string | null;
}

function getNodeColor(node: AccountNode) {
  if ((node.riskScore ?? 0) >= 85) return "#dc2626";
  if ((node.riskScore ?? 0) >= 60) return "#ea580c";
  if ((node.riskScore ?? 0) >= 30) return "#d97706";
  return "#2563eb";
}

function mapNode(node: AccountNode): GraphNode {
  return {
    ...node,
    color: getNodeColor(node),
    val: 1.5 + ((node.riskScore ?? 8) / 18)
  };
}

function mapLink(edge: TransactionEdge): GraphLink {
  return {
    source: edge.from,
    target: edge.to,
    amount: edge.amount,
    color: edge.flagged ? "rgba(220, 38, 38, 0.85)" : "rgba(100, 116, 139, 0.35)",
    flagged: Boolean(edge.flagged)
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

  const nodes = result.graph.accounts.map(mapNode);
  const links = result.graph.transactions.map(mapLink);

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
        <span><i className="legend-line" />Flagged transfer path</span>
      </div>

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
          linkDirectionalParticles={(link) => (link.flagged ? 4 : 0)}
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleSpeed={0.007}
          linkWidth={(link) => (link.flagged ? 2.4 : 1)}
          linkColor={(link) => link.color}
          nodeRelSize={7}
          onNodeClick={(node) => onSelectNode((node as GraphNode).id)}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const typedNode = node as GraphNode;
            const label = typedNode.label;
            const fontSize = 12 / globalScale;
            const isSelected = typedNode.id === selectedNodeId;

            ctx.beginPath();
            ctx.arc(typedNode.x ?? 0, typedNode.y ?? 0, typedNode.val * (isSelected ? 1.4 : 1), 0, 2 * Math.PI);
            ctx.fillStyle = typedNode.color;
            ctx.shadowColor = typedNode.color;
            ctx.shadowBlur = isSelected ? 12 : 0;
            ctx.fill();
            ctx.shadowBlur = 0;

            if (typedNode.flags.length > 0) {
              ctx.beginPath();
              ctx.arc(typedNode.x ?? 0, typedNode.y ?? 0, typedNode.val + 4, 0, 2 * Math.PI);
              ctx.strokeStyle = "rgba(15, 23, 42, 0.55)";
              ctx.lineWidth = 1.5;
              ctx.stroke();
            }

            ctx.font = `${fontSize}px "Inter", sans-serif`;
            ctx.fillStyle = "#0f172a";
            ctx.fillText(label, (typedNode.x ?? 0) + 8, (typedNode.y ?? 0) - 8);
          }}
        />
      </div>
    </section>
  );
}
