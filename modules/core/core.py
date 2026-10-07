"""
TwinSisters Core — ядро младшей сестры.

Модуль отвечает за загрузку .md файлов памяти (персона, кредо, факты, дом),
сборку единого системного промпта из них и управление фактами —
добавление новых фактов в user_facts.md и sister_facts.md.

Размещение: modules/core/core.py
Пути вычисляются от корня проекта.

Основные компоненты:
    - TwinCore: класс-менеджер ядра памяти.
      Методы:
        - load_core():        загружает все .md файлы ядра.
        - build_context():    собирает системный промпт из загруженных файлов.
        - add_fact():         добавляет факт в user_facts или sister_facts.
        - status():           возвращает словарь со статусом ядра.
"""

from pathlib import Path
from datetime import datetime
import json
import sys

# === Пути ===
BASE = Path(__file__).resolve().parent.parent.parent  # modules/core/ -> корень
CONFIG = BASE / "config"
MEMORY = BASE / "memory"
CONVERSATIONS = MEMORY / "conversations"
ARCHIVE = MEMORY / "archive"

# === Файлы ядра ===
CORE_FILES = {
    "persona":      CONFIG / "persona_v1.2.md",
    "user_facts":   CONFIG / "user_facts.md",
    "sister_facts": CONFIG / "sister_facts.md",
}


class TwinCore:
    """
    Загрузка и управление ядром памяти Алины.

    Загружает .md файлы из config/, собирает из них системный промпт
    и предоставляет инструменты для добавления новых фактов.
    """

    def __init__(self):
        self.loaded = False
        self.core_data = {}
        self.errors = []
        self.base_path = BASE

    def load_core(self):
        """
        Загружает все .md файлы ядра в self.core_data.

        Returns:
            list: Список строк с описанием ошибок (пустой, если всё ок).
        """
        self.errors = []
        for name, path in CORE_FILES.items():
            if path.exists():
                self.core_data[name] = path.read_text(encoding="utf-8")
            else:
                self.errors.append(f"Файл не найден: {path}")
                self.core_data[name] = None
        self.loaded = not self.errors
        return self.errors

    def build_context(self):
        """
        Собирает системный промпт из файлов ядра.
        """
        if not self.loaded:
            self.load_core()

        parts = []

        order = [
            ("persona",      "=== ПЕРСОНА ==="),
            ("user_facts",   "=== ФАКТЫ О СОЗДАТЕЛЕ ==="),
            ("sister_facts", "=== ФАКТЫ О СТАРШЕЙ СЕСТРЕ ==="),
        ]

        for key, header in order:
            text = self.core_data.get(key)
            if text:
                parts.append(f"{header}\n{text}")
            else:
                parts.append(f"{header}\n(не загружено)")

        return "\n\n".join(parts)
    def add_fact(self, target, section, fact):
        """
        Добавляет факт в user_facts.md или sister_facts.md.

        Если секция с указанным заголовком уже существует — факт
        дописывается в конец секции. Если секции нет — она создаётся
        в конце файла.

        Args:
            target (str):  'user' — факты о создателе,
                           'sister' — факты о старшей сестре.
            section (str): Заголовок секции (например, '## Вкусы').
            fact (str):    Текст факта (без дефиса, добавляется автоматически).

        Returns:
            str: Сообщение о результате выполнения.
        """
        if target == "user":
            path = CORE_FILES["user_facts"]
        elif target == "sister":
            path = CORE_FILES["sister_facts"]
        else:
            return f"Неизвестный target: {target}"

        if not path.exists():
            return f"Файл не найден: {path}"

        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Ищем секцию по точному совпадению заголовка
        section_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section:
                section_idx = i
                break

        if section_idx is None:
            # Секция не найдена — добавляем в конец файла
            lines.append("")
            lines.append(section)
            lines.append(f"- {fact}")
        else:
            # Ищем конец секции (следующая ## или конец файла)
            insert_idx = len(lines)
            for i in range(section_idx + 1, len(lines)):
                if lines[i].startswith("## "):
                    insert_idx = i
                    break
            # Вставляем факт перед концом секции
            lines.insert(insert_idx, f"- {fact}")

        path.write_text("\n".join(lines), encoding="utf-8")
        return f"Факт добавлен: {target} / {section} / {fact}"

    def status(self):
        """
        Возвращает словарь со статусом ядра.

        Returns:
            dict: {
                'loaded': bool,
                'base_path': str,
                'core_files': {name: '✅'/'❌'},
                'conversations_saved': int
            }
        """
        result = {
            "loaded": self.loaded,
            "base_path": str(self.base_path),
            "core_files": {},
            "conversations_saved": 0,
        }
        for name, path in CORE_FILES.items():
            result["core_files"][name] = "✅" if path.exists() else "❌"
        if CONVERSATIONS.exists():
            result["conversations_saved"] = len(list(CONVERSATIONS.glob("*.json")))
        return result


# === Тестовый запуск ===
if __name__ == "__main__":
    print("TwinSisters Core — загрузка...\n")
    core = TwinCore()
    errors = core.load_core()

    if errors:
        print("❌ Ошибки:")
        for e in errors:
            print(f"  {e}")
    else:
        print("✅ Все файлы загружены.\n")

    print("Статус:")
    st = core.status()
    print(f"  loaded: {st['loaded']}")
    print(f"  base_path: {st['base_path']}")
    print(f"  core_files:")
    for name, status in st["core_files"].items():
        print(f"    {name}: {status}")
    print(f"  conversations_saved: {st['conversations_saved']}")

    context = core.build_context()
    print(f"\nКонтекст собран: {len(context)} символов")
    print(f"Превью (первые 200):\n{context[:200]}")
