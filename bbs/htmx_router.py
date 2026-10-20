from datetime import datetime
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_async_db

router = APIRouter(prefix="/htmx", tags=["HTMX"])
templates = Jinja2Templates(directory="templates/modern_dashboard")

# 1. 비동기 추천(좋아요)
@router.post("/good/{bo_table}/{wr_id}", response_class=HTMLResponse)
async def htmx_good(
    request: Request,
    bo_table: str,
    wr_id: int,
    db: AsyncSession = Depends(get_async_db)
):
    write_table = f"g6_write_{bo_table}"
    await db.execute(
        text(f"UPDATE {write_table} SET wr_good = wr_good + 1 WHERE wr_id = :wr_id"),
        {"wr_id": wr_id}
    )
    await db.commit()

    res = await db.execute(
        text(f"SELECT wr_good FROM {write_table} WHERE wr_id = :wr_id"),
        {"wr_id": wr_id}
    )
    row = res.first()
    wr_good = row[0] if row else 0

    return templates.TemplateResponse(
        "partials/good_button.html",
        {
            "request": request,
            "bo_table": bo_table,
            "wr_id": wr_id,
            "wr_good": wr_good,
            "is_voted": True
        }
    )

# 2. 비동기 무새로고침 댓글 작성 (자동 스키마 대응)
@router.post("/comment/{bo_table}/{wr_id}", response_class=HTMLResponse)
async def htmx_comment(
    request: Request,
    bo_table: str,
    wr_id: int,
    wr_content: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    mb_id = request.session.get("ss_mb_id", "")
    member = getattr(request.state, "member", None)
    nick = getattr(member, "mb_nick", mb_id or "방문자")
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = datetime.now()
    write_table = f"g6_write_{bo_table}"

    # 1. 댓글 카운트 증가
    await db.execute(
        text(f"UPDATE {write_table} SET wr_comment = wr_comment + 1 WHERE wr_id = :wr_id"),
        {"wr_id": wr_id}
    )

    # 2. 테이블의 모든 컬럼 메타데이터 조회
    cols_res = await db.execute(text(f"DESCRIBE {write_table}"))
    columns = cols_res.fetchall()

    data = {}
    for col in columns:
        field = col[0]
        col_type = col[1].lower()
        if field == "wr_id":
            continue  # AUTO_INCREMENT
        elif field == "wr_parent":
            data[field] = wr_id
        elif field == "wr_is_comment":
            data[field] = 1
        elif field == "wr_content":
            data[field] = wr_content
        elif field == "mb_id":
            data[field] = mb_id
        elif field == "wr_name":
            data[field] = nick
        elif field in ("wr_datetime", "wr_last"):
            data[field] = now
        elif field == "wr_ip":
            data[field] = client_ip
        elif field == "wr_option":
            data[field] = "html1"
        else:
            # 기본값 없는 NOT NULL 필드 자동 방어
            if "int" in col_type or "decimal" in col_type or "float" in col_type:
                data[field] = 0
            elif "datetime" in col_type or "timestamp" in col_type or "date" in col_type:
                data[field] = now
            else:
                data[field] = ""

    col_names = ", ".join([f"`{k}`" for k in data.keys()])
    val_placeholders = ", ".join([f":{k}" for k in data.keys()])
    insert_sql = text(f"INSERT INTO {write_table} ({col_names}) VALUES ({val_placeholders})")

    await db.execute(insert_sql, data)
    await db.commit()

    # 3. 작성된 단일 댓글 카드 렌더링 반환
    return templates.TemplateResponse(
        "partials/single_comment.html",
        {
            "request": request,
            "comment": {
                "wr_name": nick,
                "wr_datetime": now.strftime("%Y-%m-%d %H:%M"),
                "wr_content": wr_content
            }
        }
    )
