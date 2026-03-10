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


class KakaoCodeRequest(BaseModel):
    code: str = ""
    redirect_uri: str = ""
    # Legacy fields
    kakao_id: str = ""
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
async def api_kakao_login(req: KakaoCodeRequest):
    """카카오 로그인 — authorization code flow (SDK v2)."""
    # New: authorization code → token → user info
    if req.code and req.redirect_uri:
        import httpx
        # 토큰 교환에는 REST API 키 사용
        app_key = os.getenv("KAKAO_REST_API_KEY", "")
        if not app_key:
            return {"error": "서버에 KAKAO_REST_API_KEY가 설정되지 않았습니다"}

        async with httpx.AsyncClient() as client:
            # 1. Exchange code for access token
            token_res = await client.post(
                "https://kauth.kakao.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": app_key,
                    "redirect_uri": req.redirect_uri,
                    "code": req.code,
                },
            )
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            if not access_token:
                return {"error": f"카카오 토큰 발급 실패: {token_data.get('error_description', 'Unknown')}"}

            # 2. Get user info
            user_res = await client.get(
                "https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_data = user_res.json()

        kakao_id = str(user_data.get("id", ""))
        profile = user_data.get("kakao_account", {}).get("profile", {})
        nickname = profile.get("nickname", "")
        profile_image = profile.get("thumbnail_image_url", "")

        if not kakao_id:
            return {"error": "카카오 유저 정보 조회 실패"}

        return kakao_login(kakao_id, nickname, profile_image)

    # Legacy: direct kakao_id
    if req.kakao_id:
        return kakao_login(req.kakao_id, req.nickname, req.profile_image)

    return {"error": "code+redirect_uri 또는 kakao_id가 필요합니다"}


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
