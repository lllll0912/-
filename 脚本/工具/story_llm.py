"""调用 OpenAI 兼容大模型，生成/润色结构化诗境解读。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

STORY_KEYS = (
    "source",
    "full_poem",
    "background",
    "life_state",
    "poem_mood",
    "why_write",
    "interpretation",
    "meaning",
)


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = v.strip().strip('"').strip("'")
    except OSError:
        return


def llm_configured() -> bool:
    load_env()
    return bool(os.environ.get("POEM_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _client_config() -> tuple[str, str, str]:
    load_env()
    api_key = os.environ.get("POEM_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    base_url = (
        os.environ.get("POEM_LLM_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://open.bigmodel.cn/api/paas/v4"
    ).rstrip("/")
    model = os.environ.get("POEM_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "glm-4-flash"
    return api_key, base_url, model


def _chat_completions_url(base_url: str) -> str:
    """兼容 DeepSeek(.../v1) 与智谱(.../paas/v4)。"""
    base = base_url.rstrip("/")
    if base.endswith("/v1") or base.endswith("/v4") or "/paas/v4" in base:
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


SYSTEM_PROMPT = """你是古典诗词学者。根据用户给出的名句，以及可能附带的检索资料与草稿，输出 JSON 对象，字段严格为：
- source: 出处，格式如「宋 · 苏轼《水调歌头》」
- full_poem: 全诗或全词正文，保留换行；查不到则只写名句
- background: 作者生平与时代背景（完整、准确，可 150-400 字；勿无故截断）
- life_state: 写这首诗时，作者大致处在怎样的生活状态/处境（80-180 字）
- poem_mood: 这首诗想表达怎样的生活状态、心情或生命感受（80-180 字）
- why_write: 作者为何要写这首诗（动机、触机、想留下什么）（80-160 字）
- interpretation: 对名句及上下文的解读（120-250 字）
- meaning: 今日读它，能带走什么余味（60-120 字）

要求：
1. 语言优美、面向普通读者；life_state / poem_mood / why_write / interpretation / meaning 必须重新撰写，禁止原样照抄草稿里的套话模板。
2. 若草稿里出现「更像把眼前一事一景」「可反复进入的生活状态」「多半不是为了说明一件事」等套话，请彻底改写。
3. 若检索资料与名句明显不符，以你的学识纠正，并在 source 中诚实标注。
4. 史实不确定时，用「或」「大约」「据传」等措辞，不要编造精确年月。
5. 只输出 JSON，不要 markdown 代码块。"""


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group())
    return json.loads(text)


def enrich_story_with_llm(
    line: str,
    draft: dict[str, str],
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    api_key, base_url, model = _client_config()
    if not api_key:
        return draft

    # 传给模型的检索资料去掉过长传记，避免超上下文；传记仍留在 draft.background
    meta_for_llm = None
    if meta:
        meta_for_llm = dict(meta)
        bio = str(meta_for_llm.get("author_bio") or "")
        if len(bio) > 800:
            meta_for_llm["author_bio"] = bio[:800] + "…"

    # 给模型的草稿：事实字段保留，解读字段只给摘要，避免它照抄模板
    draft_for_llm = {
        "source": str(draft.get("source") or "").strip(),
        "full_poem": str(draft.get("full_poem") or "").strip()[:1200],
        "background": str(draft.get("background") or "").strip()[:1200],
    }

    user_parts = [
        f"名句：{line}",
        "请重点重写 life_state、poem_mood、why_write、interpretation、meaning。",
    ]
    if meta_for_llm:
        user_parts.append(f"检索资料：{json.dumps(meta_for_llm, ensure_ascii=False)[:3500]}")
    user_parts.append(f"已知事实草稿：{json.dumps(draft_for_llm, ensure_ascii=False)[:3500]}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        "temperature": 0.55,
    }

    url = _chat_completions_url(base_url)
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    data = extract_json_from_text(content)

    # 事实字段：模型缺了就用草稿；解读字段：优先用模型
    factual = ("source", "full_poem", "background")
    interpretive = ("life_state", "poem_mood", "why_write", "interpretation", "meaning")
    out: dict[str, str] = {}
    for key in factual:
        val = str(data.get(key) or draft.get(key) or "").strip()
        if val:
            out[key] = val
    for key in interpretive:
        val = str(data.get(key) or "").strip()
        if val:
            out[key] = val
        elif str(draft.get(key) or "").strip():
            out[key] = str(draft.get(key)).strip()

    draft_bg = str(draft.get("background") or "").strip()
    out_bg = str(out.get("background") or "").strip()
    if draft_bg and len(draft_bg) > len(out_bg) + 80:
        out["background"] = draft_bg
    return out or draft