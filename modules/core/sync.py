"""
TwinSisters Sync — синхронизация диалогов.

Модуль отвечает за сохранение, подсчет и архивацию разговоров.
Реализует логику очистки папки conversations: оставляет заданное количество
самых свежих файлов, а остальные перемещает в архив (memory/archive).

Размещение: modules/core/sync.py
Пути вычисляются от корня проекта.

Основные функции:
    - get_conversation_count(): возвращает количество активных .json файлов.
    - prune_sync(limit=10): архивирует старые диалоги, оставляя лимит самых новых.
    - sync_status(): возвращает словарь со статусом синхронизации.
"""

from pathlib import Path
import shutil

# Вычисляем базовый путь относительно этого файла (modules/core/sync.py -> корень)
BASE = Path(__file__).resolve().parent.parent.parent
CONV_DIR = BASE / "memory" / "conversations"
ARCHIVE_DIR = BASE / "memory" / "archive"


def get_conversation_count():
    """Возвращает количество .json файлов в папке conversations."""
    if not CONV_DIR.exists():
        return 0
    return len([f for f in CONV_DIR.iterdir() if f.is_file() and f.suffix == ".json"])


def prune_sync(limit=10):
    """
    Архивирует старые диалоги.
    
    Оставляет 'limit' самых свежих файлов в conversations,
    остальные перемещает в archive.
    
    Args:
        limit (int): Количество самых свежих файлов, которые нужно оставить.
    """
    if not CONV_DIR.exists():
        print("   📁 Папка conversations не найдена.")
        return

    # Сортируем файлы по времени изменения (новые первыми)
    try:
        files = sorted(CONV_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
    except FileNotFoundError:
        return

    to_archive = files[limit:]

    if not to_archive:
        print(f"   📦 Лимит ({limit}) не превышен. Архивация не требуется.")
        return

    # Создаем папку архива, если нет
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    moved = 0
    for file in to_archive:
        dest = ARCHIVE_DIR / file.name
        
        # Защита от перезаписи: если файл уже есть в архиве, добавляем суффикс
        if dest.exists():
            dest = ARCHIVE_DIR / f"{file.stem}_archived_{file.suffix}"
            
        try:
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            print(f"   ⚠️ Ошибка при перемещении {file.name}: {e}")

    print(f"   📦 Архивировано {moved} файлов в {ARCHIVE_DIR}")


def sync_status():
    """Возвращает простой словарь со статусом синхронизации."""
    return {
        "conversations_active": get_conversation_count(),
        "conv_dir": str(CONV_DIR),
        "archive_dir": str(ARCHIVE_DIR)
    }
