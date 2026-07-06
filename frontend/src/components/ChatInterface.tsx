import React, { useState } from 'react';
import { searchApi, AskResponse } from '../api/client';

const ChatInterface: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; sources?: AskResponse['sources'] }>>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    if (!question.trim() || loading) return;

    const userQuestion = question;
    setQuestion('');
    setMessages((prev) => [...prev, { role: 'user', content: userQuestion }]);
    setLoading(true);

    try {
      const result = await searchApi.askQuestion(userQuestion);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.answer,
          sources: result.sources,
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `❌ Грешка: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div className="chat-interface">
      <h3>💬 Задай въпрос (RAG)</h3>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            Попитай нещо за своите бележки!<br />
            <small>Напр. "Какво записах за ОВК проекта?" или "Дай ми резюме на всички задачи"</small>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="message-bubble">
              <div className="message-text">{msg.content}</div>
              {msg.sources && msg.sources.length > 0 && (
                <div className="message-sources">
                  <small>📎 Източници: {msg.sources.map((s) => s.title).join(', ')}</small>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant">
            <div className="message-bubble loading-bubble">🤔 Мисля...</div>
          </div>
        )}
      </div>
      <div className="chat-input">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Задай въпрос..."
          rows={2}
          disabled={loading}
        />
        <button onClick={handleAsk} disabled={loading || !question.trim()}>
          {loading ? '⏳' : '➡️'}
        </button>
      </div>
    </div>
  );
};

export default ChatInterface;