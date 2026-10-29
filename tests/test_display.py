import unittest
import test_serbisyoq


class DisplayTest(unittest.TestCase):
    setUp=test_serbisyoq.AppTest.setUp
    tearDown=test_serbisyoq.AppTest.tearDown
    add=test_serbisyoq.AppTest.add
    post=test_serbisyoq.AppTest.post
    login=test_serbisyoq.AppTest.login

    def test_counter_next_and_privacy(self):
        self.add('P',name='PRIVATE PERSON')
        self.add('P')
        self.add('E')
        self.login()
        self.post('/staff/call/1')
        response=self.client.get('/api/monitor')
        state=response.json
        self.assertEqual(state['counters'][0]['ticket'],'P-001')
        self.assertEqual(state['counters'][0]['up_next'],'P-002')
        self.assertEqual(state['counters'][2]['up_next'],'E-001')
        self.assertEqual(len(state['playlist']),2)
        for private in [b'PRIVATE PERSON',b'demo@example.com',b'09123456789',b'Looking for work']:
            self.assertNotIn(private,response.data)
        page=self.client.get('/monitor').data
        self.assertIn(b'UP NEXT',page)
        self.assertIn(b'tv-time',page)
        self.assertNotIn(b'http-equiv="refresh"',page)
