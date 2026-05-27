#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PreToolUse(Write) 훅 — 저장소 루트 직속 경로에 파일 생성을 차단한다.

배경: 에이전트/스크립트가 임시·중간 파일을 저장소 루트에 흘리는 일이 반복돼(예: temp_lec1_subs.json),
CLAUDE.md 규칙으로 금지했지만 강제 장치가 없었다. 이 훅이 Write 도구의 루트 쓰기를 강제로 막는다.

동작:
- stdin 으로 받은 PreToolUse JSON 에서 tool_input.file_path 를 읽는다.
- 그 경로의 부모 디렉터리가 저장소 루트면(= 루트 직속 파일) 차단한다(exit 2, stderr 사유).
- 하위 폴더(courses/, docs/, scripts/, .claude/, templates/ ...) 쓰기는 통과(exit 0).
- 루트 직속이라도 화이트리스트(.gitignore, CLAUDE.md, README.md, DEPLOY.md)는 통과.

한계: Write 도구만 잡는다. Bash/스크립트가 만드는 루트 파일은 막지 못하므로 그건 에이전트 지침으로 지킨다.
훅이 실패하면(파싱 등) fail-open(통과)해 작업을 막지 않는다.
"""
import json
import os
import sys

# Windows 기본 인코딩(cp949)으로 한글 stderr 가 깨져 모델에 전달되지 않도록 UTF-8 고정.
for _s in ("stdin", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8")
    except Exception:
        pass

# scripts/hooks/<this> → scripts/ → <repo root>
REPO_ROOT = os.path.normcase(os.path.normpath(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

WHITELIST = {".gitignore", "claude.md", "readme.md", "deploy.md",
             "requirements.txt", ".env", ".env.example"}  # 소문자 비교, 정식 루트 파일


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 입력 파싱 실패 → 통과(fail-open)

    if data.get("tool_name") != "Write":
        sys.exit(0)

    fp = (data.get("tool_input") or {}).get("file_path")
    if not fp:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    parent = os.path.normcase(os.path.normpath(os.path.dirname(os.path.abspath(fp))))

    # 저장소 루트 직속 파일인가?
    if parent == REPO_ROOT and os.path.basename(fp).lower() not in WHITELIST:
        sys.stderr.write(
            "저장소 루트에 파일을 만들 수 없습니다(프로젝트 규칙).\n"
            f"  차단된 경로: {fp}\n"
            "  → 강좌 산출물은 courses/<슬러그>/lectures/<NN>_*/ 안에, "
            "일회성 임시파일은 OS 임시 폴더($TEMP/%TEMP%, Python tempfile)에 쓰세요.\n")
        sys.exit(2)  # 2 = 도구 호출 차단 + stderr 를 모델에 전달

    sys.exit(0)


if __name__ == "__main__":
    main()
