from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Request
from sqlalchemy import case, func, Integer, or_, select

from core.database import db_session
from core.models import Board, BoardNew
from core.template import AdminTemplates
from lib.common import domain_mail_host
from lib.template_functions import (
    get_editor_select, get_group_select,
    get_member_level_select, get_skin_select
)

router = APIRouter()
templates = AdminTemplates()
templates.env.globals['get_skin_select'] = get_skin_select
templates.env.globals['get_group_select'] = get_group_select
templates.env.globals['get_editor_select'] = get_editor_select
templates.env.globals['get_member_level_select'] = get_member_level_select
templates.env.globals["domain_mail_host"] = domain_mail_host

WRITE_COUNT_MENU_KEY = "300820"


@router.get("/write_count")
async def write_count(request: Request, db: db_session,
                      bo_table: str = Query("", alias="bo_table"),
                      period: str = Query("오늘", alias="period"),
                      graph: str = Query("bar", alias="graph")
                      ):
    '''
    글, 댓글 현황 그래프
    '''
    request.session["menu_key"] = WRITE_COUNT_MENU_KEY

    period_array = {
        '오늘': ['시간', 0],
        '어제': ['시간', 0],
        '7일전': ['일', 7],
        '14일전': ['일', 14],
        '30일전': ['일', 30],
        '3개월전': ['주', 90],
        '6개월전': ['주', 180],
        '1년전': ['월', 365],
        '2년전': ['월', 365*2],
        '3년전': ['월', 365*3],
        '5년전': ['년', 365*5],
        '10년전': ['년', 365*10],
    }
    day_info = period_array.get(period, ['시간', 0])
    day = day_info[0]

    today = datetime.now().date()
    today_min_time = datetime.combine(today, datetime.min.time())
    today_max_time = datetime.combine(today, datetime.max.time())
    yesterday_min_time = today_min_time - timedelta(days=1)
    yesterday_max_time = today_max_time - timedelta(days=1)

    if period == '오늘':
        from_date = today_min_time
        to_date = today_max_time
    elif period == '어제':
        from_date = yesterday_min_time
        to_date = yesterday_max_time
    elif period == '내일':
        from_date = today_min_time + timedelta(days=1)
        to_date = today_max_time + timedelta(days=1)
    else:
        from_date = today_min_time - timedelta(days=day_info[1])
        to_date = yesterday_max_time

    bo_table_array = db.execute(select(Board.bo_table, Board.bo_subject).order_by(Board.bo_count_write.desc())).all()

    dialect = db.bind.dialect.name
    x_label = ""

    if day == '시간':
        x_label = 'hours'
        if dialect == 'postgresql':
            hours_expr = func.to_char(BoardNew.bn_datetime, 'HH24')
        else:
            hours_expr = func.substr(BoardNew.bn_datetime, 12, 2)

        result = db.execute(
            select(
                hours_expr.label(x_label),
                func.sum(case((BoardNew.wr_id == BoardNew.wr_parent, 1), else_=0)).label('write_count'),
                func.sum(case((BoardNew.wr_id != BoardNew.wr_parent, 1), else_=0)).label('comment_count')
            ).filter(
                BoardNew.bn_datetime.between(from_date, to_date),
                or_(BoardNew.bo_table == bo_table, bo_table == '')
            ).group_by(x_label).order_by(x_label)
        ).all()

    elif day == '일':
        x_label = 'days'
        if dialect == 'mysql':
            date_expr = func.date_format(BoardNew.bn_datetime, '%Y-%m-%d')
        elif dialect == 'postgresql':
            date_expr = func.to_char(BoardNew.bn_datetime, 'YYYY-MM-DD')
        elif dialect == 'sqlite':
            date_expr = func.strftime('%Y-%m-%d', BoardNew.bn_datetime)
        else:
            raise Exception(f"Unsupported dialect: {dialect}")

        result = db.execute(
            select(
                date_expr.label(x_label),
                func.sum(case((BoardNew.wr_id == BoardNew.wr_parent, 1), else_=0)).label('write_count'),
                func.sum(case((BoardNew.wr_id != BoardNew.wr_parent, 1), else_=0)).label('comment_count')
            ).filter(
                BoardNew.bn_datetime.between(from_date, to_date),
                or_(BoardNew.bo_table == bo_table, bo_table == '')
            ).group_by(x_label).order_by(x_label)
        ).all()

    elif day == '주':
        x_label = 'weeks'
        if dialect == 'mysql':
            week_expr = func.week(BoardNew.bn_datetime)
            concat_expr = func.concat(func.substr(BoardNew.bn_datetime, 1, 4), '-', week_expr)
        elif dialect == 'postgresql':
            concat_expr = func.to_char(BoardNew.bn_datetime, 'IYYY-IW')
        elif dialect == 'sqlite':
            week_expr = func.strftime('%W', BoardNew.bn_datetime)
            concat_expr = func.substr(BoardNew.bn_datetime, 1, 4) + '-' + week_expr
        else:
            raise Exception(f"Unsupported dialect: {dialect}")

        result = db.execute(
            select(
                concat_expr.label(x_label),
                func.sum(case((BoardNew.wr_id == BoardNew.wr_parent, 1), else_=0)).label('write_count'),
                func.sum(case((BoardNew.wr_id != BoardNew.wr_parent, 1), else_=0)).label('comment_count')
            ).filter(
                BoardNew.bn_datetime.between(from_date, to_date),
                or_(BoardNew.bo_table == bo_table, bo_table == '')
            ).group_by(x_label).order_by(x_label)
        ).all()

    elif day == '월':
        x_label = 'months'
        if dialect == 'mysql':
            month_expr = func.date_format(BoardNew.bn_datetime, '%Y-%m')
        elif dialect == 'postgresql':
            month_expr = func.to_char(BoardNew.bn_datetime, 'YYYY-MM')
        elif dialect == 'sqlite':
            month_expr = func.strftime('%Y-%m', BoardNew.bn_datetime)
        else:
            raise Exception(f"Unsupported dialect: {dialect}")

        result = db.execute(
            select(
                month_expr.label(x_label),
                func.sum(case((BoardNew.wr_id == BoardNew.wr_parent, 1), else_=0)).label('write_count'),
                func.sum(case((BoardNew.wr_id != BoardNew.wr_parent, 1), else_=0)).label('comment_count')
            ).filter(
                BoardNew.bn_datetime.between(from_date, to_date),
                or_(BoardNew.bo_table == bo_table, bo_table == '')
            ).group_by(x_label).order_by(x_label)
        ).all()

    elif day == '년':
        x_label = 'years'
        if dialect == 'mysql':
            year_expr = func.year(BoardNew.bn_datetime)
        elif dialect == 'postgresql':
            year_expr = func.extract('year', BoardNew.bn_datetime).cast(Integer)
        elif dialect == 'sqlite':
            year_expr = func.strftime('%Y', BoardNew.bn_datetime)
        else:
            raise Exception(f"Unsupported dialect: {dialect}")

        result = db.execute(
            select(
                year_expr.label(x_label),
                func.sum(case((BoardNew.wr_id == BoardNew.wr_parent, 1), else_=0)).label('write_count'),
                func.sum(case((BoardNew.wr_id != BoardNew.wr_parent, 1), else_=0)).label('comment_count')
            ).filter(
                BoardNew.bn_datetime.between(from_date, to_date),
                or_(BoardNew.bo_table == bo_table, bo_table == '')
            ).group_by(x_label).order_by(x_label)
        ).all()

    # 날짜 라벨과 카운트 집계 (순수 파이썬)
    labels = []
    write_counts = []
    comment_counts = []

    for row in result:
        raw_x = str(row[0]) if row[0] is not None else ""
        w_cnt = int(row[1]) if row[1] is not None else 0
        c_cnt = int(row[2]) if row[2] is not None else 0

        # 라벨 포맷팅
        if x_label == "hours":
            formatted_label = f"{raw_x}:00"
        elif x_label == "weeks":
            formatted_label = f"Week {raw_x}"
        else:
            formatted_label = raw_x

        labels.append(formatted_label)
        write_counts.append(w_cnt)
        comment_counts.append(c_cnt)

    # Chart.js를 사용한 경량 HTML 렌더링
    chart_type = 'line' if graph == 'line' else 'bar'
    if not labels:
        graph_html = '<div style="text-align:center; padding: 50px; font-size: 18px; color: #888;">그래프를 만들 데이터가 없습니다.</div>'
    else:
        graph_html = f'''
        <div style="width: 100%; max-height: 400px;">
            <canvas id="writeCountChart"></canvas>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const ctx = document.getElementById('writeCountChart').getContext('2d');
            new Chart(ctx, {{
                type: '{chart_type}',
                data: {{
                    labels: {labels},
                    datasets: [
                        {{
                            label: '글 작성 수',
                            data: {write_counts},
                            backgroundColor: 'rgba(54, 162, 235, 0.6)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        }},
                        {{
                            label: '댓글 작성 수',
                            data: {comment_counts},
                            backgroundColor: 'rgba(255, 99, 132, 0.6)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }}
                    }}
                }}
            }});
        </script>
        '''

    context = {
        "request": request,
        "bo_table_array": bo_table_array,
        "period_array": period_array,
        "bo_table": bo_table,
        "period": period,
        "graph": graph,
        "graph_html": graph_html,
    }
    return templates.TemplateResponse("write_count.html", context)
