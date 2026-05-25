#!/usr/bin/env python3
"""yt-dlp로 자막(.vtt)을 받아 순수 텍스트로 변환.
봇 차단 시 --cookies-from-browser 로 재시도 가능."""
import argparse, glob, os, re, subprocess, sys, tempfile

def vtt_to_text(vtt_path):
    """VTT에서 타임스탐프/태그/중복을 제거해 읽을 수 있는 텍스트로."""
    lines, seen, out = open(vtt_path, encoding="utf-8").read().splitlines(), set(), []
    for ln in lines:
        if "-->" in ln or ln.strip() in ("WEBVTT", "") or ln.strip().isdigit():
            continue
        clean = re.sub(r"<[^>]+>", "", ln).strip()        # <00:00:00.000> 류 태그 제거
        clean = re.sub(r"\[[^\]]*\]", "", clean).strip()   # [음악] 류 제거
        if clean and clean not in seen:                    # 자동자막 중복 줄 제거
            seen.add(clean)
            out.append(clean)
    return "\n".join(out)

def run_ytdlp(video_id, langs, cookies_from_browser, tmpdir):
    url = f"https://www.youtube.com/watch?v={video_id}"
    # 지정된 언어 자막 다운로드
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", langs,  # 요청한 언어만
        "--sub-format", "vtt",
        "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"), url,
    ]
    if cookies_from_browser:
        cmd[1:1] = ["--cookies-from-browser", cookies_from_browser]
    return subprocess.run(cmd, capture_output=True, text=True)

def pick_subtitle(vtts, prefer_langs):
    """선호 언어 순서대로 자막 파일 선택."""
    # prefer_langs는 "ko,en" 같은 형식
    langs = [l.strip() for l in prefer_langs.split(",")]
    for lang in langs:
        for vtt in vtts:
            # 파일명: TlHvYWVUZyc.ko.vtt, TlHvYWVUZyc.en-US.vtt 등
            if f".{lang}" in vtt or f".{lang}-" in vtt:
                return vtt
    # 기본값: 첫 번째 (보통 en-US)
    return vtts[0] if vtts else None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video-id", required=True)
    p.add_argument("--lang", default="ko,en")
    p.add_argument("--out", required=True)
    p.add_argument("--cookies-from-browser", default=None,
                   help="봇 차단 시 chrome/firefox/edge 등 지정")
    a = p.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        r = run_ytdlp(a.video_id, a.lang, a.cookies_from_browser, tmp)
        if "Sign in to confirm you" in (r.stderr or "") and not a.cookies_from_browser:
            print("BOT_BLOCK: 봇 차단 감지. --cookies-from-browser chrome 으로 재시도하세요.", file=sys.stderr)
            sys.exit(2)
        vtts = sorted(glob.glob(os.path.join(tmp, "*.vtt")))
        if not vtts:
            print(f"NO_SUBTITLE: {a.video_id} 자막 없음", file=sys.stderr)
            sys.exit(3)
        # 선호 언어 순으로 선택
        selected_vtt = pick_subtitle(vtts, a.lang)
        text = vtt_to_text(selected_vtt)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"자막 저장: {a.out} ({len(text)}자)")

if __name__ == "__main__":
    main()
