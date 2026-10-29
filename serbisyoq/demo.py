"""Opt-in fictional records for a classroom walkthrough; never overwrites data."""
from datetime import datetime, timedelta
from .service import submit, now, today


def seed_demo(db):
    if db.execute('SELECT 1 FROM requests LIMIT 1').fetchone():
        return False
    names = ['Alex Sample','Sam Example','Robin Demo','Casey Sample','Taylor Example',
             'Jordan Demo','Drew Sample','Avery Example','Morgan Demo']
    stamp = datetime.fromisoformat(now())
    for i,name in enumerate(names):
        program = ['P','S','E'][i%3]
        key = submit(db,program,name,f'demo{i+1}@example.com','09123456789','Fictional classroom demonstration request.')
        created = (stamp - timedelta(minutes=45-i*4)).isoformat()
        db.execute('UPDATE requests SET created_at=?,queued_at=? WHERE id=?',(created,created,key))
        db.execute('UPDATE events SET at=? WHERE request_id=?',(created,key))
        if i < 3:
            called = (datetime.fromisoformat(created)+timedelta(minutes=6)).isoformat()
            completed = (datetime.fromisoformat(called)+timedelta(minutes=8)).isoformat()
            db.execute("UPDATE requests SET status='Completed',counter_id=?,called_at=?,completed_at=?,outcome='Served' WHERE id=?",(i+1,called,completed,key))
            db.executemany('INSERT INTO events(request_id,action,at) VALUES (?,?,?)',[(key,f'Called at Counter {i+1}',called),(key,'Completed',completed)])
        elif i < 6:
            called = (datetime.fromisoformat(created)+timedelta(minutes=5)).isoformat()
            db.execute("UPDATE requests SET status='Called',counter_id=?,called_at=? WHERE id=?",(i-2,called,key))
            db.execute('INSERT INTO events(request_id,action,at) VALUES (?,?,?)',(key,f'Called at Counter {i-2}',called))
        db.commit()
    return True
