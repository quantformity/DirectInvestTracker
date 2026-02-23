import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// AI endpoints can take much longer (LLM inference + SQL execution)
const aiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 300000, // 5 minutes
});

export default client;

// ─── Type definitions matching backend schemas ────────────────────────────────

export type CategoryEnum = "Equity" | "GIC" | "Cash" | "Dividend";

export interface Account {
  id: number;
  name: string;
  base_currency: string;
}

export interface Position {
  id: number;
  account_id: number;
  symbol: string;
  category: CategoryEnum;
  quantity: number;
  cost_per_share: number;
  date_added: string;
  yield_rate: number | null;
  currency: string;
}

export interface MarketData {
  symbol: string;
  last_price: number | null;
  pe_ratio: number | null;
  change_percent: number | null;
  beta: number | null;
  timestamp: string;
}

export interface FxRate {
  pair: string;
  rate: number;
  timestamp: string;
}

export interface EnrichedPosition {
  id: number;
  symbol: string;
  category: CategoryEnum;
  account_id: number;
  account_name: string;
  account_currency: string;
  quantity: number;
  cost_per_share: number;
  date_added: string;
  yield_rate: number | null;
  stock_currency: string;
  spot_price: number | null;
  fx_stock_to_account: number;
  fx_account_to_reporting: number;
  mtm_account: number;
  pnl_account: number;
  mtm_reporting: number;
  pnl_reporting: number;
  proportion: number;
}

export interface SummaryGroup {
  group_key: string;
  total_mtm_reporting: number;
  total_pnl_reporting: number;
  proportion: number;
}

export interface SummaryOut {
  positions: EnrichedPosition[];
  groups: SummaryGroup[];
  total_mtm_reporting: number;
  total_pnl_reporting: number;
  reporting_currency: string;
}

export interface HistoryPoint {
  date: string;
  close_price: number;
  pnl: number;
  mtm: number;
  cash_gic?: number;
}

export interface HistoryOut {
  symbol: string;
  account_id: number | null;
  points: HistoryPoint[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatResponse {
  reply: string;
  pending_sql?: string | null;
}

export interface ActionPlan {
  action: string;   // "add_position" | "delete_position" | "record_cash" | "record_dividend" | "none"
  description: string;
  params: Record<string, unknown>;
}

export interface ExecuteActionResponse {
  success: boolean;
  message: string;
}

export interface ChartResponse {
  type: "image" | "plotly" | "table" | "error";
  data: string;
}

export interface OllamaSettings {
  ollama_base_url: string;
  ollama_model: string;
  ollama_code_model: string;
}

export interface OllamaModelsResponse {
  models: string[];
  error: string | null;
}

// ─── API helpers ──────────────────────────────────────────────────────────────

export const api = {
  // Accounts
  getAccounts: () => client.get<Account[]>("/accounts/").then((r) => r.data),
  createAccount: (data: { name: string; base_currency: string }) =>
    client.post<Account>("/accounts/", data).then((r) => r.data),
  updateAccount: (id: number, data: Partial<Account>) =>
    client.put<Account>(`/accounts/${id}`, data).then((r) => r.data),
  deleteAccount: (id: number) => client.delete(`/accounts/${id}`),

  // Positions
  getPositions: (account_id?: number) =>
    client.get<Position[]>("/positions/", { params: account_id ? { account_id } : {} }).then((r) => r.data),
  createPosition: (data: Omit<Position, "id">) =>
    client.post<Position>("/positions/", data).then((r) => r.data),
  updatePosition: (id: number, data: Partial<Position>) =>
    client.put<Position>(`/positions/${id}`, data).then((r) => r.data),
  deletePosition: (id: number) => client.delete(`/positions/${id}`),

  // Market Data
  getMarketData: () => client.get<MarketData[]>("/market-data/").then((r) => r.data),
  refreshMarketData: () => client.post("/market-data/refresh").then((r) => r.data),

  // FX Rates
  getFxRates: () => client.get<FxRate[]>("/fx-rates/").then((r) => r.data),

  // Summary
  getSummary: (group_by = "category") =>
    client.get<SummaryOut>("/summary/", { params: { group_by } }).then((r) => r.data),

  // History
  getHistory: (symbol: string, account_id?: number) =>
    client.get<HistoryOut>("/history/", { params: { symbol, account_id } }).then((r) => r.data),
  getAggregateHistory: (account_id?: number) =>
    client.get<HistoryOut>("/history/aggregate", { params: account_id != null ? { account_id } : {} }).then((r) => r.data),

  // AI  (use aiClient — long timeout for LLM inference)
  chat: (messages: ChatMessage[]) =>
    aiClient.post<ChatResponse>("/ai/chat", { messages }).then((r) => r.data),
  chart: (prompt: string) =>
    aiClient.post<ChartResponse>("/ai/chart", { prompt }).then((r) => r.data),
  executeSQL: (sql: string, question: string) =>
    aiClient.post<ChatResponse>("/ai/sql/execute", { sql, question }).then((r) => r.data),
  planAction: (message: string) =>
    aiClient.post<ActionPlan>("/ai/action/plan", { message }).then((r) => r.data),
  executeAction: (action: string, params: Record<string, unknown>) =>
    aiClient.post<ExecuteActionResponse>("/ai/action/execute", { action, params }).then((r) => r.data),

  // Settings
  getSettings: () =>
    client.get<OllamaSettings>("/settings/").then((r) => r.data),
  updateSettings: (data: OllamaSettings) =>
    client.put<OllamaSettings>("/settings/", data).then((r) => r.data),
  getOllamaModels: () =>
    client.get<OllamaModelsResponse>("/settings/ollama-models").then((r) => r.data),
};
