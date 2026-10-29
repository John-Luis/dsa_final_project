"""Transactional queue operations; no in-memory state is trusted across requests."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from .structures import RequestQueue


def now():
    return datetime.now(ZoneInfo('Asia/Manila')).isoformat(timespec='microseconds')


def today():
    return now()[:10]


def queue(db, day=None):
    return RequestQueue(db.execute(
        "SELECT * FROM requests WHERE day=? AND status='Waiting' ORDER BY queued_at,id",
        (day or today(),)).fetchall())


def event(db, key, action):
    db.execute('INSERT INTO events(request_id,action,at) VALUES (?,?,?)', (key,action,now()))


def submit(db, program, name, email, phone, concern):
    stamp, key = now(), uuid4().hex
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO sequences VALUES (?,?,1) ON CONFLICT(day,program) DO UPDATE SET value=value+1',
                   (stamp[:10],program))
        number = db.execute('SELECT value FROM sequences WHERE day=? AND program=?',
                            (stamp[:10],program)).fetchone()[0]
        ticket = f'{program}-{number:03d}'
        db.execute('INSERT INTO requests(id,ticket,day,program,name,email,phone,concern,created_at,queued_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (key,ticket,stamp[:10],program,name,email,phone,concern,stamp,stamp))
        event(db,key,'Registered')
        db.commit()
        return key
    except Exception:
        db.rollback()
        raise


def call_next(db, counter_id):
    try:
        db.execute('BEGIN IMMEDIATE')
        counter = db.execute('SELECT * FROM counters WHERE id=?',(counter_id,)).fetchone()
        if not counter:
            raise ValueError('Choose a valid counter.')
        if db.execute("SELECT 1 FROM requests WHERE counter_id=? AND status IN ('Called','For Assessment')",(counter_id,)).fetchone():
            raise ValueError('Complete or skip the current transaction before calling another applicant.')
        waiting = queue(db)
        entry = waiting.first(counter['program'])
        if not entry:
            raise ValueError('No applicants are waiting for this counter today.')
        # Linked-list dequeue preserves all other applicants’ relative order.
        entry = waiting.remove(entry['id'])
        db.execute("UPDATE requests SET status='Called',counter_id=?,called_at=? WHERE id=?",
                   (counter_id,now(),entry['id']))
        event(db,entry['id'],f'Called at Counter {counter_id}')
        db.commit()
        return entry['ticket']
    except Exception:
        db.rollback()
        raise


def transition(db, key, action, outcome='Served'):
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM requests WHERE id=?',(key,)).fetchone()
        if not row:
            raise ValueError('Request not found.')
        allowed = {'assess':(['Called'],'For Assessment'),
                   'complete':(['Called','For Assessment'],'Completed'),
                   'skip':(['Waiting','Called','For Assessment'],'Skipped'),
                   'requeue':(['Skipped'],'Waiting'),
                   'cancel':(['Waiting','Skipped'],'Cancelled')}
        if action not in allowed or row['status'] not in allowed[action][0]:
            raise ValueError('This action is no longer available. Refresh the queue and try again.')
        if action == 'requeue' and row['day'] != today():
            raise ValueError('Only today’s skipped requests can rejoin the queue. Submit a new request for another day.')
        status = allowed[action][1]
        if outcome not in ['Served','Referred','Requirements incomplete']:
            raise ValueError('Choose a valid outcome.')
        if row['status'] == 'Waiting':
            queue(db,row['day']).remove(key)
        db.execute('UPDATE requests SET status=?,counter_id=?,queued_at=?,called_at=?,completed_at=?,outcome=? WHERE id=?',
            (status, row['counter_id'] if action in ('assess','complete') else None,
             now() if action == 'requeue' else row['queued_at'],
             None if action == 'requeue' else row['called_at'],
             now() if action == 'complete' else None,
             outcome if action == 'complete' else None,key))
        event(db,key,status)
        db.commit()
    except Exception:
        db.rollback()
        raise
