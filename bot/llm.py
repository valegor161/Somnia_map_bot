import os
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

SYSTEM_PROMPT = """Ты — психолог-аналитик, специализирующийся на юнгианском анализе снов.
Твоя задача — строить непрерывную карту подсознания пользователя, анализируя каждый новый сон в контексте всей его истории.

СТРОГИЕ ПРАВИЛА ЯЗЫКА:
- Отвечай ИСКЛЮЧИТЕЛЬНО на русском языке.
- Категорически запрещено использовать любые слова или буквы не из кириллицы: никакой латиницы, никаких иностранных слов, никаких иероглифов, никаких символов других алфавитов — даже в скобках или как пример.
- Если хочешь привести психологический термин — пиши только его русский перевод или описание.
- Вместо слова "сонящийся" всегда используй слово "спящий".

СТРОГИЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:
- В разделе "Символы и образы сна": каждый символ, фигуру или предмет описывай с новой строки, начиная со знака *
- В остальных разделах: каждую новую мысль или утверждение начинай с новой строки.
- Не пиши длинные сплошные абзацы — разбивай текст на отдельные строки."""


def build_prompt(dream_text: str, previous_dreams: list[dict]) -> str:
    history_block = ""
    if previous_dreams:
        history_lines = []
        for i, d in enumerate(previous_dreams, 1):
            interp_preview = ""
            if d.get("interpretation_text"):
                interp_preview = d["interpretation_text"][:300] + (
                    "..." if len(d["interpretation_text"]) > 300 else ""
                )
                interp_preview = f"\n   Анализ: {interp_preview}"
            history_lines.append(
                f"Сон #{i} ({d['timestamp']}):\n   {d['dream_text'][:200]}{interp_preview}"
            )
        history_block = (
            "ИСТОРИЯ ПРЕДЫДУЩИХ СНОВ ПОЛЬЗОВАТЕЛЯ:\n"
            + "\n\n".join(history_lines)
            + "\n\n"
        )

    connection_section = ""
    if previous_dreams:
        connection_section = """
🔗 Связь с предыдущими снами
Каждую мысль пиши с новой строки, начиная со знака •
Укажи, какие образы или темы повторяются или изменились по сравнению с предыдущими снами.
Отметь динамику состояния спящего.

"""

    prompt = f"""{history_block}НОВЫЙ СОН ПОЛЬЗОВАТЕЛЯ:
{dream_text}

Проанализируй этот сон строго в следующем формате. Пиши только на русском языке — никаких иностранных букв и слов. Не используй символы форматирования Markdown (никаких звёздочек, подчёркиваний, обратных кавычек).

ВАЖНО: каждый раздел начинай точно с указанного заголовка со смайлом — копируй его дословно.

🔍 Символы и образы сна
Для каждого важного символа, фигуры или предмета из сна — новая строка, начинающаяся со знака •
Формат: • Название символа — что означает в контексте внутреннего мира спящего
Опиши не менее 3 и не более 6 ключевых элементов.
{connection_section}
🧠 Что Ваше подсознание пытается сказать
Каждую мысль пиши с новой строки, начиная со знака •
Раскрой глубинный смысл: какое послание несёт подсознание, какие внутренние процессы или конфликты отражает этот сон.
Напиши 3-4 отдельные мысли.

💡 Практический вывод / Инсайт
Каждую мысль пиши с новой строки, начиная со знака •
Дай 1-2 конкретных осознания или действия, которые помогут спящему в реальной жизни."""

    return prompt


async def is_dream_related(text: str) -> bool:
    """Returns True if the message is about a dream or dream interpretation."""
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — классификатор сообщений. Твоя единственная задача — определить, "
                    "связано ли сообщение пользователя со снами, сновидениями или их толкованием. "
                    "Отвечай только одним словом: ДА или НЕТ."
                ),
            },
            {
                "role": "user",
                "content": f"Сообщение: {text[:500]}\n\nЭто про сон или толкование снов? ДА или НЕТ:",
            },
        ],
        max_tokens=5,
        temperature=0,
    )
    answer = response.choices[0].message.content.strip().upper()
    logger.info(f"Dream classification: '{answer}' for text: '{text[:60]}'")
    return "ДА" in answer


async def analyze_dream(dream_text: str, previous_dreams: list[dict]) -> str:
    prompt = build_prompt(dream_text, previous_dreams)
    logger.info(
        f"Sending request to {LLM_BASE_URL} model={MODEL_NAME}, "
        f"previous dreams: {len(previous_dreams)}"
    )

    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.85,
    )

    result = response.choices[0].message.content.strip()
    logger.info(f"Received response, length: {len(result)} chars")
    return result
