from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import stocks, analysis, recommendations

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


@app.get("/")
async def root():
    return {"message": "Stock Analyzer API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
