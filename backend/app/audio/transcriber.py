"""
Audio transcription module (whisper.cpp CLI engine).
Transcribes audio files to text using whisper-cli as a subprocess.
The model is loaded on-demand and released after transcription completes.
Supports auto-download of models from HuggingFace.
Supports Bulgarian and English.
"""

from pathlib import Path
from typing import Optional
from loguru import logger


class WhisperCliEngine:
    """
    Local whisper.cpp CLI engine.
    Runs whisper-cli as a subprocess for each transcription.
    The model is loaded into RAM only during transcription, then released.
    
    Supports:
    - Windows: whisper-cli.exe
    - Android/Linux: whisper-cli (compiled binary)
    - Auto-download of models from HuggingFace ggerganov/whisper.cpp
    """

    def __init__(self):
        import sys
        from app.config.settings import get_settings, get_app_base_dir

        s = get_settings()
        self.model_name = s.audio_model
        self._is_android = sys.platform == "linux" and hasattr(sys, 'getandroidapilevel') or \
                          "com.termux" in str(getattr(sys, 'executable', ''))

        # Path to whisper.cpp directory — beside the EXE or in project root
        self.whisper_dir = get_app_base_dir() / "whisper.cpp"
        
        # Determine the CLI executable based on platform
        if self._is_android or sys.platform != "win32":
            # Try multiple possible locations for whisper-cli
            self.cli_exe = self.whisper_dir / "build" / "bin" / "whisper-cli"
            if not self.cli_exe.exists():
                self.cli_exe = self.whisper_dir / "whisper-cli"
            if not self.cli_exe.exists():
                # Fallback: try the 'main' binary (older whisper.cpp builds)
                self.cli_exe = self.whisper_dir / "build" / "bin" / "main"
            if not self.cli_exe.exists():
                self.cli_exe = self.whisper_dir / "main"
        else:
            self.cli_exe = self.whisper_dir / "whisper-cli.exe"
            if not self.cli_exe.exists():
                self.cli_exe = self.whisper_dir / "main.exe"

        # Determine the model path
        self.model_file = self.whisper_dir / "models" / self.model_name
        if not self.model_file.exists():
            # Fallback: try in whisper.cpp root (Windows layout)
            fallback = self.whisper_dir / self.model_name
            if fallback.exists():
                self.model_file = fallback
                logger.warning(f"WhisperCliEngine: model found in root dir: {fallback}")
            else:
                # Model doesn't exist — will be auto-downloaded
                logger.info(f"WhisperCliEngine: model {self.model_name} not found locally, will download on first use")

    def _ensure_model(self) -> Path:
        """
        Ensures the whisper model exists locally.
        If not found, auto-downloads from HuggingFace ggerganov/whisper.cpp.
        
        Returns:
            Path to the model file
        """
        if self.model_file.exists():
            return self.model_file

        # Model not found — auto-download
        import httpx
        import asyncio

        model_url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{self.model_name}"
        models_dir = self.whisper_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        temp_path = models_dir / f"{self.model_name}.download"
        final_path = models_dir / self.model_name

        logger.info(f"⬇️ Downloading whisper model: {self.model_name}")
        logger.info(f"   From: {model_url}")
        logger.info(f"   To: {final_path}")

        try:
            # Use synchronous httpx for simplicity in __init__
            with httpx.Client(timeout=300.0, follow_redirects=True) as client:
                with client.stream("GET", model_url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                percent = (downloaded / total) * 100
                                if downloaded % (1024 * 1024) < 8192:  # Log every ~1MB
                                    logger.debug(f"   Download progress: {percent:.1f}% ({downloaded / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB)")

            # Move temp file to final location
            temp_path.rename(final_path)
            size_mb = final_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Whisper model downloaded: {self.model_name} ({size_mb:.1f}MB)")
            
            self.model_file = final_path
            return final_path

        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"❌ Failed to download whisper model: {e}")
            raise FileNotFoundError(
                f"Whisper model '{self.model_name}' not found locally and download failed. "
                f"Please download manually from: {model_url}"
            )

    async def transcribe(self, audio_path: Path, language: Optional[str] = None) -> dict:
        """
        Transcribes an audio file using whisper-cli as a subprocess.
        The model is loaded into RAM, transcription runs, then memory is released.
        
        Args:
            audio_path: Path to the audio file
            language: Optional language code ("bg", "en", or None for auto)
            
        Returns:
            dict with keys: text, language, segments, duration
        """
        import subprocess
        import time
        import os
        import tempfile
        import json

        # Ensure model exists (auto-download if needed)
        model_path = self._ensure_model()

        logger.info(f"WhisperCliEngine: transcribing {audio_path} (lang={language or 'auto'})")
        logger.info(f"WhisperCliEngine: model={model_path.name}, cli={self.cli_exe.name}")

        start_time = time.time()

        # Convert WebM/Opus to WAV (PCM int16, 16kHz mono)
        # whisper.cpp requires WAV format, cannot decode WebM directly
        from app.config.settings import get_app_base_dir
        ffmpeg_path = get_app_base_dir() / "ffmpeg.exe"
        if not ffmpeg_path.exists():
            ffmpeg_path = "ffmpeg"  # fallback to PATH

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name

        try:
            logger.info(f"WhisperCliEngine: converting {audio_path} -> {tmp_wav_path}")
            subprocess.run(
                [
                    str(ffmpeg_path), "-y",
                    "-i", str(audio_path),
                    "-ar", "16000",
                    "-ac", "1",
                    "-sample_fmt", "s16",
                    "-f", "wav",
                    tmp_wav_path
                ],
                check=True,
                capture_output=True,
                timeout=120
            )

            # Build whisper-cli command
            cmd = [
                str(self.cli_exe),
                "-m", str(model_path),
                "-f", tmp_wav_path,
                "-l", language or "bg",
                "-otxt",           # output as text to stdout
                "--no-prints",     # suppress progress output
            ]

            logger.info(f"WhisperCliEngine: running: {' '.join(str(c) for c in cmd)}")
            
            # Run whisper-cli as subprocess
            # The model loads, transcribes, then exits — releasing all RAM
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=300,  # 5 min timeout for long audio
                cwd=str(self.whisper_dir)
            )

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
                logger.error(f"WhisperCliEngine: process exited with code {result.returncode}: {stderr}")
                raise RuntimeError(f"whisper-cli failed (exit code {result.returncode}): {stderr[:500]}")

            # Read transcription from stdout
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            
            # If stdout is empty, try reading the output .txt file
            if not stdout:
                txt_output = tmp_wav_path.replace(".wav", ".txt")
                if os.path.exists(txt_output):
                    with open(txt_output, "r", encoding="utf-8") as f:
                        stdout = f.read().strip()
                    os.unlink(txt_output)

            full_text = stdout
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"WhisperCliEngine: transcription completed in {duration_ms:.0f}ms ({len(full_text)} chars)")

            # whisper-cli doesn't return segments in text mode,
            # so we return a simple result
            return {
                "text": full_text,
                "language": language or "bg",
                "segments": [],
                "duration": 0.0
            }

        except subprocess.TimeoutExpired:
            logger.error(f"WhisperCliEngine: transcription timed out after 300s")
            raise RuntimeError("whisper-cli timed out")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            logger.error(f"WhisperCliEngine: ffmpeg error: {stderr}")
            raise RuntimeError(f"ffmpeg conversion failed: {stderr[:500]}")
        except Exception as e:
            logger.error(f"WhisperCliEngine: transcription error: {e}")
            raise
        finally:
            if os.path.exists(tmp_wav_path):
                os.unlink(tmp_wav_path)


class AudioTranscriber:
    """
    Audio transcriber — uses whisper.cpp CLI engine.
    The model is loaded on-demand for each transcription and released afterwards.
    No persistent server — saves ~3GB RAM on mobile devices.
    """

    def __init__(self):
        self._engine: Optional[WhisperCliEngine] = None

    def _get_engine(self) -> WhisperCliEngine:
        """Returns (or creates) a WhisperCliEngine instance."""
        if self._engine is None:
            self._engine = WhisperCliEngine()
        return self._engine

    @property
    def is_running(self) -> bool:
        """
        Always returns True — the CLI engine doesn't need a running server.
        The model is loaded on-demand.
        """
        return True

    async def transcribe(self, audio_path: Path, language: Optional[str] = None,
                         postprocess: bool = True) -> dict:
        """
        Transcribes an audio file using the whisper.cpp CLI engine.
        Model is loaded, transcription runs, then memory is released.

        Args:
            audio_path: Path to the audio file
            language: Optional — force language ("bg", "en" or None for auto)
            postprocess: Whether to apply post-processing (regex word merging)

        Returns:
            dict with keys: text, language, segments, duration
        """
        from app.audio.postprocessor import regex_postprocess

        engine = self._get_engine()
        logger.info(f"AudioTranscriber: transcribing {audio_path}")

        result = await engine.transcribe(audio_path, language)

        # Post-process the text (merge split words, punctuation)
        if postprocess and result.get("text"):
            raw_text = result["text"]
            processed_text = regex_postprocess(raw_text)
            if processed_text != raw_text:
                logger.info(f"AudioTranscriber: post-processing — text improved "
                            f"({len(raw_text)} -> {len(processed_text)} chars)")
                result["text"] = processed_text
                # Also update segment texts
                if "segments" in result:
                    for seg in result["segments"]:
                        seg["text"] = regex_postprocess(seg.get("text", ""))

        return result

    async def transcribe_file(self, audio_bytes: bytes, filename: str,
                              language: Optional[str] = None) -> dict:
        """
        Transcribes audio from bytes.

        Args:
            audio_bytes: Audio file content
            filename: File name (for format detection)
            language: Optional language

        Returns:
            dict with transcription
        """
        from app.config.settings import get_settings
        temp_path = get_settings().audio_upload_path / f"_temp_{filename}"
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        try:
            result = await self.transcribe(temp_path, language)
            return result
        finally:
            if temp_path.exists():
                temp_path.unlink()