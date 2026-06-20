import { InvestigationResult, Scenario } from "../types";

export const mockScenarios: Scenario[] = [
  {
    id: "structuring-surge",
    name: "Structuring Surge",
    description: "Small deposits converge on a collector account before rapid consolidation.",
    seededPatterns: ["structuring"],
    transactionCount: 34
  },
  {
    id: "layering-chain",
    name: "Layering Chain",
    description: "Funds move through a chain of intermediaries before disappearing into a sink.",
    seededPatterns: ["layering"],
    transactionCount: 41
  },
  {
    id: "mule-fanout",
    name: "Mule Fan-Out",
    description: "A source account sprays money to multiple receivers that cash out independently.",
    seededPatterns: ["mule_network"],
    transactionCount: 38
  }
];

export const mockInvestigationResult: InvestigationResult = {
  scenario: mockScenarios[0],
  generatedAt: new Date().toISOString(),
  elapsedMs: 18340,
  usedMockData: true,
  stages: [
    {
      key: "ingestion",
      label: "Agent 1: Ingestion",
      status: "done",
      detail: "Normalized 34 transfers into 12 accounts and 34 linked edges."
    },
    {
      key: "detection",
      label: "Agent 2: Pattern Detection",
      status: "done",
      detail: "Detected a structuring cluster with tight time and threshold evasion signals."
    },
    {
      key: "scoring",
      label: "Agent 3: Risk Scoring",
      status: "done",
      detail: "Assigned 3 high-risk accounts using velocity, convergence, and counterparty diversity."
    },
    {
      key: "narrative",
      label: "Agent 4: Narrative",
      status: "done",
      detail: "Generated judge-friendly explanations for the flagged pattern and focal accounts."
    }
  ],
  graph: {
    accounts: [
      { id: "A1", label: "A1", totalIn: 0, totalOut: 42000, transactionCount: 3, uniqueCounterparties: 3, riskScore: 22, confidence: "low", flags: [] },
      { id: "A2", label: "A2", totalIn: 0, totalOut: 47000, transactionCount: 2, uniqueCounterparties: 2, riskScore: 35, confidence: "medium", flags: [] },
      { id: "A3", label: "A3", totalIn: 0, totalOut: 45000, transactionCount: 2, uniqueCounterparties: 2, riskScore: 38, confidence: "medium", flags: [] },
      { id: "A4", label: "A4", totalIn: 0, totalOut: 49000, transactionCount: 2, uniqueCounterparties: 2, riskScore: 41, confidence: "medium", flags: [] },
      { id: "A5", label: "A5", totalIn: 0, totalOut: 46000, transactionCount: 1, uniqueCounterparties: 1, riskScore: 33, confidence: "medium", flags: [] },
      { id: "HUB-9", label: "HUB-9", totalIn: 229000, totalOut: 227500, transactionCount: 8, uniqueCounterparties: 7, riskScore: 91, confidence: "high", flags: ["structuring"] },
      { id: "Y7", label: "Y7", totalIn: 227500, totalOut: 225000, transactionCount: 4, uniqueCounterparties: 3, riskScore: 84, confidence: "high", flags: ["structuring"] },
      { id: "Z1", label: "Z1", totalIn: 225000, totalOut: 0, transactionCount: 2, uniqueCounterparties: 1, riskScore: 73, confidence: "high", flags: ["structuring"] },
      { id: "N1", label: "N1", totalIn: 15000, totalOut: 18000, transactionCount: 3, uniqueCounterparties: 2, riskScore: 9, confidence: "low", flags: [] },
      { id: "N2", label: "N2", totalIn: 24000, totalOut: 19000, transactionCount: 3, uniqueCounterparties: 2, riskScore: 11, confidence: "low", flags: [] },
      { id: "N3", label: "N3", totalIn: 31000, totalOut: 15000, transactionCount: 4, uniqueCounterparties: 3, riskScore: 14, confidence: "low", flags: [] },
      { id: "N4", label: "N4", totalIn: 12000, totalOut: 12000, transactionCount: 2, uniqueCounterparties: 1, riskScore: 6, confidence: "low", flags: [] }
    ],
    transactions: [
      { id: "T1", from: "A1", to: "HUB-9", amount: 42000, currency: "INR", timestamp: "2026-06-20T08:00:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "T2", from: "A2", to: "HUB-9", amount: 47000, currency: "INR", timestamp: "2026-06-20T09:10:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "T3", from: "A3", to: "HUB-9", amount: 45000, currency: "INR", timestamp: "2026-06-20T10:25:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "T4", from: "A4", to: "HUB-9", amount: 49000, currency: "INR", timestamp: "2026-06-20T11:05:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "T5", from: "A5", to: "HUB-9", amount: 46000, currency: "INR", timestamp: "2026-06-20T11:40:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "T6", from: "HUB-9", to: "Y7", amount: 227500, currency: "INR", timestamp: "2026-06-20T13:00:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "T7", from: "Y7", to: "Z1", amount: 225000, currency: "INR", timestamp: "2026-06-20T14:15:00Z", flagged: true, patternTypes: ["structuring"] },
      { id: "N-T1", from: "N1", to: "N2", amount: 8000, currency: "INR", timestamp: "2026-06-20T08:30:00Z" },
      { id: "N-T2", from: "N2", to: "N3", amount: 6000, currency: "INR", timestamp: "2026-06-20T09:50:00Z" },
      { id: "N-T3", from: "N3", to: "N4", amount: 5000, currency: "INR", timestamp: "2026-06-20T10:10:00Z" },
      { id: "N-T4", from: "N4", to: "N1", amount: 4000, currency: "INR", timestamp: "2026-06-20T10:50:00Z" }
    ],
    flaggedPatterns: [
      {
        id: "P1",
        patternType: "structuring",
        accountsInvolved: ["A1", "A2", "A3", "A4", "A5", "HUB-9", "Y7", "Z1"],
        transactionIds: ["T1", "T2", "T3", "T4", "T5", "T6", "T7"],
        riskScore: 91,
        confidence: "high",
        narrative:
          "HUB-9 received five sub-threshold transfers from distinct accounts within roughly four hours, then rapidly consolidated the funds to Y7 and onward to Z1. The timing, convergence, and immediate onward movement strongly match a structuring workflow intended to avoid reporting triggers."
      }
    ]
  }
};
