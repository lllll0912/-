import uuid
from typing import Dict, List, Any, Optional


_STORE: Dict[str, Dict[str, Any]] = {}


def create_preview(meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    token = uuid.uuid4().hex
    _STORE[token] = {"meta": meta, "rows": rows}
    return token


def get_preview(token: str) -> Optional[Dict[str, Any]]:
    return _STORE.get(token)


def update_preview(token: str, rows: List[Dict[str, Any]]) -> None:
    if token in _STORE:
        _STORE[token]["rows"] = rows


def pop_preview(token: str) -> Optional[Dict[str, Any]]:
    return _STORE.pop(token, None)

