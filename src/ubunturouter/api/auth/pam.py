"""PAM 认证模块"""

import subprocess
import struct
from typing import Optional

try:
    import PAM
    HAS_PAM = True
except ImportError:
    HAS_PAM = False


def pam_authenticate(username: str, password: str) -> bool:
    """通过 PAM 认证系统账号。返回 True=认证通过"""
    if HAS_PAM:
        return _pam_python_auth(username, password)
    return _pam_subprocess_auth(username, password)


def _pam_python_auth(username: str, password: str) -> bool:
    """使用 python-pam 库认证"""
    import PAM

    def pam_conv(auth, query_list, user_data):
        resp = []
        for query, ptype in query_list:
            if ptype == PAM.PAM_PROMPT_ECHO_ON:
                resp.append((username, 0))
            elif ptype == PAM.PAM_PROMPT_ECHO_OFF:
                resp.append((password, 0))
            elif ptype == PAM.PAM_ERROR_MSG:
                resp.append(("", 0))
            elif ptype == PAM.PAM_TEXT_INFO:
                resp.append(("", 0))
            else:
                resp.append(("", 0))
        return resp

    service = PAM.pam()
    service.start("ubunturouter")
    service.set_item(PAM.PAM_USER, username)
    service.set_item(PAM.PAM_CONV, pam_conv)
    try:
        service.authenticate()
        service.acct_mgmt()
        return True
    except PAM.error:
        return False


def _pam_subprocess_auth(username: str, password: str) -> bool:
    """使用 login/passwd 或 python3-pam 子进程认证"""
    try:
        r = subprocess.run(
            ["python3", "-c", f"""
import subprocess, struct
p = subprocess.Popen(
    ['sudo', '-S', '-u', '{username}', 'true'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
p.communicate(input=b'{password}\\n', timeout=5)
exit(p.returncode)
"""],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        pass

    # fallback: 尝试 python3-pam
    try:
        r = subprocess.run(
            ["python3", "-m", "pam", "authenticate", username, password],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def get_user_groups(username: str) -> list:
    """获取用户所属组"""
    import grp
    try:
        groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
        return groups
    except Exception:
        return []
