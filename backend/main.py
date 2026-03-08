import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import stocks, analysis, recommendations, backtest, portfolio, auth

logger = logging.getLogger("stock-analyzer")

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

REFRESH_INTERVAL = 4 * 3600  # 4시간


async def _background_refresh():
    """4시간마다 추천 + 백테스트 캐시를 백그라운드에서 갱신."""
    await asyncio.sleep(30)  # 서버 시작 30초 후 첫 실행
    while True:
        try:
            logger.info("[Scheduler] 추천/백테스트 캐시 갱신 시작")
            from services.recommendation_service import get_recommendations
            from services.backtest_service import run_backtest

            # 추천 갱신
            await get_recommendations(limit=100)
            logger.info("[Scheduler] 추천 캐시 갱신 완료")

            # 백테스트 갱신 (20, 40, 60일)
            for hd in [20, 40, 60]:
                await run_backtest(hold_days=hd, limit=100)
                logger.info(f"[Scheduler] 백테스트 {hd}일 캐시 갱신 완료")

        except Exception as e:
            logger.error(f"[Scheduler] 캐시 갱신 실패: {e}")

        await asyncio.sleep(REFRESH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 lifecycle."""
    task = asyncio.create_task(_background_refresh())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Stock Analyzer API",
    description="한국/미국 주식 분석 및 AI 기반 투자 추천 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- Security headers middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://t1.kakaocdn.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://k.kakaocdn.net https://img1.kakaocdn.net; "
            "connect-src 'self' https://kapi.kakao.com https://kauth.kakao.com"
        )
        # Remove server header if present
        if "server" in response.headers:
            del response.headers["server"]
        return response


app.add_middleware(SecurityHeadersMiddleware)

# TODO: Replace "*" with actual domain(s) once known (e.g. "https://yourdomain.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://anonymous-star.github.io",
        "https://civilisable-albertha-preeconomical.ngrok-free.dev",
        "http://localhost:8000",
        "http://192.168.219.103:8000",
        "https://*.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # TODO: restrict to actual domain(s) in production
)

app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
app.include_router(analysis.router, prefix="/stocks", tags=["analysis"])
app.include_router(recommendations.router, tags=["recommendations"])
app.include_router(backtest.router, tags=["backtest"])
app.include_router(portfolio.router, tags=["portfolio"])
app.include_router(auth.router, tags=["auth"])


_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(_static_dir, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


@app.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
async def spa_fallback(request: Request, path: str):
    if path.startswith(("stocks", "recommendations", "backtest", "portfolio", "health", "docs", "openapi", "static", "model", "cache", "advisor", "auth")):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return FileResponse(os.path.join(_static_dir, "index.html"))
