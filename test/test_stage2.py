"""
TwinSisters Test Stage 2 — проверка ядра памяти и синхронизации.

Этот тест проверяет две ключевые функции:
    1. add_fact() — запись фактов в user_facts.md и sister_facts.md.
    2. prune_sync() — архивация старых диалогов из conversations/ в archive/.

Размещение: test/test_stage2.py
Запуск:     python test/test_stage2.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы импортировать модули
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from modules.core.core import TwinCore
from modules.core.sync import prune_sync, get_conversation_count


def test_add_fact():
    """
    Тест 1: Проверка add_fact() из TwinCore.
    Добавляет тестовый факт в user_facts и sister_facts, проверяет запись.
    """
    print("🧪 Тест 1: Проверка add_fact()")

    core = TwinCore()
    core.load_core()

    # Добавляем тестовый факт в user_facts.md
    result_user = core.add_fact(
        "user",
        "## Тестовая секция",
        "Тестовый факт: любит тестировать скрипты поздно вечером"
    )
    print(f"   add_fact (user): {result_user}")

    # Добавляем тестовый факт в sister_facts.md
    result_sister = core.add_fact(
        "sister",
        "## Тестовая секция",
        "Тестовый факт: Алина любит debugging"
    )
    print(f"   add_fact (sister): {result_sister}")

    # Проверяем, что факты записались
    user_facts_path = BASE_DIR / "config" / "user_facts.md"
    sister_facts_path = BASE_DIR / "config" / "sister_facts.md"

    user_ok = "Тестовый факт" in user_facts_path.read_text(encoding="utf-8")
    sister_ok = "Тестовый факт" in sister_facts_path.read_text(encoding="utf-8")

    if user_ok:
        print("   ✅ Факт записан в user_facts.md")
    else:
        print("   ❌ Факт НЕ найден в user_facts.md")

    if sister_ok:
        print("   ✅ Факт записан в sister_facts.md")
    else:
        print("   ❌ Факт НЕ найден в sister_facts.md")

    print("   ⚠️  Не забудь удалить тестовые факты после проверки!\n")
    return user_ok and sister_ok


def test_prune_sync():
    """
    Тест 2: Проверка prune_sync() и архивации.
    Создаёт 51 тестовый диалог, запускает архивацию, проверяет результат.
    """
    print("🧪 Тест 2: Проверка prune_sync() и архивации")

    conv_dir = BASE_DIR / "memory" / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)

    # 1. Генерируем 51 файл, чтобы превысить лимит
    print(f"   Создаём 51 тестовый диалог в {conv_dir}...")
    for i in range(51):
        file_path = conv_dir / f"test_conv_{i:03d}.json"
        file_path.write_text(
            f'{{"id": "{i}", "messages": []}}', encoding="utf-8"
        )

    initial_count = get_conversation_count()
    print(f"   Было файлов: {initial_count}")

    # 2. Запускаем архивацию (оставляем 10)
    print("   Запускаем prune_sync(limit=10)...")
    try:
        prune_sync(limit=10)
        print("   ✅ prune_sync() выполнен.")
    except TypeError:
        prune_sync()
        print("   ✅ prune_sync() выполнен (без аргументов).")

    # 3. Проверяем результат
    final_count = get_conversation_count()
    print(f"   Стало файлов: {final_count}")

    if final_count <= 10:
        print("✅ Архивация прошла успешно! Лишние файлы перемещены в archive.")
        return True
    else:
        print("❌ Архивация не сработала. Количество файлов всё ещё больше 10.")
        return False


if __name__ == "__main__":
    print("🚀 Запуск тестов Этапа 2...\n")

    all_passed = True

    if not test_add_fact():
        all_passed = False

    if not test_prune_sync():
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ УПАЛИ. Проверь логи выше.")
    print("=" * 50)

    print("\n🧹 Очистка после тестов:")
    print("   PowerShell:")
    print("     del memory\\conversations\\test_conv_*.json")
    print("   И удали тестовую секцию из config\\user_facts.md и config\\sister_facts.md")
