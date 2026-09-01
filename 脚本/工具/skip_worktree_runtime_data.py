"""为本机已追踪的运行态/大图设置 skip-worktree，避免落后本地覆盖 GitHub。"""

from __future__ import annotations

import subprocess
import sys


ROOTS = [
    "账单/数据",
    "喝水/数据",
    "日志/数据",
    "诗词/数据",
    "收藏/数据/pics",
    "收藏/数据/_meta/catalog.json",
    "收藏/数据/_meta/lookup_cache.json",
    "收藏/数据/_meta/pics_index.json",
    "医疗/数据",
]

# 仍允许正常追踪的占位/说明（不 skip）
KEEP_SUFFIXES = (
    "/.gitkeep",
    "catalog.empty.json",
    "说明.md",
    "README.md",
    "schema.md",
)
KEEP_EXACT = {
    "诗词/数据/README.md",
    "医疗/数据/说明.md",
    "收藏/数据/_meta/catalog.empty.json",
}


def _decode(p: bytes) -> str:
    return p.decode("utf-8", "replace").replace("\\", "/")


def _is_keeper(path: str) -> bool:
    if path in KEEP_EXACT:
        return True
    if path.endswith(KEEP_SUFFIXES):
        return True
    # 医疗说明文档
    if "/_meta/" in path and path.endswith(".md"):
        return True
    return False


def main() -> int:
    paths: list[bytes] = []
    for root in ROOTS:
        out = subprocess.check_output(["git", "ls-files", "-z", "--", root])
        paths.extend([p for p in out.split(b"\0") if p])

    for i in range(0, len(paths), 50):
        batch = paths[i : i + 50]
        subprocess.run(["git", "update-index", "--skip-worktree", "--"] + batch, check=False)

    keepers = [p for p in paths if _is_keeper(_decode(p))]
    for i in range(0, len(keepers), 50):
        batch = keepers[i : i + 50]
        subprocess.run(["git", "update-index", "--no-skip-worktree", "--"] + batch, check=False)

    skipped = len(paths) - len(keepers)
    print(f"tracked candidates: {len(paths)}")
    print(f"skip-worktree: {skipped}")
    print(f"keepers (still normal): {len(keepers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
