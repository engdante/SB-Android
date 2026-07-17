"""
API endpoints за търсене и извличане на информация (Wiki + RAG).
"""

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from app.core.storage import OkfStorage
from app.core.processor import ConceptProcessor
from app.llm.llm_manager import llm_manager
from app.wiki.indexer import WikiIndexer
from app.wiki.retriever import WikiRetriever
from app.config.settings import get_settings
from loguru import logger

router = APIRouter(prefix="/api/search", tags=["search"])
storage = OkfStorage()
processor = ConceptProcessor()
indexer = WikiIndexer(storage=storage)
wiki_retriever = WikiRetriever(storage=storage, indexer=indexer)


def _safe_resolve_concept_path(filepath: str) -> Path:
    """
    Безопасно резолвира път до концепция, предотвратявайки path traversal.
    Връща абсолютен път вътре в okf_data_path.
    Ако пътят излиза извън data директорията, хвърля ValueError.
    """
    base_dir = get_settings().okf_data_path
    # Резолвираме и нормализираме пътя
    full_path = (base_dir / filepath).resolve()
    # Проверяваме че резолвираният път е вътре в base_dir
    try:
        full_path.relative_to(base_dir)
    except ValueError:
        raise ValueError(f"Invalid path (outside data directory): {filepath}")
    return full_path


class QuestionInput(BaseModel):
    question: str


@router.get("/concepts")
async def list_concepts(
    type: Optional[str] = Query(None, description="Филтър по тип концепция"),
    tag: Optional[str] = Query(None, description="Филтър по таг"),
    date_from: Optional[str] = Query(None, description="Начална дата (ISO, напр. 2026-01-01)"),
    date_to: Optional[str] = Query(None, description="Крайна дата (ISO, напр. 2026-12-31)"),
    limit: int = Query(50, description="Максимален брой резултати")
):
    """Връща списък с всички концепции, опционално филтрирани."""
    concepts = storage.get_all_concepts()

    # Филтриране
    if type:
        concepts = [c for c in concepts if c["metadata"].get("type") == type]
    if tag:
        concepts = [c for c in concepts if tag in c["metadata"].get("tags", [])]
    if date_from:
        concepts = [c for c in concepts if c["metadata"].get("timestamp", "")[:10] >= date_from]
    if date_to:
        concepts = [c for c in concepts if c["metadata"].get("timestamp", "")[:10] <= date_to]

    # Лимит
    concepts = concepts[:limit]

    return {
        "status": "ok",
        "total": len(concepts),
        "concepts": concepts
    }


@router.get("/concepts/{filepath:path}")
async def get_concept(filepath: str, response: Response):
    """Връща конкретна концепция по път."""
    try:
        full_path = _safe_resolve_concept_path(filepath)
    except ValueError as e:
        response.status_code = 403
        return {"status": "error", "message": str(e)}

    if not full_path.exists() or not full_path.is_file():
        response.status_code = 404
        return {
            "status": "error",
            "message": f"Concept not found: {filepath}"
        }

    try:
        doc = storage.read_concept(full_path)
        return {
            "status": "ok",
            "path": filepath,
            "metadata": doc.metadata.model_dump(mode="json"),
            "body": doc.body
        }
    except Exception as e:
        response.status_code = 500
        return {
            "status": "error",
            "message": str(e)
        }


@router.delete("/concepts/{filepath:path}")
async def delete_concept(filepath: str, response: Response):
    """Изтрива конкретна концепция по път."""
    try:
        full_path = _safe_resolve_concept_path(filepath)
    except ValueError as e:
        response.status_code = 403
        return {"status": "error", "message": str(e)}

    if not full_path.exists() or not full_path.is_file():
        response.status_code = 404
        return {
            "status": "error",
            "message": f"Concept not found: {filepath}"
        }

    try:
        # Прочитаме metadata за log-ване преди изтриване
        doc = storage.read_concept(full_path)
        title = doc.metadata.title

        deleted = storage.delete_concept(full_path)
        if not deleted:
            response.status_code = 500
            return {
                "status": "error",
                "message": f"Could not delete concept: {filepath}"
            }

        # Обновяваме wiki индексите
        indexer.regenerate_all()
        indexer.log_event(
            event_type="delete",
            title=title,
            details=f"Изтрита концепция: {filepath}"
        )

        return {
            "status": "ok",
            "message": f"Концепцията е изтрита: {title}"
        }
    except Exception as e:
        response.status_code = 500
        return {
            "status": "error",
            "message": str(e)
        }


class UpdateConceptInput(BaseModel):
    metadata: dict
    body: str


@router.put("/concepts/{filepath:path}")
async def update_concept(filepath: str, data: UpdateConceptInput, response: Response):
    """Обновява съществуваща концепция."""
    from app.config.okf_schema import OkfDocument, OkfMetadata
    from datetime import datetime

    try:
        full_path = _safe_resolve_concept_path(filepath)
    except ValueError as e:
        response.status_code = 403
        return {"status": "error", "message": str(e)}

    if not full_path.exists() or not full_path.is_file():
        response.status_code = 404
        return {
            "status": "error",
            "message": f"Concept not found: {filepath}"
        }

    try:
        # Конвертираме metadata dict обратно в OkfMetadata
        meta_dict = data.metadata
        # Конвертираме timestamp от string към datetime ако е необходимо
        if isinstance(meta_dict.get("timestamp"), str):
            meta_dict["timestamp"] = datetime.fromisoformat(meta_dict["timestamp"])

        metadata = OkfMetadata(**meta_dict)
        document = OkfDocument(metadata=metadata, body=data.body)

        storage.update_concept(full_path, document)

        # Обновяваме wiki индексите
        indexer.regenerate_all()
        indexer.log_event(
            event_type="update",
            title=metadata.title,
            details=f"Обновена концепция: {filepath}"
        )

        return {
            "status": "ok",
            "path": filepath,
            "metadata": metadata.model_dump(mode="json"),
            "body": document.body,
            "message": f"Концепцията е обновена: {metadata.title}"
        }
    except Exception as e:
        response.status_code = 500
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/wiki/indexes")
async def get_wiki_indexes():
    """Връща списък на всички wiki индекси и тяхното съдържание."""
    try:
        indexes = {}
        index_files = [
            "INDEX_CATEGORIES.md",
            "INDEX_TAGS.md",
            "INDEX_DATE.md",
            "INDEX_FULL.md",
            "LOG.md",
        ]
        for fname in index_files:
            content = indexer.read_index(fname)
            indexes[fname] = content if content else ""

        return {
            "status": "ok",
            "indexes": indexes
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/wiki/ask")
async def wiki_ask(data: QuestionInput):
    """
    Wiki Q&A: Задава въпрос към wiki-то.
    Използва index-based търсене (без embeddings) — LLM навигира индексите.
    """
    try:
        # 0. Ранна проверка: има ли изобщо концепции в wiki-то?
        all_concepts = storage.get_all_concepts()
        if not all_concepts:
            logger.info("Wiki Q&A с празно wiki — връщам насочващо съобщение")
            indexer.log_event(
                event_type="query",
                title=data.question[:80],
                details="Празно wiki — няма създадени концепции"
            )
            return {
                "status": "ok",
                "answer": (
                    "📝 Все още нямаш създадени бележки в wiki-то. "
                    "Можеш да започнеш като напишеш нещо в полето за нов запис, "
                    "или използваш бутона 'Add Concept'."
                ),
                "sources": []
            }

        # 1. Вземаме резюме на индексите
        index_summary = wiki_retriever.get_index_summary()

        # 2. LLM решава кои категории/тагове са релевантни
        exploration_prompt = (
            f"Разгледай wiki индексите по-долу. "
            f"На базата на въпроса на потребителя, избери кои wiki страници "
            f"трябва да се прочетат за да се отговори.\n\n"
            f"## Индекси\n\n{index_summary}\n\n"
            f"## Въпрос\n\n{data.question}\n\n"
            f"Отговори с JSON масив от пътища на страници, които са релевантни. "
            f"Формат: [\"path/to/page.md\", ...]\n"
            f"Ако нищо не е релевантно, върни []."
        )

        llm_response = await llm_manager.rag_client.generate(
            prompt=exploration_prompt,
            system_prompt="Ти си wiki навигатор. Връщаш само JSON масив.",
            temperature=0.1,
            max_tokens=1024
        )

        # 3. Парсваме JSON отговора
        import json
        import re
        json_match = re.search(r'\[.*?\]', llm_response, re.DOTALL)
        if json_match:
            selected_paths = json.loads(json_match.group())
        else:
            selected_paths = []

        if not selected_paths:
            # Fallback: търсим по ключови думи в индекса
            logger.info("LLM не избра страници, използвам keyword fallback")
            keywords = data.question.lower().split()[:5]
            matching = []
            for kw in keywords:
                matching.extend(wiki_retriever.search_keyword(kw))
            selected_paths = list(set(c["path"] for c in matching))[:5]

        if not selected_paths:
            # Fallback 2: няма нищо релевантно изобщо
            indexer.log_event(
                event_type="query",
                title=data.question[:80],
                details="Няма релевантни страници"
            )
            return {
                "status": "ok",
                "answer": (
                    f"Нямам информация за \"{data.question[:100]}\" в твоите бележки. "
                    "Ако искаш, можеш да създадеш нова концепция по темата."
                ),
                "sources": []
            }

        # 4. Взимаме контекста от избраните страници
        selected_concepts = [
            {"path": p, "metadata": {}}
            for p in selected_paths
        ]
        for sc in selected_concepts:
            for ac in all_concepts:
                if ac["path"] == sc["path"]:
                    sc["metadata"] = ac["metadata"]
                    break

        context = wiki_retriever.get_context_for_pages(selected_concepts)

        if not context.strip():
            return {
                "status": "ok",
                "answer": "Нямам информация за това в wiki-то.",
                "sources": []
            }

        # 5. Отговаряме на въпроса с контекста
        answer = await processor.ask_question(data.question, context)

        # 6. Ако отговорът е празен дори след retry, даваме fallback
        if not answer.strip():
            logger.warning("LLM върна празен отговор след retry — използвам fallback")
            answer = (
                f"Открих {len(selected_paths)} свързани страници, "
                f"но не успях да генерирам конкретен отговор. "
                f"Прегледай ги за повече детайли."
            )

        # 7. Логваме заявката
        indexer.log_event(
            event_type="query",
            title=data.question[:80],
            details=f"Използвани страници: {len(selected_paths)}"
        )

        return {
            "status": "ok",
            "answer": answer,
            "sources": [{"path": p} for p in selected_paths]
        }

    except Exception as e:
        logger.error(f"Грешка при Wiki Q&A: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/wiki/reindex")
async def wiki_reindex():
    """Ръчно регенерира всички wiki индекси."""
    try:
        indexer.regenerate_all()
        indexer.log_event(event_type="update", title="Ръчно реиндексиране")
        return {
            "status": "ok",
            "message": "Wiki индексите са регенерирани."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/wiki/lint")
async def wiki_lint():
    """
    Lint проверка на wiki-то.
    Открива: orphan pages, липсващи cross-references, противоречия.
    """
    try:
        all_concepts = storage.get_all_concepts()
        issues = []

        # 1. Orphan pages — страници без incoming references
        all_paths = set(c["path"] for c in all_concepts)
        referenced_paths = set()

        for c in all_concepts:
            body = ""
            try:
                full_path = storage.data_dir / c["path"]
                doc = storage.read_concept(full_path)
                body = doc.body
            except Exception:
                continue

            # Търсим references към други страници
            import re
            for ref in re.findall(r'\[([^\]]+)\]\(([^)]+\.md)\)', body):
                referenced_paths.add(ref[1])

        orphans = all_paths - referenced_paths
        for o in sorted(orphans):
            meta = None
            for c in all_concepts:
                if c["path"] == o:
                    meta = c["metadata"]
                    break
            title = meta.get("title", "Untitled") if meta else "Untitled"
            issues.append({
                "type": "orphan",
                "path": o,
                "title": title,
                "description": "Тази страница няма incoming references от други страници."
            })

        # 2. Страници без тагове
        for c in all_concepts:
            meta = c["metadata"]
            if not meta.get("tags"):
                issues.append({
                    "type": "untagged",
                    "path": c["path"],
                    "title": meta.get("title", "Untitled"),
                    "description": "Страницата няма тагове."
                })

        # 3. Брой страници без описание
        for c in all_concepts:
            meta = c["metadata"]
            if not meta.get("description"):
                issues.append({
                    "type": "no_description",
                    "path": c["path"],
                    "title": meta.get("title", "Untitled"),
                    "description": "Страницата няма описание."
                })

        indexer.log_event(
            event_type="lint",
            title=f"Lint проверка",
            details=f"Открити {len(issues)} проблема ({len(orphans)} orphan, "
                    f"{sum(1 for i in issues if i['type']=='untagged')} untagged, "
                    f"{sum(1 for i in issues if i['type']=='no_description')} no description)"
        )

        return {
            "status": "ok",
            "total_issues": len(issues),
            "issues": issues[:50]  # Лимит за отговор
        }

    except Exception as e:
        logger.error(f"Грешка при lint проверка: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/wiki/log")
async def wiki_log(limit: int = Query(10, description="Брой последни entries")):
    """Връща последните N entries от LOG.md."""
    try:
        entries = indexer.get_log_entries(n=limit)
        return {
            "status": "ok",
            "entries": entries
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }