"""TTYD Terminal Manager — manage ttyd web terminal service for UbuntuRouter

Provides lifecycle management for ttyd, a lightweight terminal-in-browser tool.
Runs as a subprocess on port 7681 bound to localhost for security.
"""

import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TTYD_PORT = 7681
TTYD_BIND = "127.0.0.1"
TTYD_CMD = "ttyd"


class TTYDManager:
    """Manage ttyd web terminal service."""

    def __init__(self, port: int = TTYD_PORT, bind: str = TTYD_BIND):
        self.port = port
        self.bind = bind
        self._process: Optional[subprocess.Popen] = None

    def is_installed(self) -> bool:
        """Check if ttyd binary is available in PATH."""
        return shutil.which(TTYD_CMD) is not None

    def is_running(self) -> bool:
        """Check if ttyd process is running on the expected port."""
        if self._process is not None:
            ret = self._process.poll()
            if ret is None:
                return True  # Process still running
            self._process = None
        # Also check via netstat/ss
        try:
            r = subprocess.run(
                ["ss", "-tlnp", f"sport = :{self.port}"],
                capture_output=True, text=True, timeout=5,
            )
            if "ttyd" in r.stdout or f":{self.port}" in r.stdout:
                return True
        except Exception:
            pass
        return False

    def get_info(self) -> dict:
        """Get ttyd service information."""
        installed = self.is_installed()
        running = self.is_running() if installed else False
        install_hint = "apt install ttyd" if not installed else None
        return {
            "installed": installed,
            "running": running,
            "port": self.port,
            "bind": self.bind,
            "url": f"http://{self.bind}:{self.port}/" if running else None,
            "install_hint": install_hint,
        }

    def start(self) -> dict:
        """Start ttyd service."""
        if not self.is_installed():
            return {"success": False, "message": "ttyd is not installed. Run: apt install ttyd"}

        if self.is_running():
            return {"success": True, "message": "ttyd is already running"}

        try:
            self._process = subprocess.Popen(
                [
                    TTYD_CMD,
                    "-p", str(self.port),
                    "-a", self.bind,
                    "-W",  # Writable mode (allow input)
                    "-t", "fontSize=14",
                    "-t", "theme={\"background\":\"#1a1a2e\",\"foreground\":\"#e0e0e0\"}",
                    "bash",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            # Wait briefly to ensure it started
            time.sleep(1)
            if self._process.poll() is not None:
                return {"success": False, "message": "ttyd failed to start"}
            return {"success": True, "message": f"ttyd started on {self.bind}:{self.port}"}
        except Exception as e:
            logger.error("Failed to start ttyd: %s", e)
            return {"success": False, "message": str(e)}

    def stop(self) -> dict:
        """Stop ttyd service."""
        if self._process is not None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                self._process.wait(timeout=5)
                self._process = None
                return {"success": True, "message": "ttyd stopped"}
            except ProcessLookupError:
                self._process = None
                return {"success": True, "message": "ttyd already stopped"}
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                    self._process = None
                    return {"success": True, "message": "ttyd force killed"}
                except Exception as e:
                    return {"success": False, "message": str(e)}

        # Fallback: kill by port
        try:
            r = subprocess.run(
                ["fuser", "-k", f"{self.port}/tcp"],
                capture_output=True, text=True, timeout=5,
            )
            return {"success": True, "message": "ttyd stopped (via fuser)"}
        except Exception:
            pass
        return {"success": True, "message": "ttyd not running"}

    def restart(self) -> dict:
        """Restart ttyd service."""
        self.stop()
        time.sleep(1)
        return self.start()
