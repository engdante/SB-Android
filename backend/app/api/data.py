"""
API endpoints за управление на OKF данните:
- Export: изтегляне на всички данни като ZIP
- Import: качване на ZIP за възстановяване
- Clear: изтриване на всички концепции
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
from datetime import datetime, timezone
import io
import zipfile
import json
import shutil

from loguru import logger

from app.config.settings import get_settings
from app.core.storage import OkfStorage
from app.core.processor import ConceptProcessor
from app.wiki.indexer import WikiIndexer

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/export")
async def export_data():
    """
    Експортира всички OKF данни като ZIP файл.
    Включва: всички .md файлове, wiki индексите, и meta информация.
    """
    data_dir = get_settings().okf_data_path
    if not data_dir.exists():
        raise HTTPException(status_code=404, detail="Хранилището е празно или не съществува")

    # Създаваме ZIP в паметта
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Обхождаме всички .md файлове в data/
        md_files = list(data_dir.rglob("*.md"))
        if not md_files:
            raise HTTPException(status_code=404, detail="Няма OKF файлове за експорт")

        for filepath in md_files:
            # Запазваме релативния път спрямо data_dir
            relative_path = filepath.relative_to(data_dir)
            zf.write(filepath, arcname=str(relative_path))

        # Добавяме meta информация
        s = get_settings()
        meta = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "app": s.app_name,
            "version": s.app_version,
            "total_files": len(md_files),
            "note": "Second Brain — OKF Data Export",
        }
        zf.writestr("_export_info.json", json.dumps(meta, indent=2, ensure_ascii=False))

    zip_buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pi_sb_export_{timestamp}.zip"

    logger.info(f"Експорт: {len(md_files)} файла -> {filename}")

    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(zip_buffer.getbuffer().nbytes),
        },
    )


@router.post("/import")
async def import_data(file: UploadFile = File(...)):
    """
    Импортира ZIP файл с OKF данни.
    - Запазва съществуващите файлове (не презаписва)
    - Добавя нови файлове
    - Обновява wiki индексите след импорт
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Моля, качете ZIP файл")

    data_dir = get_settings().okf_data_path
    content = await file.read()

    # Проверяваме дали ZIP-ът е валиден
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            # Валидираме структурата
            bad_files = zf.testzip()
            if bad_files:
                raise HTTPException(status_code=400, detail=f"Повреден ZIP файл: {bad_files}")

            # Филтрираме само .md файлове (и _export_info.json)
            md_files = [f for f in zf.namelist() if f.endswith(".md") or f == "_export_info.json"]
            if not md_files:
                raise HTTPException(status_code=400, detail="ZIP файлът не съдържа OKF .md файлове")

            imported_count = 0
            skipped_count = 0

            for zip_path in md_files:
                if zip_path == "_export_info.json":
                    continue

                target_path = data_dir / zip_path

                # Не презаписваме съществуващи файлове
                if target_path.exists():
                    skipped_count += 1
                    logger.debug(f"Пропускам (съществува): {zip_path}")
                    continue

                # Създаваме директориите ако трябва
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Извличаме файла
                with zf.open(zip_path) as source:
                    with open(target_path, "wb") as dest:
                        dest.write(source.read())

                imported_count += 1
                logger.info(f"Импортиран: {zip_path}")

            # Обновяваме wiki индексите
            storage = OkfStorage()
            indexer = WikiIndexer(storage=storage)
            indexer.regenerate_all()
            indexer.log_event(
                event_type="update",
                title="Импорт на данни",
                details=f"Импортирани: {imported_count}, Пропуснати: {skipped_count}, Файл: {file.filename}",
            )

            logger.info(f"Импорт завършен: {imported_count} импортирани, {skipped_count} пропуснати")

            return {
                "status": "ok",
                "imported": imported_count,
                "skipped": skipped_count,
                "total_in_zip": len(md_files) - 1,  # без _export_info.json
                "message": f"Импортирани {imported_count} файла, {skipped_count} пропуснати (вече съществуват).",
            }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Файлът не е валиден ZIP архив")


@router.delete("/clear")
async def clear_data(confirm: bool = False):
    """
    Изтрива ВСИЧКИ OKF концепции.
    - Задължително потвърждение с confirm=true
    - Wiki индексите се регенерират (празни)
    - LOG.md се запазва с history на изтриването
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Потвърдете изтриването с confirm=true. Това действие е необратимо!",
        )

    data_dir = get_settings().okf_data_path
    if not data_dir.exists():
        return {"status": "ok", "deleted": 0, "message": "Хранилището вече е празно."}

    # Броим колко концепции ще изтрием
    wiki_dir = data_dir / "wiki"
    md_files = [
        f for f in data_dir.rglob("*.md")
        if f.name != "index.md" and wiki_dir not in f.parents
    ]
    count = len(md_files)

    # Изтриваме всички OKF .md файлове (без wiki/ и без index.md)
    deleted = 0
    for filepath in md_files:
        try:
            filepath.unlink()
            deleted += 1
        except Exception as e:
            logger.error(f"Грешка при изтриване на {filepath}: {e}")

    # Изтриваме и празните поддиректории (YYYY/MM/)
    for dirpath in sorted(data_dir.rglob("*"), key=lambda p: str(p), reverse=True):
        if dirpath.is_dir() and dirpath != data_dir and dirpath != wiki_dir:
            try:
                # Проверяваме дали е празна
                if not any(dirpath.iterdir()):
                    dirpath.rmdir()
                    logger.debug(f"Изтрита празна директория: {dirpath}")
            except Exception:
                pass

    # Обновяваме wiki индексите (вече празни)
    storage = OkfStorage()
    indexer = WikiIndexer(storage=storage)
    indexer.regenerate_all()
    indexer.log_event(
        event_type="delete",
        title="Изтриване на всички данни",
        details=f"Изтрити концепции: {deleted}",
    )

    logger.warning(f"Всички данни са изтрити! {deleted} концепции")

    return {
        "status": "ok",
        "deleted": deleted,
        "message": f"Изтрити {deleted} концепции. Wiki индексите са регенерирани (празни).",
    }