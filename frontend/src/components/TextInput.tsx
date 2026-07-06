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

  return (
    <div className="text-input">
      <h3>📝 Добави текст</h3>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Какво мислиш? Напиши своята идея, бележка, задача..."
        rows={4}
        disabled={loading}
      />
      <div className="input-actions">
        <button onClick={handleSubmit} disabled={loading || !text.trim()}>
          {loading ? '⏳ Обработва се...' : '🚀 Изпрати'}
        </button>
      </div>
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default TextInput;