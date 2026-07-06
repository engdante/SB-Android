"""
API endpoints за въвеждане на информация (текст и аудио).
"""

from fastapi import APIRouter, UploadFile, File, Form, Request
from pydantic import BaseModel

from app.core.processor import ConceptProcessor
from app.audio.transcriber import AudioTranscriber
from app.audio.postprocessor import full_postprocess, regex_postprocess
from app.config.okf_schema import OkfDocument
from app.llm.ollama_client import OllamaClient
from loguru import logger

router = APIRouter(prefix="/api/input", tags=["input"])
processor = ConceptProcessor()


class TextInput(BaseModel):
    text: str


@router.post("/text")
async def input_text(data: TextInput):
    """
    Приема текст и го обработва през LLM pipeline-а.
    """
    try:
        document = await processor.process_text(data.text)
        return {
            "status": "ok",
            "concept": document.metadata.model_dump(mode="json"),
            "body_preview": document.body[:200] + "..."
        }
    except Exception as e:
        logger.error(f"Грешка при обработка на текст: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/audio")
async def input_audio(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("bg"),
):
    """
    Приема аудио файл, транскрибира го с Whisper и го обработва през LLM pipeline-а.

    Args:
        file: Аудио файлът (webm, mp3, wav, etc.)
        language: Език за транскрипция ("bg" или "en", дефолт: "bg")
    """
    from app.config.settings import get_settings
    audio_path = get_settings().audio_upload_path / file.filename

    # Запазваме файла
    with open(audio_path, "wb") as f:
        content = await file.read()
        f.write(content)

        logger.info(f"Аудио файлът е записан: {audio_path} ({len(content)} bytes)")

    # Транскрибираме с Whisper
    try:
        transcriber: AudioTranscriber = request.app.state.transcriber
        transcription = await transcriber.transcribe(audio_path, language=language)
        transcribed_text = transcription["text"]
        detected_language = transcription["language"]
        duration = transcription["duration"]

        logger.info(f"Транскрибирано: {detected_language}, {len(transcribed_text)} символа, {duration:.1f}s")
        logger.info(f"=== ПЪЛЕН ТРАНСКРИБИРАН ТЕКСТ (преди LLM) ===")
        logger.info(transcribed_text)
        logger.info(f"=== КРАЙ НА ТРАНСКРИБИРАНИЯ ТЕКСТ ===")
        logger.info(f"Детектиран език от engine-а: {detected_language}")
        logger.info(f"Заявен език: {language}")
        logger.info(f"Engine: {type(transcriber._get_engine()).__name__}")

        if not transcribed_text.strip():
            return {
                "status": "error",
                "filename": file.filename,
                "size": len(content),
                "message": "Транскрипцията не разпозна реч в аудио файла."
            }

        # LLM пост-процесинг за подобряване на транскрипцията
        try:
            # Използваме вече създадения ingestion client от processor-а,
            # за да избегнем 401 Unauthorized (той вече има валиден api_key)
            llm_client = processor.llm_manager.ingestion_client
            improved_text = await full_postprocess(
                transcribed_text,
                llm_client=llm_client,
                use_llm=True
            )
            if improved_text and improved_text != transcribed_text:
                logger.info(f"LLM пост-процесинг: текстът е подобрен")
                logger.info(f"=== ПОДОБРЕН ТЕКСТ ===")
                logger.info(improved_text)
                logger.info(f"=== КРАЙ НА ПОДОБРЕНИЯ ТЕКСТ ===")
                transcribed_text = improved_text
        except Exception as e:
            logger.warning(f"LLM пост-процесинг не е наличен: {e}, продължавам с raw текста")

        # Обработваме транскрибирания текст през LLM pipeline-а
        document = await processor.process_text(transcribed_text)

        return {
            "status": "ok",
            "filename": file.filename,
            "size": len(content),
            "duration_seconds": duration,
            "language": detected_language,
            "transcription_preview": transcribed_text[:300] + ("..." if len(transcribed_text) > 300 else ""),
            "concept": document.metadata.model_dump(mode="json"),
            "body_preview": document.body[:200] + "..."
        }
    except Exception as e:
        logger.error(f"Грешка при аудио обработка: {e}")
        return {
            "status": "error",
            "filename": file.filename,
            "size": len(content),
            "message": f"Грешка при транскрипция/обработка: {str(e)}"
        }
