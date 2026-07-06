"""
Audio transcription module (whisper.cpp engine only).
Transcribes audio files to text via a local whisper.cpp HTTP server.
The server is started/stopped automatically by the backend (lifespan management).
Supports Bulgarian and English.
"""

from pathlib import Path
from typing import Optional
from loguru import logger

from app.config.settings import get_settings, get_app_base_dir


class WhisperCppEngine:
    """
    Local whisper.cpp HTTP server engine.
    Manages whisper-server as a subprocess and communicates via REST API.
    The server starts on FastAPI startup and stops on shutdown.
    
    Supports:
    - Windows: whisper-server.exe
    - Android/Linux: whisper-server (compiled binary)
    """

    def __init__(self):
        import sys
        s = get_settings()
        self.host = "127.0.0.1"
        self.port = 8080
        self.server_url = f"http://{self.host}:{self.port}"
        self.model_name = s.audio_model
        self._process = None
        self._is_android = sys.platform == "linux" and hasattr(sys, 'getandroidapilevel') or \
                          "com.termux" in str(getattr(sys, 'executable', ''))

        # Path to whisper.cpp directory — beside the EXE or in project root
        self.whisper_dir = get_app_base_dir() / "whisper.cpp"
        
        # Determine the server executable based on platform
        if self._is_android or sys.platform != "win32":
            self.server_exe = self.whisper_dir / "build" / "bin" / "whisper-server"
            # Fallback: try in whisper.cpp root
            if not self.server_exe.exists():
                self.server_exe = self.whisper_dir / "whisper-server"
        else:
            self.server_exe = self.whisper_dir / "whisper-server.exe"
        
        self.vad_model = self.whisper_dir / "ggml-silero-v6.2.0.bin"

        # Determine the model
        self.model_file = self.whisper_dir / "models" / self.model_name
        if not self.model_file.exists():
            # Fallback to large-v3-q5_0 if model doesn't exist
            fallback = self.whisper_dir / "models" / "ggml-large-v3-q5_0.bin"
            if not fallback.exists():
                # Try in whisper.cpp root (Windows layout)
                fallback = self.whisper_dir / "ggml-large-v3-q5_0.bin"
            if fallback.exists():
                self.model_file = fallback
                logger.warning(f"WhisperCppEngine: model {self.model_name} not found, using {fallback.name}")
            else:
                raise FileNotFoundError(
                    f"Whisper model not found: searched {self.model_file} and {fallback}"
                )

    async def start_server(self):
        """Starts whisper-server.exe as a subprocess."""
        import asyncio
        import subprocess
        import threading

        if self._process is not None:
            logger.info("WhisperCppEngine: server already running")
            return

        # Check if exe exists
        if not self.server_exe.exists():
            raise FileNotFoundError(
                f"whisper-server.exe not found at {self.server_exe}"
            )

        if not self.model_file.exists():
            raise FileNotFoundError(
                f"Whisper model not found: {self.model_file}"
            )

        cmd = [
            str(self.server_exe),
            "--model", str(self.model_file),
            "--host", self.host,
            "--port", str(self.port),
            "--vad",
            "--vad-model", str(self.vad_model),
            "--vad-threshold", "0.5",
            "--vad-min-speech-duration-ms", "250",
            "--vad-min-silence-duration-ms", "200",
            "--vad-speech-pad-ms", "50",
            "-t", "4",
            "-l", "bg",
            "-bo", "2",
            "-et", "2.40",
            "-lpt", "-1.00",
            "-nth", "0.60",
            "-sns",
            "-nf",
            "-ml", "100",
            # WITHOUT -pp (print progress) — it blocks stdout buffer during programmatic startup
        ]

        logger.info(f"WhisperCppEngine: starting {self.server_exe.name} on {self.host}:{self.port}")
        logger.info(f"WhisperCppEngine: model={self.model_file.name}")

        # Use subprocess.Popen with DEVNULL for stdout and stderr.
        # On Windows PIPE can cause deadlock if buffer fills up.
        # If there's an error, we'll see it as timeout in _wait_for_server.
        import sys
        def _start():
            kwargs = {
                "cwd": str(self.whisper_dir),
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            # Windows-specific: скрива конзолния прозорец
            if sys.platform == "win32":
                import subprocess as sp
                kwargs["creationflags"] = sp.CREATE_NO_WINDOW
            return subprocess.Popen(cmd, **kwargs)

        loop = asyncio.get_event_loop()
        self._process = await loop.run_in_executor(None, _start)

        # Wait for server to be ready
        await self._wait_for_server(timeout=30)
        logger.info("WhisperCppEngine: server is ready")

    async def stop_server(self):
        """Stops the whisper-server.exe process."""
        import asyncio

        if self._process is None:
            return

        logger.info("WhisperCppEngine: stopping server...")
        self._process.terminate()
        try:
            # subprocess.Popen.wait() is synchronous — must use run_in_executor
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, self._process.wait),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("WhisperCppEngine: process did not stop, killing...")
            self._process.kill()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._process.wait)

        self._process = None
        logger.info("WhisperCppEngine: server stopped")

    @property
    def is_running(self) -> bool:
        """Checks if the server is running."""
        if self._process is None:
            return False
        return self._process.returncode is None

    async def _wait_for_server(self, timeout: int = 30):
        """Waits for the whisper.cpp server to start responding."""
        import asyncio
        import httpx

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{self.server_url}/health")
                    if response.status_code == 200:
                        return
            except (httpx.RequestError, httpx.ConnectError):
                pass
            await asyncio.sleep(0.5)

        raise TimeoutError(
            f"WhisperCppEngine: server did not respond within {timeout} seconds"
        )

    def _start_stderr_reader(self):
        """Reads stderr from whisper-server.exe via threading (Popen stderr is synchronous)."""
        import asyncio
        import threading

        def _reader():
            try:
                while self._process is not None and self._process.returncode is None:
                    line = self._process.stderr.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        logger.debug(f"[whisper.cpp stderr] {text}")
            except Exception as e:
                logger.warning(f"WhisperCppEngine: error reading stderr: {e}")

            # After the process has ended, log remaining stderr
            if self._process is not None and self._process.returncode is not None:
                try:
                    remaining = self._process.stderr.read()
                    if remaining:
                        text = remaining.decode("utf-8", errors="replace").strip()
                        if text:
                            logger.warning(f"[whisper.cpp exited code={self._process.returncode}] {text}")
                except Exception:
                    pass

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()

    async def transcribe(self, audio_path: Path, language: Optional[str] = None) -> dict:
        """Sends an audio file to the local whisper.cpp HTTP server."""
        import httpx
        import time
        import subprocess
        import os
        import tempfile

        if not self.is_running:
            raise RuntimeError("WhisperCppEngine: server is not running. Call start_server() first.")

        logger.info(f"WhisperCppEngine: transcribing {audio_path} (lang={language or 'auto'})")

        start_time = time.time()

        # Convert WebM/Opus to WAV (PCM int16, 16kHz mono)
        # whisper.cpp requires WAV format, cannot decode WebM directly
        ffmpeg_path = get_app_base_dir() / "ffmpeg.exe"
        if not ffmpeg_path.exists():
            ffmpeg_path = "ffmpeg"  # fallback to PATH

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name

        try:
            logger.info(f"WhisperCppEngine: converting {audio_path} -> {tmp_wav_path}")
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

            # Read the converted WAV file
            with open(tmp_wav_path, "rb") as f:
                audio_bytes = f.read()

            logger.info(f"WhisperCppEngine: converted to {len(audio_bytes)} bytes WAV")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            logger.error(f"WhisperCppEngine: ffmpeg error: {stderr}")
            raise RuntimeError(f"ffmpeg conversion failed: {stderr}")
        except Exception as e:
            logger.error(f"WhisperCppEngine: conversion error: {e}")
            raise
        finally:
            if os.path.exists(tmp_wav_path):
                os.unlink(tmp_wav_path)

        # Send WAV to the local whisper.cpp server
        async with httpx.AsyncClient(timeout=300.0) as client:
            files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
            data = {
                "temperature": "0.0",
                "temperature_inc": "0.2",
                "max_len": "100",
                "best_of": "2",
                "no_speech_thold": "0.6",
                "suppress_nst": "true",
                "entropy_thold": "2.40",
                "logprob_thold": "-1.00",
            }
            if language:
                data["language"] = language

            response = await client.post(f"{self.server_url}/inference", files=files, data=data)
            response.raise_for_status()
            result = response.json()

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"WhisperCppEngine: transcription completed in {duration_ms:.0f}ms")

        # whisper.cpp server returns {text, segments, ...}
        full_text = result.get("text", "")
        segments_raw = result.get("segments", [])

        # Normalize segments
        segment_list = []
        for seg in segments_raw:
            segment_list.append({
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", "").strip(),
                "avg_logprob": seg.get("avg_logprob", 0),
                "no_speech_prob": seg.get("no_speech_prob", 0)
            })

        return {
            "text": full_text,
            "language": result.get("language", language or "unknown"),
            "segments": segment_list,
            "duration": result.get("duration", 0.0)
        }


class AudioTranscriber:
    """
    Audio transcriber — uses whisper.cpp engine.
    The server is started/stopped via start_server()/stop_server().
    """

    def __init__(self):
        self._engine: Optional[WhisperCppEngine] = None

    def _get_engine(self) -> WhisperCppEngine:
        """Returns (or creates) a WhisperCppEngine instance."""
        if self._engine is None:
            self._engine = WhisperCppEngine()
        return self._engine

    async def start_server(self):
        """Starts the whisper.cpp server."""
        engine = self._get_engine()
        await engine.start_server()

    async def stop_server(self):
        """Stops the whisper.cpp server."""
        if self._engine is not None:
            await self._engine.stop_server()

    @property
    def is_running(self) -> bool:
        """Checks if the server is running."""
        if self._engine is None:
            return False
        return self._engine.is_running

    async def transcribe(self, audio_path: Path, language: Optional[str] = None,
                         postprocess: bool = True) -> dict:
        """
        Transcribes an audio file using the whisper.cpp engine.

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

        if not engine.is_running:
            raise RuntimeError(
                "whisper.cpp server is not running. "
                "Restart the backend or check if whisper.cpp is configured correctly."
            )

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
        temp_path = get_settings().audio_upload_path / f"_temp_{filename}"
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        try:
            result = await self.transcribe(temp_path, language)
            return result
        finally:
            if temp_path.exists():
                temp_path.unlink()