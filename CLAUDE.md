# 패턴잇다

유카캐드 패턴 파일(.pax)을 아이패드·갤럭시·PC 브라우저에서 열고, 고치고, 저장하는 PWA.
만든 사람은 패턴사(코딩 전문가 아님). 설명은 한국어 반말로, 쉬운 말로.

## 구조

- `index.html` — 앱 전체 (HTML·CSS·JS 한 파일, 빌드 도구 없음)
- `sw.js` — 서비스워커 (오프라인 실행, 새 버전 알림)
- `manifest.webmanifest`, `icons/` — 홈 화면 설치용
- `tests/smoke_test.py` — 자동 테스트
- 배포: main에 푸시하면 GitHub Pages가 자동 배포 → https://ajh0072-hub.github.io/patternitda/

## .pax 형식 (index.html 상단 코드)

- 요소 레코드는 0x800부터 32바이트씩. 좌표 데이터는 별도 영역(heap)에 순서대로.
- `parse` 읽기, `build` 저장, `removeRec` 삭제, `fitRecords` 레코드 공간 확보, `setPos` 위치 바이트 계산.
- 요소 타입: 직선 2, 곡선 7(최대 15점), 원호 3, 너치 0x14, 글자 0x20(EUC-KR), 너치 데이터 0x5B, 시접 0x5C.
- 모르는 바이트는 항상 그대로 보존한다. 이 원칙을 깨지 말 것.

## 꼭 지킬 것

1. 원본 .pax는 덮어쓰지 않는다. 저장은 항상 `이름_edit.pax` 새 파일.
2. .pax 읽기/쓰기 코드는 실제 샘플 파일로 "열기 → 수정 → 저장 → 다시 열기" 검증 없이 바꾸지 않는다.
3. **실제 .pax 파일은 저장소에 커밋하지 않는다.** 저장소가 공개라 회사 패턴이 그대로 노출된다. 샘플은 `samples/`에 두고, 이 폴더는 .gitignore로 막혀 있다.
4. index.html이나 sw.js를 고쳐서 푸시할 때마다 `sw.js`의 `VERSION`을 올린다 (안 올리면 설치된 앱이 옛날 버전에 머문다).
5. 푸시 전에 `python tests/smoke_test.py`를 돌리고 결과를 알려준다.
6. 유카에서 실제로 열리는지, 아이패드 사파리·펜슬 동작은 사용자가 직접 확인한다. 그 부분은 확인 요청으로 끝낸다.

## 테스트

```
pip install playwright
python -m playwright install chromium
python tests/smoke_test.py            # 기본 테스트
python tests/smoke_test.py samples/*.pax   # 실제 파일 왕복 검증까지
```

확인 항목: 화면 실행·JS 오류, 직선 그리기·되돌리기, 저장 후 다시 열기, 오프라인 실행, 설치 조건, 샘플 파일 열기 → 저장 → 다시 열기에서 요소 수와 좌표 유지.

## 다음 할 일

- [ ] 실제 유카 .pax 샘플로 왕복 검증
- [ ] 저장한 파일이 유카에서 정상으로 열리는지 확인
- [ ] 실무 기능 추가: 너치, 시접 추가, 길이 맞추기
- [ ] 아이콘 다듬기
