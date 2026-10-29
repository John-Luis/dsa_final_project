"""Shared filtered staff view used by the initial page and live updates."""
from datetime import datetime
from flask import request, abort
from .service import today


def dashboard_data(db):
    day=request.args.get('day',today())
    try:
        datetime.strptime(day,'%Y-%m-%d')
    except ValueError:
        abort(400,'Choose a valid date.')
    program,status,search=[request.args.get(k,'').strip() for k in ('program','status','search')]
    sql,params='SELECT r.*,p.name program_name FROM requests r JOIN programs p ON r.program=p.code WHERE day=?',[day]
    if program:
        sql+=' AND program=?'; params.append(program)
    if status:
        sql+=' AND status=?'; params.append(status)
    if search:
        sql+=' AND (r.name LIKE ? OR ticket LIKE ?)'; params.extend(['%'+search+'%']*2)
    rows=db.execute(sql+' ORDER BY queued_at,id',params).fetchall()
    stats={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM requests WHERE day=? GROUP BY status',(day,))}
    counters=db.execute("SELECT c.*,r.ticket,r.id request_id,r.status FROM counters c LEFT JOIN requests r ON r.counter_id=c.id AND r.status IN ('Called','For Assessment') ORDER BY c.id").fetchall()
    return dict(rows=rows,stats=stats,counters=counters,day=day,
        announcement=db.execute("SELECT value FROM settings WHERE key='announcement'").fetchone()[0])
