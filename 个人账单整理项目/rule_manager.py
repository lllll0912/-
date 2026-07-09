import json
import os
import re
from typing import Dict, Any, List, Tuple, Optional


BASE_DIR = os.path.dirname(__file__)
RULE_FILE = os.path.join(BASE_DIR, "category_rules.json")

# 二级结构: { L1: { L2: pattern_regex_string, ... }, ... }
RulesMap = Dict[str, Dict[str, str]]

DEFAULT_RULES: Dict[str, RulesMap] = {
    "CONSUME_MAP": {
        "食品饮料": {"食品饮料": "吃|餐|水果|饮料|奶茶|外卖|超市|盒马|牛奶"},
        "交通": {"交通": "交通|打车|地铁|公交|高铁|机票|火车|车票"},
        "住宿": {"住宿": "酒店|住宿|民宿|钟点房"},
        "生活支出": {
            "医药": "药|诊",
            "日用家居": "日用|快递|房租",
            "其他生活": "生活",
        },
        "娱乐/运动": {"娱乐/运动": "攀岩|台球|桌游|电影|滑雪|健身|麻将"},
        "服饰": {"服饰": "衣|裤|鞋|袜|背心|外套"},
        "社交": {"社交": "礼物|生日|红包|请客"},
        "虚拟充值/通讯": {"通信费": "话费|vpn|会员|wifi|网费"},
        "亲友转账": {"亲友转账": "爸|妈|姐|学姐|亲友"},
    },
    "INCOME_MAP": {
        "工资": {"工资": "工资|奖学金|奖金|福利"},
        "亲友转账": {"亲友转账": "爸|妈|姐|学姐|亲友"},
        "二手物品售卖": {"二手物品售卖": "卖"},
    },
}


def _clean_pattern(pattern: str) -> str:
    """
    清洗规则字符串，避免出现空 token 导致“匹配空串”（如末尾带 | 会匹配所有明细）。
    - "a|b||" -> "a|b"
    - "  a | b  " -> "a|b"
    """
    text = str(pattern or "").strip()
    if not text:
        return ""
    tokens = [t.strip() for t in text.split("|") if t.strip()]
    return "|".join(tokens)


def _migrate_flat_to_nested(src: Dict[str, Any]) -> RulesMap:
    """兼容旧版扁平 { category: pattern } → 新版嵌套 { L1: { L2: pattern } }"""
    out: RulesMap = {}
    for key, val in src.items():
        if isinstance(val, dict):
            out[key] = {str(k): _clean_pattern(str(v)) for k, v in val.items()}
        elif isinstance(val, str):
            out[key] = {key: _clean_pattern(val)}
        else:
            out[key] = {key: _clean_pattern(str(val))}
    return out


def _normalize_rules(data: Dict[str, Any]) -> Dict[str, RulesMap]:
    consume = data.get("CONSUME_MAP", {}) if isinstance(data, dict) else {}
    income = data.get("INCOME_MAP", {}) if isinstance(data, dict) else {}
    if not isinstance(consume, dict):
        consume = {}
    if not isinstance(income, dict):
        income = {}
    return {
        "CONSUME_MAP": _migrate_flat_to_nested(consume),
        "INCOME_MAP": _migrate_flat_to_nested(income),
    }


def load_rules() -> Dict[str, RulesMap]:
    if not os.path.exists(RULE_FILE):
        save_rules(DEFAULT_RULES)
        return _normalize_rules(DEFAULT_RULES)
    try:
        with open(RULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = _normalize_rules(data)
        if not rules["CONSUME_MAP"] or not rules["INCOME_MAP"]:
            merged = {
                "CONSUME_MAP": rules["CONSUME_MAP"] or DEFAULT_RULES["CONSUME_MAP"],
                "INCOME_MAP": rules["INCOME_MAP"] or DEFAULT_RULES["INCOME_MAP"],
            }
            save_rules(merged)
            return merged
        return rules
    except Exception:
        save_rules(DEFAULT_RULES)
        return _normalize_rules(DEFAULT_RULES)


def save_rules(rules: Dict[str, Any]) -> None:
    normalized = _normalize_rules(rules)
    # 原子写入：避免保存时中断导致文件半写入，从而出现“保存/删除偶发失效”
    tmp = RULE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RULE_FILE)


# --------------- 查询类 ---------------

def l1_options(is_income: bool) -> List[str]:
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    return sorted(src.keys())


def l2_options(is_income: bool, l1: str = "") -> List[str]:
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    if l1:
        return sorted(src.get(l1, {}).keys())
    out: List[str] = []
    for sub in src.values():
        out.extend(sub.keys())
    return sorted(set(out))


def category_options(is_income: bool) -> List[str]:
    """返回所有 L2 分类名（扁平列表，向下兼容）"""
    return l2_options(is_income)


def category_options_grouped(is_income: bool) -> List[Dict[str, Any]]:
    """返回 [{l1: str, l2s: [str, ...]}, ...] 用于 <optgroup> UI"""
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    out = []
    for l1_name in sorted(src.keys()):
        l2s = sorted(src[l1_name].keys())
        out.append({"l1": l1_name, "l2s": l2s})
    return out


def l2_to_l1(category_l2: str, is_income: bool) -> str:
    """根据 L2 名反查 L1。未找到返回空串。"""
    category_l2 = (category_l2 or "").strip()
    if not category_l2:
        return ""
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    for l1_name, subs in src.items():
        if category_l2 in subs:
            return l1_name
    return ""


def is_known_category(name: str, is_income: bool) -> bool:
    """L2 名是否在当前字典（仅键名，不做正则匹配）。"""
    name = (name or "").strip()
    if not name:
        return False
    if name in ("待分类", "待分类收入"):
        return True
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    for subs in src.values():
        if name in subs:
            return True
    return False


def is_known_l1(name: str, is_income: bool) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    return name in src


# --------------- 推断 ---------------

def infer_category(detail: str, is_income: bool) -> Tuple[str, str]:
    """返回 (l1, l2)。未匹配返回 ('待分类','待分类') 或 ('待分类收入','待分类收入')。"""
    detail = (detail or "").strip()
    pending = ("待分类收入", "待分类收入") if is_income else ("待分类", "待分类")
    if detail == "":
        return pending
    rules = load_rules()
    src = rules["INCOME_MAP"] if is_income else rules["CONSUME_MAP"]
    for l1_name, subs in src.items():
        for l2_name, pattern in subs.items():
            if not pattern:
                continue
            try:
                if re.search(pattern, detail, re.IGNORECASE):
                    return (l1_name, l2_name)
            except re.error:
                continue
    return pending


# --------------- 学习 ---------------

def learn_exact_detail(detail: str, category_l2: str, is_income: bool, category_l1: str = "") -> bool:
    detail = (detail or "").strip()
    category_l2 = (category_l2 or "").strip()
    if not detail or not category_l2:
        return False
    if category_l2 in ("待分类", "待分类收入"):
        return False

    rules = load_rules()
    key = "INCOME_MAP" if is_income else "CONSUME_MAP"
    src = rules[key]

    target_l1 = (category_l1 or "").strip()
    if not target_l1:
        target_l1 = l2_to_l1(category_l2, is_income)
    if not target_l1:
        target_l1 = category_l2

    if target_l1 not in src:
        src[target_l1] = {}
    if category_l2 not in src[target_l1]:
        src[target_l1][category_l2] = ""

    escaped = re.escape(detail)
    existing = src[target_l1][category_l2] or ""
    tokens = [t for t in existing.split("|") if t]
    if escaped in tokens:
        return False
    tokens.append(escaped)
    src[target_l1][category_l2] = _clean_pattern("|".join(tokens))
    save_rules(rules)
    return True


# --------------- 管理 ---------------

def list_rule_rows(is_income: bool) -> List[Dict[str, str]]:
    rules = load_rules()
    key = "INCOME_MAP" if is_income else "CONSUME_MAP"
    rows = []
    for l1_name in sorted(rules[key].keys()):
        subs = rules[key][l1_name]
        for l2_name in sorted(subs.keys()):
            rows.append({"l1": l1_name, "l2": l2_name, "pattern": subs[l2_name] or ""})
    return rows


def upsert_rule(l1: str, l2: str, pattern: str, is_income: bool) -> None:
    l1 = (l1 or "").strip()
    l2 = (l2 or "").strip()
    if not l1 or not l2:
        return
    rules = load_rules()
    key = "INCOME_MAP" if is_income else "CONSUME_MAP"
    if l1 not in rules[key]:
        rules[key][l1] = {}
    # 业务适配：保证“一级可直接作为二级值”始终成立
    if l1 not in rules[key][l1]:
        rules[key][l1][l1] = ""
    rules[key][l1][l2] = _clean_pattern(pattern or "")
    save_rules(rules)


def delete_rule(l1: str, l2: str, is_income: bool) -> None:
    l1 = (l1 or "").strip()
    l2 = (l2 or "").strip()
    if not l1 or not l2:
        return
    rules = load_rules()
    key = "INCOME_MAP" if is_income else "CONSUME_MAP"
    if l1 in rules[key] and l2 in rules[key][l1]:
        del rules[key][l1][l2]
        if not rules[key][l1]:
            del rules[key][l1]
        save_rules(rules)
