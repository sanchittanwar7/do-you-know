"""DeepSeek answer generation and caption/comment assembly."""
import json

import requests

from .config import DEEPSEEK_KEY, DEEPSEEK_MODEL, DEEPSEEK_URL, FIXED_HASHTAGS

SYSTEM_PROMPT = (
    "You write Instagram trivia carousel content for the page 'do.you.know.7'. "
    "Given a question, produce TWO answers and THREE post-specific hashtags.\n"
    "- short_answer: at most 10 words, punchy, no preamble.\n"
    "- long_answer: at most 50 words, explain the WHY, end cleanly, no emoji.\n"
    "- hashtags: array of exactly 3 hashtags, each a short lowercase keyword or phrase "
    "(no spaces, no '#' prefix) relevant to this specific question, to boost reach "
    "for this post's topic.\n"
    'Return ONLY valid JSON: {"short_answer": "...", "long_answer": "...", '
    '"hashtags": ["...", "...", "..."]}'
)


QUESTION_PROMPT = (
    "You write Instagram trivia questions for the page 'do.you.know.7'. "
    "Return ONE surprising, curiosity-driving 'Do you know ...' question. "
    "Make it specific, factual, and answerable with one short answer and one "
    "long answer. No emoji, no preamble, no hashtags, no quotes around the text. "
    'Return ONLY valid JSON: {"question": "Do you know ..."}'
)


def generate_question():
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": QUESTION_PROMPT},
                {"role": "user", "content": "Give me a new trivia question."},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.9,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content)
    question = (data.get("question") or "").strip()
    if not question:
        raise RuntimeError("Empty question returned by model.")
    return question


def generate_answers(question: str):
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    # strip markdown fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content)
    hashtags = [str(h).strip().lstrip("#") for h in (data.get("hashtags") or [])][:3]
    return data["short_answer"].strip(), data["long_answer"].strip(), hashtags


def build_caption(question, hashtags=None):
    """Question only + 3 fixed + 3 post hashtags. Answers move to a comment."""
    parts = [question]
    tags = list(FIXED_HASHTAGS) + ["#" + str(h).lstrip("#") for h in (hashtags or [])]
    if tags:
        parts += ["", " ".join(tags)]
    return "\n".join(parts)


def build_comment(short_answer, long_answer):
    """Short + long answer combined, posted as the first comment."""
    return "\n\n".join(part for part in (short_answer, long_answer) if part)
