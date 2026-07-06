import React, { useState, useRef, useEffect } from 'react';
import { inputApi, TextInputResponse } from '../api/client';

interface AudioRecorderProps {
  onSuccess?: (result: TextInputResponse) => void;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({ onSuccess }) => {
  const [recording, setRecording] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [language, setLanguage] = useState<string>('bg');
  const audioRef = useRef<HTMLAudioElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const file = new File([blob], `recording_${Date.now()}.webm`, { type: 'audio/webm' });
        setAudioFile(file);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start();
      setRecording(true);
      setError(null);
    } catch (err) {
      setError('Няма достъп до микрофон');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAudioFile(file);
      setError(null);
    }
  };

  // Създаваме object URL за плейбек всеки път когато audioFile се промени
  useEffect(() => {
    if (audioFile) {
      const url = URL.createObjectURL(audioFile);
      setAudioUrl(url);
      // Освобождаваме предишния URL при cleanup
      return () => URL.revokeObjectURL(url);
    } else {
      setAudioUrl(null);
    }
  }, [audioFile]);

  const playAudio = () => {
    if (audioRef.current && audioUrl) {
      audioRef.current.play();
    }
  };

  const uploadAudio = async () => {
    if (!audioFile) return;
    setUploading(true);
    setError(null);

    try {
      const result = await inputApi.uploadAudio(audioFile, language);
      setAudioFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      onSuccess?.(result as any);
    } catch (err: any) {
      setError(err.message || 'Грешка при качване');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="audio-recorder">
      <h3>🎤 Гласов вход</h3>
      <div className="audio-actions">
        <button onClick={recording ? stopRecording : startRecording}
                className={recording ? 'recording' : ''}>
          {recording ? '⏹ Спри запис' : '🎙 Започни запис'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          onChange={handleFileSelect}
          hidden
        />
        <button onClick={() => fileInputRef.current?.click()}>
          📁 Избери файл
        </button>
        <button
          className="lang-toggle"
          onClick={() => setLanguage(language === 'bg' ? 'en' : 'bg')}
        >
          {language === 'bg' ? '🇧🇬 BG' : '🇬🇧 US'}
        </button>
      </div>
      {audioFile && audioUrl && (
        <div className="audio-preview">
          <div className="audio-info">
            <span>📄 {audioFile.name} ({(audioFile.size / 1024).toFixed(1)} KB)</span>
            <button className="play-btn" onClick={playAudio} title="Чуй записа">
              ▶️ Чуй
            </button>
          </div>
          <audio ref={audioRef} src={audioUrl} controls className="audio-player" />
          <button onClick={uploadAudio} disabled={uploading} className="upload-btn">
            {uploading ? '⏳ Качване...' : '📤 Изпрати за обработка'}
          </button>
        </div>
      )}
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default AudioRecorder;