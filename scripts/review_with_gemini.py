#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""강의 감수(5단계)를 Gemini CLI에 위임하는 얇은 래퍼.

content-reviewer 에이전트(Claude)는 직접 감수하지 않고 이 스크립트를 호출한다.
판단은 Gemini가 하고, 이 스크립트는 입출력·JSON 검증·재시도 한계 처리만 한다.

사용:
    python scripts/review_with_gemini.py <course_slug> <lecture_no> [--model M] [--revision-count N]

성공 시 courses/<slug>/lectures/<NN>_*/review.json 을 쓰고 종료코드 0.
gemini 실패(인증/네트워크) 또는 JSON 파싱 실패 시 stderr에 사유를 출력하고
review.json 을 만들지 않은 채 비0 종료한다(안전규칙: 조용히 건너뛰지 않는다).
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ISSUE_TYPES = (
    "accuracy", "objective_miss", "insufficient", "difficulty",
    "inappropriate", "structure", "diagram", "literal_translation",
)

PROMPT_TEMPLATE = """\
You are an educational-content reviewer (QA). Your job is precise defect-finding, not praise.
The lecture body under review is written in ENGLISH (English is the canonical authoring language
of this pipeline). First adopt the perspective of a domain expert for the course "{course_title}":
as a seasoned practitioner, what would you flag as wrong, and which best practices or caveats are missing?

[Lecture info]
- Course: {course_title}
- Lecture number: {lecture_no}
- Lecture title: {lecture_title}
- Expected type (expected_type): {expected_type}
- Learning objectives (these come from the course spec and MAY be written in Korean;
  the lecture body is English — verify the English body covers every objective regardless of language):
{objectives}

[Body under review] is the entire content.en.md that follows the divider "===== content under review =====".

[Project conventions — DO NOT flag these as false positives]
- The Korean/English text on the first fence line after ```mermaid is a caption that this builder
  (build_html.py) renders as a <figcaption>. Do NOT flag it as "non-standard / syntax error / use a title directive".
  For diagrams, judge only the diagram body from the next line on (nodes, arrows, syntax, and whether it matches the prose).
- content.en.md is a reconstructed/rewritten lesson based on transcripts, NOT a copy of the source. Do NOT flag it as "transcript copying".

[Review checklist] Check each item:
1. Accuracy: factual errors, outdated info, wrong concepts — technical errors a domain expert would reject. (Always REVISE on failure.)
2. Objective coverage: does it cover every objective? List any uncovered objective in missing_topics.
3. Sufficiency: enough for a 15-minute lecture, neither too shallow nor bloated.
4. Difficulty: matched to the audience; no hard term thrown in without explanation.
5. Appropriateness: no bias, inaccurate generalization, or irrelevant tangents.
6. Structure: a logical intro → concept → example → summary flow.
7. Diagrams: each ```mermaid block matches the prose/facts, has valid syntax, and is only where it genuinely helps. (defect type "diagram")
8. Language quality (English): is the English idiomatic and is technical terminology standard and correct?
   Flag unidiomatic/awkward English or non-standard technical terms (e.g. an invented term where a standard one exists).
   (defect type "literal_translation" — reused here as the "language/terminology quality" channel)

[Verdict rules]
- PASS: all items pass. Put minor improvements in minor_notes only.
- REVISE: any failure of accuracy / objective coverage / sufficiency. Always give concrete issues and (if objectives are missing) missing_topics.
- **Use REVISE only for factual errors, missing objectives, or clear insufficiency.** Suggestions like "would be nice to go deeper" or
  "could add this topic" are not defects — put them in minor_notes, not issues (do not REVISE an already-correct body repeatedly).

[Output format] Output ONLY raw JSON of the schema below. No markdown fences (```), no explanation, no preamble.
The type of an issue is one of: {issue_types}
{{
  "verdict": "PASS" or "REVISE",
  "issues": [{{"type": "accuracy", "detail": "concrete problem description"}}],
  "missing_topics": ["uncovered learning objective"],
  "minor_notes": ["minor points to note while passing"]
}}
"""


def die(msg):
    sys.stderr.write("[review_with_gemini] ERROR: " + msg + "\n")
    sys.exit(1)


def find_lecture_dir(course_dir, no):
    pattern = os.path.join(course_dir, "lectures", "%02d_*" % no)
    matches = sorted(glob.glob(pattern))
    if not matches:
        die("강의 폴더를 찾을 수 없음: %s" % pattern)
    return matches[0]


def extract_json(text):
    """gemini 출력에서 JSON 객체만 추출한다. ```json 펜스/머리말이 섞여 있어도 처리."""
    t = text.strip()
    # 코드펜스 제거
    if "```" in t:
        # 첫 ``` 이후 ~ 마지막 ``` 사이를 취한다
        first = t.find("```")
        body = t[first + 3:]
        # 언어 토큰(json) 줄 제거
        nl = body.find("\n")
        if nl != -1 and body[:nl].strip().lower() in ("json", ""):
            body = body[nl + 1:]
        last = body.rfind("```")
        if last != -1:
            body = body[:last]
        t = body.strip()
    # 첫 '{' 부터 균형 맞는 '}' 까지
    start = t.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return t[start:i + 1]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("lecture_no", type=int)
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--revision-count", type=int, default=None,
                    help="현재까지 재작성 횟수. 생략 시 기존 review.json 값 사용")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    course_dir = os.path.join(REPO_ROOT, "courses", args.slug)
    if not os.path.isdir(course_dir):
        die("강좌 폴더 없음: %s" % course_dir)

    curr_path = os.path.join(course_dir, "01_curriculum.json")
    if not os.path.isfile(curr_path):
        die("커리큘럼 없음: %s" % curr_path)
    with open(curr_path, encoding="utf-8") as f:
        curriculum = json.load(f)

    lec = next((l for l in curriculum.get("lectures", []) if l.get("no") == args.lecture_no), None)
    if lec is None:
        die("커리큘럼에 강의 no=%d 없음" % args.lecture_no)

    lec_dir = find_lecture_dir(course_dir, args.lecture_no)
    # 영문이 원본(canonical). 감수는 content.en.md 를 대상으로 한다.
    # (레거시 강좌처럼 영문본이 없으면 한국어 content.md 로 폴백한다.)
    content_path = os.path.join(lec_dir, "content.en.md")
    if not os.path.isfile(content_path):
        content_path = os.path.join(lec_dir, "content.md")
    if not os.path.isfile(content_path):
        die("content.en.md/content.md 둘 다 없음: %s" % lec_dir)
    with open(content_path, encoding="utf-8") as f:
        content = f.read()

    review_path = os.path.join(lec_dir, "review.json")

    # revision_count 결정: 인자 > 기존 review.json > 0
    revision_count = args.revision_count
    if revision_count is None:
        revision_count = 0
        if os.path.isfile(review_path):
            try:
                with open(review_path, encoding="utf-8") as f:
                    revision_count = int(json.load(f).get("revision_count", 0))
            except Exception:
                revision_count = 0

    objectives = "\n".join("  - " + o for o in lec.get("objectives", []))
    prompt = PROMPT_TEMPLATE.format(
        course_title=curriculum.get("course_title", args.slug),
        lecture_no=args.lecture_no,
        lecture_title=lec.get("title", ""),
        expected_type=lec.get("expected_type", ""),
        objectives=objectives,
        issue_types=" / ".join(ISSUE_TYPES),
    )

    # 지침(prompt)과 본문을 모두 stdin으로 보내고 -p 는 짧은 지시만 둔다.
    # (거대 프롬프트를 argv로 넘길 때의 길이·특수문자 인용 문제를 피한다.)
    payload = prompt + "\n\n===== content under review =====\n" + content
    directive = ("Follow the review instructions in the input and output ONLY raw JSON "
                 "per the given schema. No markdown fences, no prose.")

    exe = shutil.which("gemini")
    if not exe:
        die("gemini CLI 를 찾을 수 없음. 설치/PATH 를 확인하라.")
    flags = ["-p", directive, "-y", "--skip-trust", "-m", args.model]
    # Windows 의 .cmd/.bat 래퍼는 subprocess 가 직접 실행하지 못하므로 셸로 실행한다.
    use_shell = exe.lower().endswith((".cmd", ".bat"))
    run_cmd = subprocess.list2cmdline([exe] + flags) if use_shell else [exe] + flags
    try:
        proc = subprocess.run(
            run_cmd, input=payload, capture_output=True, text=True,
            encoding="utf-8", timeout=args.timeout, shell=use_shell,
        )
    except FileNotFoundError:
        die("gemini CLI 실행 실패(경로: %s)." % exe)
    except subprocess.TimeoutExpired:
        die("gemini 호출 타임아웃(%ds)." % args.timeout)

    if proc.returncode != 0:
        die("gemini 비정상 종료(code=%d). 인증/네트워크 확인 필요.\nstderr: %s"
            % (proc.returncode, (proc.stderr or "")[-800:]))

    raw = extract_json(proc.stdout or "")
    if not raw:
        die("gemini 출력에서 JSON 을 찾지 못함.\n출력: %s" % (proc.stdout or "")[-800:])
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        die("JSON 파싱 실패: %s\n원문: %s" % (e, raw[-800:]))

    verdict = result.get("verdict", "").upper()
    if verdict not in ("PASS", "REVISE"):
        die("verdict 값이 PASS/REVISE 가 아님: %r" % result.get("verdict"))

    issues = result.get("issues", []) or []
    missing = result.get("missing_topics", []) or []
    minor = result.get("minor_notes", []) or []

    # 재시도 한계: 4회 후에도 REVISE면 escalate=true 로 통과시키고 파이프라인을 멈추지 않는다.
    escalate = False
    if verdict == "REVISE" and revision_count >= 4:
        verdict = "PASS"
        escalate = True

    review = {
        "lecture_no": args.lecture_no,
        "verdict": verdict,
        "revision_count": revision_count,
        "escalate": escalate,
        "issues": issues,
        "missing_topics": missing,
        "minor_notes": minor,
        "reviewed_by": "gemini:" + args.model,
    }
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)

    sys.stderr.write("[review_with_gemini] %s  verdict=%s  issues=%d  escalate=%s\n"
                     % (review_path, verdict, len(issues), escalate))
    print(review_path)


if __name__ == "__main__":
    main()
