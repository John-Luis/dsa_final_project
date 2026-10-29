"""Optional real-browser walkthrough. Uses an isolated, disposable database.

Run: python tests/browser_smoke.py
Set SERBISYOQ_CHROMIUM to use a system Chromium rather than Playwright's install.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from serbisyoq.app import create_app
from serbisyoq.db import get_db
from serbisyoq.demo import seed_demo


def main():
    with tempfile.TemporaryDirectory() as directory:
        app=create_app({'TESTING':True,'DATABASE':str(Path(directory)/'smoke.sqlite'),
                        'SECRET_KEY':'isolated-browser-test'})
        with app.app_context():
            seed_demo(get_db())
        server=make_server('127.0.0.1',0,app)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                options={'headless':True}
                if os.environ.get('SERBISYOQ_CHROMIUM'):
                    options['executable_path']=os.environ['SERBISYOQ_CHROMIUM']
                browser=p.chromium.launch(**options)
                page=browser.new_page(viewport={'width':1440,'height':1050})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base)
                page.get_by_role('link',name='View requirements & join').nth(1).click()
                page.get_by_role('textbox',name='Full name').fill('Browser Demo Applicant')
                page.get_by_role('textbox',name='Email address').fill('browser@example.com')
                page.get_by_role('textbox',name='Contact number').fill('09123456789')
                page.get_by_role('checkbox').nth(0).check()
                page.get_by_role('checkbox').nth(1).check()
                page.get_by_role('button',name='Get my queue number').click()
                page.get_by_role('heading',name='Your next step is in line.').wait_for()
                assert 'P-004' in page.content()
                page.get_by_role('link',name='Staff access').click()
                page.get_by_label('Staff password').fill('peso-demo')
                page.get_by_role('button',name='Sign in').click()
                page.get_by_role('heading',name='A clearer day of service.').wait_for()
                page.get_by_role('link',name='Manage transaction').first.click()
                page.get_by_role('button',name='Start assessment').click()
                page.get_by_role('link',name='Manage transaction').first.click()
                page.get_by_role('combobox',name='Transaction outcome').select_option('Referred')
                page.get_by_role('button',name='Complete transaction').click()
                page.get_by_role('button',name='Call next').first.click()
                assert 'P-003 called to Counter 1.' in page.content()
                page.get_by_role('link',name='Reports',exact=True).click()
                page.get_by_role('heading',name='Better service starts with insight.').wait_for()
                with page.expect_download() as download:
                    page.get_by_role('link',name='Export CSV').click()
                assert download.value.suggested_filename.endswith('.csv')
                page.goto(base+'/monitor')
                assert 'Browser Demo Applicant' not in page.content()
                page.set_viewport_size({'width':390,'height':844})
                for route in ['/','/request?program=P','/staff','/staff/reports','/monitor']:
                    page.goto(base+route)
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),route
                assert not errors,errors
                browser.close()
                print('PASS: browser intake, receipt, staff assessment/completion, FIFO call, CSV download, public privacy, five mobile layouts.')
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__=='__main__':
    main()
