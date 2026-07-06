import React, { useState, useEffect } from 'react';
import TextInput from './components/TextInput';
import AudioRecorder from './components/AudioRecorder';
import ConceptList from './components/ConceptList';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
import { healthApi, HealthResponse } from './api/client';
import { initGlobalErrorHandler, checkDebugStatus, logAction } from './api/debug';

type Tab = 'input' | 'concepts' | 'chat';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('input');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    // Инициализираме debug системата
    initGlobalErrorHandler();
    checkDebugStatus();

    // Еднократна проверка при стартиране
    const checkHealth = async () => {
      try {
        const result = await healthApi.check();
        setHealth(result);
      } catch {
        setHealth(null);
      }
    };
    checkHealth();
    // НИКАКЪВ polling — само ръчно или при събития
  }, []);

  const handleManualCheck = async () => {
    setChecking(true);
    try {
      const result = await healthApi.check();
      setHealth(result);
    } catch {
      setHealth(null);
    } finally {
      setChecking(false);
    }
  };

  const handleSettingsChange = () => {
    // Refresh health after settings change
    healthApi.check().then(setHealth).catch(() => setHealth(null));
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🧠 pi_sb</h1>
        <span className="subtitle">Second Brain</span>
        <div className="status">
          <span className={`dot ${health?.status === 'healthy' ? 'green' : health ? 'yellow' : 'red'}`} />
          <span>
            {health?.status === 'healthy'
              ? `LLM онлайн (${health.total_concepts} концепции)`
              : health
                ? 'LLM недостъпен'
                : 'Сървърът не отговаря'}
          </span>
          <button
            className="check-btn"
            onClick={handleManualCheck}
            disabled={checking}
            title="Провери връзката"
          >
            {checking ? '⏳' : '🔍'}
          </button>
          <button className="settings-btn" onClick={() => setShowSettings(true)} title="Настройки">
            ⚙️
          </button>
        </div>
      </header>

      {showSettings && (
        <Settings
          onClose={() => setShowSettings(false)}
          onSettingsChange={handleSettingsChange}
        />
      )}

      <nav className="tabs">
        <button className={activeTab === 'input' ? 'active' : ''} onClick={() => setActiveTab('input')}>
          📝 Вход
        </button>
        <button className={activeTab === 'concepts' ? 'active' : ''} onClick={() => setActiveTab('concepts')}>
          📚 Концепции
        </button>
        <button className={activeTab === 'chat' ? 'active' : ''} onClick={() => setActiveTab('chat')}>
          💬 Чат
        </button>
      </nav>

      <main className="app-main">
        {lastResult && (
          <div className="notification" onClick={() => setLastResult(null)}>
            ✅ Концепцията е записана: {lastResult}
          </div>
        )}

        {activeTab === 'input' && (
          <div className="input-section">
            <TextInput onSuccess={(r) => {
              logAction('text_input', { title: r.concept.title });
              setLastResult(r.concept.title);
            }} />
            <div className="divider">или</div>
            <AudioRecorder onSuccess={(r) => {
              const filename = (r as any)?.filename || 'аудио файл';
              logAction('audio_input', { filename });
              setLastResult(`📁 Аудио файлът е получен: ${filename} (транскрипцията предстои)`);
            }} />
          </div>
        )}

        {activeTab === 'concepts' && <ConceptList />}
        {activeTab === 'chat' && <ChatInterface />}
      </main>

      <footer className="app-footer">
        <small>pi_sb v1.0 — 100% локално и поверително</small>
      </footer>
    </div>
  );
};

export default App;