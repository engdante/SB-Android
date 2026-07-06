"""
OKF Storage модул.
Отговаря за записването, четенето и индексирането на OKF файлове.

Структура:
  data/
  ├── index.md              # Коренов индекс
  ├── log.md                # Chronological log (main)
  ├── raw/                  # Source документи (immutable)
  │   └── YYYY/MM/
  │       └── YYYY-MM-DD_source_NNN.md
  ├── YYYY/MM/              # OKF концепции (LLM-анализирани)
  │   └── YYYY-MM-DD_type_NNN.md
  └── wiki/                 # Wiki индекси и концептуални страници
      ├── index.md
      ├── concepts/         # Постоянни концептуални страници
      └── INDEX_*.md, LOG.md
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import re

from loguru import logger
from app.config.settings import get_settings
from app.config.okf_schema import OkfDocument, OkfMetadata, generate_filename


class OkfStorage:
    """Управлява файловата система на OKF хранилището."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or get_settings().okf_data_path
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Създаваме основните поддиректории
        (self.data_dir / "raw").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
        # ⚠️ In-memory кешът е премахнат — водеше до проблеми с опресняването
        # (няколко инстанции на OkfStorage имаха отделни кешове, които не се синхронизираха)
        # Винаги четем от диска — достатъчно бързо за локална файлова система.

    def _get_year_month_path(self, dt: datetime) -> Path:
        """Връща път: data_dir/<година>/<месец>/"""
        path = self.data_dir / str(dt.year) / f"{dt.month:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_raw_year_month_path(self, dt: datetime) -> Path:
        """Връща път: data_dir/raw/<година>/<месец>/"""
        path = self.data_dir / "raw" / str(dt.year) / f"{dt.month:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_next_sequence(self, directory: Path, date_str: str, concept_type: str) -> int:
        """Намира следващия пореден номер за файл в директорията."""
        pattern = re.compile(rf"^{re.escape(date_str)}_{re.escape(concept_type)}_(\d+)\.md$")
        max_seq = 0
        if directory.exists():
            for f in directory.iterdir():
                match = pattern.match(f.name)
                if match:
                    seq = int(match.group(1))
                    max_seq = max(max_seq, seq)
        return max_seq + 1

    def save_source(self, text: str, dt: Optional[datetime] = None) -> Path:
        """Записва оригинален source текст в data/raw/YYYY/MM/.

        Args:
            text: Оригиналният текст от чат/аудио
            dt: Timestamp (по подразбиране: сега)

        Returns:
            Path: Път до source файла (относителен спрямо data_dir)
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        directory = self._get_raw_year_month_path(dt)
        date_str = dt.strftime("%Y-%m-%d")
        seq = self._get_next_sequence(directory, date_str, "source")
        filename = f"{date_str}_source_{seq:03d}.md"
        filepath = directory / filename

        # Source файлът съдържа само оригиналния текст (без frontmatter)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")

        logger.info(f"Source файлът е записан: {filepath}")
        return filepath

    def save_concept(self, document: OkfDocument, source_path: Optional[Path] = None) -> Path:
        """Записва OKF документ във файловата система.

        Args:
            document: OKF документът за запис
            source_path: Път до source файла (ако има). Ще се добави като resource: поле.

        Returns:
            Path: Път до записания файл
        """
        dt = document.metadata.timestamp

        # Добавяме resource: поле, ако има source
        if source_path is not None:
            # Правим пътя относителен спрямо data_dir
            try:
                rel_path = source_path.relative_to(self.data_dir)
                document.metadata.resource = str(rel_path).replace("\\", "/")
            except ValueError:
                # Ако source_path не е под data_dir, записваме го като абсолютен
                document.metadata.resource = str(source_path)

        directory = self._get_year_month_path(dt)
        date_str = dt.strftime("%Y-%m-%d")
        seq = self._get_next_sequence(directory, date_str, document.metadata.type)
        filename = generate_filename(document.metadata, seq)
        filepath = directory / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(document.to_markdown())

        logger.info(f"OKF файлът е записан: {filepath}")
        return filepath

    def read_concept(self, filepath: Path) -> OkfDocument:
        """Чете OKF файл и го връща като OkfDocument."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return OkfDocument.from_markdown(content)

    def get_all_concepts(self) -> list[dict]:
        """Връща списък с всички концепции (метаданни + път).

        Винаги чете от диска — няма in-memory кеш, за да се избегнат
        проблеми с опресняването между различни инстанции на OkfStorage.

        Пропуска:
        - index.md и log.md (коренови)
        - wiki/ директорията (индекси, LOG.md, концептуални страници)
        - raw/ директорията (source документи)
        """
        concepts = []
        wiki_dir = self.data_dir / "wiki"
        raw_dir = self.data_dir / "raw"
        md_files = sorted(self.data_dir.rglob("*.md"))

        for filepath in md_files:
            filename = filepath.name
            # Skip коренови файлове
            if filename in ("index.md", "log.md"):
                continue
            # Skip wiki директорията
            if wiki_dir in filepath.parents:
                continue
            # Skip raw директорията
            if raw_dir in filepath.parents:
                continue
            try:
                doc = self.read_concept(filepath)
                concepts.append({
                    "path": str(filepath.relative_to(self.data_dir)),
                    "metadata": doc.metadata.model_dump(mode="json"),
                    "body_preview": doc.body[:200] + "..."
                })
            except Exception as e:
                logger.warning(f"Грешка при четене на {filepath}: {e}")

        return concepts

    def get_all_documents(self) -> list[OkfDocument]:
        """Връща всички OKF документи."""
        documents = []
        for filepath in sorted(self.data_dir.rglob("*.md")):
            if filepath.name == "index.md":
                continue
            try:
                doc = self.read_concept(filepath)
                documents.append(doc)
            except Exception as e:
                logger.warning(f"Грешка при четене на {filepath}: {e}")
        return documents

    def delete_concept(self, filepath: Path) -> bool:
        """Изтрива OKF файл.

        Args:
            filepath: Път до файла (може да е относителен спрямо data_dir или абсолютен)

        Returns:
            bool: True ако файлът е изтрит, False ако не съществува
        """
        if not filepath.is_absolute():
            filepath = self.data_dir / filepath

        if not filepath.exists():
            logger.warning(f"Файлът не съществува: {filepath}")
            return False

        filepath.unlink()
        logger.info(f"OKF файлът е изтрит: {filepath}")
        return True

    def update_concept(self, filepath: Path, document: OkfDocument) -> Path:
        """Презаписва съществуващ OKF файл с ново съдържание.

        Args:
            filepath: Път до файла (може да е относителен спрямо data_dir или абсолютен)
            document: Новият OkfDocument

        Returns:
            Path: Път до обновения файл
        """
        if not filepath.is_absolute():
            filepath = self.data_dir / filepath

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(document.to_markdown())

        logger.info(f"OKF файлът е обновен: {filepath}")
        return filepath

    def update_index(self) -> None:
        """Генерира/обновява index.md файла (OKF §6).

        Следва OKF §6 формат:
        - Без frontmatter
        - Секции с heading, групирани по дата
        - Всеки entry: `[Title](relative-path) - description`
        """
        concepts = self.get_all_concepts()
        index_path = self.data_dir / "index.md"

        lines = [
            "# pi_sb — Second Brain Index\n",
            f"_Автоматично генериран на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            f"_Общо концепции: {len(concepts)}_\n",
            "---\n"
        ]

        # Групираме по дата (година/месец) — OKF §6: секции с heading
        from collections import defaultdict
        by_date = defaultdict(list)
        for c in concepts:
            ts = c["metadata"].get("timestamp", "")
            date_key = ts[:7] if len(ts) >= 7 else "unknown"
            by_date[date_key].append(c)

        for date_key in sorted(by_date.keys(), reverse=True):
            lines.append(f"\n## {date_key}\n")
            for c in by_date[date_key]:
                meta = c["metadata"]
                title = meta.get('title', 'Untitled')
                desc = meta.get('description', '')
                desc_suffix = f" - {desc}" if desc else ""
                lines.append(
                    f"* [{title}]({c['path']}){desc_suffix}"
                )

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        logger.info(f"index.md updated with {len(concepts)} concepts (OKF §6)")
