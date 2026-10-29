"""Staff-managed local multimedia playlist for the public monitor."""
from pathlib import Path
from uuid import uuid4
from flask import current_app, request, render_template, redirect, url_for, flash, abort, send_from_directory
from .db import get_db

MEDIA_SCHEMA = '''CREATE TABLE IF NOT EXISTS media (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL CHECK(kind IN ('image','video')), seconds INTEGER NOT NULL CHECK(seconds BETWEEN 5 AND 120)
);'''


def identify(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'image','png'
    if data.startswith(b'\xff\xd8\xff'): return 'image','jpg'
    if data[:6] in (b'GIF87a',b'GIF89a'): return 'image','gif'
    if data[:4]==b'RIFF' and data[8:12]==b'WEBP': return 'image','webp'
    if data[4:8]==b'ftyp': return 'video','mp4'
    if data[:4]==b'\x1aE\xdf\xa3': return 'video','webm'
    raise ValueError('Use a PNG, JPEG, GIF, WebP, MP4, or WebM file. SVG and HTML uploads are not allowed.')


def playlist(db):
    rows = db.execute('SELECT * FROM media ORDER BY id').fetchall()
    if rows:
        return [dict(id=r['id'],title=r['title'],kind=r['kind'],seconds=r['seconds'],
                     url=url_for('media_file',key=r['id'])) for r in rows]
    return [dict(id=f'default-{i}',title=title,kind='image',seconds=8,
                 url=url_for('static',filename=f'announcements/{i}.svg'))
            for i,title in [(1,'Your next opportunity starts at PESO'),(2,'Prepare for a smoother visit')]]


def register_media(app, staff_required):
    @app.get('/staff/media')
    @staff_required
    def media_library():
        return render_template('media.html',rows=get_db().execute('SELECT * FROM media ORDER BY id').fetchall())

    @app.post('/staff/media')
    @staff_required
    def media_add():
        upload = request.files.get('file')
        title = request.form.get('title','').strip()
        try:
            seconds = int(request.form.get('seconds','8'))
            if not 5 <= seconds <= 120 or not 1 <= len(title) <= 100:
                raise ValueError('Enter a title (1–100 characters) and a duration of 5–120 seconds.')
            if not upload or not upload.filename:
                raise ValueError('Choose a media file.')
            data = upload.read(25*1024*1024+1)
            if len(data)>25*1024*1024:
                raise ValueError('Media files must be 25 MB or smaller.')
            kind, extension = identify(data)
        except ValueError as error:
            flash(str(error),'error')
            return redirect(url_for('media_library'),code=303)
        directory = Path(app.config['MEDIA_DIR'])
        directory.mkdir(parents=True,exist_ok=True)
        filename = f'{uuid4().hex}.{extension}'
        target = directory/filename
        try:
            target.write_bytes(data)
            db = get_db()
            db.execute('INSERT INTO media(title,filename,kind,seconds) VALUES (?,?,?,?)',(title,filename,kind,seconds))
            db.commit()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        flash('Media added to the TV playlist.','success')
        return redirect(url_for('media_library'),code=303)

    @app.post('/staff/media/<int:key>/delete')
    @staff_required
    def media_delete(key):
        db = get_db()
        row = db.execute('SELECT * FROM media WHERE id=?',(key,)).fetchone()
        if not row:
            abort(404)
        db.execute('DELETE FROM media WHERE id=?',(key,))
        db.commit()
        (Path(app.config['MEDIA_DIR'])/row['filename']).unlink(missing_ok=True)
        flash('Media removed from the playlist.','success')
        return redirect(url_for('media_library'),code=303)

    @app.get('/media/<int:key>')
    def media_file(key):
        row = get_db().execute('SELECT filename FROM media WHERE id=?',(key,)).fetchone()
        if not row:
            abort(404)
        return send_from_directory(app.config['MEDIA_DIR'],row['filename'],conditional=True)
