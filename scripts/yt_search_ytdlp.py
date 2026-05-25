#!/usr/bin/env python3
"""yt-dlp ytsearch를 사용해 YouTube 키워드 검색 (API 키 불필요)."""
import argparse, json, os, sys, subprocess, re, datetime

def iso8601_to_sec(s):
    """'PT5M30S' -> 330"""
    if not s:
        return 0
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s or '')
    if not m:
        return 0
    h, mi, sec = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + sec

def search_with_ytdlp(query, max_results=15):
    """yt-dlp ytsearch로 검색하고 기본 메타데이터 반환."""
    search_url = f"ytsearch{max_results}:{query}"
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--no-download",
        "--flat-playlist",
        search_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding='utf-8')

    videos = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid_id = item.get('id') or item.get('url', '').replace('https://www.youtube.com/watch?v=', '')
        if not vid_id:
            continue

        duration_sec = item.get('duration') or 0

        videos.append({
            "video_id": vid_id,
            "title": item.get('title', ''),
            "channel": item.get('channel') or item.get('uploader') or '',
            "published": item.get('upload_date', ''),
            "duration_sec": int(duration_sec),
            "views": item.get('view_count') or 0,
            "likes": item.get('like_count') or 0,
            "url": f"https://www.youtube.com/watch?v={vid_id}",
        })

    return videos

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keywords", required=True, help="쉼표로 구분한 검색어")
    p.add_argument("--max", type=int, default=15)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    q = " ".join(k.strip() for k in a.keywords.split(","))
    print(f"검색어: {q}", flush=True)

    videos = search_with_ytdlp(q, a.max)

    if not videos:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump({"query": q, "videos": []}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("검색 결과 0건")
        return

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"query": q, "videos": videos}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(videos)}건 저장: {a.out}")

if __name__ == "__main__":
    main()
