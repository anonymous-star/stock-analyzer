import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import stocks, analysis, recommendations, backtest

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="Stock Analyzer API",
    description="한국/미국 주식 분석 및 AI 기반 투자 추천 API",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
app.include_router(analysis.router, prefix="/stocks", tags=["analysis"])
app.include_router(recommendations.router, tags=["recommendations"])
app.include_router(backtest.router, tags=["backtest"])


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
    if path.startswith(("stocks", "recommendations", "backtest", "health", "docs", "openapi", "static")):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return FileResponse(os.path.join(_static_dir, "index.html"))
