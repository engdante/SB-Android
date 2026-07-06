import axios from 'axios';

/**
 * Определя backend base URL по приоритет:
 * 1. localStorage (runtime override от Settings UI)
 * 2. VITE_API_BASE_URL environment variable (build/deploy time)
 * 3. Автоматично откриване от window.location (за PWA на телефон)
 * 4. '/api' (Vite dev server proxy — localhost)
 */
function getBaseURL(): string {
  const fromStorage = localStorage.getItem('sb_api_base_url');
  if (fromStorage) return `${fromStorage.replace(/\/+$/, '')}/api`;

  const fromEnv = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (fromEnv) return `${fromEnv.replace(/\/+$/, '')}/api`;

  // Автоматично откриване: ако сме на production (не dev server),
  // backend-ът е на същия host и port
  if (!import.meta.env.DEV) {
    const { protocol, hostname, port } = window.location;
    // Ако сме на стандартен порт (80/443), не го включваме
    const portStr = port && port !== '80' && port !== '443' ? `:${port}` : '';
    return `${protocol}//${hostname}${portStr}/api`;
  }

  return '/api';
}

const api = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Позволява на Settings UI да промени runtime base URL-а.
 * Извиква се при запис на нов backend адрес.
 */
export function setBackendHost(host: string): void {
  if (host) {
    localStorage.setItem('sb_api_base_url', host);
  } else {
    localStorage.removeItem('sb_api_base_url');
  }
  api.defaults.baseURL = getBaseURL();
}

/**
 * Връща текущо конфигурирания backend host (без trailing slash и без /api).
 */
export function getBackendHost(): string {
  const fromStorage = localStorage.getItem('sb_api_base_url');
  if (fromStorage) return fromStorage;

  const fromEnv = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (fromEnv) return fromEnv;

  return 'http://localhost:8000';
}

export interface Concept {
  path: string;
  metadata: {
    id: string;
    type: string;
    title: string;
    description: string;
    tags: string[];
    language: string | null;
    timestamp: string;
  };
  body_preview: string;
}

export interface ConceptDetail {
  status: string;
  path: string;
  metadata: Concept['metadata'];
  body: string;
}

export interface TextInputResponse {
  status: string;
  concept: Concept['metadata'];
  body_preview: string;
}

export interface AskResponse {
  status: string;
  answer: string;
  sources: Array<{ title: string; type: string; relevance: number }>;
}

export interface HealthResponse {
  status: string;
  llm_connected: boolean;
  data_dir: string;
  total_concepts: number;
}

export const inputApi = {
  submitText: async (text: string): Promise<TextInputResponse> => {
    const { data } = await api.post('/input/text', { text });
    return data;
  },

  uploadAudio: async (file: File, language: string = 'bg') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    const { data } = await api.post('/input/audio', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};

export const searchApi = {
  listConcepts: async (params?: { type?: string; tag?: string; date_from?: string; date_to?: string; limit?: number }) => {
    const { data } = await api.get('/search/concepts', { params });
    return data as { status: string; total: number; concepts: Concept[] };
  },

  getConcept: async (filepath: string) => {
    const { data } = await api.get(`/search/concepts/${filepath}`);
    return data as ConceptDetail;
  },

  deleteConcept: async (filepath: string) => {
    const { data } = await api.delete(`/search/concepts/${filepath}`);
    return data as { status: string; message: string };
  },

  updateConcept: async (filepath: string, metadata: Concept['metadata'], body: string) => {
    const { data } = await api.put(`/search/concepts/${filepath}`, { metadata, body });
    return data as ConceptDetail & { message: string };
  },

  askQuestion: async (question: string): Promise<AskResponse> => {
    const { data } = await api.post('/search/wiki/ask', { question });
    return data;
  },
};

export interface SettingsData {
  ollama_host: string;
  ollama_model: string;
  effective_host: string;
  effective_model: string;
  ingestion_model: string;
  rag_model: string;
  cloud_models: string[];
  available_models: string[];
  audio_model: string;
  backend_url: string;
}

export interface ListModelsResponse {
  status: string;
  host?: string;
  models?: string[];
  message?: string;
}

export interface LLMModelsResponse {
  status: string;
  models: {
    local: Array<{
      name: string;
      size: number;
      family: string;
      parameter_size: string;
      quantization: string;
      context_length: number;
      capabilities: string[];
    }>;
    cloud: Array<{
      name: string;
      host: string;
      has_api_key: boolean;
    }>;
  };
  selected: {
    ingestion: string;
    rag: string;
  };
}

export interface LLMHealthResponse {
  status: string;
  health: {
    ingestion: boolean;
    rag: boolean;
  };
  config: {
    ingestion_model: string;
    ingestion_host: string;
    rag_model: string;
    rag_host: string;
    is_ingestion_cloud: boolean;
    is_rag_cloud: boolean;
  };
}

export interface LLMSwitchResponse {
  status: string;
  message: string;
  current_model: string;
  host: string;
  is_cloud: boolean;
}

export const healthApi = {
  check: async () => {
    const { data } = await api.get('/health');
    return data as HealthResponse;
  },
};

export const settingsApi = {
  getSettings: async (): Promise<SettingsData> => {
    const { data } = await api.get('/settings');
    return data;
  },

  updateSettings: async (params: {
    ollama_host?: string;
    ollama_model?: string;
    ingestion_model?: string;
    rag_model?: string;
    audio_model?: string;
    backend_url?: string;
    save_to_env?: boolean;
  }) => {
    const { data } = await api.post('/settings', params);
    return data;
  },

  listModels: async (host?: string): Promise<ListModelsResponse> => {
    const { data } = await api.get('/settings/models', {
      params: host ? { host } : undefined,
    });
    return data;
  },
};

export interface DebugStatusResponse {
  status: string;
  debug_enabled: boolean;
  env_setting: boolean;
  runtime_override: boolean;
  log_dir: string;
}

export interface DebugLogFile {
  name: string;
  path: string;
  size: number;
  modified: string;
}

export interface DebugLogsResponse {
  status: string;
  total: number;
  files: DebugLogFile[];
}

export interface DebugLogContentResponse {
  status: string;
  file: string;
  total_entries: number;
  entries: any[];
}

export const debugApi = {
  getStatus: async (): Promise<DebugStatusResponse> => {
    const { data } = await api.get('/debug/status');
    return data;
  },

  toggle: async (enabled: boolean): Promise<{ status: string; debug_enabled: boolean }> => {
    const { data } = await api.post(`/debug/toggle?enabled=${enabled}`);
    return data;
  },

  listLogs: async (): Promise<DebugLogsResponse> => {
    const { data } = await api.get('/debug/logs');
    return data;
  },

  readLog: async (filepath: string, lines: number = 100): Promise<DebugLogContentResponse> => {
    const { data } = await api.get(`/debug/logs/${filepath}`, { params: { lines } });
    return data;
  },
};

export interface DataExportResponse {
  status: string;
  message?: string;
}

export interface DataImportResponse {
  status: string;
  imported: number;
  skipped: number;
  total_in_zip: number;
  message: string;
}

export interface DataClearResponse {
  status: string;
  deleted: number;
  message: string;
}

export const dataApi = {
  /** Експортира всички OKF данни като ZIP файл (download) */
  exportData: async (): Promise<Blob> => {
    const response = await api.post('/data/export', {}, {
      responseType: 'blob',
    });
    return response.data;
  },

  /** Импортира ZIP файл с OKF данни */
  importData: async (file: File): Promise<DataImportResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/data/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  /** Изтрива всички OKF концепции (с потвърждение) */
  clearData: async (): Promise<DataClearResponse> => {
    const { data } = await api.delete('/data/clear', {
      params: { confirm: true },
    });
    return data;
  },
};

export const llmApi = {
  /** Връща всички налични модели (local + cloud) */
  getModels: async (): Promise<LLMModelsResponse> => {
    const { data } = await api.get('/llm/models');
    return data;
  },

  /** Връща health статус на двата клиента */
  getHealth: async (): Promise<LLMHealthResponse> => {
    const { data } = await api.get('/llm/health');
    return data;
  },

  /** Switches the ingestion model at runtime */
  switchIngestion: async (modelName: string): Promise<LLMSwitchResponse> => {
    const { data } = await api.post('/llm/switch/ingestion', { model: modelName });
    return data;
  },

  /** Switches the RAG model at runtime */
  switchRag: async (modelName: string): Promise<LLMSwitchResponse> => {
    const { data } = await api.post('/llm/switch/rag', { model: modelName });
    return data;
  },

  /** Връща текущата LLM конфигурация */
  getConfig: async () => {
    const { data } = await api.get('/llm/config');
    return data;
  },
};

export default api;
