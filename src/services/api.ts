import { mockInvestigationResult, mockScenarios } from "../data/mockData";
import {
  AccountNode,
  AuditEntry,
  ChatMessage,
  ConfidenceLevel,
  FlaggedPattern,
  InvestigationResult,
  InvestigationGraph,
  PatternType,
  Scenario,
  StageStatus,
  TransactionEdge
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const KNOWN_PATTERN_TYPES: PatternType[] = ["structuring", "layering", "mule_network", "circular_flow"];

function toSeededPatterns(scenarioId: string): PatternType[] {
  return (KNOWN_PATTERN_TYPES as string[]).includes(scenarioId) ? [scenarioId as PatternType] : [];
}

const TOKEN_KEY = "hawkeye_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// A 401 means the stored token is missing/expired - drop it and force back to
// the login screen rather than silently falling back to mock data forever.
function handleUnauthorized(): void {
  clearToken();
  window.location.reload();
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? "Invalid username or password.");
  }

  const data = (await response.json()) as { token: string };
  setToken(data.token);
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", headers: authHeaders() });
  } finally {
    clearToken();
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchScenarios(): Promise<Scenario[]> {
  try {
    const scenarios = await request<
      Array<{
        id: string;
        name: string;
        description: string;
        transaction_count: number;
        deletable?: boolean;
      }>
    >("/scenarios");

    return scenarios.map((scenario) => ({
      id: scenario.id,
      name: scenario.name,
      description: scenario.description,
      seededPatterns: toSeededPatterns(scenario.id),
      transactionCount: scenario.transaction_count,
      deletable: scenario.deletable ?? false
    }));
  } catch {
    return mockScenarios;
  }
}

const stageLabelMap: Record<string, string> = {
  ingestion: "Agent 1: Ingestion",
  watchlist_screening: "Agent 1B: Watchlist Screening",
  pattern_detection: "Agent 2: Pattern Detection",
  adversarial_review: "Agent 2B: Adversarial Review",
  risk_scoring: "Agent 3: Risk Scoring",
  case_memory: "Agent 3B: Case Memory",
  narrative: "Agent 4: Narrative & Next Steps"
};

const stageKeyMap: Record<string, StageStatus["key"]> = {
  ingestion: "ingestion",
  watchlist_screening: "watchlist",
  pattern_detection: "detection",
  adversarial_review: "adversarial",
  risk_scoring: "scoring",
  case_memory: "memory",
  narrative: "narrative"
};

const stageOrder = [
  "ingestion",
  "watchlist_screening",
  "pattern_detection",
  "adversarial_review",
  "risk_scoring",
  "case_memory",
  "narrative"
] as const;

function buildInitialStages(): StageStatus[] {
  return stageOrder.map((stage) => ({
    key: stageKeyMap[stage],
    label: stageLabelMap[stage],
    status: "idle",
    detail: "Waiting for pipeline event..."
  }));
}

function mapStages(
  events: Array<{ stage: string; status: "started" | "completed" | "failed"; data?: Record<string, unknown> }>
): StageStatus[] {
  const stages = buildInitialStages();

  for (const event of events) {
    const index = stageOrder.indexOf(event.stage as (typeof stageOrder)[number]);
    if (index === -1) {
      continue;
    }

    const status =
      event.status === "started" ? "running" : event.status === "completed" ? "done" : "idle";

    let detail = "Stage completed.";
    if (event.stage === "ingestion" && event.data?.account_count) {
      detail = `Normalized ${String(event.data.account_count)} accounts from the selected scenario.`;
    } else if (event.stage === "watchlist_screening" && event.data?.accounts_flagged !== undefined) {
      const flaggedCount = Number(event.data.accounts_flagged);
      detail =
        flaggedCount > 0
          ? `${flaggedCount} account(s) matched a high-risk pattern from a past investigation.`
          : "No accounts matched the repeat-offender watchlist.";
    } else if (event.stage === "pattern_detection" && event.data?.patterns_found !== undefined) {
      detail = `Detected ${String(event.data.patterns_found)} suspicious pattern group(s).`;
    } else if (event.stage === "adversarial_review" && event.data?.patterns_reviewed !== undefined) {
      const overturned = Number(event.data.patterns_overturned ?? 0);
      detail =
        overturned > 0
          ? `A skeptical second pass overturned ${overturned} of ${String(event.data.patterns_reviewed)} candidate(s) as likely false positives.`
          : `A skeptical second pass upheld all ${String(event.data.patterns_reviewed)} candidate(s).`;
    } else if (event.stage === "risk_scoring") {
      detail = "Risk factors and confidence levels have been assigned.";
    } else if (event.stage === "case_memory" && event.data?.patterns_with_precedent !== undefined) {
      const matches = Number(event.data.patterns_with_precedent);
      detail =
        matches > 0
          ? `Found precedent for ${matches} pattern(s) in past investigations.`
          : "No matching precedent found in past investigations.";
    } else if (event.stage === "narrative") {
      detail = "Narratives and next-step recommendations generated for the suspicious account clusters.";
    } else if (event.status === "started") {
      detail = "Stage is currently running...";
    }

    stages[index] = {
      ...stages[index],
      status,
      detail,
      summary: event.status === "completed" ? event.data ?? null : stages[index].summary
    };
  }

  return stages;
}

function normalizeAccount(account: {
  id: string;
  total_in: number;
  total_out: number;
  transaction_count: number;
  unique_counterparties: number;
  risk_score?: number | null;
  confidence?: ConfidenceLevel | null;
  flags: PatternType[];
  watchlist_note?: string | null;
}): AccountNode {
  return {
    id: account.id,
    label: account.id,
    totalIn: account.total_in,
    totalOut: account.total_out,
    transactionCount: account.transaction_count,
    uniqueCounterparties: account.unique_counterparties,
    riskScore: account.risk_score ?? null,
    confidence: account.confidence ?? null,
    flags: account.flags ?? [],
    watchlistNote: account.watchlist_note ?? null
  };
}

function normalizePattern(
  pattern: {
    pattern_type: PatternType;
    accounts_involved: string[];
    risk_score: number;
    confidence: ConfidenceLevel;
    narrative: string;
    reasoning?: string;
    additional_notes?: string | null;
    skeptic_challenge?: string | null;
    review_verdict?: string | null;
    next_steps?: string[];
    similar_past_cases?: string[];
  },
  index: number
): FlaggedPattern {
  return {
    id: `pattern-${index + 1}`,
    patternType: pattern.pattern_type,
    accountsInvolved: pattern.accounts_involved,
    transactionIds: [],
    riskScore: pattern.risk_score,
    confidence: pattern.confidence,
    narrative: pattern.narrative || pattern.reasoning || "Suspicious activity was detected in this account cluster.",
    additionalNotes: pattern.additional_notes ?? null,
    skepticChallenge: pattern.skeptic_challenge ?? null,
    reviewVerdict: pattern.review_verdict ?? null,
    nextSteps: pattern.next_steps ?? [],
    similarPastCases: pattern.similar_past_cases ?? []
  };
}

function normalizeGraph(rawGraph: {
  scenario_id: string;
  accounts: Array<{
    id: string;
    total_in: number;
    total_out: number;
    transaction_count: number;
    unique_counterparties: number;
    risk_score?: number | null;
    confidence?: ConfidenceLevel | null;
    flags: PatternType[];
    watchlist_note?: string | null;
  }>;
  transactions: Array<{
    from_account: string;
    to_account: string;
    amount: number;
    timestamp: string;
    currency: string;
  }>;
  flagged_patterns: Array<{
    pattern_type: PatternType;
    accounts_involved: string[];
    risk_score: number;
    confidence: ConfidenceLevel;
    narrative: string;
    reasoning?: string;
    additional_notes?: string | null;
    skeptic_challenge?: string | null;
    review_verdict?: string | null;
    next_steps?: string[];
    similar_past_cases?: string[];
  }>;
  executive_summary?: string | null;
}): InvestigationGraph {
  const patterns = rawGraph.flagged_patterns.map(normalizePattern);

  const transactions: TransactionEdge[] = rawGraph.transactions.map((transaction, index) => {
    const matchingPatterns = patterns
      .filter(
        (pattern) =>
          pattern.accountsInvolved.includes(transaction.from_account) &&
          pattern.accountsInvolved.includes(transaction.to_account)
      )
      .map((pattern) => pattern.patternType);

    return {
      id: `txn-${index + 1}`,
      from: transaction.from_account,
      to: transaction.to_account,
      amount: transaction.amount,
      currency: transaction.currency,
      timestamp: transaction.timestamp,
      flagged: matchingPatterns.length > 0,
      patternTypes: matchingPatterns
    };
  });

  return {
    accounts: rawGraph.accounts.map(normalizeAccount),
    transactions,
    flaggedPatterns: patterns.map((pattern) => ({
      ...pattern,
      transactionIds: transactions
        .filter((transaction) => transaction.patternTypes?.includes(pattern.patternType))
        .map((transaction) => transaction.id)
    })),
    executiveSummary: rawGraph.executive_summary ?? null
  };
}

export async function runInvestigation(
  scenarioId: string,
  onStagesUpdate?: (stages: StageStatus[]) => void
): Promise<InvestigationResult> {
  const startedAt = Date.now();

  try {
    const response = await fetch(`${API_BASE}/investigate/${scenarioId}`, {
      method: "POST",
      headers: authHeaders()
    });

    if (response.status === 401) {
      handleUnauthorized();
      throw new Error("Unauthorized");
    }

    if (!response.ok || !response.body) {
      throw new Error(`Investigation stream failed with ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const events: Array<{ stage: string; status: "started" | "completed" | "failed"; data?: Record<string, unknown> }> = [];
    let rawGraph: any = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        const line = chunk
          .split("\n")
          .find((candidate) => candidate.startsWith("data:"));

        if (!line) {
          continue;
        }

        const event = JSON.parse(line.slice(5).trim()) as {
          stage: string;
          status: "started" | "completed" | "failed";
          data?: Record<string, unknown>;
        };

        events.push(event);
        onStagesUpdate?.(mapStages(events));

        if (event.stage === "pipeline" && event.status === "completed" && event.data) {
          rawGraph = event.data;
        }
      }
    }

    if (!rawGraph) {
      rawGraph = await request(`/investigate/${scenarioId}/result`);
    }

    const scenario = (await fetchScenarios()).find((item) => item.id === scenarioId) ?? mockScenarios[0];
    const graph = normalizeGraph(rawGraph as any);
    const stages = mapStages(events);

    return {
      scenario,
      graph,
      stages,
      generatedAt: new Date().toISOString(),
      elapsedMs: Date.now() - startedAt,
      usedMockData: false
    };
  } catch {
    return {
      ...mockInvestigationResult,
      scenario: mockScenarios.find((scenario) => scenario.id === scenarioId) ?? mockScenarios[0],
      generatedAt: new Date().toISOString(),
      usedMockData: true
    };
  }
}

export async function uploadScenario(
  file: File,
  name?: string
): Promise<{ scenarioId: string; transactionCount: number; name: string }> {
  const formData = new FormData();
  formData.append("file", file);
  if (name?.trim()) {
    formData.append("name", name.trim());
  }

  const response = await fetch(`${API_BASE}/scenarios/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: formData
  });

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Upload failed with ${response.status}`);
  }

  const data = (await response.json()) as { scenario_id: string; transaction_count: number; name: string };
  return { scenarioId: data.scenario_id, transactionCount: data.transaction_count, name: data.name };
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/scenarios/${scenarioId}`, {
    method: "DELETE",
    headers: authHeaders()
  });

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Delete failed with ${response.status}`);
  }
}

export async function downloadReport(scenarioId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/investigate/${scenarioId}/report.pdf`, {
    headers: authHeaders()
  });

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    throw new Error(`Report download failed with ${response.status}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${scenarioId}-report.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function askAboutCase(
  scenarioId: string,
  question: string,
  history: ChatMessage[]
): Promise<string> {
  const data = await request<{ answer: string }>(`/investigate/${scenarioId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question, history })
  });
  return data.answer;
}

export async function fetchAuditLog(scenarioId: string): Promise<AuditEntry[]> {
  try {
    const entries = await request<
      Array<{
        id: string;
        type: "investigation_run" | "chat_message";
        scenario_id: string;
        timestamp: string;
        summary: string;
        details: Record<string, unknown>;
      }>
    >(`/investigate/${scenarioId}/audit`);

    return entries.map((entry) => ({
      id: entry.id,
      type: entry.type,
      scenarioId: entry.scenario_id,
      timestamp: entry.timestamp,
      summary: entry.summary,
      details: entry.details
    }));
  } catch {
    return [];
  }
}
