import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_serbisyoq
from serbisyoq.db import get_db
from serbisyoq.mail import queue_confirmation, deliver_confirmation


class MailTest(unittest.TestCase):
    setUp = test_serbisyoq.AppTest.setUp
    tearDown = test_serbisyoq.AppTest.tearDown
    add = test_serbisyoq.AppTest.add
    post = test_serbisyoq.AppTest.post
    login = test_serbisyoq.AppTest.login

    def test_preview_is_explicit_and_contains_ticket(self):
        key = self.add()
        self.app.config['PUBLIC_BASE_URL'] = 'https://peso.example'
        with self.app.app_context():
            self.assertTrue(queue_confirmation(get_db(),key))
            row = get_db().execute('SELECT * FROM email_outbox').fetchone()
            self.assertEqual(row['status'],'Preview')
            self.assertIn('P-001',row['body'])
            self.assertIn(f'https://peso.example/ticket/{key}',row['body'])
            self.assertTrue((Path(self.app.config['MAIL_PREVIEW_DIR'])/f'{key}.eml').exists())
        self.assertIn(b'No email was sent',self.client.get('/ticket/'+key).data)
        self.assertEqual(self.client.get('/staff/email').status_code,302)
        self.login()
        self.assertIn(b'Local preview mode',self.client.get('/staff/email').data)

    @patch('serbisyoq.mail.smtplib.SMTP')
    def test_smtp_tls_delivery_and_no_duplicate_send(self, smtp):
        smtp.return_value.__enter__.return_value.send_message.return_value = {}
        self.app.config.update(SMTP_HOST='mail.example',SMTP_FROM='peso@example.com',
            SMTP_USERNAME='demo-user',SMTP_PASSWORD='test-only')
        key = self.add()
        with self.app.app_context():
            self.assertTrue(queue_confirmation(get_db(),key))
            self.assertFalse(deliver_confirmation(get_db(),key))
            self.assertEqual(get_db().execute('SELECT status FROM email_outbox').fetchone()[0],'Sent')
        connection = smtp.return_value.__enter__.return_value
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with('demo-user','test-only')
        self.assertEqual(connection.send_message.call_count,1)
        message = connection.send_message.call_args.args[0]
        self.assertIn('P-001',message.get_content())
        self.assertEqual(message['To'],'demo@example.com')

    @patch('serbisyoq.mail.smtplib.SMTP',side_effect=OSError('unavailable'))
    def test_failure_preserves_ticket_and_can_retry(self, smtp):
        self.app.config.update(SMTP_HOST='mail.example',SMTP_FROM='peso@example.com')
        key=self.add()
        with self.app.app_context():
            self.assertFalse(queue_confirmation(get_db(),key))
            self.assertEqual(get_db().execute('SELECT status FROM email_outbox').fetchone()[0],'Failed')
            self.assertEqual(get_db().execute('SELECT ticket FROM requests').fetchone()[0],'P-001')
            self.app.config['SMTP_HOST']=''
            self.assertTrue(deliver_confirmation(get_db(),key))
            self.assertEqual(get_db().execute('SELECT attempts FROM email_outbox').fetchone()[0],2)
