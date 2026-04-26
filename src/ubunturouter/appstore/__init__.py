"""App Store 引擎 — 模块入口"""
from .engine import (
    AppManifest, parse_manifest, scan_apps, scan_all_repos,
    get_installed_apps, get_categories, search_apps,
    APPS_BASE, REPOS_DIR, INSTALLED_DIR, DATA_DIR, OFFICIAL_REPO,
)
from .repo import (
    RepoInfo, add_repo, remove_repo, sync_repo,
    sync_all_repos, list_repos, ensure_official_repo,
)
from .installer import precheck, install
from .updater import update, uninstall
