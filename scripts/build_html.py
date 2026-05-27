#!/usr/bin/env python3
"""강좌 산출물(courses/<슬러그>)을 GitHub Pages용 통합 사이트(docs/)로 빌드.

- docs/index.html           : 강좌 목록 랜딩
- docs/courses/<슬러그>/...  : 강좌별 페이지 (공통 자산을 ../../assets 로 참조)
- docs/assets/{css,js,img}  : 공통 자산 (없을 때만 스캐폴드 → 손편집 보존)

CSS/JS는 더 이상 HTML에 인라인하지 않고 docs/assets 아래 외부 파일로 분리한다.
HTML 골격은 templates/page.html, templates/landing.html 에서 읽으며,
파일이 없으면 아래 내장 기본값으로 폴백한다.
"""
import argparse, json, os, re, glob, html, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(ROOT, "templates")

# ---------------------------------------------------------------- 다국어(i18n)
# 강좌 사이트는 한국어(ko)·영어(en) 두 언어로 빌드한다.
# - docs/index.html        : 언어 라우터 (브라우저 언어/저장값에 따라 ./ko 또는 ./en 로 이동)
# - docs/<lang>/...        : 언어별 랜딩·강좌 페이지
# - docs/assets/...        : 언어 공통 자산
LANGS = ["ko", "en"]
OTHER = {"ko": "en", "en": "ko"}

# 언어별 UI 문자열. {n} 은 강/강좌 개수로 치환된다.
STRINGS = {
    "ko": {
        "home": "← 강좌 목록",
        "count_unit": "총 {n}강",
        "quiz_heading": "📝 퀴즈",
        "practical_heading": "🛠 실습",
        "task_label": "실습",
        "hint": "힌트",
        "show_answer": "정답 보기",
        "sources": "출처 영상",
        "src_default": "출처",
        "escalate": "⚠ 사람 검토 필요",
        "landing_sub": "전체 {n}개 강좌",
        "empty": "아직 빌드된 강좌가 없습니다.",
        "toggle": "EN",          # 다른 언어로 가는 토글 라벨
        "site_title": "배움터",   # 랜딩 기본 제목 (--site-title 미지정 시)
    },
    "en": {
        "home": "← All courses",
        "count_unit": "{n} lecture{s}",
        "quiz_heading": "📝 Quiz",
        "practical_heading": "🛠 Practice",
        "task_label": "Practice",
        "hint": "Hint",
        "show_answer": "Show answer",
        "sources": "References",
        "src_default": "Source",
        "escalate": "⚠ Needs human review",
        "landing_sub": "{n} course{s}",
        "empty": "No courses have been built yet.",
        "toggle": "한국어",
        "site_title": "Learn",   # 랜딩 기본 제목 (--site-title 미지정 시)
    },
}

# ---------------------------------------------------------------- 파싱/렌더 헬퍼

def read_json(path, default=None):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return default

def parse_content_md(path):
    """content.md의 frontmatter와 본문 분리. 매우 단순한 파서."""
    if not os.path.exists(path):
        return {}, ""
    raw = open(path, encoding="utf-8").read()
    meta, body = {}, raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.strip().startswith("-"):
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body

def strip_leading_title(body):
    """본문 맨 앞에서 강의 제목을 한 번 더 반복하는 H1(`# ...`)을 제거한다.

    content.md 는 frontmatter 의 title 을 본문 첫 줄에 `# {제목}` 으로 또 적는 관례가 있고,
    빌더는 강의 제목을 이미 <h2> 로 출력하므로 그대로 두면 제목이 두 번 나온다.
    본문 소제목은 `##` 이상이라 '맨 앞 단일 # H1' 하나만 떼면 중복만 정확히 제거된다.
    """
    lines = body.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():   # 선행 빈 줄 건너뛰기
        i += 1
    if i < len(lines) and re.match(r"^#\s+\S", lines[i]) and not lines[i].lstrip().startswith("##"):
        del lines[i]
        while i < len(lines) and not lines[i].strip():  # 제거된 헤딩 뒤 빈 줄도 정리
            del lines[i]
    return "\n".join(lines)

def md_to_html(md):
    """경량 Markdown→HTML (헤딩/목록/코드/굵게/다이어그램). 외부 의존성 없이.

    ```mermaid <캡션>``` 펜스는 Mermaid 다이어그램으로 렌더링한다.
    펜스 시작줄에서 'mermaid' 뒤의 텍스트는 figcaption(그림 설명)으로 쓴다.
    원본 소스는 escape 없이 <div class="mermaid">에 그대로 넣어 클라이언트에서 렌더링하고,
    Mermaid 로드 실패(오프라인) 시에는 소스 텍스트가 그대로 노출되는 폴백이 된다.
    """
    out, in_list, in_quote = [], False, False
    fence = None          # None | "code" | "mermaid"
    buf, caption = [], ""
    for line in md.splitlines():
        if line.strip().startswith("```"):
            info = line.strip()[3:].strip()
            if fence is None:                       # 펜스 열기
                if info.lower().startswith("mermaid"):
                    fence, caption, buf = "mermaid", info[7:].strip(), []
                else:
                    fence, buf = "code", []
                    out.append("<pre><code>")
            else:                                   # 펜스 닫기
                if fence == "mermaid":
                    src = html.escape("\n".join(buf))   # 텍스트로 안전하게, mermaid가 파싱
                    cap = f"<figcaption>{inline(caption)}</figcaption>" if caption else ""
                    out.append(f"<figure class='diagram'><div class='mermaid'>{src}</div>{cap}</figure>")
                else:
                    out.append("</code></pre>")
                fence = None
            continue
        if fence == "mermaid":
            buf.append(line); continue
        if fence == "code":
            out.append(html.escape(line)); continue
        # 콜아웃: '> ' 로 시작하는 연속 줄을 하나의 blockquote 로 묶는다 (디자인 가이드 Callout/Note)
        if line.strip().startswith(">"):
            if in_list: out.append("</ul>"); in_list = False
            if not in_quote: out.append("<blockquote class='callout'>"); in_quote = True
            out.append(f"<p>{inline(line.strip().lstrip('>').strip())}</p>"); continue
        if in_quote: out.append("</blockquote>"); in_quote = False
        if re.match(r"^#{1,6} ", line):
            lvl = len(line) - len(line.lstrip("#"))
            txt = inline(line[lvl:].strip())
            out.append(f"<h{lvl+1}>{txt}</h{lvl+1}>"); continue
        if line.strip().startswith("- "):
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(line.strip()[2:])}</li>"); continue
        if in_list: out.append("</ul>"); in_list = False
        if line.strip(): out.append(f"<p>{inline(line)}</p>")
    if in_list: out.append("</ul>")
    if in_quote: out.append("</blockquote>")
    if fence == "code": out.append("</code></pre>")
    return "\n".join(out)

def inline(t):
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code class='ic'>\1</code>", t)
    return t

def render_exercise(ex, S):
    if not ex: return ""
    if ex.get("mode") == "quiz":
        items = []
        for i, q in enumerate(ex.get("questions", [])):
            opts = "".join(
                f"<li class='opt' onclick='pick(this,{i},{j})'>{html.escape(o)}</li>"
                for j, o in enumerate(q.get("options", [])))
            items.append(f"""<div class='quiz' data-ans='{q.get("answer_index",0)}'>
              <div class='q'>{md_to_html(f"Q{i+1}. " + q.get("question",""))}</div>
              <ul class='opts'>{opts}</ul>
              <div class='exp'>{md_to_html(q.get("explanation",""))}</div></div>""")
        return f"<section class='ex'><h3>{S['quiz_heading']}</h3>{''.join(items)}</section>"
    else:  # practical
        items = []
        for i, t in enumerate(ex.get("tasks", [])):
            starter = f"<pre class='starter'><code>{html.escape(t.get('starter',''))}</code></pre>" if t.get("starter") else ""
            hints = "".join(f"<li>{html.escape(h)}</li>" for h in t.get("hints", []))
            items.append(f"""<div class='task'>
              <div class='q'>{md_to_html(f"{S['task_label']} {i+1}. " + t.get('prompt',''))}</div>
              {starter}
              <details><summary>{S['hint']}</summary><ul>{hints}</ul></details>
              <details><summary>{S['show_answer']}</summary>
                <pre class='sol'><code>{html.escape(t.get('solution',''))}</code></pre>
                <div class='exp2'>{md_to_html(t.get('explanation',''))}</div>
              </details></div>""")
        return f"<section class='ex'><h3>{S['practical_heading']}</h3>{''.join(items)}</section>"

# ---------------------------------------------------------------- 템플릿 로딩

def load_template(name, fallback):
    """templates/<name> 을 읽고, 없으면 내장 기본 골격으로 폴백."""
    path = os.path.join(TEMPLATES_DIR, name)
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    return fallback

# ---------------------------------------------------------------- 자산 스캐폴드

def scaffold_assets(docs, force=False):
    """docs/assets 의 공통 자산과 .nojekyll 을 생성한다.

    기본은 '없을 때만' 생성 → 손으로 고친 디자인이 재빌드로 덮어쓰이지 않는다.
    force=True (--reset-assets) 시 기본값으로 덮어쓴다.
    """
    files = {
        os.path.join(docs, "assets", "css", "style.css"): CSS_DEFAULT,
        os.path.join(docs, "assets", "js", "main.js"): JS_DEFAULT,
        os.path.join(docs, "assets", "img", ".gitkeep"): "",
        os.path.join(docs, ".nojekyll"): "",
    }
    for path, content in files.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if force or not os.path.exists(path):
            open(path, "w", encoding="utf-8").write(content)

# ---------------------------------------------------------------- 강좌 페이지

def load_curriculum(course_dir, lang):
    """커리큘럼을 읽되, en 등 비-ko 언어면 01_curriculum.<lang>.json 을 덮어쓰기로 병합한다.
    번역 오버레이가 없으면 한국어 원본으로 폴백(레거시 강좌 보호)."""
    curr = read_json(os.path.join(course_dir, "01_curriculum.json"), {})
    if lang != "ko":
        ov = read_json(os.path.join(course_dir, f"01_curriculum.{lang}.json"), None)
        if ov:
            curr = {**curr, **{k: v for k, v in ov.items() if v and k != "lectures"}}
    return curr

def course_has_translation(course_dir, lang):
    """ko는 항상 True. 비-ko 언어는 01_curriculum.<lang>.json 이 있어야 해당 언어 사이트에 포함한다.
    번역이 없는 강좌가 영문 페이지에 한국어 원본으로 폴백 노출되는 것을 막는다."""
    if lang == "ko":
        return True
    return os.path.exists(os.path.join(course_dir, f"01_curriculum.{lang}.json"))

def prune_courses(docs, courses_root, lang):
    """docs/<lang>/courses 아래에서 이번 언어로 빌드되지 않을 강좌 폴더를 제거한다.
    (소스가 사라졌거나, 비-ko인데 번역이 없는 강좌의 과거 산출물이 남아 랜딩에 다시 링크되는 것을 방지)"""
    cdir = os.path.join(docs, lang, "courses")
    if not os.path.isdir(cdir):
        return
    for slug in os.listdir(cdir):
        src = os.path.join(courses_root, slug)
        keep = (os.path.isdir(src)
                and os.path.exists(os.path.join(src, "01_curriculum.json"))
                and course_has_translation(src, lang))
        if not keep:
            shutil.rmtree(os.path.join(cdir, slug), ignore_errors=True)
            print(f"정리[{lang}]: {os.path.join(cdir, slug)} 제거 (해당 언어 미대상)")

def _pick_lang_file(ldir, base, ext, lang):
    """언어별 산출물 경로를 고른다. en이면 <base>.en.<ext> 우선, 없으면 <base>.<ext> 폴백."""
    if lang != "ko":
        cand = os.path.join(ldir, f"{base}.{lang}.{ext}")
        if os.path.exists(cand):
            return cand
    return os.path.join(ldir, f"{base}.{ext}")

_STALE_TOL = 2  # 초. 원본 생성 시 ko/en이 거의 동시에 써져 생기는 1초 미만 오차를 무시한다.

def _check_staleness(ldir, lang):
    """한국어 현지화본(content.md)이 영문 원본(content.en.md)보다 (의미 있게) 오래됐는지 검사해 경고를 돌려준다.
    영문이 canonical 이므로, 영문 본문을 보강한 뒤 한국어 재현지화를 깜빡한 경우를 빌드 로그에서 잡아낸다.
    정상 흐름에서는 한국어가 영문보다 '나중에' 만들어지므로(6b 현지화) 첫 빌드에서는 경고가 나지 않는다.
    mtime 비교라 git checkout/파일복사로 흔들릴 수 있어 '하드 실패'가 아니라 소프트 경고용이며,
    _STALE_TOL 초 이내 차이는 동시 작성으로 보고 무시한다(오탐 방지).
    (레거시 한국어-원본 강좌는 영문이 번역본이라 이 검사가 어긋날 수 있으나, 그 강좌들은 더 이상 갱신되지 않는다.)"""
    if lang != "ko":
        return None
    ko = os.path.join(ldir, "content.md")
    en = os.path.join(ldir, "content.en.md")
    if os.path.exists(ko) and os.path.exists(en) and os.path.getmtime(ko) + _STALE_TOL < os.path.getmtime(en):
        return "content.md (ko localization) older than content.en.md - content.md may need re-localization"
    return None

def _filter_sources(selected, lang):
    """영문 페이지(ko 외)는 영어 자막 영상만 노출. 한글 페이지는 전체 노출."""
    if lang == "ko":
        return selected
    return [s for s in selected if str(s.get("subtitle_lang", "")).lower().startswith("en")]

def render_course(course_dir, lang, S):
    """강좌 폴더를 읽어 (제목, 대상, 강수, toc, sections) 를 만든다. lang/S 로 i18n."""
    curr = load_curriculum(course_dir, lang)
    title = curr.get("course_title", "교육 강좌")
    sections, toc = [], []
    for lec in curr.get("lectures", []):
        no = lec["no"]
        ldir = glob.glob(os.path.join(course_dir, "lectures", f"{no:02d}_*"))
        ldir = ldir[0] if ldir else None
        if ldir:
            meta, body = parse_content_md(_pick_lang_file(ldir, "content", "md", lang))
            review = read_json(os.path.join(ldir, "review.json"), {})
            ex = read_json(_pick_lang_file(ldir, "exercise", "json", lang), {})
            sources = read_json(os.path.join(ldir, "sources.json"), {})
            stale = _check_staleness(ldir, lang)
            if stale:
                slug = os.path.basename(os.path.normpath(course_dir))
                print(f"[STALE][{lang}] {slug} lec{no}: {stale}")
        else:
            meta, body, review, ex, sources = {}, "", {}, {}, {}

        # 강의 제목: 영문 본문 frontmatter에 title이 있으면 그것을, 없으면 커리큘럼 제목.
        lec_title = meta.get("title") if (lang != "ko" and meta.get("title")) else lec["title"]

        badge = ""  # escalate 는 내부 추적용 플래그일 뿐, HTML 에는 표시하지 않는다.
        src_links = "".join(
            f"<li><a href='{html.escape(s.get('url',''))}' target='_blank'>{html.escape(s.get('title', S['src_default']))}</a></li>"
            for s in _filter_sources(sources.get("selected", []), lang))
        src_block = f"<div class='src'><strong>{S['sources']}</strong><ul>{src_links}</ul></div>" if src_links else ""

        toc.append(f"<li><a href='#lec{no}'>{no:02d}. {html.escape(lec_title)}</a></li>")
        sections.append(f"""<article id='lec{no}' class='lecture'>
          <h2>{no:02d}. {html.escape(lec_title)} {badge}</h2>
          {md_to_html(strip_leading_title(body))}
          {render_exercise(ex, S)}
          {src_block}
        </article>""")
    return curr, title, sections, toc

def build_course(course_dir, docs, lang, S):
    """강좌 1개를 docs/<lang>/courses/<슬러그>/index.html 로 빌드. 슬러그 반환."""
    slug = os.path.basename(os.path.normpath(course_dir))
    curr, title, sections, toc = render_course(course_dir, lang, S)
    count = curr.get("total_lectures", len(curr.get("lectures", [])))
    other = OTHER[lang]
    lang_toggle = (f"<a class='lang-toggle' data-lang='{other}' "
                   f"href='../../../{other}/courses/{html.escape(slug)}/index.html'>{S['toggle']}</a>")
    page_tmpl = load_template("page.html", PAGE_DEFAULT)
    page = page_tmpl.format(
        title=html.escape(title),
        subtitle=html.escape(curr.get("target_audience", "")),
        count_label=S["count_unit"].format(n=count, s="" if count == 1 else "s"),
        toc="\n".join(toc),
        sections="\n".join(sections),
        asset_base="../../../assets",
        home_href="../../index.html",
        home_label=S["home"],
        lang_attr=lang,
        lang_toggle=lang_toggle,
    )
    out_dir = os.path.join(docs, lang, "courses", slug)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "index.html")
    open(out, "w", encoding="utf-8").write(page)
    print(f"강좌 빌드[{lang}]: {out}")
    return slug

# ---------------------------------------------------------------- 랜딩 페이지

def build_landing(docs, courses_root, site_title, lang, S):
    """courses_root 의 강좌 중 docs/<lang> 에 빌드된 것만 모아 docs/<lang>/index.html 생성."""
    cards = []
    for course_dir in sorted(glob.glob(os.path.join(courses_root, "*"))):
        if not os.path.isdir(course_dir):
            continue
        slug = os.path.basename(os.path.normpath(course_dir))
        if not os.path.exists(os.path.join(docs, lang, "courses", slug, "index.html")):
            continue  # 아직 빌드 안 된 강좌는 링크 깨짐 방지를 위해 제외
        curr = load_curriculum(course_dir, lang)
        title = curr.get("course_title", slug)
        audience = curr.get("target_audience", "")
        count = curr.get("total_lectures", len(curr.get("lectures", [])))
        desc = curr.get("description", curr.get("summary", ""))
        meta = " · ".join(x for x in [html.escape(audience), S["count_unit"].format(n=count, s="" if count == 1 else "s")] if x)
        cards.append(f"""<a class='course-card' href='courses/{html.escape(slug)}/index.html'>
          <span class='card-accent'></span>
          <div class='card-body'>
            <h2>{html.escape(title)}</h2>
            <p class='desc'>{html.escape(desc)}</p>
            <p class='meta'>{meta}</p>
          </div>
        </a>""")

    other = OTHER[lang]
    lang_toggle = (f"<a class='lang-toggle' data-lang='{other}' "
                   f"href='../{other}/index.html'>{S['toggle']}</a>")
    landing_tmpl = load_template("landing.html", LANDING_DEFAULT)
    page = landing_tmpl.format(
        site_title=html.escape(site_title or S["site_title"]),
        landing_sub=S["landing_sub"].format(n=len(cards), s="" if len(cards) == 1 else "s"),
        course_cards="\n".join(cards) or f"<p class='empty'>{S['empty']}</p>",
        asset_base="../assets",
        lang_attr=lang,
        lang_toggle=lang_toggle,
    )
    out_dir = os.path.join(docs, lang)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "index.html")
    open(out, "w", encoding="utf-8").write(page)
    print(f"랜딩 빌드[{lang}]: {out} (강좌 {len(cards)}개)")


def build_router(docs):
    """docs/index.html 에 언어 라우터를 작성한다 (브라우저 언어/저장값 → ./ko 또는 ./en)."""
    router_tmpl = load_template("router.html", ROUTER_DEFAULT)
    os.makedirs(docs, exist_ok=True)
    out = os.path.join(docs, "index.html")
    open(out, "w", encoding="utf-8").write(router_tmpl)
    print(f"라우터 빌드: {out}")

# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description="강좌 산출물을 docs/ 통합 사이트로 빌드")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--course", help="courses/<슬러그> 경로 (단일 강좌 빌드)")
    g.add_argument("--all", action="store_true", help="courses/ 아래 모든 강좌 빌드")
    p.add_argument("--docs", default="docs", help="출력 사이트 루트 (기본 docs)")
    p.add_argument("--courses-root", default="courses", help="강좌 소스 루트 (기본 courses)")
    p.add_argument("--site-title", default=None, help="랜딩 페이지 제목 (미지정 시 언어별 기본값: ko=배움터, en=Learn)")
    p.add_argument("--reset-assets", action="store_true", help="공통 css/js를 기본값으로 덮어쓰기")
    a = p.parse_args()

    scaffold_assets(a.docs, force=a.reset_assets)

    for lang in LANGS:
        S = STRINGS[lang]
        if a.all:
            built = 0
            for course_dir in sorted(glob.glob(os.path.join(a.courses_root, "*"))):
                if os.path.isdir(course_dir) and os.path.exists(os.path.join(course_dir, "01_curriculum.json")):
                    if not course_has_translation(course_dir, lang):
                        print(f"건너뜀[{lang}]: {course_dir} (번역 없음 → 해당 언어 사이트 제외)")
                        continue
                    build_course(course_dir, a.docs, lang, S); built += 1
            if built == 0:
                print(f"경고: {a.courses_root} 에 빌드할 강좌가 없습니다.")
        elif course_has_translation(a.course, lang):
            build_course(a.course, a.docs, lang, S)
        else:
            print(f"건너뜀[{lang}]: {a.course} (번역 없음 → 해당 언어 사이트 제외)")
        prune_courses(a.docs, a.courses_root, lang)
        build_landing(a.docs, a.courses_root, a.site_title, lang, S)

    build_router(a.docs)
    print(f"완료 → {os.path.join(a.docs, 'index.html')}")

# ================================================================ 내장 기본값
# templates/ 파일이 없을 때 쓰는 HTML 골격 폴백, 그리고 자산 스캐폴드 기본 내용.

FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Hanken+Grotesk:wght@400;600;700;800&'
    'family=Source+Serif+4:ital,wght@0,400;0,600;1,400&'
    'family=JetBrains+Mono&display=swap">'
)

PAGE_DEFAULT = """<!DOCTYPE html>
<html lang="{lang_attr}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
""" + FONT_LINKS + """
<link rel="stylesheet" href="{asset_base}/css/style.css">
</head>
<body><div class="wrap">
<nav>
  <div class="navtop"><a class="home" href="{home_href}">{home_label}</a>{lang_toggle}</div>
  <h1>{title}</h1>
  <div class="sub">{subtitle} · {count_label}</div>
  <ul>{toc}</ul>
</nav>
<main>{sections}</main>
</div>
<script src="{asset_base}/js/main.js"></script>
</body></html>
"""

LANDING_DEFAULT = """<!DOCTYPE html>
<html lang="{lang_attr}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{site_title}</title>
""" + FONT_LINKS + """
<link rel="stylesheet" href="{asset_base}/css/style.css">
</head>
<body>
<header class="site-header">
  <div class="navtop">{lang_toggle}</div>
  <h1>{site_title}</h1>
  <p class="sub">{landing_sub}</p>
</header>
<main class="landing">
  <div class="course-grid">{course_cards}</div>
</main>
<script src="{asset_base}/js/main.js"></script>
</body></html>
"""

# 언어 라우터: localStorage(eduLang) → 없으면 navigator.language → ko면 ./ko, 아니면 ./en.
# JS 비활성 시 <noscript> 의 수동 링크로 폴백한다.
ROUTER_DEFAULT = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learn</title>
<script>
(function () {
  try {
    var saved = localStorage.getItem('eduLang');
    var lang = saved || (navigator.language || navigator.userLanguage || 'en');
    var dest = (lang.toLowerCase().indexOf('ko') === 0) ? 'ko' : 'en';
    location.replace('./' + dest + '/index.html');
  } catch (e) {
    location.replace('./en/index.html');
  }
})();
</script>
</head>
<body>
<noscript>
  <p>Choose your language:
     <a href="./ko/index.html">한국어</a> ·
     <a href="./en/index.html">English</a></p>
</noscript>
</body></html>
"""

# === Academic Clarity (Educational Zen) — design-guide/DESIGN.md 기반 라이트 테마 ===
CSS_DEFAULT = """:root{
  /* M3 컬러 토큰 (design-guide) */
  --surface:#f9f9fc;--surface-dim:#dadadc;
  --surface-container-lowest:#ffffff;--surface-container-low:#f3f3f6;
  --surface-container:#eeeef0;--surface-container-high:#e8e8ea;--surface-container-highest:#e2e2e5;
  --on-surface:#1a1c1e;--on-surface-variant:#434652;
  --outline:#737783;--outline-variant:#c3c6d4;
  --primary:#003178;--on-primary:#ffffff;--primary-container:#0d47a1;--primary-fixed:#d9e2ff;--surface-tint:#2b5bb5;
  --secondary:#006a62;--secondary-container:#81f3e5;--on-secondary-container:#006f66;
  --error:#ba1a1a;--error-container:#ffdad6;--on-error-container:#93000a;
  /* 폰트 (UI=Hanken Grotesk, 본문=Source Serif 4, 코드=JetBrains Mono) + 시스템 폴백 */
  --font-ui:'Hanken Grotesk','Pretendard','Segoe UI',system-ui,sans-serif;
  --font-read:'Source Serif 4','Pretendard',Georgia,serif;
  --font-code:'JetBrains Mono',ui-monospace,Consolas,monospace;
  /* 형태/간격/그림자 */
  --radius:8px;--radius-lg:12px;--radius-xl:16px;
  --reading-max:720px;--container-max:1280px;
  --shadow-academic:0 4px 20px rgba(13,71,161,.08);
}
*{box-sizing:border-box}
body{margin:0;font-family:var(--font-ui);background:var(--surface);color:var(--on-surface);line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--primary);text-decoration:none}a:hover{text-decoration:underline}

/* ---- 강좌 페이지: 사이드바 + 읽기 컬럼 ---- */
.wrap{display:grid;grid-template-columns:280px 1fr;max-width:var(--container-max);margin:0 auto}
nav{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:32px 24px;background:var(--surface-container-lowest);border-right:1px solid var(--outline-variant)}
nav .home{display:inline-block;font-size:13px;font-weight:600;color:var(--on-surface-variant);margin-bottom:18px}
nav .home:hover{color:var(--primary);text-decoration:none}
nav h1{font-size:17px;font-weight:700;line-height:1.3;color:var(--primary);margin:0 0 6px}
nav .sub{color:var(--on-surface-variant);font-size:12px}
nav ul{list-style:none;padding:0;margin:20px 0 0}nav li{margin:2px 0}
nav a{display:block;padding:7px 12px;border-left:4px solid transparent;border-radius:0 6px 6px 0;color:var(--on-surface-variant);font-size:13px;line-height:1.4}
nav a:hover{background:var(--surface-container);color:var(--primary);text-decoration:none}
nav a.active{border-left-color:var(--secondary);background:var(--surface-container);color:var(--primary);font-weight:600}
main{padding:48px 48px 80px;min-width:0}
/* 언어 토글 (네비 상단/랜딩 헤더 우측) */
.navtop{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
.lang-toggle{font-family:var(--font-ui);font-size:12px;font-weight:700;letter-spacing:.03em;padding:5px 12px;border:1px solid var(--outline-variant);border-radius:9999px;color:var(--on-surface-variant);white-space:nowrap}
.lang-toggle:hover{border-color:var(--primary);color:var(--primary);text-decoration:none}
.site-header .navtop{margin:0 0 8px;justify-content:flex-end}
.lecture{max-width:var(--reading-max);margin:0 0 56px;padding-bottom:40px;border-bottom:1px solid var(--outline-variant)}
.lecture:last-child{border-bottom:0}

/* 제목 (Hanken Grotesk) */
h2{font-family:var(--font-ui);font-size:23px;font-weight:600;line-height:1.3;color:var(--on-surface);margin:0 0 16px;padding-bottom:10px;border-bottom:2px solid var(--primary-fixed)}
h3{font-family:var(--font-ui);font-size:18px;font-weight:600;color:var(--primary);margin:28px 0 10px}
h4{font-family:var(--font-ui);font-size:15px;font-weight:600;margin:22px 0 8px}

/* 본문 (Source Serif 4) */
.lecture p,.lecture li{font-family:var(--font-read);font-size:16px;line-height:1.7;color:var(--on-surface);overflow-wrap:break-word;word-break:break-word}
.lecture ul{padding-left:22px}.lecture li{margin:6px 0}
strong{font-weight:600}em{font-style:italic}

/* 코드 (JetBrains Mono) */
pre{background:var(--surface-container-low);border:1px solid var(--outline-variant);padding:14px;border-radius:var(--radius);overflow:auto;font-size:12.5px}
pre code{font-family:var(--font-code)}
code.ic{font-family:var(--font-code);background:var(--surface-container);color:var(--surface-tint);padding:2px 6px;border-radius:4px;font-size:.9em;overflow-wrap:break-word;word-break:break-all}

/* 콜아웃 (Callout/Note) */
blockquote.callout{margin:20px 0;padding:14px 18px;background:rgba(129,243,229,.18);border-left:4px solid var(--secondary);border-radius:0 var(--radius) var(--radius) 0}
blockquote.callout p{margin:6px 0;font-family:var(--font-read);color:var(--on-surface)}

/* 배지 */
.badge{font-family:var(--font-ui);font-size:12px;font-weight:700;padding:3px 10px;border-radius:9999px;vertical-align:middle}
.badge.warn{background:var(--error-container);color:var(--on-error-container)}

/* 실습/퀴즈 */
.ex{background:var(--surface-container-lowest);border:1px solid var(--outline-variant);box-shadow:var(--shadow-academic);border-radius:var(--radius-lg);padding:24px 28px;margin-top:28px;max-width:var(--reading-max)}
.ex h3{margin-top:0}
.quiz,.task{margin:16px 0;padding:16px;background:var(--surface-container-low);border:1px solid var(--outline-variant);border-radius:var(--radius)}
.q{font-family:var(--font-ui);font-size:15px;font-weight:600;margin:0 0 10px}
.q,.q p,.q li,.opt,.exp,.exp2,.exp p,.exp2 p,.task ul li,.quiz .exp li{overflow-wrap:break-word;word-break:break-word;min-width:0}
.opts{list-style:none;padding:0;margin:0}
.opt{padding:10px 14px;margin:8px 0;background:var(--surface-container-lowest);border:1px solid var(--outline-variant);border-radius:var(--radius);cursor:pointer;transition:background .12s,border-color .12s}
.opt:hover{background:var(--surface-container);border-color:var(--outline)}
.opt.correct{background:var(--secondary-container);border-color:var(--secondary);color:var(--on-secondary-container);font-weight:600}
.opt.wrong{background:var(--error-container);border-color:var(--error);color:var(--on-error-container)}
.exp,.exp2{display:none;margin-top:12px;color:var(--on-surface-variant);font-size:13px}
.quiz.answered .exp{display:block}
.starter,.sol{margin:8px 0}
details summary{cursor:pointer;color:var(--primary);font-family:var(--font-ui);font-weight:600;margin:10px 0}

/* 다이어그램 */
.diagram{margin:28px 0;text-align:center;overflow-x:auto}
.diagram figcaption{font-family:var(--font-ui);color:var(--on-surface-variant);font-size:13px;margin-top:8px}
.mermaid{display:flex;justify-content:center}
/* Mermaid 로드 전/실패(오프라인) 폴백: 소스를 코드블록처럼 (라이트) */
.mermaid:not([data-processed='true']){display:block;white-space:pre;text-align:left;background:var(--surface-container-low);color:var(--on-surface-variant);border:1px solid var(--outline-variant);padding:16px;border-radius:var(--radius);font-family:var(--font-code);font-size:13px}

/* 출처 */
.src{margin-top:24px;padding-top:16px;border-top:1px solid var(--outline-variant);font-family:var(--font-ui);font-size:13px;color:var(--on-surface-variant)}
.src ul{margin:8px 0 0;padding-left:18px}.src a{color:var(--primary)}

/* ---- 랜딩 페이지 ---- */
.site-header{max-width:var(--container-max);margin:0 auto;padding:64px 48px 24px}
.site-header h1{font-family:var(--font-ui);font-size:34px;font-weight:700;letter-spacing:-.02em;color:var(--primary);margin:0 0 8px}
.site-header .sub{font-family:var(--font-ui);color:var(--on-surface-variant);font-size:14px;margin:0}
.landing{max-width:var(--container-max);margin:0 auto;padding:24px 48px 80px}
.course-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}
.course-card{display:flex;flex-direction:column;background:var(--surface-container-lowest);border:1px solid var(--outline-variant);border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow-academic);text-decoration:none;color:var(--on-surface);transition:transform .18s,border-color .18s}
.course-card:hover{transform:translateY(-2px);border-color:var(--primary);text-decoration:none}
.course-card .card-accent{display:block;height:8px;background:linear-gradient(90deg,var(--primary),var(--secondary))}
.course-card .card-body{padding:22px 24px;display:flex;flex-direction:column;flex-grow:1}
.course-card h2{font-family:var(--font-ui);font-size:18px;font-weight:600;color:var(--primary);border:0;padding:0;margin:0 0 10px}
.course-card .desc{font-family:var(--font-read);color:var(--on-surface-variant);font-size:14px;line-height:1.55;margin:0 0 16px}
.course-card .meta{margin-top:auto;font-family:var(--font-ui);font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--on-surface-variant)}
.empty{color:var(--on-surface-variant)}

/* 반응형 */
@media(max-width:768px){
  .wrap{grid-template-columns:1fr}
  nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--outline-variant)}
  main{padding:24px 16px 56px}
  .site-header{padding:40px 16px 16px}.site-header h1{font-size:26px}
  .landing{padding:16px 16px 56px}
  h2{font-size:20px}
  /* 넓은 다이어그램은 줄여 찌그러뜨리지 말고 가로 스크롤(왼쪽 정렬) */
  .diagram{overflow-x:auto}
  .mermaid{justify-content:flex-start}
}
"""

JS_DEFAULT = """// 퀴즈 정답 처리 — 인라인 onclick 에서 호출되므로 전역 함수로 둔다.
function pick(el, qi, oi) {
  var quiz = el.closest('.quiz');
  if (quiz.classList.contains('answered')) return;
  var ans = parseInt(quiz.dataset.ans);
  quiz.querySelectorAll('.opt').forEach(function (o, j) {
    if (j === ans) o.classList.add('correct');
    else if (j === oi) o.classList.add('wrong');
  });
  quiz.classList.add('answered');
}

// 사이드바 활성 강의 하이라이트 (디자인 가이드: 좌측 4px Teal 바). 랜딩엔 사이드바가 없어 무시됨.
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('nav a[href^="#lec"]'));
  var articles = document.querySelectorAll('article.lecture[id]');
  if (!links.length || !articles.length || !('IntersectionObserver' in window)) return;
  var byId = {};
  links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      links.forEach(function (a) { a.classList.remove('active'); });
      var active = byId[e.target.id];
      if (active) active.classList.add('active');
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  articles.forEach(function (a) { obs.observe(a); });
})();

// Mermaid 다이어그램 — CDN 동적 import 후 mermaid.run()으로 명시 렌더.
// startOnLoad는 import가 window load 이벤트보다 늦게 끝나면(모바일=느린 망/CPU) 렌더를 놓쳐
// 소스 텍스트가 그대로 노출되므로 쓰지 않는다. 대신 명시적으로 그려 결정적으로 렌더한다.
(async function () {
  var blocks = document.querySelectorAll('.mermaid');
  if (!blocks.length) return;
  var mermaid;
  try {
    mermaid = (await import('https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.esm.min.mjs')).default;
    mermaid.initialize({
      startOnLoad: false, securityLevel: 'loose', theme: 'base',
      themeVariables: {
        fontFamily: 'Hanken Grotesk, sans-serif',
        primaryColor: '#d9e2ff', primaryBorderColor: '#003178', primaryTextColor: '#1a1c1e',
        lineColor: '#434652', secondaryColor: '#81f3e5', tertiaryColor: '#f3f3f6'
      }
    });
  } catch (e) {
    console.warn('Mermaid 로드 실패 — 다이어그램 소스를 텍스트로 표시합니다.', e);
    return; // 폴백 CSS(.mermaid:not([data-processed='true']))가 소스를 텍스트로 표시
  }
  function render(el) { mermaid.run({ nodes: [el] }).catch(function (e) { console.warn('Mermaid 렌더 실패', e); }); }
  // 화면에 가까워진 다이어그램만 렌더(성능). 옵저버 미지원이면 즉시 전부 렌더.
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        render(en.target);
      });
    }, { rootMargin: '200px 0px' });
    blocks.forEach(function (el) { io.observe(el); });
  } else {
    blocks.forEach(render);
  }
})();

// 언어 토글 — 사용자가 고른 언어를 localStorage(eduLang)에 기억해 라우터(docs/index.html)가 재사용한다.
(function () {
  document.querySelectorAll('a.lang-toggle[data-lang]').forEach(function (a) {
    a.addEventListener('click', function () {
      try { localStorage.setItem('eduLang', a.getAttribute('data-lang')); } catch (e) {}
    });
  });
})();
"""

if __name__ == "__main__":
    main()
