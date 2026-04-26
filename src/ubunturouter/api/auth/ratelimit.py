"""登录保护模块 — 失败计数 + IP 锁定"""

import time
from collections import defaultdict
from typing import Dict, Tuple


# 登录失败计数器：{ip: (fail_count, first_fail_time)}
_fail_counts: Dict[str, Tuple[int, float]] = {}

MAX_FAILS = 5          # 最多失败次数
LOCK_DURATION = 300     # 锁定时间（秒）


def record_fail(ip: str) -> int:
    """记录登录失败，返回当前失败次数"""
    now = time.time()
    if ip in _fail_counts:
        count, first = _fail_counts[ip]
        # 如果已经过了锁定时间，重置计数器
        if now - first > LOCK_DURATION:
            _fail_counts[ip] = (1, now)
            return 1
        _fail_counts[ip] = (count + 1, first)
        return count + 1
    _fail_counts[ip] = (1, now)
    return 1


def record_success(ip: str):
    """登录成功后清除失败计数"""
    _fail_counts.pop(ip, None)


def is_locked(ip: str) -> bool:
    """检查 IP 是否被锁定"""
    if ip not in _fail_counts:
        return False
    count, first = _fail_counts[ip]
    if time.time() - first > LOCK_DURATION:
        _fail_counts.pop(ip, None)
        return False
    return count >= MAX_FAILS


def remaining_attempts(ip: str) -> int:
    """返回剩余尝试次数"""
    if ip not in _fail_counts:
        return MAX_FAILS
    count, first = _fail_counts[ip]
    if time.time() - first > LOCK_DURATION:
        _fail_counts.pop(ip, None)
        return MAX_FAILS
    return max(0, MAX_FAILS - count)
