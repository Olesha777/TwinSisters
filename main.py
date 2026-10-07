"""
TwinSisters — пусковой файл.

Запускает ядро памяти, загружает модель из конфигурации (config/models.yaml),
открывает REPL-диалог. При выходе — сохраняет диалог и архивирует старые логи.

Размещение: TwinSisters/main.py (корень проекта)
Запуск:     python main.py
Зависимости: pyyaml (pip install pyyaml), llama-cpp-python
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# pyyaml — для чтения конфигурации моделей
try:
    import yaml
except ImportError:
    print("\u274c Не установлен pyyaml")
    print("   Установите: pip install pyyaml")
    sys.exit(1)

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from modules.core.core import TwinCore
from modules.core.brain import TwinBrain
from modules.core.sync import prune_sync

MODELS_DIR = BASE / "models"
CONV_DIR = BASE / "memory" / "conversations"
CONFIG_PATH = BASE / "config" / "models.yaml"

# Провайдеры (пока только local, api — заглушка на будущее)
PROVIDERS = {
    "local": "Локальная GGUF-модель",
    "api": "Внешний API (требуется ключ — пока недоступно)",
}


# =============================================================================
# Конфигурация
# =============================================================================

def load_config():
    """
    Загружает конфигурацию моделей из config/models.yaml.

    Returns:
        dict: Конфигурация с секциями 'models' и 'default', или None при ошибке.
    """
    if not CONFIG_PATH.exists():
        print(f"\u274c Конфиг не найден: {CONFIG_PATH}")
        print("   Создайте файл config/models.yaml с описанием моделей.")
        return None

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"\u274c Ошибка парсинга YAML: {e}")
        return None

    if not config or "models" not in config:
        print("\u274c Конфиг пуст или не содержит секцию 'models'.")
        return None

    return config


# =============================================================================
# Сохранение диалога
# =============================================================================

def save_dialog(messages):
    """Сохраняет диалог в memory/conversations/."""
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dialog_{timestamp}.json"
    filepath = CONV_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "messages": messages
        }, f, ensure_ascii=False, indent=2)
    print(f"   \U0001f4be Диалог сохранён: {filename}")


# =============================================================================
# Команды
# =============================================================================

def cmd_help():
    """Показывает список команд."""
    print("\n\U0001f4cb Команды:")
    print("   \\help     — этот список")
    print("   \\status  — состояние: ядро, модель, память")
    print("   \\context — размер системного промпта и истории")
    print("   \\model   — выбрать модель из конфигурации")
    print("   \\connect — выбрать провайдера (local / api)")
    print("   \\clear   — очистить историю диалога")
    print("   \\exit    — выход с сохранением")
    print()


def cmd_status(core, brain, messages, provider):
    """Показывает статус системы."""
    print()
    st = core.status()
    print(f"   Провайдер:          {provider}")
    print(f"   Ядро загружено:     {st['loaded']}")
    print(f"   Файлов ядра:")
    for name, status in st["core_files"].items():
        print(f"     {name}: {status}")
    print(f"   Диалогов сохранено: {st['conversations_saved']}")
    bst = brain.status()
    print(f"   Модель загружена:   {bst['loaded']}")
    print(f"   Модель:             {bst['name']} ({bst['model_name']})")
    print(f"   Формат чата:        {bst['chat_format']}")
    print(f"   Потоков CPU:        {bst['n_threads']}")
    print(f"   Размер контекста:   {bst['n_ctx']}")
    print(f"   Температура:        {bst['temperature']}")
    print(f"   Макс. токенов:      {bst['max_tokens']}")
    print(f"   Сообщений в диалоге: {len(messages)}")


def cmd_context(core, messages):
    """Показывает размер контекста."""
    context = core.build_context()
    print()
    print(f"   Размер системного промпта: {len(context)} символов")
    print(f"   Приблизительно токенов:    ~{len(context) // 4}")
    print(f"   Сообщений в истории:       {len(messages)}")


def cmd_model(brain, models_config, models_dir):
    """
    Выбор модели из конфигурации.

    Показывает модели из config/models.yaml с указанием формата чата
    и размера файла. Переключает через brain.switch_model с новым конфигом.
    """
    if not models_config:
        print("\n   \u274c В конфиге нет моделей.")
        return

    print("\n\U0001f4e6 Доступные модели:")
    current = brain.config.get("name", "?")
    for i, (name, cfg) in enumerate(models_config.items(), 1):
        marker = " \u2190 активна" if name == current else ""
        file_path = models_dir / cfg["file"]
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.0f} МБ"
        else:
            size_str = "\u274c не найден"
        chat_fmt = cfg.get("chat_format", "?")
        print(f"   {i}. {name} ({cfg['file']}, {size_str}, {chat_fmt}){marker}")

    print(f"\n   Текущая: {current}")
    print("   Введите номер модели (или Enter для отмены): ", end="", flush=True)

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not choice:
        return

    try:
        idx = int(choice) - 1
        names = list(models_config.keys())
        if 0 <= idx < len(names):
            new_name = names[idx]
            if new_name == current:
                print("   Эта модель уже активна.")
                return
            # Копируем конфиг и добавляем имя для отображения
            new_config = dict(models_config[new_name])
            new_config["name"] = new_name
            print(f"\n   \u23f3 Переключение на {new_name}...")
            if brain.switch_model(new_config, models_dir):
                print(f"   \u2705 Модель загружена: {new_name}")
            else:
                print("   \u274c Не удалось загрузить модель.")
        else:
            print("   Неверный номер.")
    except ValueError:
        print("   Нужно число.")


def cmd_connect(provider):
    """Выбор провайдера."""
    print("\n\U0001f50c Доступные провайдеры:")
    for key, desc in PROVIDERS.items():
        marker = " \u2190 активен" if key == provider else ""
        print(f"   {key}: {desc}{marker}")

    print(f"\n   Текущий: {provider}")
    print("   Введите имя провайдера (или Enter для отмены): ", end="", flush=True)

    try:
        choice = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return provider

    if not choice:
        return provider

    if choice in PROVIDERS:
        if choice == "api":
            print("   \u26a0\ufe0f  API-провайдер пока недоступен (требуется ключ).")
            return provider
        print(f"   \u2705 Провайдер: {choice}")
        return choice
    else:
        print(f"   Неизвестный провайдер: {choice}")
        print(f"   Доступные: {', '.join(PROVIDERS.keys())}")
        return provider


# =============================================================================
# Главная функция
# =============================================================================

def main():
    print("=" * 50)
    print("  TwinSisters \U0001f998")
    print("  Младшая сестра Алина — локальная версия")
    print("=" * 50)

    provider = "local"

    # 1. Загрузка конфигурации моделей
    print("\n\u2699\ufe0f  Загрузка конфигурации...")
    config = load_config()
    if not config:
        return

    models = config.get("models", {})
    default_name = config.get("default")

    if not models:
        print("\u274c В конфиге нет моделей.")
        return

    # Проверяем модель по умолчанию
    if not default_name or default_name not in models:
        print(f"\u26a0\ufe0f  Модель по умолчанию '{default_name}' не найдена.")
        default_name = list(models.keys())[0]
        print(f"   Используем первую: {default_name}")

    # Копируем конфиг и добавляем имя для отображения
    model_config = dict(models[default_name])
    model_config["name"] = default_name

    # 2. Загрузка ядра памяти
    print("\n\U0001f4d6 Загрузка ядра памяти...")
    core = TwinCore()
    errors = core.load_core()

    if errors:
        print("\u274c Ошибки загрузки ядра:")
        for e in errors:
            print(f"   {e}")
        print("   Продолжаем без некоторых файлов.")

    print("\u2705 Ядро памяти загружено.")
    context = core.build_context()
    print(f"\u2705 Контекст собран: {len(context)} символов")

    # 3. Загрузка модели
    print(f"\n\u23f3 Загрузка модели ({model_config['name']})...")
    print(f"   Файл: {model_config['file']}")
    print(f"   Формат: {model_config.get('chat_format', 'chatml')}")
    print(f"   Потоков CPU: {model_config.get('n_threads', 4)}")
    print(f"   Контекст: {model_config.get('n_ctx', 4096)} токенов")
    brain = TwinBrain(model_config, MODELS_DIR)
    if not brain.load():
        print("\u274c Не удалось загрузить модель.")
        return
    print("\u2705 Модель загружена.")

    # 4. REPL — диалог
    print(f"\n\U0001f4ac Диалог начат. Напиши что-нибудь.")
    print(f"   Команды начинаются с \\ — \\help для списка\n")

    messages = []

    while True:
        try:
            user_input = input("Ты: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        # Команды
        if user_input.startswith("\\"):
            cmd = user_input.lower()

            if cmd == "\\exit":
                break
            elif cmd == "\\status":
                cmd_status(core, brain, messages, provider)
            elif cmd == "\\context":
                cmd_context(core, messages)
            elif cmd == "\\model":
                cmd_model(brain, models, MODELS_DIR)
            elif cmd == "\\connect":
                provider = cmd_connect(provider)
            elif cmd == "\\clear":
                messages.clear()
                print("   \U0001f9f9 История диалога очищена.")
            elif cmd == "\\help":
                cmd_help()
            else:
                print(f"   Неизвестная команда: {user_input}")
                print(f"   Введите \\help для списка команд.")
            continue

        # Добавляем сообщение пользователя
        messages.append({"role": "user", "content": user_input})

        # Генерация ответа (стриминг — токены печатаются по мере генерации)
        print("Алина: ", end="", flush=True)
        try:
            response = brain.generate(context, messages)
            if not response:
                print("(пустой ответ)")
        except Exception as e:
            print(f"\n\u274c Ошибка генерации: {e}")
            continue

        # Добавляем ответ модели
        messages.append({"role": "assistant", "content": response})

    # 5. Выход — сохранение и архивация
    print("\n\U0001f44b Пока!")

    if messages:
        print("\U0001f4be Сохранение диалога...")
        save_dialog(messages)

    print("\U0001f4e6 Архивация...")
    prune_sync(limit=10)

    print("\nДо свидания! \U0001f998")


if __name__ == "__main__":
    main()
