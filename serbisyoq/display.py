"""Privacy-safe public queue snapshots; never serialize applicant records."""
from .media import playlist
from .service import queue, now, today


def monitor_snapshot(db):
    waiting=queue(db).to_list()
    counters=db.execute("SELECT c.*,r.ticket,r.status FROM counters c LEFT JOIN requests r ON r.counter_id=c.id AND r.status IN ('Called','For Assessment') ORDER BY c.id").fetchall()
    return dict(server_time=now(),day=today(),total=len(waiting),
        counters=[dict(id=c['id'],name=c['name'],ticket=c['ticket'],status=c['status'],
            up_next=next((r['ticket'] for r in waiting if r['program']==c['program']),None)) for c in counters],
        upcoming=[dict(ticket=r['ticket'],counter={'P':1,'S':2,'E':3}[r['program']]) for r in waiting[:8]],
        announcement=db.execute("SELECT value FROM settings WHERE key='announcement'").fetchone()[0],
        playlist=playlist(db))
