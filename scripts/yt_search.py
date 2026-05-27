#!/usr/bin/env python3
"""YouTube Data API v3로 키워드 검색. 자막 유무 확인은 yt_check.py가 담당."""
import argparse, json, os, sys, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

API = "https://www.googleapis.com/youtube/v3"


class ApiUnavailable(Exception):
    """API 키 없음 또는 할당량 소진(403/429) 등으로 Data API를 못 쓰는 상황.
    → main()이 이를 잡아 yt-dlp ytsearch 폴백으로 우회한다."""

def load_dotenv():
    """저장소 루트의 .env를 읽어 환경변수로 채운다(이미 설정된 값은 보존). 표준 라이브러리만 사용."""
    # scripts/yt_search.py -> 저장소 루트는 한 단계 위
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)  # 기존 환경변수가 우선

def api_get(endpoint, params):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise ApiUnavailable("YOUTUBE_API_KEY 미설정")
    params["key"] = key
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # 403 = quotaExceeded/forbidden, 429 = rate limit → 폴백 신호로 전환
        if e.code in (403, 429):
            raise ApiUnavailable(f"HTTP {e.code} (할당량 소진/레이트 제한)") from e
        raise


def sec_to_iso8601(sec):
    """330 -> 'PT5M30S' (yt-dlp의 duration_sec를 API의 duration_iso 스키마에 맞춤)."""
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    out = "PT"
    if h: out += f"{h}H"
    if m: out += f"{m}M"
    if s or out == "PT": out += f"{s}S"
    return out


def run_ytdlp_fallback(q, max_results, out, reason):
    """Data API 사용 불가 시 yt-dlp ytsearch로 우회 검색하고 동일 스키마로 저장."""
    print(f"[폴백] YouTube Data API 사용 불가({reason}). yt-dlp ytsearch로 우회합니다.",
          file=sys.stderr, flush=True)
    # 같은 scripts/ 폴더의 재사용 폴백 모듈을 임포트
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from yt_search_ytdlp import search_with_ytdlp
    videos = search_with_ytdlp(q, max_results)
    # API 출력 스키마에 맞춰 보강: duration_iso, caption_flag
    for v in videos:
        v["duration_iso"] = sec_to_iso8601(v.pop("duration_sec", 0))
        v.setdefault("caption_flag", None)  # 검색 단계에선 미확정 → yt_check.py가 자막을 확정
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"query": q, "videos": videos, "source": "yt-dlp-fallback"},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(videos)}건 저장 (yt-dlp 폴백): {out}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keywords", required=True, help="쉼표로 구분한 검색어")
    p.add_argument("--max", type=int, default=15)
    p.add_argument("--out", required=True)
    p.add_argument("--max-age-years", type=float, default=3,
                   help="이 연수보다 오래된 영상은 검색에서 제외 (기본 3년). 0이면 제한 없음.")
    a = p.parse_args()

    load_dotenv()  # .env의 YOUTUBE_API_KEY를 환경에 주입 (없으면 무시)
    q = " ".join(k.strip() for k in a.keywords.split(","))

    try:
        # 1) 검색
        params = {
            "part": "snippet", "q": q, "type": "video",
            "maxResults": a.max, "relevanceLanguage": "ko",
            "videoCaption": "closedCaption",  # 자막 있는 영상 우선 필터
            "order": "relevance",
        }
        # 최신성 강제: 최근 N년 이내 게시 영상만 (publishedAfter, RFC3339 UTC)
        if a.max_age_years and a.max_age_years > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=a.max_age_years * 365.25)
            params["publishedAfter"] = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        search = api_get("search", params)
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
        window = f" (최근 {a.max_age_years:g}년 이내)" if a.max_age_years and a.max_age_years > 0 else ""
        print(f"{len(videos)}건 저장{window}: {a.out}")
    except ApiUnavailable as e:
        # API 키 없음 또는 할당량 소진 → yt-dlp ytsearch로 자동 우회
        # (주의: yt-dlp 검색은 publishedAfter 최신성 필터를 적용하지 못한다. 최신성은 후속 점수화에서 보정)
        run_ytdlp_fallback(q, a.max, a.out, str(e))

if __name__ == "__main__":
    main()
