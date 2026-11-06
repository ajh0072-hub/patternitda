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

        # 길이 맞추기: 10cm 기준, 12cm 직선을 10cm로 맞춘다
        page.click('#new')
        page.click('[data-tool=line]')
        for y, L in ((300, '10'), (400, '12')):
            page.mouse.click(box['x'] + 300, box['y'] + y)
            page.mouse.move(box['x'] + 500, box['y'] + y)
            page.fill('#len', L)
            page.click('#apply')
        mids = page.evaluate("S.adds.map(e => toS({x: (e.pts[0].x + e.pts[1].x) / 2, y: (e.pts[0].y + e.pts[1].y) / 2}))")
        page.click('[data-tool=match]')
        page.mouse.click(box['x'] + mids[0]['x'], box['y'] + mids[0]['y'])
        page.click('#matchB')
        page.mouse.click(box['x'] + mids[1]['x'], box['y'] + mids[1]['y'])
        before = page.text_content('#matchDiff')
        page.click('#matchFix')
        after = page.evaluate("S.adds.map(e => elLen(e).toFixed(2))")
        check('길이 맞추기', before == '맞출 쪽이 2.00 cm 깁니다' and after == ['10.00', '10.00']
              and page.text_content('#matchDiff') == '길이가 같습니다', f'{before} → {after}')
        page.click('#undo')
        check('길이 맞추기 되돌리기', page.evaluate("elLen(S.adds[1]).toFixed(2)") == '12.00')

        # 곡선으로 길이 맞추기: 늘이기와 줄이기
        page.click('[data-tool=curve]')
        for x, y in ((300, 150), (380, 100), (460, 160), (540, 120)):
            page.mouse.click(box['x'] + x, box['y'] + y)
        page.click('#done')
        curve_ok = []
        for target, y in (('14', 230), ('6', 280)):
            page.click('[data-tool=line]')
            page.mouse.click(box['x'] + 650, box['y'] + y)
            page.mouse.move(box['x'] + 850, box['y'] + y)
            page.fill('#len', target)
            page.click('#apply')
            line_mid, curve_pt = page.evaluate(
                "[toS({x:(S.adds.at(-1).pts[0].x+S.adds.at(-1).pts[1].x)/2, y:S.adds.at(-1).pts[0].y}), toS(S.adds[2].pts[7])]")
            page.click('[data-tool=match]')
            page.mouse.click(box['x'] + line_mid['x'], box['y'] + line_mid['y'])
            page.click('#matchB')
            page.mouse.click(box['x'] + curve_pt['x'], box['y'] + curve_pt['y'])
            page.click('#matchFix')
            curve_ok.append(page.evaluate(f"[elLen(S.adds[2]).toFixed(2), S.adds[2].pts.length]"))
            page.click('#undo')
        check('곡선 길이 맞추기', curve_ok == [['14.00', 15], ['6.00', 15]], str(curve_ok))

        # 너치: 10cm 직선의 시작점에서 3cm에 넣고 저장 → 다시 열기
        page.click('#new')
        page.click('[data-tool=line]')
        page.mouse.click(box['x'] + 300, box['y'] + 300)
        page.mouse.move(box['x'] + 500, box['y'] + 300)
        page.fill('#len', '10')
        page.click('#apply')
        mid = page.evaluate("toS({x:(S.adds[0].pts[0].x+S.adds[0].pts[1].x)/2, y:S.adds[0].pts[0].y})")
        page.click('[data-tool=notch]')
        page.mouse.click(box['x'] + mid['x'], box['y'] + mid['y'])
        if page.text_content('#notchEnd') != '시작점':
            page.click('#notchEnd')
        page.fill('#notchAt', '3')
        page.click('#notchAdd')
        with page.expect_download() as dl:
            page.click('#save')
        saved = os.path.join(OUT, 'notch.pax')
        dl.value.save_as(saved)
        page.set_input_files('#file', saved)
        page.wait_for_timeout(300)
        r = page.evaluate("""(() => { const n = S.doc.els.find(e => e.type === TYPE.NOTCH), l = S.doc.els.find(e => e.type === TYPE.LINE);
          if (!n || !l) return null; const c = {x:(n.pts[0].x+n.pts[1].x)/2, y:(n.pts[0].y+n.pts[1].y)/2};
          return [S.doc.els.length, Math.hypot(c.x-l.pts[0].x, c.y-l.pts[0].y).toFixed(2), Math.hypot(n.pts[1].x-n.pts[0].x, n.pts[1].y-n.pts[0].y).toFixed(2)] })()""")
        check('너치 넣기 → 저장 → 다시 열기', r == [2, '3.00', '2.00'], str(r))

        # 너치 여러 개: 위 직선에서 시작점 2cm부터 1cm 간격 3개
        page.click('[data-tool=notch]')
        page.mouse.click(box['x'] + mid['x'], box['y'] + mid['y'])
        if page.text_content('#notchEnd') != '시작점':
            page.click('#notchEnd')
        page.fill('#notchAt', '2')
        page.fill('#notchN', '3')
        page.fill('#notchGap', '1')
        page.click('#notchAdd')
        r = page.evaluate("""(() => { const l = S.doc.els.find(e => e.type === TYPE.LINE);
          return S.adds.filter(e => e.kind === 'notch').map(n => Math.hypot(n.at.x - l.pts[0].x, n.at.y - l.pts[0].y).toFixed(2)) })()""")
        page.click('#undo')
        check('너치 여러 개 넣기·한 번에 되돌리기', r == ['2.00', '3.00', '4.00'] and page.evaluate('S.adds.length') == 0, str(r))

        # 시접 넣기: 20×10 사각형 → 저장 → 다시 열기 → 시접 1cm(밑변 4cm) → 저장 → 다시 열기
        page.click('#new')
        page.evaluate("""(() => { const P = [[0,0],[20,0],[20,10],[0,10]].map(([x,y]) => ({x:x+10, y:y+10}));
          for (let i = 0; i < 4; i++) commit({kind:'line', pts:[P[i], P[(i+1)%4]], flag:1}) })()""")
        with page.expect_download() as dl:
            page.click('#save')
        rect = os.path.join(OUT, 'rect.pax')
        dl.value.save_as(rect)
        page.set_input_files('#file', rect)
        page.wait_for_timeout(300)
        page.click('[data-tool=seam]')
        def tap_world(x, y):
            q = page.evaluate(f'toS({{x:{x}, y:{y}}})')
            page.mouse.click(box['x'] + q['x'], box['y'] + q['y'])
        tap_world(20, 20)          # 윗변 → 사각형 한 바퀴
        tap_world(20, 10)          # 밑변 선택
        page.fill('#seamW', '4')
        page.click('#seamAdd')
        with page.expect_download() as dl:
            page.click('#save')
        seamed = os.path.join(OUT, 'rect_seam.pax')
        dl.value.save_as(seamed)
        page.set_input_files('#file', seamed)
        page.wait_for_timeout(300)
        r = page.evaluate("""(() => { const v = new DataView(S.doc.bytes.buffer, S.doc.bytes.byteOffset);
          const z = S.doc.els.find(e => e.type === 0x5C); if (!z) return null;
          const n = v.getUint16(z.addr + 4, true), idx = (z.rec - REC) / RSZ + 1;
          const seams = S.doc.els.filter(e => e.link === 0x15 && e.owner === idx);
          const xs = seams.flatMap(e => e.pts.map(p => p.x)), ys = seams.flatMap(e => e.pts.map(p => p.y));
          const w = Array.from({length:n}, (_, i) => v.getFloat32(z.addr + 6 + 16*n + 4*i, true)).sort();
          return [n, seams.length, Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys), w.join(','), seamSet(seams[0]).length] })()""")
        check('시접 넣기 → 저장 → 다시 열기', r == [4, 4, 9, 31, 6, 21, '1,1,1,4', 5], str(r))

        # 박스 → 무브 → 시무브 → MVRT
        page.click('#new')
        page.click('[data-tool=box]')
        tap_world(10, 10)
        page.mouse.move(box['x'] + 700, box['y'] + 100)
        page.fill('#boxW', '20')
        page.fill('#boxH', '10')
        page.click('#boxApply')
        r1 = page.evaluate("S.adds.map(e => e.pts.map(p => p.x.toFixed(1) + ',' + p.y.toFixed(1)).join(' ')).sort().join(' | ')")
        check('박스', r1 == '10.0,10.0 30.0,10.0 | 10.0,20.0 10.0,10.0 | 30.0,10.0 30.0,20.0 | 30.0,20.0 10.0,20.0', r1)

        def drag_select():
            a = page.evaluate('toS({x: 5, y: 25})'); b = page.evaluate('toS({x: 35, y: 5})')
            page.mouse.move(box['x'] + a['x'], box['y'] + a['y']); page.mouse.down()
            page.mouse.move(box['x'] + (a['x'] + b['x']) / 2, box['y'] + (a['y'] + b['y']) / 2, steps=4)
            page.mouse.move(box['x'] + b['x'], box['y'] + b['y'], steps=4); page.mouse.up()
        bounds = "(() => { const P = S.adds.flatMap(e => e.pts); return [Math.min(...P.map(p => p.x)), Math.max(...P.map(p => p.x)), Math.min(...P.map(p => p.y)), Math.max(...P.map(p => p.y))].map(v => v.toFixed(1)).join(',') })()"
        page.click('[data-tool=move]')
        drag_select()
        n_sel = page.text_content('#mvInfo')
        page.click('#mvNext')
        tap_world(10, 10)
        page.fill('#mvX', '5')
        page.fill('#mvY', '-2')
        page.click('#mvApply')
        check('무브 (네모로 고르기, 거리 입력)', n_sel == '4개 고름' and page.evaluate(bounds) == '15.0,35.0,8.0,18.0', n_sel + ' ' + page.evaluate(bounds))
        page.click('#undo')
        page.click('[data-tool=cmove]')
        drag_select()
        page.click('#mvNext')
        tap_world(10, 10)
        tap_world(10, 30)
        check('시무브 (복사)', page.evaluate('S.adds.length') == 8 and page.evaluate(bounds) == '10.0,30.0,10.0,40.0', str(page.evaluate('S.adds.length')) + ' ' + page.evaluate(bounds))
        page.click('#undo')
        page.click('[data-tool=mvrt]')
        drag_select()
        page.click('#mvNext')
        tap_world(10, 10)
        tap_world(10, 10)
        page.fill('#mvAng', '90')
        page.click('#mvRot')
        check('MVRT (90° 회전)', page.evaluate(bounds) == '0.0,10.0,10.0,30.0', page.evaluate(bounds))

        # SG / AG: 사각형 4변 → 저장 → 다시 열기 → 위·아래 변 SG, 왼쪽 변 AG → 저장 → 다시 열기
        page.click('#undo')
        with page.expect_download() as dl:
            page.click('#save')
        sq = os.path.join(OUT, 'square.pax')
        dl.value.save_as(sq)
        page.set_input_files('#file', sq)
        page.wait_for_timeout(300)
        page.click('[data-tool=sg]')
        tap_world(20, 10)
        tap_world(20, 20)
        page.click('#mvNext')
        page.click('[data-tool=ag]')
        tap_world(10, 15)
        page.click('#mvNext')
        tap_world(20, 20)
        with page.expect_download() as dl:
            page.click('#save')
        sqg = os.path.join(OUT, 'square_group.pax')
        dl.value.save_as(sqg)
        page.set_input_files('#file', sqg)
        page.wait_for_timeout(300)
        r = page.evaluate("""S.doc.els.map(e => { const m = {x:(e.pts[0].x+e.pts[1].x)/2, y:(e.pts[0].y+e.pts[1].y)/2};
          return (m.y < 11 ? '아래' : m.y > 19 ? '위' : m.x < 11 ? '왼쪽' : '오른쪽') + ':' + e.group }).sort().join(' ')""")
        g = page.evaluate('S.doc.els.find(e => e.group).group')
        check('SG 그룹 만들기 · AG 그룹에 추가 → 저장 → 다시 열기', r == f'아래:{g} 오른쪽:0 왼쪽:{g} 위:{g}' and g > 0, r)

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
