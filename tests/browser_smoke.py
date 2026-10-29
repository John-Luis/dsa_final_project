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
                        'SECRET_KEY':'isolated-browser-test','MAIL_PREVIEW_DIR':str(Path(directory)/'mail'),
                        'MEDIA_DIR':str(Path(directory)/'media')})
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
                context=browser.new_context(viewport={'width':1440,'height':1050})
                page=context.new_page()
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
                assert 'No email was sent' in page.content()
                page.get_by_role('link',name='Staff access').click()
                page.get_by_label('Staff password').fill('peso-demo')
                page.get_by_role('button',name='Sign in').click()
                page.get_by_role('heading',name='A clearer day of service.').wait_for()
                monitor=page.context.new_page()
                monitor.on('pageerror',lambda error:errors.append(str(error)))
                monitor.goto(base+'/monitor')
                previous_clock=monitor.locator('#tv-time').inner_text()
                page.get_by_role('link',name='Manage transaction').first.click()
                page.get_by_role('button',name='Start assessment').click()
                page.get_by_role('link',name='Manage transaction').first.click()
                page.get_by_role('combobox',name='Transaction outcome').select_option('Referred')
                page.get_by_role('button',name='Complete transaction').click()
                page.get_by_role('button',name='Call next').first.click()
                assert 'P-003 called to Counter 1.' in page.content()
                monitor.wait_for_function("document.querySelector('#tv-counter-1 [data-current]').textContent === 'P-003'",timeout=12000)
                assert monitor.locator('#tv-counter-1 [data-next]').inner_text()=='P-004'
                assert monitor.locator('#tv-time').inner_text()!=previous_clock
                page.locator('#announcement').fill('Keep this unsaved announcement draft')
                with app.app_context():
                    from serbisyoq.service import submit
                    submit(get_db(),'S','Live Poll Applicant','live@example.com','09123456789','Live concern')
                page.get_by_role('cell',name='Live Poll Applicant',exact=True).wait_for(timeout=12000)
                assert page.locator('#announcement').input_value()=='Keep this unsaved announcement draft'
                page.get_by_role('link',name='Reports',exact=True).click()
                page.get_by_role('heading',name='Better service starts with insight.').wait_for()
                with page.expect_download() as download:
                    page.get_by_role('link',name='Export CSV').click()
                assert download.value.suggested_filename.endswith('.csv')
                assert page.get_by_role('img',name='Request and completion trend').count()==1
                assert page.get_by_role('img',name='Transaction status distribution').count()==1
                page.get_by_role('link',name='Email log',exact=True).click()
                page.get_by_role('link',name='View message').first.click()
                assert 'PESO service request is confirmed' in page.content()
                page.get_by_role('link',name='TV media',exact=True).click()
                page.get_by_label('Announcement title').fill('Video playback test')
                page.get_by_label('Image or video').set_input_files(str(Path(__file__).parent/'fixtures'/'announcement.webm'))
                page.get_by_label('Display duration / video limit').fill('20')
                page.get_by_role('button',name='Add media').click()
                monitor.wait_for_selector('#media-screen video',timeout=12000)
                monitor.wait_for_function("document.querySelector('#media-screen video')?.currentTime > 0",timeout=12000)
                monitor.evaluate("window.originalVideo=document.querySelector('#media-screen video')")
                # Poll once more while the same video plays. The player must not be rebuilt.
                with monitor.expect_response('**/api/monitor',timeout=12000):
                    pass
                assert monitor.evaluate("window.originalVideo === document.querySelector('#media-screen video')")
                monitor.get_by_role('button',name='Pause slideshow').click()
                assert monitor.locator('#media-screen video').evaluate('(v)=>v.paused')
                monitor.get_by_role('button',name='Resume slideshow').click()
                # Add a valid PNG after the video, then manually advance to it.
                page.get_by_label('Announcement title').fill('Image carousel test')
                import base64
                png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
                page.get_by_label('Image or video').set_input_files({'name':'slide.png','mimeType':'image/png','buffer':png})
                page.get_by_role('button',name='Add media').click()
                with monitor.expect_response('**/api/monitor',timeout=12000):
                    pass
                monitor.get_by_role('button',name='Next announcement').click()
                monitor.get_by_role('img',name='Image carousel test').wait_for()
                page.get_by_role('button',name='Remove from playlist').first.click()
                page.get_by_role('button',name='Remove from playlist').first.click()
                monitor.get_by_role('img',name='Your next opportunity starts at PESO').wait_for(timeout=12000)
                screenshot_dir=os.environ.get('SERBISYOQ_SCREENSHOTS')
                if screenshot_dir:
                    output=Path(screenshot_dir); output.mkdir(parents=True,exist_ok=True)
                    monitor.screenshot(path=str(output/'monitor-tv.png'),full_page=True)
                    page.goto(base+'/staff')
                    page.screenshot(path=str(output/'staff-queue.png'),full_page=True)
                    page.goto(base+'/staff/reports')
                    page.screenshot(path=str(output/'report-analysis.png'),full_page=True)
                monitor.close()
                page.goto(base+'/monitor')
                assert 'Browser Demo Applicant' not in page.content()
                page.set_viewport_size({'width':390,'height':844})
                for route in ['/','/request?program=P','/staff','/staff/reports','/staff/media','/staff/email','/monitor']:
                    page.goto(base+route)
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),route
                assert not errors,errors
                browser.close()
                print('PASS: intake and email preview; two-tab live queue and clock; saved form draft; video playback across polling; image carousel; report charts and CSV; seven mobile layouts.')
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__=='__main__':
    main()
