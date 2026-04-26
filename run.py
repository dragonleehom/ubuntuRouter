#!/usr/bin/env python3
"""UbuntuRouter API Server — 启动入口"""

import sys
import os
from pathlib import Path

# 确保能找到包
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    import uvicorn
    from ubunturouter.api.tls import init_https
    from ubunturouter.api.main import app

    import argparse
    parser = argparse.ArgumentParser(description="UbuntuRouter API Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=443, help="监听端口")
    parser.add_argument("--no-https", action="store_true", help="禁用 HTTPS（开发用）")
    args = parser.parse_args()

    if args.no_https:
        uvicorn.run(app, host=args.host, port=args.port or 8080, log_level="info")
    else:
        cert_file, key_file = init_https()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file,
            log_level="info",
        )


if __name__ == "__main__":
    main()
