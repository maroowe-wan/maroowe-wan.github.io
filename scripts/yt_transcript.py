#!/usr/bin/env python3
"""yt-dlp로 자막(.vtt)을 받아 순수 텍스트로 변환.
봇 차단 시 --cookies-from-browser 로 재시도 가능."""
import argparse, glob, os, re, sys, tempfile
import yt_dlp

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

    # 언어 코드를 yt-dlp 형식으로 변환
    # en -> en,en-US,en-GB 등으로 확장
    lang_list = []
    for lang in langs.split(","):
        lang = lang.strip()
        if lang == "en":
            lang_list.extend(["en", "en-US", "en-GB", "en-AU", "en-CA", "en-NZ", "en-IN"])
        elif lang == "ko":
            lang_list.extend(["ko", "ko-KR"])
        else:
            lang_list.append(lang)

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": lang_list,
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(tmpdir, "%(id)s"),
        "quiet": False,
        "no_warnings": False,
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = cookies_from_browser

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return None
    except Exception as e:
        return str(e)

def pick_subtitle(vtts, prefer_langs):
    """선호 언어 순서대로 자막 파일 선택."""
    # prefer_langs는 "ko,en" 같은 형식
    langs = [l.strip() for l in prefer_langs.split(",")]

    for lang in langs:
        for vtt in sorted(vtts):
            # 파일명: TlHvYWVUZyc.ko.vtt, TlHvYWVUZyc.en-US.vtt 등
            # 언어 코드가 파일명에 포함되는지 확인 (단, "-" 후 숫자가 따르는 경우도 포함)
            pattern = f".{lang}" in vtt or f".{lang}-" in vtt
            if pattern:
                return vtt

    # 기본값: 첫 번째 (보통 en-US)
    return sorted(vtts)[0] if vtts else None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video-id", required=True)
    p.add_argument("--lang", default="ko,en")
    p.add_argument("--out", required=True)
    p.add_argument("--cookies-from-browser", default=None,
                   help="봇 차단 시 chrome/firefox/edge 등 지정")
    a = p.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        error = run_ytdlp(a.video_id, a.lang, a.cookies_from_browser, tmp)
        if error and "Sign in to confirm you" in error and not a.cookies_from_browser:
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
