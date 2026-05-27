---
name: html-builder
description: 강좌 산출물을 GitHub Pages용 통합 HTML 교육 사이트(docs/)로 빌드하는 방법. html-publisher 에이전트가 참조.
---

# HTML 교육 사이트 빌드 스킬

## 명령
```bash
python scripts/build_html.py --course courses/<슬러그>   # 단일 강좌 (랜딩 자동 갱신)
python scripts/build_html.py --all                      # 전체 강좌
python scripts/build_html.py --all --reset-assets        # 공통 css/js를 기본값으로 복원
```

## 출력 구조 (GitHub Pages `/docs` 배포용, 한/영 이중 언어)
한 번의 빌드로 한국어(`ko`)·영어(`en`) 두 언어가 모두 생성된다:
```
docs/
  index.html                       # 언어 라우터 (navigator.language/localStorage eduLang → ./ko 또는 ./en)
  ko/index.html                    # 한국어 랜딩
  ko/courses/<슬러그>/index.html    # 한국어 강좌 페이지 (자산을 ../../../assets 로 참조, 출처=한+영 전체)
  en/index.html                    # 영어 랜딩
  en/courses/<슬러그>/index.html    # 영어 강좌 페이지 (출처=영어 영상만)
  assets/css/style.css             # 공통 스타일 (한 곳에서 관리)
  assets/js/main.js                # 공통 스크립트 (퀴즈 pick() + Mermaid + 언어토글)
  assets/img/                      # 이미지/로고
  .nojekyll
```
- 언어별 UI 문자열은 build_html.py의 `STRINGS` 딕셔너리에서 관리한다(`LANGS = ["ko","en"]`).
- 영문 본문/실습/커리큘럼은 `content.en.md`·`exercise.en.json`·`01_curriculum.en.json`(6b content-localizer 산출)을 우선 사용하고, 없으면 한국어 원본으로 폴백한다.
- **출처 영상 필터**: `en` 페이지는 `sources.json`의 `selected` 중 `subtitle_lang`이 `en`으로 시작하는 영상만, `ko` 페이지는 전체를 노출한다.
- CSS/JS는 **인라인하지 않고 외부 파일로 분리**한다. HTML 골격은 `templates/page.html`·`templates/landing.html`·`templates/router.html`에서 읽는다(없으면 build_html.py 내장 기본값으로 폴백).
- 공통 자산은 **없을 때만** 생성 → 손편집 보존. 기본값 복원은 `--reset-assets`. (언어 토글 JS가 추가됐으므로 기존 저장소엔 1회 `--reset-assets` 필요.)
- 모든 링크는 상대경로라 `user.github.io/<repo>/` 프로젝트 사이트에서도 동작. 배포 절차는 `DEPLOY.md`.

## 빌더가 자동 처리하는 것
- `01_curriculum.json` → 사이드바 목차 + 강좌 메타.
- 각 강의 `content.md`의 frontmatter/본문 분리 후 경량 Markdown→HTML 변환.
- ` ```mermaid <캡션> ` 펜스 → `<figure class="diagram">` + `<div class="mermaid">` 로 렌더링. Mermaid.js(CDN, ESM, `theme:'dark'`)가 브라우저에서 그림을 그리고, 캡션은 `<figcaption>`. **인터넷 차단 시** CDN 로드가 실패하면 `.mermaid:not([data-processed])` CSS 폴백으로 다이어그램 소스가 코드블록처럼 그대로 노출된다(빈 화면이 되지 않음).
- `exercise.json`의 `mode`에 따라:
  - `practical` → 실습 과제 + 힌트/정답 토글(`<details>`).
  - `quiz` → 클릭형 객관식 (정답=초록, 오답=주황, 해설 표시). **브라우저 storage 미사용**, JS 메모리 상태만.
- `review.json`의 `escalate: true` → "⚠ 사람 검토 필요" 배지.
- `sources.json` → 각 강의 하단 출처 영상 링크 (저작권 표기). 영어 페이지는 `subtitle_lang=en` 영상만.
- 각 페이지 상단 KO↔EN 토글 + `docs/index.html` 언어 라우터 자동 생성.

## 디자인 시스템
공통 스타일은 **`design-guide/DESIGN.md`** 의 "Academic Clarity"(라이트) 토큰을 따른다 — Oxford Blue `#003178`(primary), Teal `#006a62`(secondary), off-white `#f9f9fc` 배경, 본문 Source Serif 4, UI/제목 Hanken Grotesk, 코드 JetBrains Mono, 8px 라운드, 720px 읽기 폭, blue-tinted academic shadow. 이 토큰은 `scripts/build_html.py`의 `CSS_DEFAULT` 와 머티리얼라이즈된 `docs/assets/css/style.css` 에 반영돼 있다. 폰트는 Google Fonts CDN + 시스템 폴백, Mermaid는 라이트 테마(`theme:'base'`). 콜아웃은 본문 `> ` blockquote 로 작성하면 Teal 노트로 렌더된다.
> `CSS_DEFAULT`/`JS_DEFAULT` 상수를 고친 뒤에는 `--reset-assets` 로 `docs/assets` 를 재생성해야 반영된다(자산은 write-if-absent).

## 커스터마이징 포인트 (이후 웹사이트 고도화)
- 디자인/테마: `docs/assets/css/style.css`의 CSS 변수(`:root`)를 직접 수정. 재빌드해도 보존된다.
- 동작(퀴즈·다이어그램): `docs/assets/js/main.js`.
- 페이지/랜딩 골격: `templates/page.html`·`templates/landing.html`.
- 회사 로고/브랜딩: `docs/assets/img/`에 넣고 템플릿에서 참조.
- 사이트 제목: `--site-title "..."` 옵션.

## 검증
빌드 후 다음을 확인:
- 출력 구조 존재: `docs/index.html`(라우터), `docs/ko/index.html`, `docs/en/index.html`, `docs/<lang>/courses/<슬러그>/index.html`, `docs/assets/css/style.css`, `docs/assets/js/main.js`, `docs/.nojekyll`.
- 강좌 페이지에 인라인 `<style>`/`<script>`가 **없고** `../../../assets/...` 링크가 있는지.
- 랜딩에 강좌 카드와 `courses/<슬러그>/index.html` 링크, 상단 언어 토글이 있는지.
- `en` 강좌 페이지 출처에 `subtitle_lang=ko` 영상이 빠지고 `ko`엔 전부 보이는지.
- `docs/index.html`을 브라우저 언어 ko/en 으로 열어 각각 `ko`/`en`으로 이동하고, 토글 후 재접속 시 localStorage 선택이 유지되는지.
- 모든 강의 article이 생성됐는지 (`grep -c '<article'`).
- 퀴즈/실습이 강의 유형에 맞게 들어갔는지.
- 다이어그램이 들어간 강의는 `grep -c "class='mermaid'"` 로 개수를 확인하고, 브라우저에서 **그림으로 렌더링**되는지 본다. 코드 텍스트가 그대로 보이면 인터넷 차단(폴백)이거나 Mermaid 문법 오류다 → 후자면 diagram-architect로 수정.
- 브라우저에서 `docs/index.html`을 열어 랜딩→강좌 이동, 스타일 적용, 퀴즈 클릭·정답 토글이 동작하는지.
