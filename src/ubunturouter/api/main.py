"""FastAPI 应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routes import auth, dashboard, interfaces, system as system_routes, config as config_routes
from .routes import firewall, dhcp, routing, vpn, topology
from .routes import containers, appstore, multiwan, orchestrator, vm as vm_routes
from .routes import ddns as ddns_routes
from .routes import storage as storage_routes
from .routes import monitor as monitor_routes
from .routes import samba as samba_routes
from .routes import pppoe as pppoe_routes
from .routes import ttyd as ttyd_routes
from .routes import apt as apt_routes
from .routes import dns as dns_routes
from .routes import diag as diag_routes
from .routes import backup as backup_routes
from .routes import wireless as wireless_routes
from .routes import arp as arp_routes
from .routes import cron as cron_routes
from .routes import startup as startup_routes
from .ws import dashboard as ws_dashboard
from .auth import jwt as jwt_auth
from .tls import init_https


def create_app() -> FastAPI:
    app = FastAPI(
        title="UbuntuRouter API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS（开发环境允许任意来源）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
    app.include_router(interfaces.router, prefix="/api/v1/interfaces", tags=["Interfaces"])
    app.include_router(system_routes.router, prefix="/api/v1/system", tags=["System"])
    app.include_router(config_routes.router, prefix="/api/v1/config", tags=["Config"])
    app.include_router(firewall.router, prefix="/api/v1/firewall", tags=["Firewall"])
    app.include_router(dhcp.router, prefix="/api/v1/dhcp", tags=["DHCP"])
    app.include_router(routing.router, prefix="/api/v1/routing", tags=["Routing"])
    app.include_router(vpn.router, prefix="/api/v1/vpn", tags=["VPN"])
    app.include_router(topology.router, prefix="/api/v1/topology", tags=["Topology"])
    app.include_router(containers.router, prefix="/api/v1/containers", tags=["Containers"])
    app.include_router(appstore.router, prefix="/api/v1/appstore", tags=["AppStore"])
    app.include_router(multiwan.router, prefix="/api/v1/multiwan", tags=["MultiWAN"])
    app.include_router(orchestrator.router, prefix="/api/v1/orchestrator", tags=["Orchestrator"])
    app.include_router(vm_routes.router, prefix="/api/v1/vm", tags=["VM"])
    app.include_router(ddns_routes.router, prefix="/api/v1/ddns", tags=["DDNS"])
    app.include_router(storage_routes.router, prefix="/api/v1/storage", tags=["Storage"])
    app.include_router(monitor_routes.router, prefix="/api/v1/monitor", tags=["Monitor"])
    app.include_router(samba_routes.router, prefix="/api/v1/samba", tags=["Samba"])
    app.include_router(pppoe_routes.router, prefix="/api/v1/pppoe", tags=["PPPoE"])
    app.include_router(ttyd_routes.router, prefix="/api/v1/ttyd", tags=["TTYD"])
    app.include_router(apt_routes.router, prefix="/api/v1/apt", tags=["APT"])
    app.include_router(dns_routes.router, prefix="/api/v1/dns", tags=["DNS"])
    app.include_router(diag_routes.router, prefix="/api/v1/diag", tags=["Diagnostics"])
    app.include_router(backup_routes.router, prefix="/api/v1/backup", tags=["Backup"])
    app.include_router(wireless_routes.router, prefix="/api/v1/wireless", tags=["Wireless"])
    app.include_router(arp_routes.router, prefix="/api/v1/arp", tags=["ARP"])
    app.include_router(cron_routes.router, prefix="/api/v1/system", tags=["Cron"])
    app.include_router(startup_routes.router, prefix="/api/v1/system", tags=["Startup"])

    # WebSocket
    app.add_api_websocket_route("/api/v1/ws/dashboard", ws_dashboard.websocket_endpoint)

    # 静态文件（Vue 前端构建产物） - 多个备选路径
    static_candidates = [
        Path(__file__).resolve().parent.parent.parent / "web" / "dist",  # 包内路径
        Path("/opt/ubunturouter/web/dist"),  # 安装目标路径（优先）
        Path("/tmp/ubunturouter-web-build/dist"),  # VM 本地构建目录
    ]
    static_dir = None
    for p in static_candidates:
        if p.exists() and (p / "index.html").exists():
            static_dir = p
            break

    if static_dir:
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="web")

        # ─── SPA fallback: 所有非 API 的未匹配路径返回 index.html ───
        import starlette.status as status
        from fastapi.responses import HTMLResponse, JSONResponse
        from starlette.exceptions import HTTPException as StarletteHTTPException

        @app.exception_handler(StarletteHTTPException)
        async def spa_fallback(request, exc):
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                path = request.url.path
                # 只对非 API 路径做 SPA fallback
                if not path.startswith("/api/") and not path.startswith("/."):
                    index = static_dir / "index.html"
                    if index.exists():
                        content = index.read_text(encoding="utf-8")
                        return HTMLResponse(content=content, status_code=200)
            # 非 404 或 API 路径的异常：返回原始 detail
            detail = exc.detail if hasattr(exc, 'detail') else "Not Found"
            return JSONResponse(
                content={"detail": detail}, status_code=exc.status_code
            )

    return app


app = create_app()
