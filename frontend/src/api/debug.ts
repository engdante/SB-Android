/**
 * Frontend Debug Logger.
 * Изпраща debug информация към backend /api/debug/log.
 * Автоматично прихваща грешки и потребителски действия.
 */

import axios from 'axios';

const debugApi = axios.create({
  baseURL: '/api',
  timeout: 5000,
});

let debugEnabled = true;

export function setDebugEnabled(enabled: boolean) {
  debugEnabled = enabled;
}

export function isDebugEnabled(): boolean {
  return debugEnabled;
}

/**
 * Изпраща debug log към backend-а.
 */
async function sendLog(level: string, source: string, message: string, data?: any) {
  if (!debugEnabled) return;

  try {
    await debugApi.post('/debug/log', {
      level,
      source,
      message,
      data: data ? JSON.stringify(data, null, 2).slice(0, 2000) : undefined,
    });
  } catch {
    // Silent fail — debug logging shouldn't break the app
  }
}

/**
 * Логва информационно съобщение.
 */
export function logInfo(source: string, message: string, data?: any) {
  sendLog('info', source, message, data);
}

/**
 * Логва предупреждение.
 */
export function logWarn(source: string, message: string, data?: any) {
  sendLog('warn', source, message, data);
}

/**
 * Логва грешка.
 */
export function logError(source: string, message: string, data?: any) {
  sendLog('error', source, message, data);
  console.error(`[${source}] ${message}`, data);
}

/**
 * Логва потребителско действие.
 */
export function logAction(action: string, details?: any) {
  sendLog('info', 'user_action', action, details);
}

/**
 * Инициализира глобален error handler за необработени грешки.
 */
export function initGlobalErrorHandler() {
  window.addEventListener('error', (event) => {
    logError('global', event.message, {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logError('global', 'Unhandled Promise rejection', {
      reason: String(event.reason),
    });
  });

  logInfo('system', 'Global error handlers initialized');
}

/**
 * Check debug status from backend.
 */
export async function checkDebugStatus(): Promise<boolean> {
  try {
    const { data } = await axios.get('/api/debug/status');
    debugEnabled = data.debug_enabled;
    return debugEnabled;
  } catch {
    return debugEnabled;
  }
}

/**
 * Toggle debug on the backend.
 */
export async function toggleDebug(enabled: boolean): Promise<boolean> {
  try {
    const { data } = await axios.post(`/api/debug/toggle?enabled=${enabled}`);
    debugEnabled = data.debug_enabled;
    return debugEnabled;
  } catch {
    return debugEnabled;
  }
}