"""把医疗上传同步进私密 GitHub（正式站手机上传用）。"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Optional

import requests

GITHUB_API = "https://api.github.com"


def github_sync_enabled() -> bool:
    """仅正式站（有 BILL_DATA_DIR）且配置了 token 时启用。"""
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
        "User-Agent": "bill-private-health-sync",
    }


def _api(method: str, path: str, **kwargs: Any) -> requests.Response:
    url = f"{GITHUB_API}{path}"
    return requests.request(method, url, headers=_headers(), timeout=60, **kwargs)


def commit_health_files(
    *,
    files: dict[str, bytes],
    message: str,
) -> tuple[bool, str]:
    """
    一次 commit 写入多个仓库路径（相对仓库根，如 医疗/数据/...）。
    files: { repo_relpath: raw_bytes }
    """
    if not files:
        return True, "无文件"
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

        tree_items: list[dict[str, str]] = []
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


def sync_upload_to_github(
    *,
    github_path: str,
    file_bytes: bytes,
    catalog: dict[str, Any],
    exam_name: str = "",
) -> tuple[bool, str]:
    """上传原件 + catalog 进 GitHub。"""
    catalog_path = "医疗/数据/_meta/catalog.json"
    catalog_bytes = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    leaf = github_path.replace("\\", "/").rsplit("/", 1)[-1]
    name = (exam_name or leaf).strip() or "材料"
    ok, detail = commit_health_files(
        files={
            github_path.replace("\\", "/"): file_bytes,
            catalog_path: catalog_bytes,
        },
        message=f"health: upload {name}",
    )
    return ok, detail


def sync_catalog_to_github(catalog: dict[str, Any], *, reason: str = "update catalog") -> tuple[bool, str]:
    catalog_path = "医疗/数据/_meta/catalog.json"
    catalog_bytes = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return commit_health_files(
        files={catalog_path: catalog_bytes},
        message=f"health: {reason}",
    )


def sync_status_label() -> Optional[str]:
    """给模板提示用：local / github / volume_only。"""
    if not (os.environ.get("BILL_DATA_DIR") or "").strip():
        return "local"
    if github_sync_enabled():
        return "github"
    return "volume_only"
