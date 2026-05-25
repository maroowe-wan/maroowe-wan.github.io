#!/usr/bin/env python3
"""yt-dlp를 이용해 자막 존재 여부와 언어를 확인한다.
Usage:
  python scripts/yt_check.py --video-id abc123
  python scripts/yt_check.py --video-ids-file candidates.json
"""
import argparse, json, subprocess, sys, re, os

def check_subtitle(video_id):
    """Returns (has_subtitle: bool, lang: str|None, detail: dict)"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--list-subs",
        "--skip-download",
        "--no-download",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr

    # 자막 없음 케이스
    if "has no subtitles" in output.lower() or "no subtitles" in output.lower():
        return False, None, {"raw": output[-500:]}

    # 자막 언어 감지: yt-dlp --list-subs 출력에서 ko/en 찾기
    # 자동생성: "ko (auto-generated)", 수동: "ko"
    ko_found = bool(re.search(r'\bko\b', output))
    en_found = bool(re.search(r'\ben\b', output))

    # Available subtitles/Automatic captions 섹션이 있는지 확인
    has_sub_section = (
        "Available subtitles" in output
        or "Automatic captions" in output
        or "available subtitles" in output.lower()
    )

    if not has_sub_section:
        return False, None, {"raw": output[-300:]}

    # 우선순위: ko > en > 기타
    if ko_found:
        lang = "ko"
    elif en_found:
        lang = "en"
    else:
        # 다른 언어라도 자막 섹션이 있으면 허용
        lang = "other"

    return True, lang, {"ko": ko_found, "en": en_found, "raw": output[-300:]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video-id", help="단일 영상 ID")
    p.add_argument("--video-ids-file", help="candidates.json 경로")
    p.add_argument("--out", help="결과 JSON 저장 경로")
    a = p.parse_args()

    if a.video_id:
        has_sub, lang, detail = check_subtitle(a.video_id)
        result = {"video_id": a.video_id, "has_subtitle": has_sub, "subtitle_lang": lang}
        print(json.dumps(result, ensure_ascii=False))
        return

    if a.video_ids_file:
        with open(a.video_ids_file, encoding='utf-8') as f:
            candidates = json.load(f)

        results = []
        for i, c in enumerate(candidates):
            vid = c["video_id"]
            print(f"[{i+1}/{len(candidates)}] 자막 확인: {vid} - {c.get('title','')[:50]}", flush=True)
            try:
                has_sub, lang, detail = check_subtitle(vid)
            except subprocess.TimeoutExpired:
                has_sub, lang = False, None
                print(f"  TIMEOUT")
            except Exception as e:
                has_sub, lang = False, None
                print(f"  ERROR: {e}")

            c_result = dict(c)
            c_result["has_subtitle"] = has_sub
            c_result["subtitle_lang"] = lang
            results.append(c_result)
            status = f"자막={lang}" if has_sub else "자막없음"
            print(f"  -> {status}")

        if a.out:
            os.makedirs(os.path.dirname(a.out), exist_ok=True)
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n결과 저장: {a.out}")
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    p.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
