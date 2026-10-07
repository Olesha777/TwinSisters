"""
TwinBrain — загрузка GGUF-модели и генерация ответов.

Использует llama-cpp-python для локального инференса.
Поддерживает несколько форматов чата через конфигурацию (chatml, llama3, ...).
Параметры модели берутся из config/models.yaml — в коде ничего не хардкодится.

Размещение: TwinSisters/modules/core/brain.py
Зависимости: llama-cpp-python
"""

import re
from pathlib import Path
from llama_cpp import Llama


# =============================================================================
# Форматы чата
# =============================================================================

def _format_chatml(system_prompt, messages, enable_thinking=True):
    """
    ChatML — формат Qwen3, Yi, и других моделей.
    """
    prompt = ""
    if system_prompt:
        prompt += "<|im_start|>system\n" + system_prompt + "<|im_end|>\n"
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        prompt += "<|im_start|>" + role + "\n" + content + "<|im_end|>\n"
    if not enable_thinking:
        prompt += "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    else:
        prompt += "<|im_start|>assistant\n"

    return prompt


CHAT_FORMATS = {
    "chatml": {
        "build": _format_chatml,
        "stop": ["<|im_end|>", "<|im_start|>"],
    },
}


# =============================================================================
# Очистка thinking-блоков и мусорных тегов
# =============================================================================

_THINK_OPEN = '<think'
_THINK_CLOSE = '</think>'
_THINK_PATTERN = re.compile(_THINK_OPEN + r'.*?' + _THINK_CLOSE + r'\s*', re.DOTALL)

# Мусорные теги, которые модель может генерировать
_GARBAGE_TAGS = [
    r'<\|im_\w+\|>',       # <|im_start|>, <|im_end|>, etc.
    r'</?output>',            # </output>, <output>
    r'<\|\w+:?[^|]*\|>',   # <|Imitation: ...|>, <|Thought: ...|>, <|Act: ...|>
]


def _strip_thinking(text):
    """
    Удаляет блоки размышлений Qwen3 и мусорные теги из текста.
    """
    # Удаляем закрывающий тег <think/> в начале (из префикса)
    text = re.sub(r'^\s*</think\s*/?>\s*', '', text)

    # Удаляем блок <think>...</think>
    if _THINK_OPEN in text and _THINK_CLOSE in text:
        text = _THINK_PATTERN.sub('', text)
    elif _THINK_OPEN in text:
        text = re.sub(r'<think\s*/?>', '', text, count=1)

    # Удаляем мусорные теги
    for pattern in _GARBAGE_TAGS:
        text = re.sub(pattern, '', text)

    # Удаляем пустые строки в начале
    text = re.sub(r'^\s+', '', text)

    return text.strip()


# =============================================================================
# TwinBrain
# =============================================================================

class TwinBrain:
    """
    Загружает GGUF-модель и генерирует ответы.
    """

    def __init__(self, model_config, models_dir):
        self.llm = None
        self._loaded = False
        self._apply_config(model_config, models_dir)

    def _apply_config(self, model_config, models_dir):
        self.config = model_config
        self.model_path = models_dir / model_config["file"]
        self.chat_format = model_config.get("chat_format", "chatml")
        self.n_threads = model_config.get("n_threads", 4)
        self.n_ctx = model_config.get("n_ctx", 4096)
        self.n_batch = model_config.get("n_batch", 512)
        self.max_tokens = model_config.get("max_tokens", 512)
        self.temperature = model_config.get("temperature", 0.6)
        self.top_p = model_config.get("top_p", 0.95)
        self.top_k = model_config.get("top_k", 20)
        self.repeat_penalty = model_config.get("repeat_penalty", 1.1)
        self.enable_thinking = model_config.get("enable_thinking", False)

    def load(self):
        """Загружает модель в память. Возвращает True при успехе."""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Модель не найдена: {self.model_path}\n"
                f"Положите GGUF-файл в папку models/ "
                f"или проверьте config/models.yaml"
            )

        try:
            self.llm = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=0,
                n_batch=self.n_batch,
                verbose=False,
            )
            self._loaded = True
            return True
        except Exception as e:
            print(f"\u274c Ошибка загрузки модели: {e}")
            return False

    def unload(self):
        """Выгружает модель из памяти."""
        if self.llm is not None:
            del self.llm
            self.llm = None
        self._loaded = False

    def switch_model(self, model_config, models_dir):
        """Выгружает текущую модель и загружает новую."""
        self.unload()
        self._apply_config(model_config, models_dir)
        return self.load()

    def generate(self, system_prompt, messages, stream=True):
        """
        Генерирует ответ на основе системного промпта и истории.

        Args:
            system_prompt: str — системный промпт (из ядра памяти)
            messages: list — история вида [{"role": ..., "content": ...}]
            stream: bool — печатать ли токены по мере генерации

        Returns:
            str — текст ответа (без блоков размышлений и мусорных тегов)
        """
        if not self._loaded:
            return "Модель не загружена."

        fmt = CHAT_FORMATS.get(self.chat_format)
        if not fmt:
            return f"Неизвестный формат чата: {self.chat_format}"

        prompt = fmt["build"](system_prompt, messages, self.enable_thinking)
        stop_tokens = fmt["stop"]


        try:
            if stream:
                response = self.llm.create_completion(
                    prompt=prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    stop=stop_tokens,
                    stream=True,
                )

                full_response = ""
                for chunk in response:
                    if "choices" in chunk and chunk["choices"]:
                        text = chunk["choices"][0].get("text", "")
                        if text:
                            print(text, end="", flush=True)
                            full_response += text

                print()  # перенос строки после стрима


                # Очищаем от thinking-блоков и мусорных тегов
                full_response = _strip_thinking(full_response)

                return full_response.strip()
            else:
                response = self.llm.create_completion(
                    prompt=prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    stop=stop_tokens,
                )
                text = response["choices"][0]["text"]
                text = _strip_thinking(text)

                return text.strip()
        except Exception as e:
            return f"Ошибка генерации: {e}"

    def status(self):
        """Возвращает статус модели и параметры генерации."""
        return {
            "loaded": self._loaded,
            "name": self.config.get("name", "?"),
            "model_name": self.model_path.name if self.model_path else None,
            "chat_format": self.chat_format,
            "n_threads": self.n_threads,
            "n_ctx": self.n_ctx,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
