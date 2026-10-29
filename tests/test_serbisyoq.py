import csv
import io
import re
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from serbisyoq.app import create_app
from serbisyoq.db import get_db
from serbisyoq.service import submit, call_next, transition, queue, today
from serbisyoq.structures import RequestQueue
from serbisyoq.reporting import summarize, csv_safe


class StructuresTest(unittest.TestCase):
    def test_links_lookup_and_removal(self):
        q = RequestQueue([{'id':str(i),'program':p} for i,p in enumerate('PSP')])
        self.assertEqual(q.neighbors('1')[0]['id'],'0')
        self.assertEqual(q.neighbors('1')[1]['id'],'2')
        q.remove('1')
        self.assertEqual(q.neighbors('0')[1]['id'],'2')
        self.assertEqual(q.first('P')['id'],'0')
        self.assertIsNone(q.first('E'))
        q.remove('0'); q.remove('2')
        self.assertIsNone(q.head); self.assertIsNone(q.tail)
        self.assertEqual(q.to_list(),[])

    def test_duplicate_ids_rejected(self):
        q = RequestQueue([{'id':'a','program':'P'}])
        with self.assertRaises(ValueError):
            q.append({'id':'a','program':'P'})


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING':True,'DATABASE':str(Path(self.tmp.name)/'test.sqlite'),'SECRET_KEY':'test-only'})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def post(self,path,data=None):
        self.client.get('/')
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        return self.client.post(path,data={'csrf':csrf,**(data or {})})

    def login(self):
        return self.post('/staff/login',{'password':'peso-demo'})

    def add(self,program='P',name='Demo Applicant'):
        with self.app.app_context():
            return submit(get_db(),program,name,'demo@example.com','09123456789','Looking for work')

    def test_resident_submission_and_private_receipt(self):
        response = self.post('/request',{'program':'P','name':'Demo Applicant','email':'demo@example.com','phone':'09123456789','requirements':'on','consent':'on'})
        self.assertEqual(response.status_code,303)
        page = self.client.get(response.location)
        self.assertIn(b'P-001',page.data)
        self.assertIn(b'0</strong> applicant(s) ahead',page.data)
        self.assertEqual(self.client.get('/ticket/not-a-real-token').status_code,404)

    def test_invalid_form_creates_nothing(self):
        response = self.post('/request',{'program':'P','name':'X','email':'bad','phone':'x'})
        self.assertIn(b'Enter a valid email',response.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)

    def test_csrf_and_staff_access(self):
        self.assertEqual(self.client.post('/request',data={}).status_code,400)
        for route in ['/staff','/staff/reports','/staff/reports?export=csv']:
            self.assertEqual(self.client.get(route).status_code,302)
        self.assertEqual(self.post('/staff/call/1').status_code,302)
        self.post('/staff/login',{'password':'wrong'})
        self.assertEqual(self.client.get('/staff').status_code,302)
        self.login()
        self.assertEqual(self.client.get('/staff').status_code,200)
        self.post('/staff/logout')
        self.assertEqual(self.client.get('/staff').status_code,302)

    def test_fifo_program_eligibility_and_counter_conflict(self):
        employer = self.add('E')
        first, second = self.add(),self.add()
        with self.app.app_context():
            db = get_db()
            self.assertEqual(call_next(db,1),'P-001')
            with self.assertRaises(ValueError): call_next(db,1)
            transition(db,first,'complete','Referred')
            self.assertEqual(call_next(db,1),'P-002')
            self.assertEqual(call_next(db,3),'E-001')
            self.assertEqual(db.execute('SELECT status FROM requests WHERE id=?',(employer,)).fetchone()[0],'Called')

    def test_skip_requeue_moves_to_tail(self):
        first,second = self.add(),self.add()
        with self.app.app_context():
            db = get_db()
            transition(db,first,'skip')
            transition(db,first,'requeue')
            self.assertEqual(queue(db).first()['id'],second)
            self.assertEqual(call_next(db,1),'P-002')
            transition(db,second,'assess')
            transition(db,second,'complete')
            self.assertEqual(call_next(db,1),'P-001')

    def test_invalid_transition_and_empty_queue(self):
        key=self.add()
        with self.app.app_context():
            db=get_db()
            with self.assertRaises(ValueError): transition(db,key,'complete')
            with self.assertRaises(ValueError): call_next(db,3)
            with self.assertRaises(ValueError): call_next(db,99)
            self.assertEqual(queue(db).first()['id'],key)

    def test_concurrent_submission_numbers_unique(self):
        def create(i):
            with self.app.app_context():
                return submit(get_db(),'P',f'Demo {i}','demo@example.com','09123456789','')
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(create,range(12)))
        self.assertEqual(len(set(ids)),12)
        with self.app.app_context():
            tickets=[r[0] for r in get_db().execute('SELECT ticket FROM requests')]
            self.assertEqual(len(set(tickets)),12)
            self.assertIn('P-012',tickets)

    def test_concurrent_counter_calls_only_one_wins(self):
        self.add(); self.add()
        def call(_):
            with self.app.app_context():
                try: return call_next(get_db(),1)
                except ValueError: return 'busy'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(call,range(2)))
        self.assertCountEqual(results,['P-001','busy'])

    def test_public_monitor_excludes_personal_details(self):
        self.add(name='PRIVATE APPLICANT')
        page=self.client.get('/monitor')
        self.assertEqual(page.status_code,200)
        self.assertIn(b'P-001',page.data)
        self.assertNotIn(b'PRIVATE APPLICANT',page.data)
        self.assertNotIn(b'demo@example.com',page.data)
        self.assertIn(b'http-equiv="refresh"',page.data)

    def test_admin_flow_search_announcements_and_reports(self):
        key=self.add()
        self.login()
        self.assertIn(b'Demo Applicant',self.client.get('/staff?search=P-001').data)
        self.assertIn(b'Applicant details',self.client.get('/staff/request/'+key).data)
        self.post('/staff/call/1')
        self.assertIn(b'P-001',self.client.get('/monitor').data)
        self.post(f'/staff/request/{key}/assess')
        self.post(f'/staff/request/{key}/complete',{'outcome':'Referred'})
        self.post('/staff/announcement',{'announcement':'Bring your resume.'})
        self.assertIn(b'Bring your resume.',self.client.get('/monitor').data)
        report=self.client.get('/staff/reports')
        self.assertEqual(report.status_code,200)
        self.assertIn(b'1 called requests measured',report.data)
        export=self.client.get('/staff/reports?export=csv')
        rows=list(csv.DictReader(io.StringIO(export.data.decode())))
        self.assertEqual(rows[0]['status'],'Completed')
        self.assertEqual(rows[0]['outcome'],'Referred')
        self.assertNotIn('name',rows[0])
        self.assertEqual(self.client.get('/staff/reports?start=bad').status_code,400)
        self.assertEqual(self.client.get('/staff/reports?start=2030-01-01&end=2020-01-01').status_code,400)

    def test_restart_retains_requests(self):
        self.add()
        other=create_app({'TESTING':True,'DATABASE':self.app.config['DATABASE']})
        self.assertIn(b'P-001',other.test_client().get('/monitor').data)

    def test_safe_rendering_qr_and_unknown_program(self):
        self.add(name='<script>alert(1)</script>')
        self.login()
        self.assertNotIn(b'<script>alert(1)</script>',self.client.get('/staff').data)
        qr=self.client.get('/qr.svg')
        self.assertEqual(qr.status_code,200)
        self.assertIn(b'<svg',qr.data)
        self.assertEqual(self.client.get('/request?program=unknown').status_code,400)

    def test_summary_known_times(self):
        rows=[dict(program='P',status='Completed',created_at='2026-10-30T08:00:00+08:00',queued_at='2026-10-30T08:00:00+08:00',called_at='2026-10-30T08:10:00+08:00',completed_at='2026-10-30T08:15:00+08:00')]
        result=summarize(rows)
        self.assertEqual(result['average_wait'],10)
        self.assertEqual(result['average_service'],5)
        self.assertEqual(result['peak'],8)
        self.assertIsNone(summarize([])['average_wait'])
        self.assertEqual(csv_safe(' =SUM(A1)'),"' =SUM(A1)")


if __name__=='__main__':
    unittest.main()
