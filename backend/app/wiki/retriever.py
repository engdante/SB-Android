"""
Wiki Retriever — index-based търсене без embeddings/vector DB.
LLM-ът навигира multi-level индексите за да намери релевантни страници.
"""

from typing import Optional

from loguru import logger
from app.core.storage import OkfStorage
from app.config.okf_schema import OkfDocument
from app.wiki.indexer import WikiIndexer


class WikiRetriever:
    """
    Index-based retriever.
    Използва multi-level индекси вместо vector embeddings.
    """

    def __init__(self, storage: Optional[OkfStorage] = None,
                 indexer: Optional[WikiIndexer] = None):
        self.storage = storage or OkfStorage()
        self.indexer = indexer or WikiIndexer()

    def search_by_categories(self, categories: list[str]) -> list[dict]:
        """
        Търси концепции по категории (типове).

        Args:
            categories: Списък от типове (напр. ["journal", "idea"])

        Returns:
            list[dict]: Концепциите, филтрирани по категория
        """
        all_concepts = self.storage.get_all_concepts()
        return [
            c for c in all_concepts
            if c["metadata"].get("type") in categories
        ]

    def search_by_tags(self, tags: list[str]) -> list[dict]:
        """
        Търси концепции по тагове.

        Args:
            tags: Списък от тагове (напр. ["hvac", "revit"])

        Returns:
            list[dict]: Концепциите, които имат поне един от таговете
        """
        all_concepts = self.storage.get_all_concepts()
        return [
            c for c in all_concepts
            if any(tag in c["metadata"].get("tags", []) for tag in tags)
        ]

    def search_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        """
        Търси концепции в период.

        Args:
            start_date: "2026-01-01"
            end_date: "2026-12-31"

        Returns:
            list[dict]: Концепциите в периода
        """
        all_concepts = self.storage.get_all_concepts()
        result = []
        for c in all_concepts:
            ts = c["metadata"].get("timestamp", "")
            date = ts[:10] if len(ts) >= 10 else ""
            if start_date <= date <= end_date:
                result.append(c)
        return result

    def search_keyword(self, keyword: str, include_body: bool = True) -> list[dict]:
        """
        Търси по ключова дума в заглавие, описание, тагове и опционално в body.

        Args:
            keyword: Ключова дума за търсене
            include_body: Ако True, търси и в body съдържанието (по-бавно, но по-точно)

        Returns:
            list[dict]: Концепции, които съдържат ключовата дума
        """
        keyword_lower = keyword.lower()
        all_concepts = self.storage.get_all_concepts()
        result = []
        for c in all_concepts:
            meta = c["metadata"]
            title = meta.get("title", "").lower()
            desc = meta.get("description", "").lower()
            tags = " ".join(meta.get("tags", [])).lower()

            # Търси първо в метаданните (бързо)
            if (keyword_lower in title or
                keyword_lower in desc or
                keyword_lower in tags):
                result.append(c)
                continue

            # Ако не е намерено в метаданните, търси в body-то
            if include_body:
                try:
                    full_path = self.storage.data_dir / c["path"]
                    doc = self.storage.read_concept(full_path)
                    if keyword_lower in doc.body.lower():
                        result.append(c)
                except Exception:
                    continue

        return result

    def get_context_for_pages(self, concepts: list[dict], max_chars: int = 8000) -> str:
        """
        Подготвя контекст от списък концепции за подаване на LLM.
        Чете пълното съдържание на всяка страница.

        Args:
            concepts: Списък концепции (от search_* методите)
            max_chars: Максимален брой символи за контекста

        Returns:
            str: Контекст за LLM
        """
        context_parts = []
        total_chars = 0

        for c in concepts:
            path = c["path"]
            meta = c["metadata"]

            try:
                full_path = self.storage.data_dir / path
                doc = self.storage.read_concept(full_path)
            except Exception:
                continue

            header = f"## [{meta.get('type', '?')}] {meta.get('title', 'Untitled')}"
            if meta.get("tags"):
                header += f" ({', '.join('#' + t for t in meta['tags'])})"

            # Добавяме timestamp и description от frontmatter-а (ако има)
            meta_lines = []
            ts = meta.get("timestamp")
            if ts:
                # Вземаме само датата (YYYY-MM-DD) от ISO timestamp-а
                date_str = str(ts)[:10] if len(str(ts)) >= 10 else str(ts)
                meta_lines.append(f"Дата: {date_str}")
            desc = meta.get("description")
            if desc:
                meta_lines.append(f"Описание: {desc}")

            meta_section = "\n".join(meta_lines)
            if meta_section:
                meta_section = "\n" + meta_section

            entry = f"{header}{meta_section}\n\n{doc.body}\n\n---\n"
            if total_chars + len(entry) > max_chars:
                # Добавяме само част, ако надхвърлим лимита
                remaining = max_chars - total_chars
                if remaining > 200:
                    entry = entry[:remaining] + "\n[... truncated]"
                else:
                    break

            context_parts.append(entry)
            total_chars += len(entry)

        return "\n".join(context_parts)

    def get_index_summary(self) -> str:
        """
        Връща резюме на индексите — кои са налични и какво съдържат.
        """
        summary = []
        index_files = [
            "INDEX_CATEGORIES.md",
            "INDEX_TAGS.md",
            "INDEX_DATE.md",
            "INDEX_FULL.md",
        ]

        for fname in index_files:
            content = self.indexer.read_index(fname)
            if content:
                lines = content.strip().split("\n")
                # Взимаме само първите няколко реда
                preview = "\n".join(lines[:15])
                summary.append(f"### {fname}\n```markdown\n{preview}\n```")

        return "\n\n".join(summary)