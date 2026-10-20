import httpx
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_async_db
from core.models import Member

router = APIRouter(prefix="/auth/kakao", tags=["OAuth"])

KAKAO_REST_API_KEY = "8297e3ea68982c5c06249ac53d77d2ce"
KAKAO_REDIRECT_URI = "http://192.168.0.51:8000/auth/kakao/callback"

@router.get("/login")
async def kakao_login():
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?"
        f"client_id={KAKAO_REST_API_KEY}&"
        f"redirect_uri={KAKAO_REDIRECT_URI}&"
        f"response_type=code"
    )
    return RedirectResponse(kakao_auth_url)

@router.get("/callback")
async def kakao_callback(request: Request, code: str, db: AsyncSession = Depends(get_async_db)):
    token_url = "https://kauth.kakao.com/oauth/token"
    token_headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, headers=token_headers, data=token_data)
        if token_res.status_code != 200:
            print("\n[KAKAO TOKEN ERROR]", token_res.status_code, token_res.text)
            return RedirectResponse("/bbs/login?error=token_failed")
        access_token = token_res.json().get("access_token")

        user_info_res = await client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_info_res.status_code != 200:
            print("\n[KAKAO USERINFO ERROR]", user_info_res.status_code, user_info_res.text)
            return RedirectResponse("/bbs/login?error=userinfo_failed")
        user_info = user_info_res.json()

    # 회원 정보 파싱
    kakao_id = str(user_info.get("id"))
    mb_id = f"k_{kakao_id}"
    kakao_account = user_info.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    nickname = profile.get("nickname", f"카카오_{kakao_id[-4:]}")
    email = kakao_account.get("email", f"{mb_id}@kakao.local")
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = datetime.now()

    # 1. 비동기 회원 조회 (SELECT)
    stmt = select(Member).where(Member.mb_id == mb_id)
    res = await db.execute(stmt)
    member = res.scalars().first()

    if not member:
        # 닉네임 중복 체크 (비동기)
        nick_stmt = select(Member).where(Member.mb_nick == nickname)
        nick_res = await db.execute(nick_stmt)
        if nick_res.scalars().first():
            nickname = f"{nickname}_{kakao_id[-4:]}"

        member = Member(
            mb_id=mb_id,
            mb_password="",
            mb_name=nickname,
            mb_nick=nickname,
            mb_nick_date=now,
            mb_email=email,
            mb_level=2,
            mb_point=0,
            mb_today_login=now,
            mb_login_ip=client_ip,
            mb_datetime=now,
            mb_ip=client_ip,
            mb_mailling=0,
            mb_sms=0,
            mb_open=1
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
    else:
        member.mb_today_login = now
        member.mb_login_ip = client_ip
        await db.commit()

    # 세션 등록 및 완료 리다이렉트
    request.session["ss_mb_id"] = member.mb_id
    request.session["ss_mb_key"] = member.mb_id
    print(f"[ASYNC SUCCESS] Logged in as: {member.mb_id} ({nickname})")

    return RedirectResponse(url="/", status_code=303)
