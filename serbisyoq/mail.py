"""SMTP confirmations with durable delivery state and an explicit local preview mode."""
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app
from .service import now

MAIL_SCHEMA = '''
CREATE TABLE IF NOT EXISTS email_outbox (
 request_id TEXT PRIMARY KEY REFERENCES requests(id),
 recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('Pending','Sending','Sent','Preview','Failed')),
 attempts INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, error TEXT
);
'''


def queue_confirmation(db, key):
    row = db.execute('SELECT r.*,p.name program_name FROM requests r JOIN programs p ON p.code=r.program WHERE r.id=?',(key,)).fetchone()
    base = current_app.config['PUBLIC_BASE_URL'].rstrip('/')
    if base and (urlsplit(base).scheme not in ('http','https') or not urlsplit(base).netloc):
        base = ''
    body = (f"Hello {row['name']},\n\nYour PESO service request is confirmed.\n"
            f"Queue number: {row['ticket']}\nProgram: {row['program_name']}\n"
            f"Service date: {row['day']} (Philippine Standard Time)\n\n"
            'Please prepare your required documents and proceed to your assigned counter when called. '
            'PESO services are free.\n')
    if base:
        body += f"\nPrivate request status: {base}/ticket/{key}\nPublic queue monitor: {base}/monitor\n"
    body += '\nKeep your confirmation private. Thank you for using SerbisyoQ.\n'
    db.execute('INSERT OR IGNORE INTO email_outbox(request_id,recipient,subject,body,status,updated_at) VALUES (?,?,?,?,?,?)',
               (key,row['email'],f"PESO queue confirmation — {row['ticket']}",body,'Pending',now()))
    db.commit()
    return deliver_confirmation(db,key)


def deliver_confirmation(db, key):
    config = current_app.config
    claimed = db.execute("UPDATE email_outbox SET status='Sending',attempts=attempts+1,updated_at=?,error=NULL WHERE request_id=? AND status IN ('Pending','Failed','Preview')",(now(),key)).rowcount
    db.commit()
    if not claimed:
        return False
    row = db.execute('SELECT * FROM email_outbox WHERE request_id=?',(key,)).fetchone()
    message = EmailMessage()
    try:
        message['From'] = config['SMTP_FROM'] or 'PESO SerbisyoQ <demo@localhost>'
        message['To'] = row['recipient']
        message['Subject'] = row['subject']
        message.set_content(row['body'])
        if not config['SMTP_HOST']:
            directory = Path(config['MAIL_PREVIEW_DIR'])
            directory.mkdir(parents=True,exist_ok=True)
            (directory/f'{key}.eml').write_bytes(message.as_bytes())
            status = 'Preview'
        else:
            if not config['SMTP_FROM']:
                raise ValueError('SMTP_FROM must be configured')
            mode = config['SMTP_SECURITY']
            if mode not in ('starttls','ssl'):
                raise ValueError('SMTP_SECURITY must be starttls or ssl')
            transport = smtplib.SMTP_SSL if mode=='ssl' else smtplib.SMTP
            kwargs = {'host':config['SMTP_HOST'],'port':config['SMTP_PORT'],'timeout':10}
            if mode=='ssl':
                kwargs['context'] = ssl.create_default_context()
            with transport(**kwargs) as smtp:
                if mode=='starttls':
                    smtp.ehlo()
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if config['SMTP_USERNAME']:
                    smtp.login(config['SMTP_USERNAME'],config['SMTP_PASSWORD'])
                refused = smtp.send_message(message)
                if refused:
                    raise smtplib.SMTPRecipientsRefused(refused)
            status = 'Sent'
        db.execute('UPDATE email_outbox SET status=?,updated_at=?,error=NULL WHERE request_id=?',(status,now(),key))
        db.commit()
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        # Do not persist SMTP exception text: provider responses can contain sensitive data.
        db.execute("UPDATE email_outbox SET status='Failed',updated_at=?,error=? WHERE request_id=?",
                   (now(),'Delivery failed. Check the private SMTP configuration before retrying.',key))
        db.commit()
        return False
