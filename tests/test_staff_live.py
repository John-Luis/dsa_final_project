import unittest
import test_serbisyoq


class LiveStaffTest(unittest.TestCase):
    setUp=test_serbisyoq.AppTest.setUp
    tearDown=test_serbisyoq.AppTest.tearDown
    add=test_serbisyoq.AppTest.add
    post=test_serbisyoq.AppTest.post
    login=test_serbisyoq.AppTest.login

    def test_live_endpoint_requires_staff_and_applies_filters(self):
        self.assertEqual(self.client.get('/api/staff/queue').status_code,302)
        self.add('P',name='Live Applicant')
        self.add('E')
        self.login()
        response=self.client.get('/api/staff/queue?program=P')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['record_count'],1)
        self.assertIn('Live Applicant',response.json['rows_html'])
        self.assertIn('Looking for work',response.json['rows_html'])
        self.assertNotIn('E-001',response.json['rows_html'])
        page=self.client.get('/staff').data
        for text in [b'Staff navigation',b'TV media',b'Email log',b'<th>Concern</th>',b'staff.js']:
            self.assertIn(text,page)
