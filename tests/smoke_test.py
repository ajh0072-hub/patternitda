"""패턴잇다 자동 테스트.

사용법:
  python tests/smoke_test.py                 # 기본 테스트
  python tests/smoke_test.py samples/*.pax   # 실제 파일 왕복 검증까지

크롬이 이미 설치돼 있으면 CHROME 환경변수로 경로를 지정해도 된다.
"""
import functools
import glob
import http.server
import os
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tests', 'output')
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('통과 ' if ok else '실패 ') + name + (f' — {detail}' if detail else ''))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(QuietHandler, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}/'


ROUNDTRIP_JS = """async (b64) => {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const d1 = __pax.parse(bytes);
  const out = __pax.build(d1, [], [], []);
  const d2 = __pax.parse(out);
  const key = e => e.type + ':' + e.pts.map(p => p.x.toFixed(3) + ',' + p.y.toFixed(3)).join(';');
  const a = d1.els.map(key), b = d2.els.map(key);
  return {n1: a.length, n2: b.length, same: a.length === b.length && a.every((k, i) => k === b[i])};
}"""


def main(samples):
    os.makedirs(OUT, exist_ok=True)
    srv, url = serve()
    with sync_playwright() as p:
        kw = {'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}
        browser = p.chromium.launch(**kw)
        ctx = browser.new_context(viewport={'width': 1180, 'height': 820}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        page.goto(url)
        page.wait_for_function('navigator.serviceWorker.controller !== null', timeout=15000)
        check('화면 실행', page.title() == '패턴잇다')

        cdp = ctx.new_cdp_session(page)
        man = cdp.send('Page.getAppManifest')
        check('설치 설정(manifest)', not man.get('errors'), str(man.get('errors') or ''))

        page.click('[data-tool=line]')
        box = page.locator('#c').bounding_box()
        page.mouse.click(box['x'] + 300, box['y'] + 300)
        page.mouse.move(box['x'] + 500, box['y'] + 300)
        page.fill('#len', '10')
        page.click('#apply')
        check('직선 그리기', page.text_content('#count') == '요소 1')

        with page.expect_download() as dl:
            page.click('#save')
        saved = os.path.join(OUT, 'saved.pax')
        dl.value.save_as(saved)
        page.set_input_files('#file', saved)
        page.wait_for_timeout(300)
        check('저장 후 다시 열기', page.text_content('#count') == '요소 1')

        page.click('[data-tool=line]')
        page.mouse.click(box['x'] + 300, box['y'] + 400)
        page.mouse.click(box['x'] + 500, box['y'] + 400)
        page.click('#undo')
        check('되돌리기', page.text_content('#count') == '요소 1')

        ctx.set_offline(True)
        page.reload()
        page.wait_for_timeout(800)
        check('오프라인 실행', page.title() == '패턴잇다' and not page.is_hidden('#c'))
        ctx.set_offline(False)

        import base64
        for path in samples:
            name = os.path.basename(path)
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            try:
                r = page.evaluate(ROUNDTRIP_JS, b64)
                check(f'샘플 왕복 {name}', r['same'], f"요소 {r['n1']} → {r['n2']}")
            except Exception as e:
                check(f'샘플 왕복 {name}', False, str(e).splitlines()[0])

        page.screenshot(path=os.path.join(OUT, 'screen.png'))
        check('JS 오류 없음', not errors, '; '.join(errors))
        browser.close()
    srv.shutdown()

    fails = results.count(False)
    print(f'\n{len(results) - fails}/{len(results)} 통과')
    return 1 if fails else 0


if __name__ == '__main__':
    files = [f for a in sys.argv[1:] for f in glob.glob(a)]
    sys.exit(main(files))
