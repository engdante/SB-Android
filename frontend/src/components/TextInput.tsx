import React, { useState } from 'react';
import { inputApi, TextInputResponse } from '../api/client';

interface TextInputProps {
  onSuccess?: (result: TextInputResponse) => void;
}

const TextInput: React.FC<TextInputProps> = ({ onSuccess }) => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!text.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await inputApi.submitText(text);
      if (result.status === 'ok') {
        setText('');
        onSuccess?.(result);
      } else {
        setError('Грешка при обработката');
      }
    } catch (err: any) {
      setError(err.message || 'Грешка при комуникация със сървъра');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="text-input">
      <h3>📝 Добави текст</h3>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Какво мислиш? Напиши своята идея, бележка, задача..."
        rows={4}
        disabled={loading}
      />
      <div className="input-actions">
        <button onClick={handleSubmit} disabled={loading || !text.trim()}>
          {loading ? '⏳ Обработва се...' : '🚀 Изпрати'}
        </button>
        <span className="hint">Enter за изпращане, Shift+Enter за нов ред</span>
      </div>
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default TextInput;