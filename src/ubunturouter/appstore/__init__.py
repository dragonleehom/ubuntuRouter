"""App Store 引擎 — 模块入口"""
from .engine import (
    AppManifest, parse_manifest, parse_onepanel_manifest, scan_apps, scan_all_repos,
    get_installed_apps, get_categories, search_apps, _detect_repo_format,
    APPS_BASE, REPOS_DIR, INSTALLED_DIR, DATA_DIR, OFFICIAL_REPO, REPO_FORMATS,
)
from .repo import (
    RepoInfo, add_repo, remove_repo, sync_repo,
    sync_all_repos, list_repos, ensure_official_repo,
    verify_repo_compatibility,
)
from .installer import precheck, install
from .updater import update, uninstall, start_app, stop_app
