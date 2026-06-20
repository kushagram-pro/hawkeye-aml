// The four named detectors emit one of these, but the general anomaly detector
// can mint its own free-form snake_case label for a scam shape none of them
// cover - so this is a plain string, not a closed union.
export type PatternType = string;
export type ConfidenceLevel = "low" | "medium" | "high";

export interface Scenario {
  id: string;
  name: string;
  description: string;
  seededPatterns: PatternType[];
  transactionCount: number;
  deletable?: boolean;
}

export interface AccountNode {
  id: string;
  label: string;
  totalIn: number;
  totalOut: number;
  transactionCount: number;
  uniqueCounterparties: number;
  riskScore?: number | null;
  confidence?: ConfidenceLevel | null;
  flags: PatternType[];
}

export interface TransactionEdge {
  id: string;
  from: string;
  to: string;
  amount: number;
  currency: string;
  timestamp: string;
  flagged?: boolean;
  patternTypes?: PatternType[];
}

export interface FlaggedPattern {
  id: string;
  patternType: PatternType;
  accountsInvolved: string[];
  transactionIds: string[];
  riskScore: number;
  confidence: ConfidenceLevel;
  narrative: string;
  additionalNotes?: string | null;
}

export interface InvestigationGraph {
  accounts: AccountNode[];
  transactions: TransactionEdge[];
  flaggedPatterns: FlaggedPattern[];
  executiveSummary?: string | null;
}

export interface StageStatus {
  key: "ingestion" | "detection" | "scoring" | "narrative";
  label: string;
  status: "idle" | "running" | "done";
  detail: string;
  summary?: Record<string, unknown> | null;
}

export interface InvestigationResult {
  scenario: Scenario;
  graph: InvestigationGraph;
  stages: StageStatus[];
  generatedAt: string;
  elapsedMs: number;
  usedMockData?: boolean;
}
