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
당신은 교육 컨텐츠 감수자(QA)다. 칭찬이 아니라 정확한 결함 발견이 역할이다.
먼저 이 강좌의 도메인 전문가 시각을 채택한다: "{course_title}" 강좌의 숙련 실무자라면
이 설명에서 무엇이 틀렸다고 지적할지, 어떤 모범 사례·주의점이 빠졌다고 볼지를 기준으로 본다.

[강의 정보]
- 강좌: {course_title}
- 강의 번호: {lecture_no}
- 강의 제목: {lecture_title}
- 예상 유형(expected_type): {expected_type}
- 학습 목표(objectives):
{objectives}

[감수 본문] 은 아래 "===== 감수 대상 content.md =====" 구분선 뒤에 이어지는 content.md 전체다.

[감수 체크리스트] 항목별로 점검한다:
1. 정확성: 사실 오류·오래된 정보·잘못된 개념. 도메인 전문가가 틀렸다 할 기술 오류. (실패 시 반드시 REVISE)
2. 목표 충족: objectives를 모두 다루는가? 빠진 목표는 missing_topics에 적는다.
3. 충분성: 15분 강의로 충분한가, 너무 얕거나 과하지 않은가.
4. 난이도: 대상 수준에 맞는가, 설명 없이 어려운 용어를 던지지 않는가.
5. 적절성: 편향·부정확한 일반화·무관한 곁가지가 없는가.
6. 구조: 도입-개념-예시-정리 흐름이 논리적인가.
7. 다이어그램: ```mermaid 블록이 본문·사실과 일치하는가, 문법이 유효한가, 꼭 필요한 곳에 있는가. (결함은 type "diagram")
8. 직역 오류(번역투): 영어 기술 용어를 뜻이 깨지게 직역하지 않았는가?
   예) "flat network"를 "평평한 네트워크"로, 고유 개념을 어색하게 직역해 의미 파악이 안 되는 경우.
   표준 한국어 기술 표기 또는 원어 병기로 바로잡아야 한다. (결함은 type "literal_translation")

[판정 규칙]
- PASS: 모든 항목 통과. 사소한 개선점은 minor_notes 에만 적는다.
- REVISE: 정확성/목표충족/충분성 중 하나라도 실패. 구체적 issues 와 (목표 누락 시) missing_topics 를 반드시 적는다.

[출력 형식] 오직 아래 스키마의 raw JSON 만 출력한다. 마크다운 펜스(```), 설명, 머리말 금지.
issue 의 type 은 다음 중 하나: {issue_types}
{{
  "verdict": "PASS" 또는 "REVISE",
  "issues": [{{"type": "accuracy", "detail": "구체적 문제 설명"}}],
  "missing_topics": ["다루지 않은 학습 목표"],
  "minor_notes": ["통과시키되 참고할 사소한 점"]
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
    content_path = os.path.join(lec_dir, "content.md")
    if not os.path.isfile(content_path):
        die("content.md 없음: %s" % content_path)
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
    payload = prompt + "\n\n===== 감수 대상 content.md =====\n" + content
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

    # 재시도 한계: 2회 후에도 REVISE면 escalate=true 로 통과시키고 파이프라인을 멈추지 않는다.
    escalate = False
    if verdict == "REVISE" and revision_count >= 2:
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
