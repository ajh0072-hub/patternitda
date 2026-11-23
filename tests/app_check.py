"""패턴잇다 명령 점검 (패턴 파일 없이 돈다).

앱 안에서 시험용 패턴(네모·대각선·곡선)을 만들어 저장한 바이트로 다시 연 뒤 확인한다.
 1) 시작: 도구 단추를 하나씩 눌러도 JS 오류가 없다
 2) 계산 칸: 12/4 같은 식, 앞 수치에 이어 계산
 3) 점 잡기: F1 끝점 · F2 임의점 · F3 선상점 · ⇧F1 교점 · ⇧F2 중점 · ⇧F3 비율점, F4·F5·F11 영역, F6 부분확대
 4) 명령 흐름: 명령 중간에 되돌리기·오류·파일 열기·도구 바꾸기를 해도 옛 선을 쥐고 있지 않다
 5) 명령 훑기: 명령 코드마다 세 가지 순서로 눌러 본다 → JS 오류 없음, 저장됨, 끝까지 되돌리면 처음 바이트와 같음

사용법: python tests/app_check.py      (CHROME 환경변수로 브라우저 경로를 줄 수 있다)
"""
import functools
import http.server
import os
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('통과 ' if ok else '실패 ') + name + (f' — {detail}' if detail else ''))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


# 시험용 패턴: 네모(0,0)-(40,30), 대각선, 곡선. 저장한 바이트를 window.__raw에 둔다.
MAKE = r'''()=>{load(blank(),'t');const L=(a,b)=>({kind:'line',pts:[{x:a[0],y:a[1]},{x:b[0],y:b[1]}],layer:43,color:7,flag:1});
 S.adds.push(L([0,0],[40,0]),L([40,0],[40,30]),L([40,30],[0,30]),L([0,30],[0,0]),L([5,5],[35,25]),
  {kind:'curve',pts:[{x:5,y:25},{x:15,y:18},{x:25,y:14},{x:35,y:5}],layer:43,color:7,flag:1,keepPts:true});
 window.__raw=build(S.doc,S.adds,[],[]);load(window.__raw,'t');fit();draw();
 window.__cur=()=>build(S.doc,S.adds,S.dels,[...S.edits].filter(e=>!S.dels.includes(e.rec)),[...S.regroup].filter(e=>!S.dels.includes(e.rec)).map(e=>({rec:e.rec,addr:e.addr,group:e.group,color:e.color,flag:e.flag,scol:e.type===0x5C?e.scol:null})));
 return S.doc.els.length}'''

CALC = r'''()=>{const r={};
 r.c=[calc('12/4'),calc('3*2+1'),calc('(10-4)/3'),calc('1/0'),calc('alert(1)'),calc('-')];
 r.v=numVals('20/2, 30*2');r.v2=numVals('mv');
 $('new').click();fit();runCmd('52/2.54');r.c1=S.calcLast;runCmd('*2');r.c2=S.calcLast;
 setTool('box');S.box={x:0,y:0};refresh();const t=numTarget();r.target=t&&t.b;
 const n0=S.adds.length;runCmd('20/2,15*2');const L=S.adds.slice(n0).filter(e=>e.kind==='line');
 const xs=L.flatMap(e=>e.pts.map(p=>p.x)),ys=L.flatMap(e=>e.pts.map(p=>p.y));r.box=[L.length,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys)];
 setTool('line');tap(toS({x:0,y:0}));const el=$('len');el.value='45/3';el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));r.len=el.value;setTool('pan');
 return r}'''

SNAP = r'''()=>{load(blank(),'t');S.adds.push({kind:'line',pts:[{x:0,y:0},{x:40,y:0}],layer:1,color:7,flag:1},{kind:'line',pts:[{x:20,y:-10},{x:20,y:10}],layer:1,color:7,flag:1});fit();
 const at=(x,y)=>{const p=snapAt(toS({x,y}));return p?[+p.x.toFixed(3),+p.y.toFixed(3)]:null},out={};
 const key=(k,sh)=>dispatchEvent(new KeyboardEvent('keydown',{key:k,shiftKey:!!sh}));
 key('F1');out.end=at(39.5,0.3);key('F2');out.free=at(39.5,0.3);key('F3');out.on=at(30,0.2);
 key('F1',1);out.cross=at(20.3,0.3);key('F2',1);out.mid=at(5,0.1);key('F3',1);$('snapRatio').value=0.25;out.ratio=at(35,0.1);
 key('F3',1);runCmd('0.3');out.ratio03=at(35,0.1);
 const first=(k,sh,pts,mode)=>{setTool('line');if(mode)setSnap(mode);key(k,sh);for(const q of pts)tap(toS(q));if(k==='F11'&&pts.length>2)tap(toS(pts[0]));const d=S.draft[0];return d?[+d.x.toFixed(3),+d.y.toFixed(3)]:null};
 out.F4end=first('F4',0,[{x:36,y:-3},{x:44,y:3}],'end');
 out.F5=first('F5',0,[{x:15,y:-3},{x:25,y:3}],'end');
 out.F4mid=first('F4',0,[{x:15,y:-3},{x:25,y:3}],'mid');
 out.F11=first('F11',0,[{x:-2,y:-2},{x:3,y:-2},{x:3,y:2},{x:-2,y:2}],'end');
 setTool('pan');key('F6');tap(toS({x:30,y:-5}));tap(toS({x:40,y:5}));const c=toW({x:S.w/2,y:S.h/2});out.F6=[+c.x.toFixed(2),+c.y.toFixed(2)];
 setSnap('end');say('');return out}'''
SNAP_WANT = {'end': [40, 0], 'free': None, 'on': [30, 0], 'cross': [20, 0], 'mid': [20, 0], 'ratio': [30, 0],
             'ratio03': [28, 0], 'F4end': [40, 0], 'F5': [20, 0], 'F4mid': [20, 0], 'F11': [0, 0], 'F6': [35, 0]}

# 명령 흐름: 시험용 명령 __two(선 → 점)와 __err(선을 긋고 오류)를 잠깐 넣어 쓴다.
FLOW = r'''()=>{const raw=window.__raw,R={};
 const line=x=>({kind:'line',pts:[{x:500+x,y:500},{x:510+x,y:500}],layer:43,color:7,flag:1});
 const key=(k,ctrl)=>dispatchEvent(new KeyboardEvent('keydown',{key:k,ctrlKey:!!ctrl,bubbles:true}));
 YC.__two={name:'시험',steps:[{t:'el',need:'any',hint:'선'},{t:'pt',hint:'점'}],run:()=>{}};
 const pickFirst=e=>{S.yc.els.push(e);S.yc.taps.push({x:501,y:500});ycNext()};
 {const quiet=()=>{const e=line(0);S.adds.push(e);S.hist.push({a:e})};
  load(raw,'t');quiet();key('z',true);const z=S.hist.length;load(raw,'t');quiet();runCmd('u');R.J=z===0&&S.hist.length===0}
 load(raw,'t');{commit(line(0));const e=S.adds[S.adds.length-1];ycStart('__two');pickFirst(e);$('undo').click();
  const a=!S.yc.els.includes(e)&&S.yc.i===0&&S.tool==='yc';
  $('redo').click();setTool('move');S.mv.sel.add(e);refresh();$('undo').click();R.B=a&&!S.mv.sel.has(e)}
 load(raw,'t');{commit(line(0));const a=S.adds[S.adds.length-1];commit(line(30));const b=S.adds[S.adds.length-1];ycStart('__two');pickFirst(a);const i1=S.yc.i;runCmd('u');
  R.K=S.yc.i===i1&&S.yc.els.includes(a)&&!S.adds.includes(b)&&S.tool==='yc';setTool('pan')}
 load(raw,'t');{YC.__err={name:'시험',steps:[{t:'pt',hint:'점'}],run:()=>{commit(line(0));commit(line(20));throw new Error('시험 오류')}};
  const a0=S.adds.length,h0=S.hist.length,v0=S.ver;ycStart('__err');S.yc.pts.push({x:0,y:0});ycNext();
  R.C=S.adds.length===a0&&S.hist.length===h0&&S.ver===v0&&$('notice').textContent==='시험 오류';delete YC.__err;setTool('pan')}
 load(raw,'t');{commit(line(0));const e=S.adds[S.adds.length-1];ycStart('__two');pickFirst(e);areaSnapStart('in');load(raw,'t2');
  R.A=!(S.yc&&S.yc.els.length)&&!S.areaSnap&&S.tool==='yc'&&S.yc.i===0}
 load(raw,'t');{setTool('line');areaSnapStart('in');setTool('curve');const on=!!S.areaSnap;tap(toS({x:500,y:500}));R.D=!on&&S.draft.length===1;setTool('pan')}
 {load(raw,'t');commit(line(0));const e=S.adds[S.adds.length-1];setTool('move');S.mv.sel.add(e);S.hl=e;const old=S.t;setTool('line');
  const fresh=S.t!==old&&S.mv.sel.size===0&&S.hl===null&&S.yc===null;ycStart('__two');pickFirst(e);key('Escape');R.G=fresh&&S.yc.i===0&&S.yc.els.length===0&&S.tool==='yc';setTool('pan')}
 delete YC.__two;load(raw,'t');fit();draw();say('');return R}'''

SPOTS = r'''()=>{const b=cv.getBoundingClientRect(),o={lines:[],curve:null};
 for(const e of S.doc.els){if(!e.pts.length)continue;const P=shape(e),s=toS(P[P.length>>1]);
  const q=e.pts.length===2?toS({x:(e.pts[0].x+e.pts[1].x)/2,y:(e.pts[0].y+e.pts[1].y)/2}):s;if(pick(q)!==e)continue;
  if(e.type===TYPE.CURVE){if(!o.curve)o.curve=[b.left+q.x,b.top+q.y]}else if(o.lines.length<2)o.lines.push([b.left+q.x,b.top+q.y])}
 o.box=[b.left,b.top,b.width,b.height];return o}'''

AFTER = r'''()=>{const o={},same=b=>b.length===window.__raw.length&&b.every((v,i)=>v===window.__raw[i]);
 try{const out=window.__cur();o.n=parse(out).els.length;o.changed=!same(out)}catch(e){o.err=String(e).slice(0,160)}
 let k=0;while(S.hist.length&&k++<500)$('undo').click();try{o.undo=same(window.__cur())}catch(e){o.err2=String(e).slice(0,160)}
 return o}'''

SKIP = {'call', 'new', 'save', 'ref', 'bf', 'full', 'fr', '1q', '2q', '3q', 'gid', 'gdel', 'u'}


def sweep(page, errs):
    T = page.evaluate(SPOTS)
    if len(T['lines']) < 2 or not T['curve']:
        check('명령 훑기: 누를 선 찾기', False, str(T))
        return
    bx = T['box']
    E = (bx[0] + 40, bx[1] + bx[3] - 40)
    P1 = (bx[0] + bx[2] - 120, bx[1] + 60)
    P2 = (bx[0] + bx[2] - 60, bx[1] + 110)
    A, B = T['lines'][0], T['curve']
    codes = [c for c in page.evaluate('Object.keys(ACT)') if c not in SKIP]
    bad, runs, changed = [], 0, 0
    kb, ms = page.keyboard, page.mouse

    def num(t):
        kb.type(t)
        kb.press('Space')
        page.wait_for_timeout(25)

    for seq in (1, 2, 3):
        for c in codes:
            ne = len(errs)
            ms.move(*E)
            kb.type(c)
            kb.press('Space')
            page.wait_for_timeout(30)
            if seq == 1:    # 선 → 곡선 → 오른클릭 → 2 → 빈 점 둘 → 오른클릭 → 1
                ms.click(*A); ms.click(*B); ms.click(*E, button='right'); num('2')
                ms.click(*P1); ms.click(*P2); ms.click(*E, button='right'); num('1')
            elif seq == 2:  # 1.5 → 선 → 점 → 곡선 → 점 → 오른클릭 → 3 → 점
                num('1.5'); ms.click(*A); ms.click(*P1); ms.click(*B); ms.click(*P2)
                ms.click(*E, button='right'); num('3'); ms.click(*P1)
            else:           # 영역 2점 → 선 → 곡선 → 오른클릭 → 점 → 2 → 1 → 점 → 오른클릭
                ms.click(bx[0] + 30, bx[1] + 30); ms.click(bx[0] + bx[2] - 30, bx[1] + bx[3] - 200)
                ms.click(*A); ms.click(*B); ms.click(*E, button='right'); ms.click(*P1)
                num('2'); num('1'); ms.click(*P2); ms.click(*E, button='right')
            kb.press('Escape'); kb.press('Escape')
            page.wait_for_timeout(25)
            r = page.evaluate(AFTER)
            runs += 1
            changed += 1 if r.get('changed') else 0
            why = []
            if len(errs) > ne:
                why.append('JS 오류 ' + errs[-1][:200])
            if r.get('err'):
                why.append('저장 실패 ' + r['err'])
            if r.get('err2'):
                why.append('되돌린 뒤 저장 실패 ' + r['err2'])
            if r.get('undo') is False:
                why.append('끝까지 되돌려도 처음과 다름')
            if why:
                bad.append(f'{c}(순서 {seq}): ' + ' / '.join(why))
                page.evaluate("load(window.__raw,'t');fit();draw()")
    check(f'명령 훑기 — 명령 {len(codes)}개 × 순서 3가지 = {runs}번, 그중 {changed}번이 패턴을 바꿈', not bad, ' | '.join(bad[:8]))


def main():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        kw = {'executable_path': os.environ['CHROME']} if os.environ.get('CHROME') else {}
        browser = p.chromium.launch(**kw)
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        errs = []
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('dialog', lambda d: d.dismiss())
        page.goto(f'http://127.0.0.1:{srv.server_address[1]}/index.html')
        page.wait_for_timeout(1200)

        ok = page.evaluate("typeof window.__pax === 'object' && typeof setTool === 'function'")
        for t in page.evaluate("[...document.querySelectorAll('nav [data-tool]')].map(b => b.dataset.tool)"):
            page.evaluate(f"setTool('{t}')")
        page.evaluate("setTool('pan')")
        check('시작 · 도구 단추', ok and not errs, '; '.join(errs[:3]))

        r = page.evaluate(CALC)
        c = r['c']
        check('계산 칸 (12/4, 이어 계산, 칸 여러 개)',
              c[:3] == [3, 7, 2] and all(x != x for x in c[3:]) and r['v'] and r['v']['v'] == [10, 60] and r['v2'] is None
              and r['target'] == 'boxApply' and r['box'][0] == 4 and abs(r['box'][1] - 10) < 1e-6 and abs(r['box'][2] - 30) < 1e-6
              and abs(r['c1'] - 20.4724) < 1e-3 and abs(r['c2'] - 40.9449) < 1e-3 and r['len'] == '15', str(r))

        r = page.evaluate(SNAP)
        wrong = {k: r[k] for k, v in SNAP_WANT.items() if r[k] != v}
        check('점 잡기 (F1~F3, ⇧F1~⇧F3, F4·F5·F6·F11)', not wrong, str(wrong) if wrong else '')

        n = page.evaluate(MAKE)
        check('시험용 패턴 만들기 → 저장 → 다시 열기', n == 6, f'요소 {n}개')

        r = page.evaluate(FLOW)
        names = {'J': '되돌리기 키', 'B': '명령 중 되돌리기(고른 선이 사라짐)', 'K': '명령 중 되돌리기(다른 작업)', 'C': '명령 오류 뒤 원래대로',
                 'A': '명령 중 파일 열기', 'D': '영역 잡기 중 도구 바꾸기', 'G': '도구를 바꾸면 고른 것 비움 · Esc'}
        check('명령 흐름', all(r.values()), ', '.join(names[k] for k, v in r.items() if not v))

        sweep(page, errs)
        check('JS 오류 없음', not errs, '; '.join(errs[:3]))
        browser.close()
    srv.shutdown()
    print(f'\n{sum(results)}/{len(results)} 통과')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
