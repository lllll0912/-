"""账单类型字典：仅一级类型（扁平 {类型名: 匹配规则}）。"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(__file__)
RULE_FILE = os.path.join(BASE_DIR, "category_rules.json")

# 扁平：{ 类型名: pattern }
RulesMap = Dict[str, str]

DEFAULT_RULES: Dict[str, RulesMap] = {
    "CONSUME_MAP": {
        "食品饮料": "吃|餐|水果|饮料|奶茶|外卖|超市|盒马|牛奶",
        "交通": "交通|打车|地铁|公交|高铁|机票|火车|车票",
        "住宿": "酒店|住宿|民宿|钟点房",
        "生活支出": "药|诊|日用|快递|房租|生活",
        "娱乐/运动": "攀岩|台球|桌游|电影|滑雪|健身|麻将",
        "服饰": "衣|裤|鞋|袜|背心|外套",
        "社交": "礼物|生日|红包|请客",
        "虚拟充值/通讯": "话费|vpn|会员|wifi|网费",
        "亲友转账": "爸|妈|姐|学姐|亲友",
    },
    "INCOME_MAP": {
        "工资": "工资|奖学金|奖金|福利",
        "亲友转账": "爸|妈|姐|学姐|亲友",
        "二手物品售卖": "卖",
    },
}


def _clean_pattern(pattern: str) -> str:
    text = str(pattern or "").strip()
    if not text:
        return ""
    tokens = [t.strip() for t in text.split("|") if t.strip()]
    # 去重保序
    seen = set()
    out = []
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return "|".join(out)


def _merge_patterns(*parts: str) -> str:
    return _clean_pattern("|".join(p for p in parts if p))


def collapse_nested_to_flat(src: Dict[str, Any]) -> Tuple[RulesMap, Dict[str, str]]:
    """
    将旧版嵌套 {L1: {L2: pattern}} 或扁平 {name: pattern} 收成单层。
    同时返回旧 L2→L1 映射，供历史记录迁移。
    """
    flat: RulesMap = {}
    l2_to_l1_map: Dict[str, str] = {}
    if not isinstance(src, dict):
        return flat, l2_to_l1_map

    for key, val in src.items():
        l1 = str(key).strip()
        if not l1:
            continue
        if isinstance(val, dict):
            merged = ""
            for l2_name, pattern in val.items():
                l2 = str(l2_name).strip()
                if not l2:
                    continue
                if l2 not in l2_to_l1_map:
                    l2_to_l1_map[l2] = l1
                merged = _merge_patterns(merged, str(pattern or ""))
            # 同名 L1 也映射到自身
            if l1 not in l2_to_l1_map:
                l2_to_l1_map[l1] = l1
            flat[l1] = _merge_patterns(flat.get(l1, ""), merged)
        elif isinstance(val, str):
            flat[l1] = _merge_patterns(flat.get(l1, ""), val)
            l2_to_l1_map[l1] = l1
        else:
            flat[l1] = _merge_patterns(flat.get(l1, ""), str(val))
            l2_to_l1_map[l1] = l1
    return flat, l2_to_l1_map


def _normalize_rules(data: Dict[str, Any]) -> Tuple[Dict[str, RulesMap], Dict[str, str]]:
    """返回 (规则, 合并后的旧L2→类型映射)。"""
    consume_raw = data.get("CONSUME_MAP", {}) if isinstance(data, dict) else {}
    income_raw = data.get("INCOME_MAP", {}) if isinstance(data, dict) else {}
    if not isinstance(consume_raw, dict):
        consume_raw = {}
    if not isinstance(income_raw, dict):
        income_raw = {}
    consume, map_c = collapse_nested_to_flat(consume_raw)
    income, map_i = collapse_nested_to_flat(income_raw)
    legacy = {}
    legacy.update(map_c)
    legacy.update(map_i)
    return {"CONSUME_MAP": consume, "INCOME_MAP": income}, legacy


def load_rules() -> Dict[str, RulesMap]:
    if not os.path.exists(RULE_FILE):
        save_rules(DEFAULT_RULES)
        return dict(DEFAULT_RULES)
    try:
        with open(RULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules, _ = _normalize_rules(data)
        if not rules["CONSUME_MAP"] or not rules["INCOME_MAP"]:
            merged = {
                "CONSUME_MAP": rules["CONSUME_MAP"] or dict(DEFAULT_RULES["CONSUME_MAP"]),
                "INCOME_MAP": rules["INCOME_MAP"] or dict(DEFAULT_RULES["INCOME_MAP"]),
            }
            save_rules(merged)
            return merged
        return rules
    except Exception:
        save_rules(DEFAULT_RULES)
        return dict(DEFAULT_RULES)


def peek_legacy_l2_map() -> Dict[str, str]:
    """旧二级→一级映射：优先旁路文件，其次从规则文件折叠结果。"""
    side = os.path.join(BASE_DIR, "legacy_l2_map.json")
    if os.path.exists(side):
        try:
            with open(side, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
    if not os.path.exists(RULE_FILE):
        return {}
    try:
        with open(RULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _, legacy = _normalize_rules(data)
        return legacy
    except Exception:
        return {}


def save_rules(rules: Dict[str, Any]) -> None:
    normalized, _ = _normalize_rules(rules if isinstance(rules, dict) else {})
    tmp = RULE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RULE_FILE)


# --------------- 查询 ---------------

def category_options(is_income: bool) -> List[str]:
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    return sorted(src.keys())


def l1_options(is_income: bool) -> List[str]:
    """兼容旧名：等同类型列表。"""
    return category_options(is_income)


def l2_options(is_income: bool, l1: str = "") -> List[str]:
    """兼容旧名：单层后与类型列表相同（忽略 l1）。"""
    return category_options(is_income)


def category_options_grouped(is_income: bool) -> List[Dict[str, Any]]:
    """兼容旧 UI：每组只有自身一个选项。"""
    return [{"l1": name, "l2s": [name]} for name in category_options(is_income)]


def l2_to_l1(category: str, is_income: bool) -> str:
    """
    兼容旧调用：已知类型返回自身；否则查一次磁盘上的遗留 L2 映射。
    """
    category = (category or "").strip()
    if not category:
        return ""
    if is_known_category(category, is_income) or is_known_l1(category, is_income):
        return category
    legacy = peek_legacy_l2_map()
    return legacy.get(category, "")


def is_known_category(name: str, is_income: bool) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    if name in ("待分类", "待分类收入"):
        return True
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    return name in src


def is_known_l1(name: str, is_income: bool) -> bool:
    return is_known_category(name, is_income)


# --------------- 推断 ---------------

def infer_category(detail: str, is_income: bool) -> Tuple[str, str]:
    """返回 (类型, 类型)。未匹配返回待分类。"""
    detail = (detail or "").strip()
    pending = ("待分类收入", "待分类收入") if is_income else ("待分类", "待分类")
    if detail == "":
        return pending
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    for name, pattern in src.items():
        if not pattern:
            continue
        try:
            if re.search(pattern, detail, re.IGNORECASE):
                return (name, name)
        except re.error:
            continue
    return pending


# --------------- 学习 ---------------

def learn_exact_detail(detail: str, category: str, is_income: bool, category_l1: str = "") -> bool:
    """把明细精确加入该类型的匹配规则。category_l1 参数保留兼容，忽略。"""
    detail = (detail or "").strip()
    category = (category or category_l1 or "").strip()
    if not detail or not category:
        return False
    if category in ("待分类", "待分类收入"):
        return False

    rules = load_rules()
    key = "INCOME_MAP" if is_income else "CONSUME_MAP"
    src = rules[key]
    if category not in src:
        src[category] = ""

    escaped = re.escape(detail)
    existing = src[category] or ""
    tokens = [t for t in existing.split("|") if t]
    if escaped in tokens:
        return False
    tokens.append(escaped)
    src[category] = _clean_pattern("|".join(tokens))
    save_rules(rules)
    return True


# --------------- 管理 ---------------

def list_rule_rows(is_income: bool) -> List[Dict[str, str]]:
    rules = load_rules()
    key = "INCOME_MAP" if is_income else "CONSUME_MAP"
    rows = []
    for name in sorted(rules[key].keys()):
        rows.append({"name": name, "l1": name, "l2": name, "pattern": rules[key][name] or ""})
    return rows


def upsert_rule(*args, **kwargs) -> None:
    """
    保存类型规则。
    - 新：upsert_rule(name, pattern, is_income)
    - 旧：upsert_rule(l1, l2, pattern, is_income) —— 写入一级名 l1（忽略细分 l2）
    """
    if len(args) >= 4:
        l1, _l2, pattern, is_income = args[0], args[1], args[2], args[3]
        name = str(l1 or _l2 or "").strip()
        pat = str(pattern or "")
        income = bool(is_income)
    elif len(args) == 3:
        name, pat, income = str(args[0] or "").strip(), str(args[1] or ""), bool(args[2])
    elif len(args) == 2:
        name, pat = str(args[0] or "").strip(), str(args[1] or "")
        income = bool(kwargs.get("is_income", False))
    else:
        name = str(kwargs.get("name") or kwargs.get("l1") or kwargs.get("l2") or "").strip()
        pat = str(kwargs.get("pattern") or "")
        income = bool(kwargs.get("is_income", False))
    if not name:
        return
    rules = load_rules()
    key = "INCOME_MAP" if income else "CONSUME_MAP"
    rules[key][name] = _clean_pattern(pat)
    save_rules(rules)


def delete_rule(*args, **kwargs) -> None:
    """
    - 新：delete_rule(name, is_income)
    - 旧：delete_rule(l1, l2, is_income)
    """
    if len(args) >= 3:
        l1, l2, is_income = args[0], args[1], args[2]
        name = str(l1 or l2 or "").strip()
        income = bool(is_income)
    elif len(args) == 2:
        name, income = str(args[0] or "").strip(), bool(args[1])
    else:
        name = str(kwargs.get("name") or kwargs.get("l1") or kwargs.get("l2") or "").strip()
        income = bool(kwargs.get("is_income", False))
    if not name:
        return
    rules = load_rules()
    key = "INCOME_MAP" if income else "CONSUME_MAP"
    if name in rules[key]:
        del rules[key][name]
        save_rules(rules)


def replace_rule_maps(
    consume_items: Optional[List[Dict[str, str]]] = None,
    income_items: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    一次性替换支出/收入类型字典（确认后整表写入，只 save 一次）。
    items: [{name, pattern}, ...]；空 name 跳过。
    返回 {changed, consume_count, income_count, error}。
    """
    def _build(items: Optional[List[Dict[str, str]]]) -> Tuple[Optional[RulesMap], str]:
        out: RulesMap = {}
        for it in items or []:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or "").strip()
            if not name:
                continue
            if name in out:
                return None, "类型名重复：{}".format(name)
            out[name] = _clean_pattern(it.get("pattern") or "")
        return out, ""

    consume_map, err = _build(consume_items)
    if err:
        return {"changed": False, "consume_count": 0, "income_count": 0, "error": err}
    income_map, err = _build(income_items)
    if err:
        return {"changed": False, "consume_count": 0, "income_count": 0, "error": err}

    rules = load_rules()
    old_c = rules.get("CONSUME_MAP") or {}
    old_i = rules.get("INCOME_MAP") or {}
    if consume_map is None:
        consume_map = dict(old_c)
    if income_map is None:
        income_map = dict(old_i)

    changed = consume_map != old_c or income_map != old_i
    if changed:
        rules["CONSUME_MAP"] = consume_map
        rules["INCOME_MAP"] = income_map
        save_rules(rules)
    return {
        "changed": changed,
        "consume_count": len(consume_map),
        "income_count": len(income_map),
        "error": "",
    }

