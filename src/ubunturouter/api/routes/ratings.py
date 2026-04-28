"""应用评分 API — 提交/查询/获取用户评分"""

import json
import os
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Body

from ..deps import require_auth

router = APIRouter()

DATA_DIR = "/opt/ubunturouter/data"
RATINGS_FILE = os.path.join(DATA_DIR, "ratings.json")

_lock = threading.Lock()


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_ratings() -> dict:
    """加载评分数据"""
    _ensure_data_dir()
    if not os.path.exists(RATINGS_FILE):
        return {}
    try:
        with open(RATINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_ratings(data: dict):
    """保存评分数据"""
    _ensure_data_dir()
    with open(RATINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _calculate_stats(app_data: dict) -> dict:
    """计算应用评分统计信息"""
    if not app_data:
        return {
            "average": None,
            "count": 0,
            "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        }

    ratings_list = list(app_data.values())
    total = len(ratings_list)
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for entry in ratings_list:
        r = entry.get("rating", 0)
        if 1 <= r <= 5:
            distribution[r] += 1

    average = round(sum(entry.get("rating", 0) for entry in ratings_list) / total, 1) if total > 0 else None

    return {
        "average": average,
        "count": total,
        "distribution": distribution,
    }


@router.get("/{app_id}")
async def get_app_ratings(app_id: str, auth=Depends(require_auth)):
    """获取应用评分（平均分+评分人数+评分分布+当前用户评分）"""
    username = auth.sub

    with _lock:
        all_ratings = _load_ratings()
        app_data = all_ratings.get(app_id, {})

    stats = _calculate_stats(app_data)

    # 当前用户评分
    user_rating = None
    if username and app_data:
        for entry in app_data.values():
            if entry.get("user") == username:
                user_rating = entry.get("rating")
                break

    return {
        "average": stats["average"],
        "count": stats["count"],
        "distribution": stats["distribution"],
        "user_rating": user_rating,
    }


@router.post("/{app_id}")
async def submit_rating(
    app_id: str,
    body: dict = Body(..., description='{"rating": 3}'),
    auth=Depends(require_auth),
):
    """提交评分（1-5星）

    Body:
        {"rating": 3}
        {"rating": 5, "comment": "非常好用"}
    """
    username = auth.sub
    if not username:
        raise HTTPException(status_code=401, detail="无法识别用户身份")

    rating = body.get("rating")
    if rating is None or not isinstance(rating, int) or rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="评分必须是 1-5 的整数")

    comment = body.get("comment", "")

    now = datetime.now().isoformat(timespec="seconds")

    with _lock:
        all_ratings = _load_ratings()
        if app_id not in all_ratings:
            all_ratings[app_id] = {}

        app_data = all_ratings[app_id]

        # 查找用户是否已评分，覆盖旧评分
        entry_id = None
        for eid, entry in app_data.items():
            if entry.get("user") == username:
                entry_id = eid
                break

        if entry_id is not None:
            # 更新已有评分
            app_data[entry_id]["rating"] = rating
            app_data[entry_id]["comment"] = comment
            app_data[entry_id]["created"] = now
        else:
            # 新增评分
            new_id = str(len(app_data) + 1)
            app_data[new_id] = {
                "user": username,
                "rating": rating,
                "comment": comment,
                "created": now,
            }

        _save_ratings(all_ratings)

    return {
        "success": True,
        "message": "评分提交成功",
        "rating": rating,
    }


@router.get("/{app_id}/my")
async def get_my_rating(app_id: str, auth=Depends(require_auth)):
    """获取当前用户对应用的评分"""
    username = auth.sub
    if not username:
        raise HTTPException(status_code=401, detail="无法识别用户身份")

    with _lock:
        all_ratings = _load_ratings()
        app_data = all_ratings.get(app_id, {})

    for entry in app_data.values():
        if entry.get("user") == username:
            return {
                "rating": entry.get("rating"),
                "comment": entry.get("comment", ""),
                "created": entry.get("created", ""),
            }

    return {
        "rating": None,
        "comment": "",
        "created": "",
    }
