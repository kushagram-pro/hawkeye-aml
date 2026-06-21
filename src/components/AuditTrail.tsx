import { useEffect, useState } from "react";
import { fetchAuditLog } from "../services/api";
import { AuditEntry } from "../types";

interface AuditTrailProps {
  scenarioId: string | null;
  refreshToken: number;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "none";
  return String(value);
}

function detailLabel(key: string): string {
  return key.replace(/_/g, " ");
}

export function AuditTrail({ scenarioId, refreshToken }: AuditTrailProps) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!scenarioId) {
      setEntries([]);
      return;
    }
    setLoading(true);
    let cancelled = false;
    void fetchAuditLog(scenarioId).then((result) => {
      if (!cancelled) {
        setEntries(result);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [scenarioId, refreshToken]);

  return (
    <section className="panel audit-trail">
      <div className="section-heading">
        <span className="eyebrow">Audit Trail</span>
        <h2>Investigation activity log</h2>
      </div>

      {!scenarioId ? (
        <p className="helper-text">Run an investigation to start building an audit trail for this case.</p>
      ) : (
        <>
          {loading ? <p className="helper-text">Loading activity...</p> : null}
          {!loading && entries.length === 0 ? <p className="helper-text">No logged activity yet for this case.</p> : null}

          <div className="audit-list">
            {entries.map((entry) => {
              const expanded = expandedId === entry.id;
              return (
                <div key={entry.id} className="audit-entry">
                  <button
                    type="button"
                    className="audit-entry-header"
                    onClick={() => setExpandedId(expanded ? null : entry.id)}
                  >
                    <span className={`audit-type-badge ${entry.type}`}>
                      {entry.type === "investigation_run" ? "Pipeline Run" : "Chat"}
                    </span>
                    <span className="audit-summary">{entry.summary}</span>
                    <span className="audit-timestamp">{formatTimestamp(entry.timestamp)}</span>
                  </button>
                  {expanded ? (
                    <dl className="audit-details">
                      {Object.entries(entry.details).map(([key, value]) => (
                        <div key={key} className="audit-detail-row">
                          <dt>{detailLabel(key)}</dt>
                          <dd>{formatDetailValue(value)}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
