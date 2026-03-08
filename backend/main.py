import os
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

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="Stock Analyzer API",
    description="한국/미국 주식 분석 및 AI 기반 투자 추천 API",
    version="1.0.0",
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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


@app.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
async def spa_fallback(request: Request, path: str):
    if path.startswith(("stocks", "recommendations", "backtest", "portfolio", "health", "docs", "openapi", "static", "model", "cache", "advisor", "auth")):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return FileResponse(os.path.join(_static_dir, "index.html"))
