/**
 * Settings API — calls the existing backend on port 8000.
 * The A2UI backend reads the same settings, so saving here affects both.
 */

const BACKEND = "http://localhost:8000";

export type AIProvider = "ollama" | "lmstudio" | "gemini" | "claude" | "llamacpp";

export interface AISettings {
  ai_provider: AIProvider;
  ollama_base_url: string;
  ollama_model: string;
  ollama_code_model: string;
  lmstudio_base_url: string;
  lmstudio_model: string;
  lmstudio_code_model: string;
  gemini_api_key: string;
  gemini_model: string;
  gemini_code_model: string;
  claude_api_key: string;
  claude_model: string;
  claude_code_model: string;
  llamacpp_base_url: string;
  llamacpp_model: string;
  llamacpp_code_model: string;
  history_cache_path: string;
  history_cache_path_resolved?: string;
  db_path?: string;
}

export interface ModelsResponse {
  models: string[];
  error: string | null;
}

export const EMPTY_SETTINGS: AISettings = {
  ai_provider: "ollama",
  ollama_base_url: "",
  ollama_model: "",
  ollama_code_model: "",
  lmstudio_base_url: "http://localhost:1234/v1",
  lmstudio_model: "",
  lmstudio_code_model: "",
  gemini_api_key: "",
  gemini_model: "gemini-2.0-flash",
  gemini_code_model: "gemini-2.0-flash",
  claude_api_key: "",
  claude_model: "claude-3-5-haiku-20241022",
  claude_code_model: "claude-3-5-haiku-20241022",
  llamacpp_base_url: "http://localhost:8080/v1",
  llamacpp_model: "",
  llamacpp_code_model: "",
  history_cache_path: "",
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const settingsApi = {
  getSettings: () => get<AISettings>("/settings/"),
  updateSettings: (data: AISettings) => put<AISettings>("/settings/", data),
  getOllamaModels: () => get<ModelsResponse>("/settings/ollama-models"),
  getLmStudioModels: () => get<ModelsResponse>("/settings/lmstudio-models"),
  getLlamaCppModels: () => get<ModelsResponse>("/settings/llamacpp-models"),
};
