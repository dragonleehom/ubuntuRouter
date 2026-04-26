"""Network Diagnostics Manager — ping, traceroute, nslookup, mtr, TCP port check

Executes network diagnostic commands as background subprocesses,
captures output to temp files, and allows streaming results.
"""

import logging
import os
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────
TASK_DIR = Path("/tmp/ubunturouter-diag")
DEFAULT_TIMEOUT = 30  # seconds


class DiagManager:
    """Execute and track network diagnostic tasks."""

    def __init__(self):
        TASK_DIR.mkdir(parents=True, exist_ok=True)
        # Ensure directory is writable
        try:
            TASK_DIR.chmod(0o777)
        except Exception:
            pass

    # ─── Task Management ─────────────────────────────────────────

    @staticmethod
    def _new_task_id() -> str:
        return str(uuid.uuid4())[:8]

    def _create_task(self, cmd: list, task_id: str,
                     timeout: int = DEFAULT_TIMEOUT) -> dict:
        """Create a background diagnostic task."""
        output_file = TASK_DIR / f"{task_id}.out"
        pid_file = TASK_DIR / f"{task_id}.pid"

        try:
            with open(output_file, "w", encoding="utf-8") as outf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=outf,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid,
                )
            pid_file.write_text(str(proc.pid))

            # Start monitor thread for timeout
            self._monitor_timeout(task_id, proc, timeout)

            return {
                "success": True,
                "task_id": task_id,
                "pid": proc.pid,
                "message": f"Task {task_id} started",
            }
        except FileNotFoundError:
            return {"success": False, "task_id": task_id, "message": f"Command not found: {cmd[0]}"}
        except Exception as e:
            return {"success": False, "task_id": task_id, "message": str(e)}

    def _monitor_timeout(self, task_id: str, proc: subprocess.Popen,
                         timeout: int):
        """Spawn a thread to kill the process if it exceeds timeout."""
        import threading

        def _kill():
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                # Append timeout message
                out_file = TASK_DIR / f"{task_id}.out"
                try:
                    with open(out_file, "a", encoding="utf-8") as f:
                        f.write(f"\n[Timeout: {timeout}s exceeded]\n")
                except Exception:
                    pass

        t = threading.Thread(target=_kill, daemon=True)
        t.start()

    def get_task_result(self, task_id: str) -> dict:
        """Get the result of a completed or running task."""
        output_file = TASK_DIR / f"{task_id}.out"
        pid_file = TASK_DIR / f"{task_id}.pid"

        if not output_file.exists():
            return {"success": False, "message": f"Task {task_id} not found"}

        output = output_file.read_text(encoding="utf-8")
        running = False
        pid = None

        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)  # Check if process exists
                running = True
            except (ProcessLookupError, ValueError, OSError):
                running = False

        return {
            "success": True,
            "task_id": task_id,
            "running": running,
            "output": output,
            "lines": output.split("\n"),
        }

    def get_task_output(self, task_id: str) -> Optional[str]:
        """Get raw output string for a task."""
        output_file = TASK_DIR / f"{task_id}.out"
        if output_file.exists():
            return output_file.read_text(encoding="utf-8")
        return None

    # ─── Diagnostic Commands ─────────────────────────────────────

    def ping(self, target: str, count: int = 4, timeout: int = 15) -> dict:
        """Execute ping to a target host/IP."""
        task_id = self._new_task_id()
        cmd = ["ping", "-c", str(count), "-W", "3", target]
        return self._create_task(cmd, task_id, timeout)

    def traceroute(self, target: str, timeout: int = 30) -> dict:
        """Execute traceroute to a target."""
        task_id = self._new_task_id()
        cmd = ["traceroute", "-n", "-w", "2", target]
        return self._create_task(cmd, task_id, timeout)

    def nslookup(self, domain: str, dns_server: Optional[str] = None,
                 timeout: int = 15) -> dict:
        """Execute DNS lookup."""
        task_id = self._new_task_id()
        if dns_server:
            cmd = ["nslookup", domain, dns_server]
        else:
            cmd = ["nslookup", domain]
        return self._create_task(cmd, task_id, timeout)

    def mtr(self, target: str, count: int = 10, timeout: int = 60) -> dict:
        """Execute MTR (My TraceRoute) in report mode."""
        task_id = self._new_task_id()
        cmd = ["mtr", "-r", "-c", str(count), "-n", target]
        return self._create_task(cmd, task_id, timeout)

    def tcp_check(self, host: str, port: int, timeout: int = 10) -> dict:
        """Check TCP port reachability."""
        task_id = self._new_task_id()
        # Use timeout command to wrap nc
        cmd = ["timeout", str(timeout), "nc", "-zv", host, str(port)]
        return self._create_task(cmd, task_id, timeout)

    def curl(self, url: str, timeout: int = 15) -> dict:
        """Execute HTTP request to check web server reachability."""
        task_id = self._new_task_id()
        cmd = ["curl", "-s", "-o", "/dev/null", "-w",
               "HTTP_CODE: %{http_code}\\nTIME_TOTAL: %{time_total}s\\n"
               "DNS: %{time_namelookup}s\\nCONNECT: %{time_connect}s\\n"
               "SPEED: %{speed_download}B/s\\nSIZE: %{size_download}B",
               "--max-time", str(timeout), url]
        return self._create_task(cmd, task_id, timeout)

    def cleanup(self, age_hours: int = 1):
        """Clean up old diagnostic task files."""
        now = time.time()
        cutoff = now - (age_hours * 3600)
        for f in TASK_DIR.glob("*"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass
