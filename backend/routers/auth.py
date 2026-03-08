"""인증 API."""

import os
from fastapi import APIRouter, Header
from pydantic import BaseModel
from services.auth_service import register, login, verify_token, get_user, kakao_login

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class KakaoLoginRequest(BaseModel):
    kakao_id: str
    nickname: str = ""
    profile_image: str = ""


@router.post("/register")
async def api_register(req: AuthRequest):
    """회원가입."""
    result = register(req.username, req.password, req.display_name)
    return result


@router.post("/login")
async def api_login(req: AuthRequest):
    """로그인."""
    result = login(req.username, req.password)
    return result


@router.post("/kakao")
async def api_kakao_login(req: KakaoLoginRequest):
    """카카오 로그인 — 프론트에서 Kakao JS SDK로 인증 후 유저 정보 전달."""
    result = kakao_login(req.kakao_id, req.nickname, req.profile_image)
    return result


@router.get("/config")
async def api_auth_config():
    """프론트에 전달할 인증 설정 (카카오 앱 키 등)."""
    kakao_key = os.getenv("KAKAO_JS_KEY", "")
    return {"kakao_js_key": kakao_key}


@router.get("/me")
async def api_me(authorization: str = Header(default="")):
    """현재 로그인 사용자 정보."""
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if not token:
        return {"error": "로그인이 필요합니다"}
    payload = verify_token(token)
    if not payload:
        return {"error": "토큰이 만료되었거나 유효하지 않습니다"}
    user = get_user(payload["user_id"])
    if not user:
        return {"error": "사용자를 찾을 수 없습니다"}
    return {"user": user}
