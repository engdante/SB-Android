import React, { useState, useEffect } from 'react';
import { settingsApi, SettingsData, debugApi, DebugLogFile, DebugLogContentResponse, dataApi, setBackendHost, getBackendHost, llmApi } from '../api/client';
import { setDebugEnabled } from '../api/debug';
import { NotificationType } from '../config/conceptTypes';

interface SettingsProps {
  onClose: () => void;
  onSettingsChange: () => void;
}

const Settings: React.FC<SettingsProps> = ({ onClose, onSettingsChange }) => {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [host, setHost] = useState('');
  const [model, setModel] = useState('');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ type: NotificationType; text: string } | null>(null);
  const [saveToEnv, setSaveToEnv] = useState(false);

  // Dual model state
  const [ingestionModel, setIngestionModel] = useState('');
  const [ragModel, setRagModel] = useState('');
  const [allModelOptions, setAllModelOptions] = useState<{ name: string; source: 'local' | 'cloud' }[]>([]);

  // Audio model state (whisper.cpp GGUF модел)
  const [audioModel, setAudioModel] = useState('');

  // Data management state
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearingConfirm, setClearingConfirm] = useState(false);

  // Backend host state
  const [backendHost, setBackendHostState] = useState(getBackendHost());

  // Debug state
  const [debugEnabled, setDebugEnabledState] = useState(true);
  const [logFiles, setLogFiles] = useState<DebugLogFile[]>([]);
  const [selectedLog, setSelectedLog] = useState<DebugLogContentResponse | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  useEffect(() => {
    loadSettings();
    loadDebugStatus();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await settingsApi.getSettings();
      setSettings(data);
      setHost(data.effective_host);
      setModel(data.effective_model);
      setAvailableModels(data.available_models || []);
      setIngestionModel(data.ingestion_model);
      setRagModel(data.rag_model);
      setAudioModel(data.audio_model);
      setBackendHostState(data.backend_url);

      // Комбинираме локални + cloud модели в един списък
      const options: { name: string; source: 'local' | 'cloud' }[] = [];
      for (const m of data.available_models || []) {
        options.push({ name: m, source: 'local' });
      }
      for (const cm of data.cloud_models || []) {
        if (!options.some(o => o.name === cm)) {
          options.push({ name: cm, source: 'cloud' });
        }
      }
      setAllModelOptions(options);
    } catch (err) {
      setMessage({ type: 'error', text: 'Грешка при зареждане на настройките' });
    }
    setLoading(false);
  };

  const loadDebugStatus = async () => {
    try {
      const status = await debugApi.getStatus();
      setDebugEnabledState(status.debug_enabled);
      setDebugEnabled(status.debug_enabled);
    } catch {
      // silent
    }
  };

  const loadLogFiles = async () => {
    setLoadingLogs(true);
    try {
      const data = await debugApi.listLogs();
      setLogFiles(data.files);
      setShowLogs(true);
    } catch {
      setMessage({ type: 'error', text: 'Грешка при зареждане на логовете' });
    }
    setLoadingLogs(false);
  };

  const readLogFile = async (filepath: string) => {
    try {
      const data = await debugApi.readLog(filepath, 200);
      setSelectedLog(data);
    } catch {
      setMessage({ type: 'error', text: 'Грешка при четене на лог файл' });
    }
  };

  const toggleDebug = async () => {
    const newState = !debugEnabled;
    try {
      const result = await debugApi.toggle(newState);
      setDebugEnabledState(result.debug_enabled);
      setDebugEnabled(result.debug_enabled);
      setMessage({
        type: 'success',
        text: `🔍 Debug системата е ${result.debug_enabled ? 'ВКЛЮЧЕНА' : 'ИЗКЛЮЧЕНА'}`,
      });
    } catch {
      setMessage({ type: 'error', text: 'Грешка при промяна на debug състоянието' });
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setMessage(null);
    try {
      const data = await settingsApi.listModels(host);
      if (data.status === 'ok' && data.models) {
        setAvailableModels(data.models);
        const options: { name: string; source: 'local' | 'cloud' }[] = [];
        for (const m of data.models) {
          options.push({ name: m, source: 'local' });
        }
        for (const cm of settings?.cloud_models || []) {
          if (!options.some(o => o.name === cm)) {
            options.push({ name: cm, source: 'cloud' });
          }
        }
        setAllModelOptions(options);
        setMessage({ type: 'success', text: `✅ Свързването успешно! Намерени модели: ${data.models.join(', ')}` });
      } else {
        setMessage({ type: 'error', text: `❌ ${data.message || 'Грешка при свързване'}` });
      }
    } catch (err) {
      setMessage({ type: 'error', text: '❌ Неуспешна връзка с Ollama сървъра' });
    }
    setTesting(false);
  };

  const applyAll = async () => {
    setApplying(true);
    setMessage(null);
    let errors: string[] = [];

    try {
      const result = await llmApi.switchIngestion(ingestionModel);
      setMessage({ type: 'success', text: `✅ Ingestion: ${result.message}` });
    } catch (err: any) {
      errors.push(`Ingestion: ${err?.response?.data?.detail || 'грешка'}`);
    }

    try {
      const result = await llmApi.switchRag(ragModel);
      setMessage({ type: 'success', text: `✅ RAG: ${result.message}` });
    } catch (err: any) {
      errors.push(`RAG: ${err?.response?.data?.detail || 'грешка'}`);
    }


    if (errors.length > 0) {
      setMessage({ type: 'error', text: `❌ Грешки: ${errors.join('; ')}` });
    } else {
      setMessage({ type: 'success', text: '✅ Всички настройки са приложени!' });
      onSettingsChange();
    }
    setApplying(false);
  };

  const reloadModels = async () => {
    setMessage(null);
    try {
      const data = await llmApi.getModels();
      const options: { name: string; source: 'local' | 'cloud' }[] = [];
      for (const m of data.models.local) {
        options.push({ name: m.name, source: 'local' });
      }
      for (const cm of data.models.cloud) {
        if (!options.some(o => o.name === cm.name)) {
          options.push({ name: cm.name, source: 'cloud' });
        }
      }
      setAllModelOptions(options);
      setMessage({
        type: 'success',
        text: `✅ Заредени ${options.length} модела (${data.models.local.length} local + ${data.models.cloud.length} cloud)`,
      });
    } catch (err) {
      setMessage({ type: 'error', text: '❌ Грешка при зареждане на модели' });
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await settingsApi.updateSettings({
        ollama_host: host,
        ollama_model: model,
        ingestion_model: ingestionModel,
        rag_model: ragModel,
        audio_model: audioModel,
        save_to_env: saveToEnv,
      });
      setMessage({ type: 'success', text: '✅ Настройките са запазени!' });
      onSettingsChange();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Грешка при запазване';
      setMessage({ type: 'error', text: `❌ ${detail}` });
    }
    setSaving(false);
  };

  // ─── Data management handlers ───

  const handleExport = async () => {
    setExporting(true);
    setMessage(null);
    try {
      const blob = await dataApi.exportData();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
      a.download = `pi_sb_export_${timestamp}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      setMessage({ type: 'success', text: '✅ Данните са експортирани успешно!' });
    } catch (err) {
      setMessage({ type: 'error', text: '❌ Грешка при експорт на данните' });
    }
    setExporting(false);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    setMessage(null);
    try {
      const result = await dataApi.importData(file);
      setMessage({
        type: 'success',
        text: `✅ Импорт: ${result.imported} добавени, ${result.skipped} пропуснати.`,
      });
      onSettingsChange();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Грешка при импорт';
      setMessage({ type: 'error', text: `❌ ${detail}` });
    }
    setImporting(false);
    e.target.value = '';
  };

  const handleClear = async () => {
    if (!clearingConfirm) {
      setClearingConfirm(true);
      setMessage({ type: 'error', text: '⚠️ Потвърдете изтриването — натиснете отново "Изтрий всичко". Това действие е НЕОБРАТИМО!' });
      return;
    }

    setClearing(true);
    setMessage(null);
    try {
      const result = await dataApi.clearData();
      setMessage({
        type: 'success',
        text: `✅ Изтрити ${result.deleted} концепции. Wiki индексите са регенерирани.`,
      });
      onSettingsChange();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Грешка при изтриване';
      setMessage({ type: 'error', text: `❌ ${detail}` });
    }
    setClearing(false);
    setClearingConfirm(false);
  };

  if (loading) {
    return (
      <div className="settings-overlay">
        <div className="settings-panel">
          <div className="loading">Зареждане...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-overlay">
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>⚙️ Настройки</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="settings-body">
          {/* ─── Backend Connection Settings ─── */}
          <div className="settings-section">
            <h3>🔗 Backend сървър</h3>
            <label>
              <span>Backend URL</span>
              <div className="input-with-button">
                <input
                  type="text"
                  value={backendHost}
                  onChange={(e) => setBackendHostState(e.target.value)}
                  placeholder="http://192.168.1.100:8000"
                />
                <button
                  onClick={async () => {
                    try {
                      await settingsApi.updateSettings({ backend_url: backendHost, save_to_env: saveToEnv });
                      setBackendHost(backendHost);
                      setMessage({ type: 'success', text: '✅ Backend URL е запазен! Страницата ще се презареди...' });
                      setTimeout(() => window.location.reload(), 1500);
                    } catch {
                      setMessage({ type: 'error', text: '❌ Грешка при запис на Backend URL' });
                    }
                  }}
                >
                  💾 Задай
                </button>
              </div>
            </label>
            <p className="hint">
              Може да укажеш друг компютър в мрежата (напр. http://192.168.1.100:8000) или публичен адрес.
              Стойността се записва в localStorage на браузъра.
            </p>
            <button
              className="btn-secondary"
              onClick={async () => {
                const localUrl = settings?.backend_url || 'http://localhost:8000';
                setBackendHostState(localUrl);
                setBackendHost('');
                try {
                  await settingsApi.updateSettings({ backend_url: localUrl, save_to_env: saveToEnv });
                } catch { /* silent */ }
                setMessage({ type: 'success', text: `✅ Върнато към backend: ${localUrl}. Страницата ще се презареди...` });
                setTimeout(() => window.location.reload(), 1500);
              }}
              style={{ marginTop: '8px' }}
            >
              ↺ От .env ({settings?.backend_url || 'localhost:8000'})
            </button>
          </div>

          <div className="settings-divider" />

          {/* ─── Ollama Settings ─── */}
          <div className="settings-section">
            <h3>🤖 Ollama Сървър</h3>
            <label>
              <span>Host URL</span>
              <div className="input-with-button">
                <input
                  type="text"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  placeholder="http://192.168.1.100:11434"
                />
                <button onClick={testConnection} disabled={testing}>
                  {testing ? '⏳' : '🔍 Тест'}
                </button>
              </div>
            </label>
          </div>

          <div className="settings-divider" />

          {/* ─── Dual Model Settings ─── */}
          <div className="settings-section">
            <h3>🧠 Избор на модели</h3>

            <div className="model-switch-row">
              <div className="model-switch-info">
                <strong>✏️ Ingestion модел (за записване)</strong>
                <p className="hint">По-умен модел, който структурира бележките</p>
              </div>
              <div className="model-switch-controls">
                <select
                  value={ingestionModel}
                  onChange={(e) => setIngestionModel(e.target.value)}
                >
                  {allModelOptions.length > 0 ? (
                    <>
                      <optgroup label="── Локални ──">
                        {allModelOptions.filter(o => o.source === 'local').map((o) => (
                          <option key={o.name} value={o.name}>{o.name}</option>
                        ))}
                      </optgroup>
                      <optgroup label="── Cloud ──">
                        {allModelOptions.filter(o => o.source === 'cloud').map((o) => (
                          <option key={o.name} value={o.name}>☁️ {o.name}</option>
                        ))}
                      </optgroup>
                    </>
                  ) : (
                    <option value={ingestionModel}>{ingestionModel || 'Няма модели'}</option>
                  )}
                </select>
              </div>
            </div>

            <div className="model-switch-row">
              <div className="model-switch-info">
                <strong>💬 RAG модел (за отговаряне)</strong>
                <p className="hint">По-бърз модел за Q&A в чата</p>
              </div>
              <div className="model-switch-controls">
                <select
                  value={ragModel}
                  onChange={(e) => setRagModel(e.target.value)}
                >
                  {allModelOptions.length > 0 ? (
                    <>
                      <optgroup label="── Локални ──">
                        {allModelOptions.filter(o => o.source === 'local').map((o) => (
                          <option key={o.name} value={o.name}>{o.name}</option>
                        ))}
                      </optgroup>
                      <optgroup label="── Cloud ──">
                        {allModelOptions.filter(o => o.source === 'cloud').map((o) => (
                          <option key={o.name} value={o.name}>☁️ {o.name}</option>
                        ))}
                      </optgroup>
                    </>
                  ) : (
                    <option value={ragModel}>{ragModel || 'Няма модели'}</option>
                  )}
                </select>
              </div>
            </div>

            <button className="btn-secondary" onClick={reloadModels} style={{ marginTop: '8px' }}>
              🔄 Опресни списъка с модели
            </button>
            <p className="hint">
              Cloud моделите се конфигурират в .env файла (CLOUD_MODELS).
              Локалните идват от Ollama сървъра.
            </p>
          </div>

          {/* ─── Audio Settings ─── */}
          <div className="settings-divider" />

          <div className="settings-section">
            <h3>🎤 Аудио транскрипция (whisper.cpp)</h3>
            <p className="hint">
              Използва се локален whisper.cpp сървър с GGUF модел.
              Сървърът се стартира автоматично при пускане на backend-а.
            </p>
            <div className="model-switch-row">
              <div className="model-switch-info">
                <strong>GGUF модел</strong>
                <p className="hint">Име на GGUF файла в whisper.cpp_vulcan/ директорията</p>
              </div>
              <div className="model-switch-controls">
                <input
                  type="text"
                  value={audioModel}
                  onChange={(e) => setAudioModel(e.target.value)}
                  placeholder="ggml-medium.en-q5_0.bin"
                />
              </div>
            </div>
          </div>

          <div className="settings-section">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={saveToEnv}
                onChange={(e) => setSaveToEnv(e.target.checked)}
              />
              <span>Запомни настройките (запис в .env)</span>
            </label>
            <p className="hint">Ако е отметнато, настройките ще се запазят и след рестарт</p>
          </div>

          {/* ─── Data Management Section ─── */}
          <div className="settings-divider" />

          <div className="settings-section">
            <h3>💾 Управление на данните</h3>

            <div className="data-action-row">
              <button
                className="btn-secondary"
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? '⏳ Експортиране...' : '📤 Експорт (ZIP)'}
              </button>
              <p className="hint">Изтегли всички концепции като ZIP архив</p>
            </div>

            <div className="data-action-row">
              <label className="import-label">
                <span className={`btn-secondary ${importing ? 'disabled' : ''}`}>
                  {importing ? '⏳ Импортиране...' : '📥 Импорт (ZIP)'}
                </span>
                <input
                  type="file"
                  accept=".zip"
                  onChange={handleImport}
                  disabled={importing}
                  style={{ display: 'none' }}
                />
              </label>
              <p className="hint">Възстанови данни от предишен експорт</p>
            </div>

            <div className="data-action-row">
              <button
                className={`btn-danger ${clearingConfirm ? 'btn-danger-confirm' : ''}`}
                onClick={handleClear}
                disabled={clearing}
              >
                {clearing
                  ? '⏳ Изтриване...'
                  : clearingConfirm
                    ? '⚠️ ПОТВЪРДИ ИЗТРИВАНЕТО'
                    : '🗑️ Изтрий всички данни'}
              </button>
              <p className="hint danger-hint">
                {clearingConfirm
                  ? 'Натисни отново за потвърждение — всички концепции ще бъдат изтрити!'
                  : 'Премахва всички OKF концепции без възстановяване'}
              </p>
            </div>
          </div>

          {/* ─── Debug Section ─── */}
          <div className="settings-divider" />

          <div className="settings-section">
            <h3>🔍 Debug Система</h3>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={debugEnabled}
                onChange={toggleDebug}
              />
              <span>{debugEnabled ? 'Включена' : 'Изключена'}</span>
            </label>
            <p className="hint">
              Записва всички API заявки, LLM разговори и грешки в debug/ папката
            </p>
          </div>

          <div className="settings-section">
            <button
              className="btn-secondary"
              onClick={loadLogFiles}
              disabled={loadingLogs}
            >
              {loadingLogs ? '⏳ Зареждане...' : '📋 Преглед на логовете'}
            </button>

            {showLogs && logFiles.length > 0 && (
              <div className="log-list">
                {logFiles.map((file) => (
                  <div
                    key={file.path}
                    className="log-item"
                    onClick={() => readLogFile(file.path)}
                  >
                    <span className="log-name">{file.name}</span>
                    <span className="log-size">{(file.size / 1024).toFixed(1)} KB</span>
                  </div>
                ))}
              </div>
            )}

            {showLogs && logFiles.length === 0 && !loadingLogs && (
              <p className="hint">Няма лог файлове. Изпратете заявка към API-то за да се създадат.</p>
            )}
          </div>

          {/* ─── Log Viewer ─── */}
          {selectedLog && (
            <div className="settings-section">
              <div className="log-viewer-header">
                <h3>📄 {selectedLog.file}</h3>
                <button className="btn-secondary" onClick={() => setSelectedLog(null)}>✕</button>
              </div>
              <div className="log-viewer">
                {selectedLog.entries.length === 0 ? (
                  <p className="hint">Празен файл</p>
                ) : (
                  selectedLog.entries.map((entry, i) => (
                    <div key={i} className="log-entry">
                      <pre>{JSON.stringify(entry, null, 2)}</pre>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {message && (
            <div className={`settings-message ${message.type}`}>
              {message.text}
            </div>
          )}

          <div className="settings-actions">
            <button className="btn-secondary" onClick={onClose}>Затвори</button>
            <button onClick={applyAll} disabled={applying}>
              {applying ? '⏳ Прилагане...' : '✅ Приложи'}
            </button>
            <button onClick={saveSettings} disabled={saving}>
              {saving ? '⏳ Запазване...' : '💾 Запази'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;