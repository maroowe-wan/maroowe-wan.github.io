#!/usr/bin/env python3
"""yt-dlp를 이용해 자막 존재 여부와 언어를 확인한다.
Usage:
  python scripts/yt_check.py --video-id abc123
  python scripts/yt_check.py --video-ids-file candidates.json
"""
import argparse, json, subprocess, sys, re, os

def check_subtitle(video_id):
    """Returns (has_subtitle: bool, lang: str|None, subtitle_type: str|None, detail: dict)

    subtitle_lang: 영상 콘텐츠의 원본 언어 (ko/en/other).
      - en-orig 가 있으면 영어 원본 → 'en'
      - ko 수동 자막(Available subtitles 섹션)이 있으면 → 'ko'
      - 그 외 자동 자막만 있는 경우 en이 있으면 'en', ko이 있으면 'ko'
    subtitle_type: 'manual' | 'auto'
    """
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

    # 수동 자막 섹션 감지
    manual_section = bool(re.search(r'Available subtitles for', output, re.IGNORECASE))
    # 자동 자막 섹션 감지 (yt-dlp는 "Available automatic captions for ..." 로 표시)
    auto_section = bool(re.search(r'Available automatic captions for', output, re.IGNORECASE))

    has_sub_section = manual_section or auto_section

    if not has_sub_section:
        return False, None, None, {"raw": output[-300:]}

    # en-orig = 영어 원본 콘텐츠
    en_orig = bool(re.search(r'\ben-orig\b', output))
    # 수동 자막에서 언어 감지 (Available subtitles 섹션)
    if manual_section:
        # 수동 자막 섹션 텍스트만 추출
        manual_match = re.search(
            r'Available subtitles.*?(?=Available automatic captions|$)',
            output, re.DOTALL | re.IGNORECASE
        )
        manual_text = manual_match.group(0) if manual_match else ""
        ko_manual = bool(re.search(r'\bko\b', manual_text))
        en_manual = bool(re.search(r'\ben\b', manual_text))
    else:
        ko_manual = False
        en_manual = False

    # 자동 자막 언어 감지
    auto_match = re.search(
        r'Available automatic captions.*',
        output, re.DOTALL | re.IGNORECASE
    )
    auto_text = auto_match.group(0) if auto_match else ""
    ko_auto = bool(re.search(r'\bko\b', auto_text))
    en_auto = bool(re.search(r'\ben\b', auto_text))

    # 원본 언어 판정 우선순위:
    # 1. en-orig 있으면 → 영어 원본 → en
    # 2. 수동 자막 ko → ko
    # 3. 수동 자막 en → en
    # 4. 자동 자막만: en이 있으면 en (영어 원본의 자동 자막), ko만 있으면 ko
    if en_orig or (not ko_manual and en_auto):
        lang = "en"
    elif ko_manual:
        lang = "ko"
    elif en_manual:
        lang = "en"
    elif ko_auto and not en_auto:
        lang = "ko"
    else:
        lang = "other"

    sub_type = "manual" if manual_section else "auto"

    return True, lang, sub_type, {
        "en_orig": en_orig, "ko_manual": ko_manual, "en_manual": en_manual,
        "ko_auto": ko_auto, "en_auto": en_auto, "raw": output[-300:]
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video-id", help="단일 영상 ID")
    p.add_argument("--video-ids-file", help="candidates.json 경로")
    p.add_argument("--out", help="결과 JSON 저장 경로")
    a = p.parse_args()

    if a.video_id:
        has_sub, lang, sub_type, detail = check_subtitle(a.video_id)
        result = {"video_id": a.video_id, "has_subtitle": has_sub, "subtitle_lang": lang, "subtitle_type": sub_type}
        print(json.dumps(result, ensure_ascii=False))
        return

    if a.video_ids_file:
        with open(a.video_ids_file, encoding='utf-8') as f:
            candidates = json.load(f)

        results = []
        for i, c in enumerate(candidates):
            vid = c["video_id"]
            title_safe = c.get('title','')[:50].encode('ascii', errors='replace').decode('ascii')
            print(f"[{i+1}/{len(candidates)}] 자막 확인: {vid} - {title_safe}", flush=True)
            try:
                has_sub, lang, sub_type, detail = check_subtitle(vid)
            except subprocess.TimeoutExpired:
                has_sub, lang, sub_type = False, None, None
                print(f"  TIMEOUT")
            except Exception as e:
                has_sub, lang, sub_type = False, None, None
                print(f"  ERROR: {e}")

            c_result = dict(c)
            c_result["has_subtitle"] = has_sub
            c_result["subtitle_lang"] = lang
            c_result["subtitle_type"] = sub_type
            results.append(c_result)
            status = f"자막={lang}({sub_type})" if has_sub else "자막없음"
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
