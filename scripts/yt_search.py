#!/usr/bin/env python3
"""YouTube Data API v3로 키워드 검색. 자막 유무 확인은 yt_check.py가 담당."""
import argparse, json, os, sys, urllib.parse, urllib.request

API = "https://www.googleapis.com/youtube/v3"

def api_get(endpoint, params):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("환경변수 YOUTUBE_API_KEY 가 필요합니다. (Google Cloud Console에서 발급)")
    params["key"] = key
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url) as r:
        return json.load(r)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keywords", required=True, help="쉼표로 구분한 검색어")
    p.add_argument("--max", type=int, default=15)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    q = " ".join(k.strip() for k in a.keywords.split(","))
    # 1) 검색
    search = api_get("search", {
        "part": "snippet", "q": q, "type": "video",
        "maxResults": a.max, "relevanceLanguage": "ko",
        "videoCaption": "closedCaption",  # 자막 있는 영상 우선 필터
        "order": "relevance",
    })
    ids = [it["id"]["videoId"] for it in search.get("items", [])]
    if not ids:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        json.dump({"query": q, "videos": []}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("검색 결과 0건")
        return

    # 2) 통계/길이 보강
    details = api_get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)})
    videos = []
    for it in details.get("items", []):
        st = it.get("statistics", {})
        videos.append({
            "video_id": it["id"],
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
            "published": it["snippet"]["publishedAt"],
            "duration_iso": it["contentDetails"]["duration"],
            "caption_flag": it["contentDetails"].get("caption") == "true",
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "url": f"https://www.youtube.com/watch?v={it['id']}",
        })

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"query": q, "videos": videos}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(videos)}건 저장: {a.out}")

if __name__ == "__main__":
    main()
