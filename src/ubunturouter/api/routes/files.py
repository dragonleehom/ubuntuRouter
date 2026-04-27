"""文件管理 API: ls / read / write / upload / delete / mkdir / rename / move / copy / chmod / stat"""

import os
import shutil
import stat as stat_module
import mimetypes
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query

from ..deps import require_auth


router = APIRouter()

# 允许的根路径（安全限制，不允许访问系统敏感目录）
ALLOWED_ROOTS = [
    Path("/"),
]

# 禁止访问的敏感路径片段
BLOCKED_PATHS = [
    "/etc/shadow",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/ssh/",
    "/root/.ssh/",
    "/home/*/.ssh/",
    "/var/lib/systemd/",
    "/sys/",
    "/proc/",
    "/dev/",
    "/run/",
]


def _resolve_path(path_str: str) -> Path:
    """解析并验证路径安全性"""
    path = Path(path_str).resolve()
    # 检查是否在允许的根路径下
    allowed = False
    for root in ALLOWED_ROOTS:
        try:
            path.relative_to(root)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(403, "路径不在允许范围内")
    # 检查是否在禁止路径列表
    for blocked in BLOCKED_PATHS:
        if blocked.endswith("/"):
            if str(path).startswith(blocked.rstrip("/")):
                raise HTTPException(403, "禁止访问系统敏感目录")
        elif blocked in str(path):
            raise HTTPException(403, "禁止访问系统敏感文件")
    return path


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _format_perms(mode: int) -> str:
    """将文件权限位转为 rwx 字符串"""
    perms = ""
    for who in "USR", "GRP", "OTH":
        for what in "R", "W", "X":
            bit = getattr(stat_module, f"S_I{what}{who}")
            perms += what.lower() if (mode & bit) else "-"
    return perms


def _get_file_info(path: Path, base_path: Path) -> dict:
    """获取文件/目录信息"""
    try:
        st = path.stat()
    except PermissionError:
        return {
            "name": path.name,
            "path": str(path),
            "relative_path": str(path.relative_to(base_path)),
            "type": "error",
            "error": "权限不足",
        }

    is_dir = path.is_dir()
    info = {
        "name": path.name,
        "path": str(path),
        "relative_path": str(path.relative_to(base_path)),
        "type": "dir" if is_dir else "file",
        "size": st.st_size,
        "size_str": _format_size(st.st_size) if not is_dir else "-",
        "mode": oct(st.st_mode & 0o777),
        "perms": _format_perms(st.st_mode),
        "owner": st.st_uid,
        "group": st.st_gid,
        "mtime": int(st.st_mtime),
        "atime": int(st.st_atime),
        "ctime": int(st.st_ctime),
        "is_symlink": path.is_symlink(),
        "is_hidden": path.name.startswith("."),
    }

    if not is_dir:
        mime_type, _ = mimetypes.guess_type(str(path))
        info["mime_type"] = mime_type or "application/octet-stream"
        # 判断是否为文本文件（可预览）
        text_extensions = {
            ".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
            ".css", ".js", ".ts", ".py", ".sh", ".conf", ".cfg", ".ini",
            ".env", ".log", ".csv", ".toml", ".lock", ".gitignore",
        }
        info["is_text"] = path.suffix.lower() in text_extensions
        info["extension"] = path.suffix.lower()

    return info


def _list_dir(path: Path, base_path: Path, show_hidden: bool = False) -> list:
    """列出目录内容"""
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        raise HTTPException(403, f"无权访问目录: {path}")

    items = []
    for entry in entries:
        if entry.name.startswith(".") and not show_hidden:
            continue
        items.append(_get_file_info(entry, base_path))

    return items


# ─── API ─────────────────────────────────────────────────────────────


@router.get("/files/list")
async def list_files(
    path: str = Query("/", description="目录路径"),
    show_hidden: bool = Query(False, description="显示隐藏文件"),
    auth=Depends(require_auth),
):
    """列出目录内容"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"路径不存在: {path}")
    if not target.is_dir():
        raise HTTPException(400, f"不是目录: {path}")

    items = _list_dir(target, target, show_hidden)

    # 统计信息
    total = len(items)
    dirs = sum(1 for i in items if i["type"] == "dir")
    files = sum(1 for i in items if i["type"] == "file")
    total_size = sum(i["size"] for i in items if i["type"] == "file")

    return {
        "path": str(target),
        "name": target.name,
        "parent": str(target.parent) if target.parent != target else None,
        "items": items,
        "stats": {
            "total": total,
            "dirs": dirs,
            "files": files,
            "total_size": total_size,
            "total_size_str": _format_size(total_size),
        },
        "disk_usage": _get_disk_usage(target),
    }


@router.get("/files/stat")
async def file_stat(
    path: str = Query(..., description="文件路径"),
    auth=Depends(require_auth),
):
    """获取文件/目录详细信息"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"路径不存在: {path}")
    return _get_file_info(target, target.parent)


@router.get("/files/read")
async def read_file(
    path: str = Query(..., description="文件路径"),
    offset: int = Query(0, description="读取偏移（字节）"),
    limit: int = Query(4096, description="最大读取字节数", ge=1, le=1048576),
    auth=Depends(require_auth),
):
    """读取文本文件内容"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"文件不存在: {path}")
    if target.is_dir():
        raise HTTPException(400, "不能读取目录")

    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 4096
    if limit > 1048576:
        limit = 1048576

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            content = f.read(limit)
        return {
            "path": str(target),
            "content": content,
            "offset": offset,
            "read_bytes": len(content.encode("utf-8")),
            "total_size": target.stat().st_size,
        }
    except PermissionError:
        raise HTTPException(403, "无权读取此文件")
    except UnicodeDecodeError:
        raise HTTPException(400, "文件不是有效的 UTF-8 文本")
    except Exception as e:
        raise HTTPException(500, f"读取失败: {str(e)}")


@router.post("/files/write")
async def write_file_api(
    path: str = Query(..., description="文件路径"),
    content: str = Form(..., description="文件内容"),
    auth=Depends(require_auth),
):
    """写入文本文件"""
    target = _resolve_path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"message": "文件已保存", "path": str(target), "size": len(content)}
    except PermissionError:
        raise HTTPException(403, "无权写入此文件")
    except Exception as e:
        raise HTTPException(500, f"写入失败: {str(e)}")


@router.post("/files/upload")
async def upload_file(
    path: str = Form(..., description="上传目录"),
    file: UploadFile = File(...),
    auth=Depends(require_auth),
):
    """上传文件"""
    target_dir = _resolve_path(path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(400, f"目标目录不存在: {path}")

    target_path = target_dir / file.filename
    try:
        content = await file.read()
        target_path.write_bytes(content)
        return {
            "message": "文件已上传",
            "path": str(target_path),
            "filename": file.filename,
            "size": len(content),
        }
    except PermissionError:
        raise HTTPException(403, "无权写入此目录")
    except Exception as e:
        raise HTTPException(500, f"上传失败: {str(e)}")


@router.delete("/files/delete")
async def delete_file(
    path: str = Query(..., description="文件/目录路径"),
    recursive: bool = Query(False, description="是否递归删除目录"),
    auth=Depends(require_auth),
):
    """删除文件或目录"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"路径不存在: {path}")

    try:
        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                # 只删除空目录
                target.rmdir()
        else:
            target.unlink()
        return {"message": "已删除", "path": str(target)}
    except OSError as e:
        if "Directory not empty" in str(e):
            raise HTTPException(400, "目录不为空，请使用 recursive=true 删除")
        raise HTTPException(500, f"删除失败: {str(e)}")
    except PermissionError:
        raise HTTPException(403, "无权删除")


@router.post("/files/mkdir")
async def create_directory(
    path: str = Query(..., description="新建目录路径"),
    auth=Depends(require_auth),
):
    """创建目录"""
    target = _resolve_path(path)
    if target.exists():
        raise HTTPException(400, f"路径已存在: {path}")
    try:
        target.mkdir(parents=True, exist_ok=False)
        return {"message": "目录已创建", "path": str(target)}
    except PermissionError:
        raise HTTPException(403, "无权创建目录")
    except Exception as e:
        raise HTTPException(500, f"创建失败: {str(e)}")


@router.post("/files/rename")
async def rename_file(
    path: str = Query(..., description="原路径"),
    new_name: str = Query(..., description="新名称"),
    auth=Depends(require_auth),
):
    """重命名文件或目录"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"路径不存在: {path}")

    new_path = target.parent / new_name
    if new_path.exists():
        raise HTTPException(400, f"目标路径已存在: {new_path}")

    try:
        target.rename(new_path)
        return {"message": "已重命名", "path": str(new_path), "old_path": str(target)}
    except PermissionError:
        raise HTTPException(403, "无权重命名")
    except Exception as e:
        raise HTTPException(500, f"重命名失败: {str(e)}")


@router.post("/files/copy")
async def copy_file(
    src: str = Query(..., description="源路径"),
    dest: str = Query(..., description="目标路径"),
    auth=Depends(require_auth),
):
    """复制文件或目录"""
    source = _resolve_path(src)
    if not source.exists():
        raise HTTPException(404, f"源路径不存在: {src}")

    dest_path = _resolve_path(dest)
    if dest_path.exists():
        raise HTTPException(400, f"目标路径已存在: {dest}")

    try:
        if source.is_dir():
            shutil.copytree(source, dest_path)
        else:
            shutil.copy2(source, dest_path)
        return {"message": "已复制", "src": str(source), "dest": str(dest_path)}
    except PermissionError:
        raise HTTPException(403, "无权复制")
    except Exception as e:
        raise HTTPException(500, f"复制失败: {str(e)}")


@router.post("/files/move")
async def move_file(
    src: str = Query(..., description="源路径"),
    dest: str = Query(..., description="目标路径"),
    auth=Depends(require_auth),
):
    """移动文件或目录"""
    source = _resolve_path(src)
    if not source.exists():
        raise HTTPException(404, f"源路径不存在: {src}")

    dest_path = _resolve_path(dest)
    if dest_path.exists():
        raise HTTPException(400, f"目标路径已存在: {dest}")

    try:
        shutil.move(str(source), str(dest_path))
        return {"message": "已移动", "src": str(source), "dest": str(dest_path)}
    except PermissionError:
        raise HTTPException(403, "无权移动")
    except Exception as e:
        raise HTTPException(500, f"移动失败: {str(e)}")


@router.post("/files/chmod")
async def change_permissions(
    path: str = Query(..., description="文件路径"),
    mode: str = Query(..., description="权限模式，如 755, 644"),
    recursive: bool = Query(False, description="是否递归"),
    auth=Depends(require_auth),
):
    """修改文件权限"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"路径不存在: {path}")

    try:
        mode_int = int(mode, 8)
    except ValueError:
        raise HTTPException(400, f"无效的权限模式: {mode}")

    try:
        if recursive and target.is_dir():
            for root, dirs, files in os.walk(target):
                for d in dirs:
                    os.chmod(os.path.join(root, d), mode_int)
                for f in files:
                    os.chmod(os.path.join(root, f), mode_int)
        else:
            os.chmod(target, mode_int)
        return {"message": f"权限已修改为 {mode}", "path": str(target)}
    except PermissionError:
        raise HTTPException(403, "无权修改权限")
    except Exception as e:
        raise HTTPException(500, f"修改失败: {str(e)}")


@router.post("/files/download")
async def download_file_prepare(
    path: str = Query(..., description="文件路径"),
    auth=Depends(require_auth),
):
    """获取文件下载信息（前端通过此路径下载）"""
    target = _resolve_path(path)
    if not target.exists():
        raise HTTPException(404, f"文件不存在: {path}")
    if target.is_dir():
        raise HTTPException(400, "不能下载目录（请先打包）")

    return {
        "path": str(target),
        "name": target.name,
        "size": target.stat().st_size,
        "size_str": _format_size(target.stat().st_size),
        "download_url": f"/api/v1/files/download/raw?path={target}",
    }


# ─── 辅助 ────────────────────────────────────────────────────────────


def _get_disk_usage(path: Path) -> dict:
    """获取磁盘使用情况"""
    try:
        st = os.statvfs(str(path))
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bfree
        used = total - free
        return {
            "total": total,
            "used": used,
            "free": free,
            "total_str": _format_size(total),
            "used_str": _format_size(used),
            "free_str": _format_size(free),
            "usage_percent": round(used / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        return None
