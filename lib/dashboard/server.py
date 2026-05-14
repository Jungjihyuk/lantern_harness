"""FastAPI app + uvicorn 부트스트랩.

사용:
    python3 -m lib.dashboard.server [--port 8765] [--no-open]

`bin/cmd/dashboard.sh` 가 호출.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as e:
    sys.stderr.write(
        "Error: fastapi 미설치. 설치:\n"
        "  pip3 install --user fastapi 'uvicorn[standard]' pydantic\n"
        f"  ({e})\n"
    )
    sys.exit(1)

from lib.dashboard.routes import artifacts as artifacts_routes
from lib.dashboard.routes import compose as compose_routes
from lib.dashboard.routes import validate as validate_routes


STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> "FastAPI":
    app = FastAPI(
        title="lantern_harness dashboard",
        description="n8n 스타일 시각 편집기 backend",
        version="0.1.0",
    )

    app.include_router(compose_routes.router)
    app.include_router(artifacts_routes.router)
    app.include_router(validate_routes.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": "0.1.0"}

    # 정적 산출물 serve (frontend 빌드 결과). 없으면 안내 페이지.
    if (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:
        @app.get("/", response_class=HTMLResponse)
        def index_placeholder() -> str:
            return _placeholder_html()

    return app


def _placeholder_html() -> str:
    return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>harness dashboard</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 720px;
         margin: 4rem auto; padding: 0 1rem; color: #111; line-height: 1.6; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }
  pre { background: #f4f4f4; padding: 1rem; border-radius: 8px; overflow-x: auto; }
  a { color: #3b82f6; }
</style></head><body>
<h1>harness dashboard</h1>
<p>Backend 가동 중. Frontend 가 아직 빌드되지 않았습니다.</p>
<h2>API 점검</h2>
<ul>
  <li><a href="/api/health">/api/health</a></li>
  <li><a href="/api/compose">/api/compose</a></li>
  <li><a href="/api/compose/graph">/api/compose/graph</a></li>
  <li><a href="/api/artifacts">/api/artifacts</a></li>
  <li><a href="/api/validate">/api/validate</a></li>
  <li><a href="/docs">/docs</a> (OpenAPI Swagger)</li>
</ul>
<h2>Frontend 빌드</h2>
<pre>cd web
npm install
npm run build       # web/dist → lib/dashboard/static 로 복사</pre>
<p>또는 개발 모드: <code>HARNESS_DASHBOARD_DEV=1</code> 후 별 터미널에서
<code>cd web && npm run dev</code>.</p>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="harness dashboard server")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true", help="브라우저 자동 오픈 안 함")
    ap.add_argument("--reload", action="store_true", help="dev: 코드 변경 시 자동 reload")
    args = ap.parse_args()

    try:
        import uvicorn
    except ImportError:
        sys.stderr.write("Error: uvicorn 미설치. pip3 install --user 'uvicorn[standard]'\n")
        return 1

    url = f"http://{args.host}:{args.port}"
    sys.stderr.write(f"harness dashboard → {url}\n")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(
        "lib.dashboard.server:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
