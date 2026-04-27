"""计划任务 API: 基于 crontab 的定时任务管理"""

import subprocess
from dataclasses import dataclass
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_auth


router = APIRouter()

CRONTAB_HEADER = "# ── UbuntuRouter Managed ─────────────────────────────────\n"
CRONTAB_FOOTER = "# ── End UbuntuRouter Managed ─────────────────────────────\n"

CRON_FIELD_NAMES = [
    "分 (0-59)", "时 (0-23)", "日 (1-31)", "月 (1-12)", "周 (0-7, 0=周日)"
]


@dataclass
class CronTask:
    id: int
    minute: str
    hour: str
    day: str
    month: str
    weekday: str
    command: str
    comment: Optional[str] = None


def parse_cron_line(line: str, idx: int) -> Optional[CronTask]:
    """解析单行 crontab 条目"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split(None, 5)
    if len(parts) < 6:
        return None
    return CronTask(
        id=idx,
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        weekday=parts[4],
        command=parts[5],
    )


def _list_jobs() -> List[CronTask]:
    """获取当前用户 crontab 中的所有任务"""
    try:
        r = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=5,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "crontab -l 超时")
    except FileNotFoundError:
        raise HTTPException(500, "crontab 命令不可用，请安装 cron")

    if r.returncode != 0:
        # 没有 crontab 返回非零但不算错误
        if "no crontab" in r.stderr.lower():
            return []
        raise HTTPException(500, f"读取 crontab 失败: {r.stderr.strip()}")

    tasks = []
    in_managed = False
    idx = 0
    for line in r.stdout.split("\n"):
        line = line.strip()
        if line == CRONTAB_HEADER.strip():
            in_managed = True
            continue
        if line == CRONTAB_FOOTER.strip():
            in_managed = False
            continue
        if in_managed:
            task = parse_cron_line(line, idx)
            if task:
                tasks.append(task)
                idx += 1
    return tasks


def _write_jobs(tasks: List[CronTask]) -> None:
    """写入 crontab，使用标记段落管理"""
    lines = []
    lines.append("")

    # 现有 crontab 的非管理段落
    try:
        r = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=5,
        )
        old_crontab = r.stdout if r.returncode == 0 else ""
    except Exception:
        old_crontab = ""

    in_managed = False
    for line in old_crontab.split("\n"):
        stripped = line.strip()
        if stripped == CRONTAB_HEADER.strip():
            in_managed = True
            continue
        if stripped == CRONTAB_FOOTER.strip():
            in_managed = False
            continue
        if not in_managed:
            lines.append(line)

    # 写入管理段落
    lines.append(CRONTAB_HEADER)
    for task in tasks:
        cron_expr = f"{task.minute} {task.hour} {task.day} {task.month} {task.weekday}"
        if task.comment:
            lines.append(f"# {task.comment}")
        lines.append(f"{cron_expr} {task.command}")
    lines.append(CRONTAB_FOOTER)
    lines.append("")

    content = "\n".join(lines)
    r = subprocess.run(
        ["crontab", "-"],
        input=content, capture_output=True, text=True, timeout=5,
    )
    if r.returncode != 0:
        raise HTTPException(500, f"写入 crontab 失败: {r.stderr.strip()}")


# ─── API ─────────────────────────────────────────────────────────────


@router.get("/cron")
async def list_jobs(auth=Depends(require_auth)):
    """列出所有计划任务"""
    tasks = _list_jobs()
    return {
        "tasks": [
            {
                "id": t.id,
                "minute": t.minute,
                "hour": t.hour,
                "day": t.day,
                "month": t.month,
                "weekday": t.weekday,
                "command": t.command,
                "comment": t.comment or "",
                "expression": f"{t.minute} {t.hour} {t.day} {t.month} {t.weekday}",
                "schedule_text": _describe_schedule(t),
            }
            for t in tasks
        ],
        "field_names": CRON_FIELD_NAMES,
        "managed_header": CRONTAB_HEADER.strip(),
    }


@router.post("/cron")
async def create_job(job: dict, auth=Depends(require_auth)):
    """创建计划任务"""
    tasks = _list_jobs()
    new_id = max((t.id for t in tasks), default=-1) + 1
    task = CronTask(
        id=new_id,
        minute=job.get("minute", "*"),
        hour=job.get("hour", "*"),
        day=job.get("day", "*"),
        month=job.get("month", "*"),
        weekday=job.get("weekday", "*"),
        command=job.get("command", ""),
        comment=job.get("comment", ""),
    )
    if not task.command:
        raise HTTPException(400, "命令不能为空")
    tasks.append(task)
    _write_jobs(tasks)
    return {"message": "计划任务已创建", "id": new_id}


@router.put("/cron/{task_id}")
async def update_job(task_id: int, job: dict, auth=Depends(require_auth)):
    """更新计划任务"""
    tasks = _list_jobs()
    for t in tasks:
        if t.id == task_id:
            t.minute = job.get("minute", t.minute)
            t.hour = job.get("hour", t.hour)
            t.day = job.get("day", t.day)
            t.month = job.get("month", t.month)
            t.weekday = job.get("weekday", t.weekday)
            t.command = job.get("command", t.command)
            t.comment = job.get("comment", t.comment)
            _write_jobs(tasks)
            return {"message": "计划任务已更新"}
    raise HTTPException(404, f"任务 {task_id} 不存在")


@router.delete("/cron/{task_id}")
async def delete_job(task_id: int, auth=Depends(require_auth)):
    """删除计划任务"""
    tasks = [t for t in _list_jobs() if t.id != task_id]
    if len(tasks) == len(_list_jobs()):
        raise HTTPException(404, f"任务 {task_id} 不存在")
    _write_jobs(tasks)
    return {"message": "计划任务已删除"}


@router.post("/cron/toggle")
async def toggle_cron_service(enable: bool = True, auth=Depends(require_auth)):
    """启用/禁用 cron 服务"""
    action = "enable" if enable else "disable"
    r = subprocess.run(
        ["systemctl", action, "cron"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        raise HTTPException(500, f"{action} cron 服务失败: {r.stderr.strip()}")
    return {"message": f"cron 服务已{'启用' if enable else '禁用'}", "enabled": enable}


@router.get("/cron/status")
async def cron_service_status(auth=Depends(require_auth)):
    """获取 cron 服务状态"""
    r = subprocess.run(
        ["systemctl", "is-active", "cron"],
        capture_output=True, text=True, timeout=5,
    )
    active = r.stdout.strip() == "active"
    r2 = subprocess.run(
        ["systemctl", "is-enabled", "cron"],
        capture_output=True, text=True, timeout=5,
    )
    enabled = r2.stdout.strip() == "enabled"
    return {"active": active, "enabled": enabled}


# ─── 辅助函数 ────────────────────────────────────────────────────────


_SCHEDULE_NAMES = {
    ("*", "*", "*", "*", "*"): "每分钟",
    ("*/5", "*", "*", "*", "*"): "每5分钟",
    ("*/10", "*", "*", "*", "*"): "每10分钟",
    ("*/15", "*", "*", "*", "*"): "每15分钟",
    ("*/30", "*", "*", "*", "*"): "每30分钟",
    ("0", "*", "*", "*", "*"): "每小时",
    ("0", "*/2", "*", "*", "*"): "每2小时",
    ("0", "*/4", "*", "*", "*"): "每4小时",
    ("0", "*/6", "*", "*", "*"): "每6小时",
    ("0", "*/12", "*", "*", "*"): "每12小时",
    ("0", "0", "*", "*", "*"): "每天零点",
    ("0", "1", "*", "*", "*"): "每天凌晨1点",
    ("0", "3", "*", "*", "*"): "每天凌晨3点",
    ("0", "6", "*", "*", "*"): "每天早上6点",
    ("0", "9", "*", "*", "*"): "每天早上9点",
    ("0", "22", "*", "*", "*"): "每天晚上10点",
    ("0", "0", "*", "*", "0"): "每周日零点",
    ("0", "0", "*", "*", "1"): "每周一零点",
    ("0", "0", "*", "*", "6"): "每周六零点",
    ("0", "0", "1", "*", "*"): "每月1日零点",
    ("0", "0", "15", "*", "*"): "每月15日零点",
}

_WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
_MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月",
           "7月", "8月", "9月", "10月", "11月", "12月"]


def _describe_schedule(task: CronTask) -> str:
    """生成人类可读的时间描述"""
    key = (task.minute, task.hour, task.day, task.month, task.weekday)
    if key in _SCHEDULE_NAMES:
        return _SCHEDULE_NAMES[key]

    # 尝试智能描述
    parts = []
    if task.minute != "*":
        parts.append(f"第{task.minute}分")
    if task.hour != "*":
        if task.hour.isdigit():
            parts.append(f"第{task.hour}时")
        else:
            parts.append(f"时:{task.hour}")
    if task.day != "*":
        if task.day.isdigit():
            parts.append(f"第{task.day}日")
        else:
            parts.append(f"日:{task.day}")
    if task.month != "*":
        if task.month.isdigit() and 1 <= int(task.month) <= 12:
            parts.append(_MONTHS[int(task.month) - 1])
        else:
            parts.append(f"月:{task.month}")
    if task.weekday != "*":
        if task.weekday.isdigit() and 0 <= int(task.weekday) <= 6:
            parts.append(_WEEKDAYS[int(task.weekday)])
        else:
            parts.append(f"周:{task.weekday}")
    return " ".join(parts) if parts else "自定义时间"
