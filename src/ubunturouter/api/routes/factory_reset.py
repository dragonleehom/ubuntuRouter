"""工厂重置 API: 恢复出厂设置与状态查询"""

import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── 常量路径 ──────────────────────────────────────────────────────

ETC_UBUNTUROUTER = Path("/etc/ubunturouter")
OPT_BACKUP = Path("/opt/ubunturouter/backup/factory-reset-snapshot")
OPT_APPS_INSTALLED = Path("/opt/ubunturouter/apps/installed")
OPT_APPS_REPOS = Path("/opt/ubunturouter/apps/repos")
NETPLAN_DIR = Path("/etc/netplan")

# ─── 请求/响应模型 ─────────────────────────────────────────────────


class FactoryResetRequest(BaseModel):
    """发起恢复出厂设置请求"""
    confirm: bool = False
    keep_network: bool = True
    reason: str = "user_request"


class FactoryResetResponse(BaseModel):
    """恢复出厂设置操作结果"""
    success: bool
    message: str
    snapshot_path: str = ""


class FactoryResetStatusResponse(BaseModel):
    """当前系统重置状态"""
    ready: bool
    last_reset: str | None = None
    config_count: int = 0
    installed_apps: int = 0


# ─── 辅助函数 ──────────────────────────────────────────────────────


def _check_root() -> None:
    """检查是否以 root 运行"""
    if os.geteuid() != 0:
        raise HTTPException(
            status_code=403,
            detail="需要 root 权限才能执行恢复出厂设置",
        )


def _create_snapshot() -> str:
    """备份当前 ubunturouter 配置文件到快照目录"""
    if not ETC_UBUNTUROUTER.exists():
        logger.warning("/etc/ubunturouter 不存在，跳过备份")
        return ""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_dir = OPT_BACKUP / timestamp

    try:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for item in ETC_UBUNTUROUTER.iterdir():
            dest = snapshot_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest)
        logger.info("配置快照已创建: %s", snapshot_dir)
        return str(snapshot_dir)
    except Exception as e:
        logger.error("创建快照失败: %s", e)
        raise HTTPException(status_code=500, detail=f"创建配置快照失败: {e}")


def _clear_etc_ubunturouter(keep_network: bool) -> int:
    """清空 /etc/ubunturouter/ 下所有文件（除网络配置外）"""
    if not ETC_UBUNTUROUTER.exists():
        return 0

    count = 0
    for item in ETC_UBUNTUROUTER.iterdir():
        # 如果 keep_network=True，跳过网络相关配置文件
        if keep_network and item.name in ("network", "interfaces", "netplan"):
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            count += 1
        except Exception as e:
            logger.warning("删除 %s 失败: %s", item, e)

    return count


def _reset_network() -> None:
    """重置网络配置：删除 /etc/netplan/*.yaml"""
    if not NETPLAN_DIR.exists():
        return
    for item in NETPLAN_DIR.iterdir():
        if item.suffix in (".yaml", ".yml"):
            try:
                item.unlink()
                logger.info("已删除网络配置: %s", item)
            except Exception as e:
                logger.warning("删除 %s 失败: %s", item, e)


def _clear_installed_apps() -> int:
    """清空应用安装记录（保留 repos/）"""
    if not OPT_APPS_INSTALLED.exists():
        return 0

    count = 0
    for item in OPT_APPS_INSTALLED.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            count += 1
        except Exception as e:
            logger.warning("删除 %s 失败: %s", item, e)

    return count


def _clean_docker_containers() -> dict:
    """清除所有 Docker 容器"""
    try:
        r = subprocess.run(
            ["docker", "ps", "-aq"],
            capture_output=True, text=True, timeout=15,
        )
        container_ids = r.stdout.strip().split()
        if not container_ids or (len(container_ids) == 1 and not container_ids[0]):
            return {"removed": 0, "message": "无运行中的容器"}

        rm_r = subprocess.run(
            ["docker", "rm", "-f"] + container_ids,
            capture_output=True, text=True, timeout=30,
        )
        return {
            "removed": len(container_ids),
            "message": rm_r.stdout.strip() or "容器已清除",
        }
    except FileNotFoundError:
        logger.info("Docker 未安装，跳过容器清理")
        return {"removed": 0, "message": "Docker 未安装"}
    except subprocess.TimeoutExpired:
        logger.warning("Docker 清理超时")
        return {"removed": 0, "message": "Docker 清理超时"}
    except Exception as e:
        logger.warning("Docker 清理失败: %s", e)
        return {"removed": 0, "message": f"Docker 清理失败: {e}"}


def _restart_uvicorn() -> None:
    """重启 uvicorn 服务"""
    try:
        subprocess.Popen(
            ["systemctl", "restart", "ubunturouter"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("已触发 uvicorn 服务重启")
    except Exception as e:
        logger.warning("重启 uvicorn 服务失败: %s", e)


def _get_last_reset_time() -> str | None:
    """获取最近一次出厂重置的快照时间"""
    if not OPT_BACKUP.exists():
        return None
    snapshots = sorted(OPT_BACKUP.iterdir())
    if not snapshots:
        return None
    # 从目录名解析时间戳
    try:
        ts = snapshots[-1].name
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (ValueError, IndexError):
        return None


def _count_config_files() -> int:
    """统计 /etc/ubunturouter/ 下的配置文件数量"""
    if not ETC_UBUNTUROUTER.exists():
        return 0
    return sum(1 for _ in ETC_UBUNTUROUTER.iterdir())


def _count_installed_apps() -> int:
    """统计已安装的应用数量"""
    if not OPT_APPS_INSTALLED.exists():
        return 0
    return sum(1 for item in OPT_APPS_INSTALLED.iterdir() if item.is_dir())


# ─── API 端点 ──────────────────────────────────────────────────────


@router.post("/factory-reset", response_model=FactoryResetResponse)
async def factory_reset(
    body: FactoryResetRequest,
    auth=Depends(require_auth),
):
    """发起系统恢复出厂设置

    校验确认 → 创建恢复点 → 清除配置 → 重启服务
    """
    # 1. 校验确认
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="请确认恢复出厂设置 (confirm=true)",
        )

    # 2. 检查 root 权限
    _check_root()

    logger.info(
        "开始恢复出厂设置: keep_network=%s, reason=%s",
        body.keep_network,
        body.reason,
    )

    # 3. 创建恢复点（备份当前配置）
    snapshot_path = _create_snapshot()

    # 4. 清除配置
    cleared_count = _clear_etc_ubunturouter(body.keep_network)

    if not body.keep_network:
        _reset_network()

    apps_cleared = _clear_installed_apps()
    docker_result = _clean_docker_containers()

    # 5. 重启服务
    _restart_uvicorn()

    message_parts = [
        "恢复出厂设置已完成",
        f"已清除 {cleared_count} 个配置文件",
    ]
    if not body.keep_network:
        message_parts.append("已重置网络配置")
    if apps_cleared > 0:
        message_parts.append(f"已清除 {apps_cleared} 个应用记录")
    if docker_result["removed"] > 0:
        message_parts.append(f"已移除 {docker_result['removed']} 个容器")

    message = "，".join(message_parts)

    return FactoryResetResponse(
        success=True,
        message=message,
        snapshot_path=snapshot_path,
    )


@router.post("/factory-reset/status", response_model=FactoryResetStatusResponse)
async def factory_reset_status(
    auth=Depends(require_auth),
):
    """查看系统重置状态"""
    return FactoryResetStatusResponse(
        ready=True,
        last_reset=_get_last_reset_time(),
        config_count=_count_config_files(),
        installed_apps=_count_installed_apps(),
    )
