"""收藏图片 / catalog 同步进私密 GitHub（与医疗同一套 token）。

正式站：Volume 仅作短时缓存，真相在 GitHub。
本机：写仓库目录，由你 git push。
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

GITHUB_API = "https://api.github.com"
REPO_PICS_PREFIX = "收藏/数据/pics"
REPO_CATALOG_PATH = "收藏/数据/_meta/catalog.json"


def github_sync_enabled() -> bool:
    if not (os.environ.get("BILL_DATA_DIR") or "").strip():
        return False
    return bool(_token())


def _token() -> str:
    return (
        os.environ.get("HEALTH_GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or ""
    ).strip()


def _repo() -> str:
    return (os.environ.get("HEALTH_GITHUB_REPO") or "lllll0912/-").strip()


def _branch() -> str:
    return (os.environ.get("HEALTH_GITHUB_BRANCH") or "main").strip()


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bill-private-collection-sync",
    }


def _api(method: str, path: str, **kwargs: Any) -> requests.Response:
    url = f"{GITHUB_API}{path}"
    return requests.request(method, url, headers=_headers(), timeout=90, **kwargs)


def repo_pic_path(folder: str, filename: str) -> str:
    folder = (folder or "").replace("\\", "/").strip("/")
    name = (filename or "").replace("\\", "/").split("/")[-1]
    return f"{REPO_PICS_PREFIX}/{folder}/{name}"


def commit_collection_files(
    *,
    files: dict[str, bytes],
    message: str,
    delete_paths: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """
    一次 commit 写入/删除仓库路径。
    files: { repo_relpath: raw_bytes }
    delete_paths: 要删除的仓库相对路径
    """
    files = files or {}
    delete_paths = [p.replace("\\", "/").lstrip("/") for p in (delete_paths or []) if p]
    if not files and not delete_paths:
        return True, "无变更"
    if not _token():
        return False, "未配置 HEALTH_GITHUB_TOKEN，无法写入 GitHub"
    repo = _repo()
    branch = _branch()
    if "/" not in repo:
        return False, f"仓库名无效: {repo}"

    try:
        ref = _api("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        if ref.status_code != 200:
            return False, f"读取分支失败 ({ref.status_code}): {ref.text[:200]}"
        commit_sha = ref.json()["object"]["sha"]

        commit = _api("GET", f"/repos/{repo}/git/commits/{commit_sha}")
        if commit.status_code != 200:
            return False, f"读取提交失败 ({commit.status_code})"
        base_tree = commit.json()["tree"]["sha"]

        tree_items: list[dict[str, Any]] = []
        for path, raw in files.items():
            path = path.replace("\\", "/").lstrip("/")
            blob = _api(
                "POST",
                f"/repos/{repo}/git/blobs",
                json={
                    "content": base64.b64encode(raw).decode("ascii"),
                    "encoding": "base64",
                },
            )
            if blob.status_code not in (200, 201):
                return False, f"上传 blob 失败 {path}: {blob.status_code} {blob.text[:200]}"
            tree_items.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob.json()["sha"],
                }
            )

        for path in delete_paths:
            tree_items.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": None,
                }
            )

        tree = _api(
            "POST",
            f"/repos/{repo}/git/trees",
            json={"base_tree": base_tree, "tree": tree_items},
        )
        if tree.status_code not in (200, 201):
            return False, f"创建 tree 失败: {tree.status_code} {tree.text[:200]}"

        new_commit = _api(
            "POST",
            f"/repos/{repo}/git/commits",
            json={
                "message": message,
                "tree": tree.json()["sha"],
                "parents": [commit_sha],
            },
        )
        if new_commit.status_code not in (200, 201):
            return False, f"创建 commit 失败: {new_commit.status_code} {new_commit.text[:200]}"

        upd = _api(
            "PATCH",
            f"/repos/{repo}/git/refs/heads/{branch}",
            json={"sha": new_commit.json()["sha"]},
        )
        if upd.status_code != 200:
            return False, f"更新分支失败: {upd.status_code} {upd.text[:200]}"
        return True, new_commit.json().get("sha", "")[:12]
    except requests.RequestException as e:
        return False, f"网络错误: {e}"


def sync_uploads_to_github(
    *,
    uploads: dict[str, bytes],
    catalog: Optional[dict[str, Any]] = None,
    label: str = "",
) -> tuple[bool, str]:
    """仅上传图片到 GitHub（文字 catalog 不实时提交，靠 Volume 日备）。"""
    files = dict(uploads or {})
    if not files:
        return True, "无图片变更"
    name = (label or "upload").strip() or "upload"
    ok, detail = commit_collection_files(files=files, message=f"collection: upload {name}")
    if ok:
        invalidate_pics_index()
    return ok, detail


def sync_catalog_to_github(catalog: dict[str, Any], *, reason: str = "update catalog") -> tuple[bool, str]:
    catalog_bytes = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return commit_collection_files(
        files={REPO_CATALOG_PATH: catalog_bytes},
        message=f"collection: {reason}",
    )


def sync_delete_pic_to_github(folder: str, filename: str) -> tuple[bool, str]:
    path = repo_pic_path(folder, filename)
    ok, detail = commit_collection_files(
        files={},
        delete_paths=[path],
        message=f"collection: delete {folder}/{filename}",
    )
    if ok:
        invalidate_pics_index()
    return ok, detail


def fetch_github_file(repo_path: str) -> Optional[bytes]:
    """从 GitHub Contents API 拉取单个文件原始字节。"""
    if not _token():
        return None
    repo = _repo()
    branch = _branch()
    path = repo_path.replace("\\", "/").lstrip("/")
    try:
        r = _api(
            "GET",
            f"/repos/{repo}/contents/{path}",
            params={"ref": branch},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"])
        if data.get("download_url"):
            dl = requests.get(data["download_url"], timeout=90)
            if dl.status_code == 200:
                return dl.content
    except (requests.RequestException, ValueError, TypeError):
        return None
    return None


def list_github_pics(folder: str) -> list[dict[str, Any]]:
    """从本地缓存的 pics 索引取目录；必要时刷新一次整树索引。"""
    index = _load_pics_index(refresh_if_stale=True)
    folder = (folder or "").replace("\\", "/").strip("/")
    return list(index.get(folder) or [])


def load_all_github_pics() -> dict[str, list[dict[str, Any]]]:
    """返回完整 pics 索引（folder -> files）。"""
    return dict(_load_pics_index(refresh_if_stale=True))


def _pics_index_path() -> Path:
    data_dir = (os.environ.get("BILL_DATA_DIR") or "").strip()
    if data_dir:
        return Path(data_dir) / "collection" / "_meta" / "pics_index.json"
    return Path(__file__).resolve().parents[1] / "数据" / "_meta" / "pics_index.json"


def _load_pics_index(*, refresh_if_stale: bool = False) -> dict[str, list[dict[str, Any]]]:
    path = _pics_index_path()
    stale = True
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = float(data.get("fetched_at") or 0)
            stale = (time.time() - ts) > 600  # 10 分钟
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            data = {}
            stale = True
    if refresh_if_stale and (stale or not data.get("folders")):
        refreshed = refresh_pics_index()
        if refreshed:
            return refreshed
    folders = data.get("folders") if isinstance(data, dict) else None
    return folders if isinstance(folders, dict) else {}


def refresh_pics_index() -> dict[str, list[dict[str, Any]]]:
    """一次递归拉取 GitHub 上 收藏/数据/pics 目录树，写入缓存。避免每个作品单独打 API。"""
    if not _token():
        return {}
    repo = _repo()
    branch = _branch()
    try:
        ref = _api("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        if ref.status_code != 200:
            return {}
        commit_sha = ref.json()["object"]["sha"]
        commit = _api("GET", f"/repos/{repo}/git/commits/{commit_sha}")
        if commit.status_code != 200:
            return {}
        tree_sha = commit.json()["tree"]["sha"]
        tree = _api(
            "GET",
            f"/repos/{repo}/git/trees/{tree_sha}",
            params={"recursive": "1"},
        )
        if tree.status_code != 200:
            return {}
        prefix = f"{REPO_PICS_PREFIX}/"
        folders: dict[str, list[dict[str, Any]]] = {}
        for item in tree.json().get("tree") or []:
            if not isinstance(item, dict) or item.get("type") != "blob":
                continue
            path = (item.get("path") or "").replace("\\", "/")
            if not path.startswith(prefix):
                continue
            rel = path[len(prefix) :]
            if "/" not in rel:
                continue
            folder, name = rel.split("/", 1)
            if "/" in name:
                continue
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                continue
            folders.setdefault(folder, []).append(
                {"name": name, "size": int(item.get("size") or 0)}
            )
        for folder in folders:
            folders[folder] = sorted(folders[folder], key=lambda x: x["name"])
        out_path = _pics_index_path()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": time.time(), "folders": folders}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return folders
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return {}


def invalidate_pics_index() -> None:
    _pics_index_path().unlink(missing_ok=True)


def sync_status_label() -> Optional[str]:
    if not (os.environ.get("BILL_DATA_DIR") or "").strip():
        return "local"
    if github_sync_enabled():
        return "github"
    return "volume_only"
