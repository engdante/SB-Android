"""
OKF v0.1 (Open Knowledge Format) — Google OKF conformant + pi_sb extensions.

Следва официалния OKF стандарт на Google:
https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Структура на OKF файл (OKF v0.1 + pi_sb extensions):
---
okf_version: "0.1"       # OKF §11 — bundle версия
type: <тип>              # OKF §4.1 — REQUIRED, свободен текст
title: <заглавие>        # OKF §4.1 — Recommended
description: <описание>  # OKF §4.1 — Recommended
resource: <URI>          # OKF §4.1 — Optional (външен URI или път до source)
tags: [таг1, таг2]       # OKF §4.1 — Optional
timestamp: <ISO 8601>    # OKF §4.1 — Optional
id: <uuid>               # ⬅️ pi_sb extension (UUID[0:8])
language: bg             # ⬅️ pi_sb extension
---

Структура на директорията:
data/
├── index.md           (автоматично генериран, OKF §6)
├── log.md             (автоматично генериран, OKF §7)
├── raw/               (pi_sb — source документи, immutable)
├── wiki/              (pi_sb — wiki индекси)
├── YYYY/MM/           (OKF §3 — произволни поддиректории)
│   └── YYYY-MM-DD_type_NNN.md
└── ...
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import yaml
import uuid

from app.config.concept_types import DEFAULT_CONCEPT_TYPE


class OkfMetadata(BaseModel):
    """YAML frontmatter на OKF файл (OKF v0.1 + pi_sb extensions).

    Следва Google OKF SPEC §4.1:
    - `type` е единственото REQUIRED поле
    - `title`, `description`, `resource`, `tags`, `timestamp` са Recommended/Optional
    - `id` и `language` са pi_sb extension полета (позволени от §4.1 "Extensions")
    """
    # OKF v0.1 задължителни полета
    okf_version: str = "0.1"       # OKF §11
    type: str = DEFAULT_CONCEPT_TYPE  # OKF §4.1 — REQUIRED, свободен текст (от concept_types.py)

    # OKF v0.1 препоръчителни полета (вече Optional)
    title: Optional[str] = None    # OKF §4.1 — Recommended (беше REQUIRED)
    description: Optional[str] = None  # OKF §4.1 — Recommended (беше REQUIRED)
    resource: Optional[str] = None # OKF §4.1 — Optional, URI или път до source
    tags: list[str] = Field(default_factory=list)  # OKF §4.1 — Optional (беше REQUIRED)
    timestamp: Optional[datetime] = None  # OKF §4.1 — Optional (беше REQUIRED)

    # pi_sb extension полета (позволени от OKF §4.1 "Extensions")
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    language: Optional[str] = None  # "bg" или "en"

    def to_yaml(self) -> str:
        """Конвертира метаданните в YAML frontmatter.

        Подрежда полетата в логичен ред:
        1. OKF задължителни (okf_version, type)
        2. OKF препоръчителни (title, description, resource, tags, timestamp)
        3. pi_sb extensions (id, language)
        """
        data = self.model_dump(mode='json', exclude_none=True)

        # Подреждаме ключовете в желания ред
        ordered_keys = [
            "okf_version",
            "type",
            "title",
            "description",
            "tags",
            "resource",
            "language",
            "timestamp",
            "id",
        ]
        ordered_data = {}
        for key in ordered_keys:
            if key in data:
                ordered_data[key] = data[key]
        # Добавяме всички останали (ако има extension полета)
        for key in data:
            if key not in ordered_data:
                ordered_data[key] = data[key]

        return yaml.dump(ordered_data, default_flow_style=False, allow_unicode=True, sort_keys=False)


class OkfDocument(BaseModel):
    """Пълен OKF документ (YAML frontmatter + Markdown body)."""
    metadata: OkfMetadata
    body: str

    def to_markdown(self) -> str:
        """Конвертира документа в OKF Markdown формат."""
        return f"---\n{self.metadata.to_yaml()}---\n\n{self.body.strip()}\n"

    @staticmethod
    def from_markdown(content: str) -> "OkfDocument":
        """Парсира OKF Markdown обратно в OkfDocument.

        Опитва няколко стратегии в ред:
        1. Стандартен YAML frontmatter (--- ... ---)
        2. YAML/OKF code block (```yaml ... ``` или ```okf ... ```)
        3. JSON code block (```json ... ``` или ```okf ... ``` с JSON inside)
        4. Първия `---` блок ако има множествени
        5. Ако целият текст е JSON, парсва като JSON

        Args:
            content: OKF файл със YAML frontmatter + Markdown body
                     или JSON в code block, или произволен текст

        Returns:
            OkfDocument: Парсираният документ

        Raises:
            ValueError: Ако не може да се извлече валиден frontmatter
        """
        import re

        # Стратегия 1: Стандартен YAML frontmatter (--- ... ---)
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_content = parts[1].strip()
            body = parts[2].strip()
            if yaml_content:
                try:
                    metadata_dict = yaml.safe_load(yaml_content)
                    if isinstance(metadata_dict, dict):
                        return OkfDocument._build_from_dict(metadata_dict, body)
                except yaml.YAMLError:
                    pass

        # Стратегия 2: Търси code block с yaml, okf, или json
        code_block_pattern = re.compile(
            r'```(?:yaml|okf|json)\s*\n(.*?)```',
            re.DOTALL
        )
        match = code_block_pattern.search(content)
        if match:
            block_content = match.group(1).strip()
            # Пробвай като YAML
            try:
                metadata_dict = yaml.safe_load(block_content)
                if isinstance(metadata_dict, dict):
                    # Извади body-то — всичко след code block-а
                    body_after = content[match.end():].strip()
                    return OkfDocument._build_from_dict(metadata_dict, body_after)
            except yaml.YAMLError:
                pass
            # Пробвай като JSON
            try:
                import json
                metadata_dict = json.loads(block_content)
                if isinstance(metadata_dict, dict):
                    body_after = content[match.end():].strip()
                    return OkfDocument._build_from_dict(metadata_dict, body_after)
            except json.JSONDecodeError:
                pass

        # Стратегия 3: Провери дали целият текст е JSON
        import json
        stripped = content.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                metadata_dict = json.loads(stripped)
                if isinstance(metadata_dict, dict):
                    return OkfDocument._build_from_dict(metadata_dict, "")
            except json.JSONDecodeError:
                pass

        # Стратегия 4: Ако има `---` някъде в текста (не само в началото)
        # Намери първия `---` и пробвай оттам
        first_sep = content.find("\n---\n")
        if first_sep >= 0:
            after_sep = content[first_sep + 5:]  # +5 за "\n---\n"
            second_sep = after_sep.find("\n---\n")
            if second_sep >= 0:
                yaml_content = after_sep[:second_sep].strip()
                body = after_sep[second_sep + 5:].strip()
                if yaml_content:
                    try:
                        metadata_dict = yaml.safe_load(yaml_content)
                        if isinstance(metadata_dict, dict):
                            return OkfDocument._build_from_dict(metadata_dict, body)
                    except yaml.YAMLError:
                        pass

        # Ако нищо не работи, хвърли грешка
        raise ValueError("Invalid OKF format: missing YAML frontmatter")

    @staticmethod
    def _build_from_dict(data: dict, body: str) -> "OkfDocument":
        """Създава OkfDocument от dict (YAML или JSON парснат)."""
        # Конвертира timestamp от string към datetime
        if isinstance(data.get("timestamp"), str):
            try:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            except ValueError:
                # Ако timestamp е невалиден, премахваме го
                if "timestamp" in data:
                    del data["timestamp"]

        metadata = OkfMetadata(**data)
        return OkfDocument(metadata=metadata, body=body)


def generate_filename(metadata: OkfMetadata, sequence: int = 1) -> str:
    """Генерира уникално име на файл според OKF конвенцията.

    Формат: YYYY-MM-DD_type_NNN.md
    Ако няма timestamp, използва текущата дата.
    Ако type съдържа невалидни символи, ги замества с '_'.

    Args:
        metadata: Метаданните на концепцията
        sequence: Пореден номер (1-based)

    Returns:
        str: Име на файл
    """
    dt = metadata.timestamp or datetime.now(timezone.utc)
    date_str = dt.strftime("%Y-%m-%d")
    # Заместваме невалидни символи в type с '_'
    safe_type = "".join(c if c.isalnum() or c in "-_" else "_" for c in metadata.type)
    return f"{date_str}_{safe_type}_{sequence:03d}.md"