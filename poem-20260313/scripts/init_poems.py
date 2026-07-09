import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.connector import get_cursor


POEM_FILE = ROOT_DIR / "poem.txt"


def create_tables() -> None:
    """在 teacher_db 中创建诗句及收藏相关表。"""
    with get_cursor() as cur:
        # 主表：每日诗句
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS poems (
                id INT AUTO_INCREMENT PRIMARY KEY,
                poem_date DATE NULL,
                content TEXT NOT NULL,
                done TINYINT(1) NOT NULL DEFAULT 0,
                done_date DATE NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4
            """
        )

        # 收藏表：记录每个用户收藏了哪些诗句
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS poem_favorites (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                poem_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_user_poem (user_id, poem_id),
                CONSTRAINT fk_poem_fav_poem
                  FOREIGN KEY (poem_id) REFERENCES poems(id)
                  ON DELETE CASCADE
            ) CHARACTER SET utf8mb4
            """
        )


def normalise_date(raw: str) -> Optional[datetime]:
    """将文本中的日期字符串转换为 datetime.date。"""
    s = raw.strip()
    if not s:
        return None

    # 20210-03-05 -> 2021-03-05
    m = re.fullmatch(r"20210-(\d{2})-(\d{2})", s)
    if m:
        return datetime.strptime(f"2021-{m.group(1)}-{m.group(2)}", "%Y-%m-%d")

    # 2021-6-20 / 2021-06-2 等
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return datetime(int(y), int(mo), int(d))

    # 12-03 -> 默认视为 2021-12-03
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", s)
    if m:
        mo, d = m.groups()
        return datetime(2021, int(mo), int(d))

    return None


def extract_content(line: str) -> Optional[str]:
    """从一行中抽取诗句内容。"""
    s = line.strip()
    if not s:
        return None

    # 中文引号
    if "“" in s and "”" in s:
        start = s.find("“") + 1
        end = s.rfind("”")
        if start < end:
            return s[start:end].strip()

    # 英文引号
    if '"' in s:
        start = s.find('"') + 1
        end = s.rfind('"')
        if start < end:
            return s[start:end].strip()

    # 普通行，当作整句诗词（避免前言被错误识别，后面有额外保护逻辑）
    return s


def load_poems_from_text() -> List[Tuple[Optional[datetime], str]]:
    """从 poem.txt 中解析出 (日期, 诗句) 列表。"""
    text = POEM_FILE.read_text(encoding="utf-8")
    lines = [ln.rstrip("\n") for ln in text.splitlines()]

    items = []  # type: List[Tuple[Optional[datetime], str]]
    current_date = None  # type: Optional[datetime]
    started = False  # 在遇到第一行合法日期前，忽略所有内容，防止把前言当诗句

    for raw in lines:
        line = raw.strip()
        if not line or line == ".":
            continue

        dt = normalise_date(line)
        if dt:
            current_date = dt
            started = True
            continue

        if not started:
            # 开头的说明文字全部跳过
            continue

        # 特殊说明：例如“11-20号，我跟女朋友同居了...”之类的文字
        if "号，我跟女朋友" in line or "好梦诗词" in line:
            continue

        content = extract_content(line)
        if not content:
            continue

        # 保护：大于一定长度且明显是说明性文字的，这里简单用 “。” 且包含“朋友 / 同居”等关键词排除
        if any(k in content for k in ("同居", "朋友", "更新）")) and "。" in content:
            continue

        # 对于没有明确日期的尾部诗句，poem_date 记为 None
        items.append((current_date, content))

    return items


def insert_poems(items: List[Tuple[Optional[datetime], str]]) -> None:
    """将解析出的诗句批量插入数据库。"""
    if not items:
        return

    with get_cursor() as cur:
        # 先查出已存在的数据
        cur.execute("SELECT poem_date, content FROM poems")
        existing = {(row["poem_date"], row["content"]) for row in cur.fetchall()}

        to_insert = [
            (dt.date() if dt else None, content)
            for dt, content in items
            if (dt.date() if dt else None, content) not in existing
        ]

        if not to_insert:
            print("没有新的诗句需要插入。")
            return

        cur.executemany(
            "INSERT INTO poems (poem_date, content) VALUES (%s, %s)",
            to_insert,
        )
        print(f"已插入 {cur.rowcount} 条新诗句。")


def main() -> None:
    create_tables()
    items = load_poems_from_text()
    print(f"从文本中解析出 {len(items)} 条诗句。")
    insert_poems(items)


if __name__ == "__main__":
    main()

