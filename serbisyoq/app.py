import csv
import io
import os
import re
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

import qrcode
import qrcode.image.svg
from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for, Response)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, init_db, close_db
from .service import submit, queue, today, now, call_next, transition


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('staff'):
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(DATABASE=str(Path(app.instance_path) / 'serbisyoq.sqlite'),
        SECRET_KEY=os.environ.get('SERBISYOQ_SECRET_KEY') or secrets.token_hex(32),
        STAFF_PASSWORD_HASH=generate_password_hash(os.environ.get('SERBISYOQ_STAFF_PASSWORD','peso-demo')),
        DEMO_MODE=not bool(os.environ.get('SERBISYOQ_STAFF_PASSWORD')),
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.before_request
    def csrf_check():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'],request.form.get('csrf','')):
            abort(400, 'Your form expired. Reload the page and try again.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.context_processor
    def context():
        return {'programs':get_db().execute('SELECT * FROM programs ORDER BY code DESC').fetchall(),
                'current_day':today(), 'demo_mode':app.config['DEMO_MODE']}

    @app.template_filter('clock')
    def clock(value):
        return datetime.fromisoformat(value).strftime('%I:%M %p') if value else '—'

    @app.get('/')
    def home():
        db = get_db()
        counts = {r['program']:r['n'] for r in db.execute("SELECT program,COUNT(*) n FROM requests WHERE day=? AND status='Waiting' GROUP BY program",(today(),))}
        return render_template('home.html',counts=counts)

    @app.route('/request', methods=['GET','POST'])
    def intake():
        db = get_db()
        selected = request.form.get('program') if request.method == 'POST' else request.args.get('program','P')
        program = db.execute('SELECT * FROM programs WHERE code=?',(selected,)).fetchone()
        if not program:
            abort(400,'Choose one of the available programs.')
        errors = []
        if request.method == 'POST':
            name, email, phone, concern = [request.form.get(k,'').strip() for k in ('name','email','phone','concern')]
            if not 2 <= len(name) <= 100:
                errors.append('Enter a name between 2 and 100 characters.')
            if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
                errors.append('Enter a valid email address.')
            if not re.fullmatch(r'[+0-9()\s-]{7,24}',phone):
                errors.append('Enter a valid contact number (7–24 characters).')
            if len(concern) > 1000:
                errors.append('Keep your concern within 1,000 characters.')
            if not request.form.get('consent') or not request.form.get('requirements'):
                errors.append('Confirm that you reviewed the requirements and consent to processing.')
            if not errors:
                key = submit(db,selected,name,email,phone,concern)
                return redirect(url_for('receipt',key=key),code=303)
        return render_template('intake.html',program=program,errors=errors)

    @app.get('/ticket/<key>')
    def receipt(key):
        db = get_db()
        row = db.execute('SELECT r.*,p.name program_name FROM requests r JOIN programs p ON r.program=p.code WHERE r.id=?',(key,)).fetchone()
        if not row:
            abort(404)
        waiting = queue(db,row['day']).to_list()
        ahead = next((sum(x['program']==row['program'] for x in waiting[:i]) for i,x in enumerate(waiting) if x['id']==key),None)
        return render_template('receipt.html',row=row,ahead=ahead)

    @app.get('/qr.svg')
    def qr():
        image = qrcode.make(url_for('home',_external=True),image_factory=qrcode.image.svg.SvgPathImage)
        output = io.BytesIO()
        image.save(output)
        return Response(output.getvalue(),mimetype='image/svg+xml')

    @app.get('/monitor')
    def monitor():
        db = get_db()
        counters = db.execute("SELECT c.*,r.ticket,r.status FROM counters c LEFT JOIN requests r ON r.counter_id=c.id AND r.status IN ('Called','For Assessment') ORDER BY c.id").fetchall()
        waiting = queue(db).to_list()
        announcement = db.execute("SELECT value FROM settings WHERE key='announcement'").fetchone()[0]
        return render_template('monitor.html',counters=counters,waiting=waiting[:8],total=len(waiting),announcement=announcement)

    register_staff(app)
    return app


def register_staff(app):
    @app.route('/staff/login', methods=['GET','POST'])
    def login():
        if request.method == 'POST':
            if check_password_hash(app.config['STAFF_PASSWORD_HASH'],request.form.get('password','')):
                session.clear()
                session['staff'] = True
                session['csrf'] = secrets.token_hex(32)
                return redirect(url_for('dashboard'),code=303)
            flash('Incorrect staff password. Please try again.','error')
        return render_template('login.html')

    @app.post('/staff/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'),code=303)

    @app.get('/staff')
    @staff_required
    def dashboard():
        db = get_db()
        day = request.args.get('day',today())
        try:
            datetime.strptime(day,'%Y-%m-%d')
        except ValueError:
            abort(400,'Choose a valid date.')
        program, status, search = [request.args.get(k,'').strip() for k in ('program','status','search')]
        sql, params = 'SELECT r.*,p.name program_name FROM requests r JOIN programs p ON r.program=p.code WHERE day=?', [day]
        if program:
            sql += ' AND program=?'
            params.append(program)
        if status:
            sql += ' AND status=?'
            params.append(status)
        if search:
            sql += ' AND (r.name LIKE ? OR ticket LIKE ?)'
            params.extend(['%'+search+'%']*2)
        rows = db.execute(sql+' ORDER BY queued_at,id',params).fetchall()
        stats = {r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM requests WHERE day=? GROUP BY status',(day,))}
        counters = db.execute("SELECT c.*,r.ticket,r.id request_id,r.status FROM counters c LEFT JOIN requests r ON r.counter_id=c.id AND r.status IN ('Called','For Assessment') ORDER BY c.id").fetchall()
        return render_template('dashboard.html',rows=rows,stats=stats,counters=counters,day=day,
            announcement=db.execute("SELECT value FROM settings WHERE key='announcement'").fetchone()[0])

    @app.post('/staff/call/<int:counter>')
    @staff_required
    def call(counter):
        try:
            ticket = call_next(get_db(),counter)
            flash(f'{ticket} called to Counter {counter}.','success')
        except ValueError as error:
            flash(str(error),'error')
        return redirect(url_for('dashboard'),code=303)

    @app.post('/staff/request/<key>/<action>')
    @staff_required
    def update_request(key,action):
        try:
            transition(get_db(),key,action,request.form.get('outcome','Served'))
            flash('Transaction updated.','success')
        except ValueError as error:
            flash(str(error),'error')
        return redirect(url_for('dashboard'),code=303)

    @app.get('/staff/request/<key>')
    @staff_required
    def detail(key):
        db = get_db()
        row = db.execute('SELECT r.*,p.name program_name FROM requests r JOIN programs p ON p.code=r.program WHERE r.id=?',(key,)).fetchone()
        if not row:
            abort(404)
        neighbors = queue(db,row['day']).neighbors(key) if row['status']=='Waiting' else (None,None)
        events = db.execute('SELECT * FROM events WHERE request_id=? ORDER BY id',(key,)).fetchall()
        return render_template('detail.html',row=row,neighbors=neighbors,events=events)

    @app.post('/staff/announcement')
    @staff_required
    def announcement():
        text = request.form.get('announcement','').strip()
        if not 1 <= len(text) <= 400:
            flash('Announcements must contain 1–400 characters.','error')
        else:
            db = get_db()
            db.execute("UPDATE settings SET value=? WHERE key='announcement'",(text,))
            db.commit()
            flash('Public announcement updated.','success')
        return redirect(url_for('dashboard'),code=303)

