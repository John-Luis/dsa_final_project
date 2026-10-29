import csv
import io
import os
import re
import secrets
from datetime import date, datetime
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
        SMTP_HOST=os.environ.get('SMTP_HOST',''),
        SMTP_PORT=int(os.environ.get('SMTP_PORT','587')),
        SMTP_USERNAME=os.environ.get('SMTP_USERNAME',''),
        SMTP_PASSWORD=os.environ.get('SMTP_PASSWORD',''),
        SMTP_FROM=os.environ.get('SMTP_FROM',''),
        SMTP_SECURITY=os.environ.get('SMTP_SECURITY','starttls'),
        PUBLIC_BASE_URL=os.environ.get('SERBISYOQ_PUBLIC_URL',''),
        MAIL_PREVIEW_DIR=str(Path(app.instance_path)/'mail-preview'),
        MEDIA_DIR=str(Path(app.instance_path)/'media'),
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.before_request
    def csrf_check():
        if request.endpoint == 'media_add':
            request.max_content_length = 26 * 1024 * 1024
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
                from .mail import queue_confirmation
                queue_confirmation(db,key)
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
        return render_template('receipt.html',row=row,ahead=ahead,mail=db.execute('SELECT status FROM email_outbox WHERE request_id=?',(key,)).fetchone())

    @app.get('/qr.svg')
    def qr():
        image = qrcode.make(url_for('home',_external=True),image_factory=qrcode.image.svg.SvgPathImage)
        output = io.BytesIO()
        image.save(output)
        return Response(output.getvalue(),mimetype='image/svg+xml')

    @app.get('/monitor')
    def monitor():
        from .display import monitor_snapshot
        return render_template('monitor.html',state=monitor_snapshot(get_db()))

    @app.get('/api/monitor')
    def monitor_data():
        from .display import monitor_snapshot
        return monitor_snapshot(get_db())

    @app.cli.command('seed-demo')
    def seed_demo_command():
        """Add fictional demonstration records only when the database is empty."""
        import click
        from .demo import seed_demo
        click.echo('Added 9 fictional demo requests.' if seed_demo(get_db()) else 'Database already has requests; no records changed.')

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def friendly_error(error):
        return render_template('error.html',error=error),error.code

    register_staff(app)
    from .media import register_media
    register_media(app,staff_required)
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
        from .staff import dashboard_data
        return render_template('dashboard.html',**dashboard_data(get_db()))

    @app.get('/api/staff/queue')
    @staff_required
    def staff_queue_data():
        from .staff import dashboard_data
        data=dashboard_data(get_db())
        return dict(stats_html=render_template('partials/stats.html',**data),
                    counters_html=render_template('partials/counters.html',**data),
                    rows_html=render_template('partials/rows.html',**data),
                    record_count=len(data['rows']))

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


    @app.get('/staff/reports')
    @staff_required
    def reports():
        from .reporting import summarize, csv_safe
        start, end = request.args.get('start',today()), request.args.get('end',today())
        try:
            date.fromisoformat(start)
            date.fromisoformat(end)
            if start > end:
                raise ValueError()
        except ValueError:
            abort(400,'Choose a valid date range with the start on or before the end.')
        rows = get_db().execute('SELECT r.*,p.name program_name FROM requests r JOIN programs p ON r.program=p.code WHERE day BETWEEN ? AND ? ORDER BY created_at,id',(start,end)).fetchall()
        if request.args.get('export') == 'csv':
            output = io.StringIO(newline='')
            writer = csv.writer(output)
            fields = ['day','ticket','program_name','status','outcome','created_at','called_at','completed_at']
            writer.writerow(fields)
            writer.writerows([[csv_safe(r[k]) for k in fields] for r in rows])
            return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="serbisyoq-{start}-to-{end}.csv"'})
        from .charts import chart_data, line_svg, pie_svg, STATUS_COLORS
        charts=chart_data(rows,start,end)
        return render_template('reports.html',summary=summarize(rows),start=start,end=end,
            charts=charts,line_chart=line_svg(charts['trend']),pie_chart=pie_svg(charts['statuses']),
            status_colors=STATUS_COLORS)


    @app.get('/staff/email')
    @staff_required
    def email_outbox():
        rows = get_db().execute('SELECT m.*,r.ticket,r.day FROM email_outbox m JOIN requests r ON r.id=m.request_id ORDER BY m.updated_at DESC LIMIT 100').fetchall()
        return render_template('email.html',rows=rows,smtp_enabled=bool(app.config['SMTP_HOST']))

    @app.post('/staff/email/<key>/retry')
    @staff_required
    def retry_email(key):
        from .mail import deliver_confirmation
        result = deliver_confirmation(get_db(),key)
        flash('Confirmation processed. Check its delivery status below.' if result else 'Message was not sent. Check its status and SMTP settings.','success' if result else 'error')
        return redirect(url_for('email_outbox'),code=303)


    @app.get('/staff/email/<key>')
    @staff_required
    def email_preview(key):
        row=get_db().execute('SELECT * FROM email_outbox WHERE request_id=?',(key,)).fetchone()
        if not row:
            abort(404)
        return render_template('email_preview.html',row=row)
