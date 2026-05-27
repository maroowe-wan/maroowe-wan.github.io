#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostToolUse(ExitPlanMode) 훅 — plan mode에서 확정된 계획을 plans/ 에 영속 저장한다.

배경: plan mode가 만든 계획은 대화(transcript)에만 남아, 새 세션을 시작하거나
대화가 자동 요약되면 사라진다. 이 훅이 ExitPlanMode 직후 계획 본문을 파일로 떨궈
중단 후 재시작(다른 세션/PC/팀원)이 용이하도록 만든다.

동작:
- stdin 으로 받은 PostToolUse JSON 에서 tool_input.plan(계획 마크다운)을 읽는다.
- plans/<타임스탬프>_<슬러그>.md 로 저장하고, plans/_latest.md 를 같은 내용으로 갱신한다.
- 헤더에 저장 시각·git 브랜치·작업 디렉터리·승인여부(추정)를 기록한다.
- 어떤 예외에도 fail-open(exit 0)해 작업 흐름을 막지 않는다.

저장 위치: 저장소 루트의 plans/ (하위 폴더이므로 block_root_writes 훅에 걸리지 않음).
"""
import datetime
import json
import os
import re
import subprocess
import sys

for _s in ("stdin", "stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8")
    except Exception:
        pass

# scripts/hooks/<this> → scripts/ → <repo root>
REPO_ROOT = os.path.normpath(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PLANS_DIR = os.path.join(REPO_ROOT, "plans")


def slugify(text, maxlen=40):
    """계획 첫 줄에서 파일명용 짧은 슬러그를 만든다(한글·영문·숫자 보존)."""
    first = ""
    for line in (text or "").splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            first = line
            break
    first = re.sub(r"[\s/\\]+", "-", first)         # 공백·구분자 → 하이픈
    first = re.sub(r"[^\w가-힣\-]", "", first)        # 안전한 문자만
    first = re.sub(r"-{2,}", "-", first).strip("-")
    return first[:maxlen] or "plan"


def git_branch():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "?"
    except Exception:
        return "?"


def approval_hint(data):
    """tool_response 에서 승인 여부를 best-effort 로 추정한다(불확실하면 '확정')."""
    resp = data.get("tool_response")
    blob = json.dumps(resp, ensure_ascii=False).lower() if resp is not None else ""
    if any(k in blob for k in ("reject", "denied", "cancel", "false")):
        return "거부/취소 추정"
    return "확정(승인) 추정"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") != "ExitPlanMode":
        sys.exit(0)

    plan = (data.get("tool_input") or {}).get("plan")
    if not plan or not plan.strip():
        sys.exit(0)

    now = datetime.datetime.now()
    ts_file = now.strftime("%Y%m%d-%H%M%S")
    ts_human = now.strftime("%Y-%m-%d %H:%M:%S")
    cwd = data.get("cwd") or os.getcwd()

    header = (
        f"<!-- 자동 저장: plan mode 계획 (save_plan.py 훅) -->\n"
        f"# 계획 — {ts_human}\n\n"
        f"- 저장 시각: {ts_human}\n"
        f"- git 브랜치: {git_branch()}\n"
        f"- 작업 디렉터리: {cwd}\n"
        f"- 상태: {approval_hint(data)}\n\n"
        f"---\n\n"
    )
    body = header + plan.rstrip() + "\n"

    try:
        os.makedirs(PLANS_DIR, exist_ok=True)
        fname = os.path.join(PLANS_DIR, f"{ts_file}_{slugify(plan)}.md")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(body)
        with open(os.path.join(PLANS_DIR, "_latest.md"), "w", encoding="utf-8") as f:
            f.write(body)
        # PostToolUse stdout 은 컨텍스트로 전달된다 — 어디 저장됐는지 한 줄 알린다.
        rel = os.path.relpath(fname, REPO_ROOT).replace("\\", "/")
        print(f"[save_plan] 계획을 {rel} 에 저장했습니다 (plans/_latest.md 갱신).")
    except Exception as e:
        sys.stderr.write(f"[save_plan] 저장 실패(무시): {e}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
