"""
Processor pipeline.
Приема текст, изпраща го на LLM за анализ, парсира OKF резултата и го записва.

Следва OKF v0.1:
- Единственото задължително поле е `type` (OKF §9 Conformance)
- Всички останали полета са препоръчителни (soft guidance)
- LLM получава инструкции чрез analysis_prompt.txt, но не се retry-ва при липсващи полета
"""

from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from loguru import logger
from app.llm.ollama_client import OllamaClient
from app.llm.llm_manager import LLMManager, llm_manager as default_llm_manager
from app.core.storage import OkfStorage
from app.config.okf_schema import OkfDocument, OkfMetadata
from app.config.concept_types import DEFAULT_CONCEPT_TYPE
from app.config.settings import get_app_internal_dir
from app.wiki.indexer import WikiIndexer
from app.core.debug_logger import debug_logger


class ConceptProcessor:
    """Pipeline за обработка на нова концепция."""

    def __init__(self, llm_manager: Optional[LLMManager] = None,
                 storage: Optional[OkfStorage] = None,
                 indexer: Optional[WikiIndexer] = None):
        self.llm_manager = llm_manager or default_llm_manager
        self.storage = storage or OkfStorage()
        self.indexer = indexer or WikiIndexer(storage=self.storage)
        self._load_prompts()

    def _load_prompts(self):
        """Зарежда системните промпти от файлове."""
        prompts_dir = get_app_internal_dir() / "backend" / "app" / "config" / "prompts"
        analysis_path = prompts_dir / "analysis_prompt.txt"
        rag_path = prompts_dir / "rag_prompt.txt"

        if analysis_path.exists():
            with open(analysis_path, "r", encoding="utf-8") as f:
                self.analysis_system_prompt = f.read()
        else:
            self.analysis_system_prompt = "Analyze the text and create an OKF file."

        if rag_path.exists():
            with open(rag_path, "r", encoding="utf-8") as f:
                self.rag_system_prompt = f.read()
        else:
            self.rag_system_prompt = "Answer based on the context."

    async def process_text(self, text: str) -> OkfDocument:
        """
        Обработва текстов вход:
        1. Записва оригиналния source текст в data/raw/
        2. Изпраща текста на Ollama за анализ (използва analysis_prompt.txt)
        3. Парсира OKF резултата
        4. Валидира според OKF §9 (само `type` е задължително)
        5. Коригира timestamp и language
        6. Записва OKF файла с resource: поле сочещо към source-а

        Args:
            text: Потребителският текст

        Returns:
            OkfDocument: Записаният документ
        """
        logger.info(f"Обработвам текст ({len(text)} символа)")

        # ⚠️ Винаги презареждаме клиента преди употреба, за да вземем
        # актуалните настройки от .env (модел, host и т.н.)
        self.llm_manager._ensure_clients()

        # Стъпка 1: Записваме source текста в data/raw/ (преди анализ)
        source_path = self.storage.save_source(text)
        logger.info(f"Source текстът е записан: {source_path}")

        # Стъпка 2: Генерираме OKF чрез LLM (един опит, без retry)
        # Според OKF §9 всички полета освен `type` са optional,
        # така че няма нужда от retry при липсващи полета.
        document = await self._try_generate_okf(text, temperature=0.3)

        # Стъпка 3: OKF §9 Conformance — единственото задължително нещо е `type`.
        # Ако дори `type` липсва, създаваме fallback.
        if not self._validate_conformance(document):
            logger.warning("OKF документът не покрива OKF §9 conformance. Използвам fallback.")
            document = self._create_fallback_document(text)

        # ⚠️ Винаги презаписваме timestamp с реалното текущо време,
        # защото LLM-то често измисля/фалшифицира дата и час.
        document.metadata.timestamp = datetime.now(timezone.utc)

        # ⚠️ Винаги презаписваме language на bg — цялата wiki е на български.
        if document.metadata.language != "bg":
            logger.warning(f"Коригирам language от {document.metadata.language} на bg")
            document.metadata.language = "bg"

        # Стъпка 4: Записваме OKF файла с resource: поле сочещо към source-а
        filepath = self.storage.save_concept(document, source_path=source_path)
        logger.info(f"Концепцията е записана: {filepath}")

        # Стъпка 5: Обновяваме wiki индексите и LOG.md
        self.indexer.regenerate_all()
        self.indexer.log_event(
            event_type="ingest",
            title=document.metadata.title or "(без заглавие)",
            details=f"Тип: {document.metadata.type}, Път: {filepath}, Source: {source_path}"
        )

        return document

    async def _try_generate_okf(self, text: str, temperature: float) -> OkfDocument:
        """
        Генерира OKF документ чрез LLM с до 3 опита.

        Стратегия:
        1. Опит 1: temperature=0.3 (нормален)
        2. Опит 2: temperature=0.1 (по-стриктно спазване на форма̀та)
        3. Опит 3: temperature=0.0 (максимално детерминиран)

        Всеки следващ опит добавя по-силно напомняне за форма̀та към текста.

        Args:
            text: Оригиналният текст
            temperature: Температура за LLM генерация (0.0 - 1.0)

        Returns:
            OkfDocument: Генерираният документ (или fallback при грешка)
        """
        system_prompt = self.analysis_system_prompt

        # Дефинираме опитите: (temperature, reminder_suffix)
        attempts = [
            (temperature, ""),  # Първи опит — оригиналната температура
            (0.1, "\n\n⚠️ ВАЖНО: Предишният опит НЕ беше в правилен формат. Отговорът трябва да започва с `---` и да съдържа само YAML frontmatter + Markdown body. НЕ добавяй code block-ове (```), обяснения или друг текст преди или след frontmatter-а."),
            (0.0, "\n\n⚠️ КРИТИЧНО: Отговорът ти трябва да започва ЕДИНСТВЕНО с `---`. НЕ добавяй никакъв текст преди `---`. НЕ използвай code block-ове. Само чист YAML frontmatter + Markdown body."),
        ]

        last_error = None
        for i, (temp, reminder) in enumerate(attempts):
            prompt = text + reminder
            raw_response = await self.llm_manager.ingestion_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temp,
                max_tokens=4096
            )

            try:
                document = OkfDocument.from_markdown(raw_response)
                if i > 0:
                    logger.info(f"OKF генериран успешно на опит {i + 1} (temp={temp})")
                return document
            except Exception as e:
                last_error = e
                logger.warning(f"Опит {i + 1}/{len(attempts)} неуспешен (temp={temp}): {e}")
                logger.debug(f"LLM отговор (опит {i + 1}): {raw_response[:300]}")

        # Ако всички опити са неуспешни, създаваме fallback
        logger.error(f"Всичките {len(attempts)} опита за генериране на OKF са неуспешни. Последна грешка: {last_error}")
        return self._create_fallback_document(text)

    def _validate_conformance(self, document: OkfDocument) -> bool:
        """
        Проверява OKF §9 conformance.

        OKF §9 изисква единствено:
        1. Parseable YAML frontmatter (вече проверено при парсване)
        2. `type` полето не е празно

        Всички останали полета (title, description, tags, resource, timestamp)
        са optional според OKF §4.1 — тяхната липса НЕ е грешка.

        Args:
            document: Генерираният OKF документ

        Returns:
            bool: True ако документът е OKF §9 conformant
        """
        # Проверка: type не е празен
        doc_type = (document.metadata.type or "").strip()
        if not doc_type:
            logger.warning("OKF §9 conformance: `type` полето е празно")
            return False

        # ⚠️ Soft warnings за липсващи препоръчителни полета
        # (това не е грешка според OKF, но логваме за информация)
        if not document.metadata.title:
            logger.info(f"OKF: концепция от тип '{doc_type}' няма заглавие (optional)")

        if not document.metadata.description:
            logger.info(f"OKF: концепция '{document.metadata.title or '(без заглавие)'}' няма описание (optional)")

        if not document.metadata.tags:
            logger.info(f"OKF: концепция '{document.metadata.title or '(без заглавие)'}' няма тагове (optional)")

        body = document.body.strip()
        if not body:
            logger.info(f"OKF: концепция '{document.metadata.title or '(без заглавие)'}' няма body съдържание")

        logger.info(f"OKF §9 conformance OK: тип '{doc_type}'")
        return True

    async def ask_question(self, question: str, context: str) -> str:
        """
        Задава въпрос към RAG системата.

        Args:
            question: Въпросът на потребителя
            context: Контекст от OKF бележките

        Returns:
            str: Отговорът на LLM
        """
        # ⚠️ Винаги презареждаме клиента преди употреба
        self.llm_manager._ensure_clients()

        system_prompt = self.rag_system_prompt.replace("{context}", context)
        response = await self.llm_manager.rag_client.generate(
            prompt=question,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2048
        )
        return response

    def _create_fallback_document(self, text: str) -> OkfDocument:
        """Създава OKF документ като fallback, ако LLM не върне валиден OKF.

        Според OKF §9, минималният conformant документ има само `type`.
        """
        metadata = OkfMetadata(
            type=DEFAULT_CONCEPT_TYPE,
            title=None,
            description=None,
            tags=[],
            language="bg"
        )
        return OkfDocument(metadata=metadata, body=text)