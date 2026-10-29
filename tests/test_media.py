import io
import unittest
import test_serbisyoq
from serbisyoq.db import get_db
from serbisyoq.media import identify


class MediaTest(unittest.TestCase):
    setUp=test_serbisyoq.AppTest.setUp
    tearDown=test_serbisyoq.AppTest.tearDown
    post=test_serbisyoq.AppTest.post
    login=test_serbisyoq.AppTest.login

    def test_upload_public_file_and_remove(self):
        self.login()
        self.post('/staff/media',{'title':'Job fair','seconds':'8','file':(io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'demo'),'../../unsafe.html')})
        with self.app.app_context():
            row=get_db().execute('SELECT * FROM media').fetchone()
            self.assertEqual(row['kind'],'image')
            self.assertTrue(row['filename'].endswith('.png'))
            key=row['id']
        with self.client.get(f'/media/{key}') as response:
            self.assertEqual(response.mimetype,'image/png')
        self.post(f'/staff/media/{key}/delete')
        self.assertEqual(self.client.get(f'/media/{key}').status_code,404)

    def test_reject_html_and_invalid_duration(self):
        self.assertEqual(self.client.get('/staff/media').status_code,302)
        self.login()
        for seconds,data in [('8',b'<script>alert(1)</script>'),('0',b'\x89PNG\r\n\x1a\n')]:
            self.post('/staff/media',{'title':'Unsafe','seconds':seconds,'file':(io.BytesIO(data),'test.png')})
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM media').fetchone()[0],0)
        with self.assertRaises(ValueError): identify(b'<svg></svg>')
        self.assertEqual(identify(b'\0\0\0\x20ftypisom'),('video','mp4'))
