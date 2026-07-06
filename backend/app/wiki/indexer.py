"""
Wiki Indexer — Multi-level indexer for LLM Wiki.
Generates and maintains hierarchical indexes without embeddings/vector DB.

Levels:
  LEVEL 0: INDEX_CATEGORIES.md — categories with page counts
  LEVEL 1: INDEX_TAGS.md       — for each tag, list of pages
  LEVEL 2: INDEX_DATE.md       — chronological index
  LEVEL 3: INDEX_FULL.md       — full list (for small databases / fallback)
  LOG.md                       — append-only chronological log
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from app.config.settings import get_settings
from app.core.storage import OkfStorage
from app.config.concept_types import CONCEPT_TYPE_DESCRIPTIONS


class WikiIndexer:
    """Generates and maintains multi-level indexes for the wiki."""

    def __init__(self, storage: Optional[OkfStorage] = None):
        self.storage = storage or OkfStorage()
        self.wiki_dir: Path = get_settings().okf_data_path / "wiki"
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def regenerate_all(self) -> None:
        """Regenerates all indexes. Called on startup or manually."""
        concepts = self.storage.get_all_concepts()
        logger.info(f"Regenerating wiki indexes for {len(concepts)} concepts...")

        self._write_category_index(concepts)
        self._write_tags_index(concepts)
        self._write_date_index(concepts)
        self._write_full_index(concepts)
        self._write_wiki_index(concepts)

        # Also update data/index.md (OKF §6) — once here to avoid
        # duplicate calls from storage.save_concept()/delete_concept()/update_concept()
        self.storage.update_index()

        logger.info(f"✓ Wiki indexes updated ({len(concepts)} concepts)")

    def log_event(self, event_type: str, title: str, details: str = "") -> None:
        """
        Adds an entry to LOG.md (both wiki/LOG.md and data/log.md).
        event_type: ingest | query | lint | update | delete
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        entry = f"## [{timestamp}] {event_type} | {title}\n"
        if details:
            entry += f"{details}\n\n"
        else:
            entry += "\n"

        # Write to wiki/LOG.md
        log_path = self.wiki_dir / "LOG.md"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

        # Also write to data/log.md (main log)
        data_log_path = self.storage.data_dir / "log.md"
        with open(data_log_path, "a", encoding="utf-8") as f:
            f.write(entry)

        logger.debug(f"LOG.md: {event_type} | {title}")

    def get_log_entries(self, n: int = 10) -> list[str]:
        """Returns the last N entries from LOG.md."""
        log_path = self.wiki_dir / "LOG.md"
        if not log_path.exists():
            return []

        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        entries = []
        current = ""
        for line in lines:
            if line.startswith("## ["):
                if current.strip():
                    entries.append(current.strip())
                current = line.strip()
            else:
                current += line

        if current.strip():
            entries.append(current.strip())

        return entries[-n:]

    # ──────────────────────────────────────────────
    # LEVEL 0: INDEX_CATEGORIES.md
    # ──────────────────────────────────────────────

    def _write_category_index(self, concepts: list[dict]) -> None:
        """Generates INDEX_CATEGORIES.md — list of categories."""
        from collections import Counter
        categories = Counter()
        for c in concepts:
            cat = c["metadata"].get("type", "other")
            categories[cat] += 1

        lines = [
            "# INDEX_CATEGORIES.md — Категории\n",
            f"_Автоматично генериран на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            f"_Общо категории: {len(categories)}_\n",
            "---\n",
            "| Категория | Брой страници | Описание |",
            "|-----------|---------------|----------|",
        ]

        for cat in sorted(categories.keys()):
            desc = CONCEPT_TYPE_DESCRIPTIONS.get(cat, f"{cat.replace('_', ' ').title()} — автоматично")
            lines.append(f"| `{cat}` | {categories[cat]} | {desc} |")

        lines.append(f"\n_Общо концепции: {len(concepts)}_")
        self._write_index("INDEX_CATEGORIES.md", lines)

    # ──────────────────────────────────────────────
    # LEVEL 1: INDEX_TAGS.md
    # ──────────────────────────────────────────────

    def _write_tags_index(self, concepts: list[dict]) -> None:
        """Generates INDEX_TAGS.md — for each tag, list of pages."""
        from collections import defaultdict

        tag_map = defaultdict(list)
        for c in concepts:
            tags = c["metadata"].get("tags", [])
            for tag in tags:
                tag_map[tag].append(c)

        lines = [
            "# INDEX_TAGS.md — Тагове\n",
            f"_Автоматично генериран на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            f"_Общо тагове: {len(tag_map)}_\n",
            "---\n",
        ]

        for tag in sorted(tag_map.keys()):
            pages = tag_map[tag]
            lines.append(f"\n## #{tag} ({len(pages)} страници)\n")
            for p in pages:
                meta = p["metadata"]
                title = meta.get("title", "Untitled")
                path = p["path"]
                ptype = meta.get("type", "?")
                lines.append(f"- [{title}]({path}) `{ptype}`")

        self._write_index("INDEX_TAGS.md", lines)

    # ──────────────────────────────────────────────
    # LEVEL 2: INDEX_DATE.md
    # ──────────────────────────────────────────────

    def _write_date_index(self, concepts: list[dict]) -> None:
        """Generates INDEX_DATE.md — chronological index."""
        from collections import defaultdict

        by_date = defaultdict(list)
        for c in concepts:
            ts = c["metadata"].get("timestamp", "")
            date_key = ts[:10] if len(ts) >= 10 else "unknown"
            by_date[date_key].append(c)

        lines = [
            "# INDEX_DATE.md — Хронологичен указател\n",
            f"_Автоматично генериран на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            f"_Общо концепции: {len(concepts)}_\n",
            "---\n",
        ]

        for date_key in sorted(by_date.keys(), reverse=True):
            pages = by_date[date_key]
            lines.append(f"\n## {date_key} ({len(pages)} страници)\n")
            for p in pages:
                meta = p["metadata"]
                title = meta.get("title", "Untitled")
                path = p["path"]
                ptype = meta.get("type", "?")
                tags = meta.get("tags", [])
                tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
                lines.append(f"- [{title}]({path}) `{ptype}` {tag_str}")

        self._write_index("INDEX_DATE.md", lines)

    # ──────────────────────────────────────────────
    # LEVEL 3: INDEX_FULL.md
    # ──────────────────────────────────────────────

    def _write_full_index(self, concepts: list[dict]) -> None:
        """Generates INDEX_FULL.md — full list of all pages."""
        lines = [
            "# INDEX_FULL.md — Пълен индекс\n",
            f"_Автоматично генериран на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            f"_Общо концепции: {len(concepts)}_\n",
            "---\n",
            "| # | Заглавие | Тип | Тагове | Дата | Път |",
            "|---|----------|-----|--------|------|------|",
        ]

        for idx, c in enumerate(concepts, 1):
            meta = c["metadata"]
            title = meta.get("title", "Untitled")
            ptype = meta.get("type", "?")
            tags = ", ".join(meta.get("tags", []))
            date = meta.get("timestamp", "")[:10]
            path = c["path"]
            lines.append(f"| {idx} | [{title}]({path}) | `{ptype}` | {tags} | {date} | `{path}` |")

        self._write_index("INDEX_FULL.md", lines)

    # ──────────────────────────────────────────────
    # wiki/index.md — Categorized index by topic
    # ──────────────────────────────────────────────

    def _write_wiki_index(self, concepts: list[dict]) -> None:
        """Generates wiki/index.md — categorized index by topic."""
        from collections import defaultdict

        # Group concepts by type
        by_type = defaultdict(list)
        for c in concepts:
            cat = c["metadata"].get("type", "other")
            by_type[cat].append(c)

        lines = [
            "# wiki/index.md — Категоризиран индекс\n",
            f"_Автоматично генериран на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            f"_Общо концепции: {len(concepts)}_\n",
            "---\n",
        ]

        for cat in sorted(by_type.keys()):
            desc = CONCEPT_TYPE_DESCRIPTIONS.get(cat, f"{cat.replace('_', ' ').title()} — автоматично")
            pages = by_type[cat]
            lines.append(f"\n## {cat} ({len(pages)} страници) — {desc}\n")
            for p in pages:
                meta = p["metadata"]
                title = meta.get("title", "Untitled")
                path = p["path"]
                tags = meta.get("tags", [])
                tag_str = " ".join(f"#{t}" for t in tags) if tags else ""
                resource = meta.get("resource", "")
                resource_str = f" — [Source]({resource})" if resource else ""
                lines.append(f"- [{title}]({path}) {tag_str}{resource_str}")

        # Референции към други индекси
        lines.append("\n---\n")
        lines.append("## Индекси\n")
        lines.append("- [INDEX_CATEGORIES.md](INDEX_CATEGORIES.md) — Категории")
        lines.append("- [INDEX_TAGS.md](INDEX_TAGS.md) — Тагове")
        lines.append("- [INDEX_DATE.md](INDEX_DATE.md) — Хронологичен")
        lines.append("- [INDEX_FULL.md](INDEX_FULL.md) — Пълен списък")
        lines.append("- [LOG.md](LOG.md) — Хронологичен лог")
        lines.append("- [Концептуални страници](concepts/) — Постоянни концепции")

        self._write_index("index.md", lines)

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _write_index(self, filename: str, lines: list[str]) -> None:
        """Writes an index file to the wiki/ directory."""
        path = self.wiki_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        logger.debug(f"Updated index: {filename}")

    def read_index(self, filename: str) -> str:
        """Reads an index file. Returns empty string if it doesn't exist."""
        path = self.wiki_dir / filename
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()