"""App Store 仓库同步 — git clone/pull + 索引更新"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass

from .engine import REPOS_DIR, OFFICIAL_REPO


GIT_BIN = "/usr/bin/git"
SYNC_LOCK = "/tmp/ubunturouter-appstore-sync.lock"


@dataclass
class RepoInfo:
    name: str
    url: str
    branch: str = "main"
    local_path: Path = None
    last_sync: str = ""
    status: str = "unknown"  # unknown / syncing / ok / error
    app_count: int = 0
    format: str = "auto"     # auto / self / 1panel / openwrt


def _git_run(cmd: list, cwd: Path, timeout: int = 120) -> dict:
    """运行 git 命令"""
    try:
        r = subprocess.run(
            [GIT_BIN] + cmd,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(cwd) if cwd.exists() else None,
        )
        return {
            "success": r.returncode == 0,
            "stdout": r.stdout[-2000:] if r.stdout else "",
            "stderr": r.stderr[-2000:] if r.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timeout"}
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "git not found"}


def verify_repo_compatibility(repo_path: Path) -> dict:
    """验证仓库与应用商店兼容性
    
    检查：
    1. 仓库格式是否可识别 (self/1panel)
    2. 应用是否能在 Ubuntu Linux 上运行
    3. 至少有一个 docker-compose 应用
    """
    from .engine import _detect_repo_format

    if not repo_path.exists():
        return {"compatible": False, "reason": "仓库目录不存在"}

    fmt = _detect_repo_format(repo_path)
    if not fmt:
        return {"compatible": False, "reason": "无法识别仓库格式（未找到 app.yaml 或 data.yml）"}

    # 检查是否基于 Docker（即包含 docker-compose.yml）
    # 所有 UbuntuRouter 应用都通过 Docker 部署，这是兼容性前提
    compose_count = 0
    if fmt == "self":
        for item in repo_path.iterdir():
            if item.is_dir() and (item / "docker-compose.yml").exists():
                compose_count += 1
    elif fmt == "1panel":
        apps_dir = repo_path / "apps" if repo_path.name != "apps" else repo_path
        if not apps_dir.exists():
            return {"compatible": False, "reason": "仓库缺少 apps/ 目录"}
        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                for item in app_dir.iterdir():
                    if item.is_dir() and (item / "docker-compose.yml").exists():
                        compose_count += 1
                        break
                    if item.name == "docker-compose.yml":
                        compose_count += 1
                        break

    if compose_count == 0:
        return {"compatible": False, "reason": "仓库中没有 Docker Compose 应用（UbuntuRouter 需要 Docker 部署）"}

    return {
        "compatible": True,
        "format": fmt,
        "app_count": compose_count,
        "message": f"仓库兼容，识别为 {fmt} 格式，包含 {compose_count} 个 Docker 应用",
    }


def add_repo(name: str, url: str, branch: str = "main") -> dict:
    """添加第三方仓库（包含兼容性验证）"""
    repo_path = REPOS_DIR / name
    if repo_path.exists():
        return {"success": False, "error": f"仓库 '{name}' 已存在"}

    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    result = _git_run(
        ["clone", "-b", branch, "--depth", "1", url, str(repo_path)],
        REPOS_DIR, timeout=300
    )

    if not result["success"]:
        return {
            "success": False,
            "error": f"克隆失败: {result.get('stderr', '')[:200]}",
        }

    # 兼容性验证
    compat = verify_repo_compatibility(repo_path)
    if not compat["compatible"]:
        # 清理已克隆的目录
        import shutil
        shutil.rmtree(repo_path)
        return {"success": False, "error": f"仓库不兼容: {compat['reason']}"}

    return {
        "success": result["success"],
        "name": name,
        "url": url,
        "path": str(repo_path),
        "format": compat["format"],
        "app_count": compat["app_count"],
        "error": "",
    }


def remove_repo(name: str) -> dict:
    """删除本地仓库"""
    repo_path = REPOS_DIR / name
    if not repo_path.exists():
        return {"success": False, "error": f"仓库 '{name}' 不存在"}

    import shutil
    shutil.rmtree(repo_path)
    return {"success": True, "name": name}


def sync_repo(name: str) -> dict:
    """同步单个仓库（git pull）"""
    repo_path = REPOS_DIR / name
    if not repo_path.exists():
        return {"success": False, "error": f"仓库 '{name}' 不存在"}

    result = _git_run(["pull", "--ff-only"], repo_path, timeout=120)

    return {
        "success": result["success"],
        "name": name,
        "output": result["stdout"][:500],
        "error": result["stderr"][:500] if not result["success"] else "",
    }


def sync_all_repos() -> List[dict]:
    """同步所有仓库"""
    if not REPOS_DIR.exists():
        return []

    results = []
    for repo_dir in sorted(REPOS_DIR.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue
        result = sync_repo(repo_dir.name)
        results.append(result)

    return results


def list_repos() -> List[RepoInfo]:
    """列出所有已配置的仓库"""
    repos = []

    # 默认官方仓库
    official_path = REPOS_DIR / "official"
    repos.append(RepoInfo(
        name="official",
        url=OFFICIAL_REPO,
        local_path=official_path,
        status="ok" if official_path.exists() else "unknown",
    ))

    # 第三方仓库
    if REPOS_DIR.exists():
        for item in REPOS_DIR.iterdir():
            if not item.is_dir() or item.name.startswith(".") or item.name == "official":
                continue
            # 尝试读取 git remote
            git_dir = item / ".git"
            url = ""
            if git_dir.exists():
                r = _git_run(["remote", "get-url", "origin"], item)
                if r["success"]:
                    url = r["stdout"].strip()

            repos.append(RepoInfo(
                name=item.name,
                url=url or "unknown",
                local_path=item,
                status="ok" if url else "unknown",
            ))

    return repos


def ensure_official_repo() -> dict:
    """确保官方仓库已克隆"""
    repo_path = REPOS_DIR / "official"
    if repo_path.exists():
        return {"success": True, "action": "exists", "path": str(repo_path)}

    return add_repo("official", OFFICIAL_REPO)
