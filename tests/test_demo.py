import unittest
import test_serbisyoq
from serbisyoq.demo import seed_demo
from serbisyoq.db import get_db
from serbisyoq.service import today


class DemoTest(unittest.TestCase):
    setUp = test_serbisyoq.AppTest.setUp
    tearDown = test_serbisyoq.AppTest.tearDown
    def test_seed_preserves_existing_data(self):
        with self.app.app_context():
            db=get_db()
            self.assertTrue(seed_demo(db))
            self.assertFalse(seed_demo(db))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],9)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests WHERE status='Called'").fetchone()[0],3)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
