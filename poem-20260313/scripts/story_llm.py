"""调用 OpenAI 兼容大模型，生成结构化诗境解读。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def llm_configured() -> bool:
    load_env()
    return bool(os.environ.get("POEM_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _client_config() -> tuple[str, str, str]:
    load_env()
    api_key = os.environ.get("POEM_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    base_url = (
        os.environ.get("POEM_LLM_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.deepseek.com"
    ).rstrip("/")
    model = os.environ.get("POEM_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "deepseek-chat"
    return api_key, base_url, model


SYSTEM_PROMPT = """你是古典诗词学者。根据用户给出的名句，以及可能附带的检索资料，输出 JSON 对象，字段严格为：
- source: 出处，格式如「宋 · 苏轼《水调歌头》」
- full_poem: 全诗或全词正文，保留换行
- background: 创作背景、时代环境与诗人处境（80-200字）
- interpretation: 对名句及上下文的解读（120-250字）
- meaning: 这句诗要表达什么、为何适合作为晚安诗（80-150字）

要求：内容准确、语言优美、面向普通读者；若检索资料与名句明显不符，以你的学识纠正；只输出 JSON，不要 markdown 代码块。"""


def enrich_story_with_llm(line: str, draft: dict[str, str], meta: Optional[dict[str, Any]] = None) -> dict[str, str]:
    api_key, base_url, model = _client_config()
    if not api_key:
        return draft

    user_parts = [f"名句：{line}"]
    if meta:
        user_parts.append(f"检索资料：{json.dumps(meta, ensure_ascii=False)[:2000]}")
    if draft:
        user_parts.append(f"草稿：{json.dumps(draft, ensure_ascii=False)}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }

    try:
        r = requests.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        out = {}
        for key in ("source", "full_poem", "background", "interpretation", "meaning"):
            val = str(data.get(key) or draft.get(key) or "").strip()
            if val:
                out[key] = val
        return out or draft
    except Exception:
        return draft


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group())
    return json.loads(text)
