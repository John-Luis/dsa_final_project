import unittest
import xml.etree.ElementTree as ET
from serbisyoq.charts import chart_data, line_svg, pie_svg


class ChartTest(unittest.TestCase):
    def test_real_counts_and_empty_days(self):
        data=chart_data([{'day':'2026-10-01','status':'Completed'},
                         {'day':'2026-10-01','status':'Waiting'},
                         {'day':'2026-10-03','status':'Called'}],'2026-10-01','2026-10-03')
        self.assertEqual([b['received'] for b in data['trend']],[2,0,1])
        self.assertEqual([b['completed'] for b in data['trend']],[1,0,0])
        self.assertEqual(data['statuses']['Completed'],1)
        ET.fromstring(str(line_svg(data['trend'])))
        ET.fromstring(str(pie_svg(data['statuses'])))

    def test_empty_single_slice_and_long_ranges(self):
        for statuses in [{},{'Waiting':3},{'Waiting':1,'Completed':2}]:
            ET.fromstring(str(pie_svg(statuses)))
        self.assertIn('No data',str(pie_svg({})))
        data=chart_data([],'2020-01-01','2030-01-01')
        self.assertLessEqual(len(data['trend']),14)
        self.assertEqual(sum(b['received'] for b in data['trend']),0)
