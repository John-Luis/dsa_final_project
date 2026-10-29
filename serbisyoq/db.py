import sqlite3
from pathlib import Path
from flask import current_app, g

SCHEMA = '''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS programs (
 code TEXT PRIMARY KEY, name TEXT NOT NULL, audience TEXT NOT NULL,
 description TEXT NOT NULL, requirements TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS counters (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, program TEXT REFERENCES programs(code)
);
CREATE TABLE IF NOT EXISTS requests (
 id TEXT PRIMARY KEY, ticket TEXT NOT NULL, day TEXT NOT NULL,
 program TEXT NOT NULL REFERENCES programs(code), name TEXT NOT NULL,
 email TEXT NOT NULL, phone TEXT NOT NULL, concern TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Waiting' CHECK(status IN
 ('Waiting','Called','For Assessment','Skipped','Completed','Cancelled')),
 counter_id INTEGER REFERENCES counters(id), created_at TEXT NOT NULL,
 queued_at TEXT NOT NULL, called_at TEXT, completed_at TEXT, outcome TEXT,
 UNIQUE(day,ticket)
);
CREATE TABLE IF NOT EXISTS sequences (
 day TEXT NOT NULL, program TEXT NOT NULL REFERENCES programs(code),
 value INTEGER NOT NULL, PRIMARY KEY(day,program)
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id),
 action TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS queue_order ON requests(day,status,queued_at);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_per_counter ON requests(counter_id)
 WHERE status IN ('Called','For Assessment');
'''
PROGRAMS = [
 ('P','Job Placement','Jobseekers','Job referral, employment matching, and career guidance.',
  'Updated résumé|Valid government or school ID|Available certificates, if applicable'),
 ('S','SPES Application','Students & out-of-school youth','Get assistance with the Special Program for Employment of Students.',
  'Valid ID or birth certificate|Proof of enrollment or education status|Proof of family income'),
 ('E','Employer Registration','Employers','Register your establishment and submit job vacancies.',
  'Business registration|Authorized representative’s valid ID|List of job vacancies'),
]


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def init_db():
    Path(current_app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    from .mail import MAIL_SCHEMA
    from .media import MEDIA_SCHEMA
    db.executescript(SCHEMA + MAIL_SCHEMA + MEDIA_SCHEMA)
    db.executemany('INSERT OR IGNORE INTO programs VALUES (?,?,?,?,?)', PROGRAMS)
    db.executemany('INSERT OR IGNORE INTO counters VALUES (?,?,?)',
                   [(1,'Jobseekers','P'), (2,'SPES assistance','S'), (3,'Employers','E')])
    db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',
               ('announcement','Welcome to PESO. Please prepare your documents before your number is called. All services are free.'))
    db.commit()


def close_db(error=None):
    db = g.pop('db', None)
    if db:
        db.close()
