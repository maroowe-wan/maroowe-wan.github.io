---
name: youtube-search
description: YouTube Data API v3로 교육용 영상을 검색하고 자막·평점 기준으로 선별하는 방법. youtube-scout 에이전트가 참조.
---

# YouTube 영상 검색 & 선별 스킬

## 사전 준비
- `YOUTUBE_API_KEY` 필요. Google Cloud Console → YouTube Data API v3 활성화 → API 키 발급. 저장소 루트 `.env`에 `YOUTUBE_API_KEY=...` 로 두면 `yt_search.py`가 자동 로드한다(환경변수가 있으면 그쪽 우선).
- 무료 할당량은 하루 10,000 유닛. search 1회 = 100유닛, videos 조회 = 1유닛. 강좌 10강 × 검색 1회면 약 1,010유닛으로 여유 있음.
- **키가 없거나 할당량이 소진(403/429)되면 `yt_search.py`가 자동으로 `yt-dlp ytsearch` 폴백으로 우회**한다(키 불필요). 따라서 검색 자체는 항상 동작하며, 별도의 폴백 스크립트를 만들 필요가 없다.

## 검색 명령
```bash
python scripts/yt_search.py --keywords "키워드1,키워드2" --max 15 --out <경로>/raw_search.json
```
- `videoCaption=closedCaption` 파라미터로 **자막 있는 영상만** 1차 필터링됨 (단 자동생성 자막은 이 필터를 통과 못 할 수 있으므로 3단계에서 재확인).
- **최신성 강제(필수):** 스크립트는 `publishedAfter`로 **최근 3년 이내 게시 영상만** 검색한다(`--max-age-years` 기본값 3). 오래된 기술 강의를 원천 차단하기 위함이다. 특별한 사유로 더 넓혀야 할 때만 `--max-age-years 5`처럼 늘리고, `0`이면 제한 해제(권장하지 않음). 3년 이내로 검색이 0건이면 기간을 늘리기 전에 키워드 완화를 먼저 시도한다.

## 선별 점수 공식 (권장)
```
score = 0.35 * normalize(likes/views)      # 참여도
      + 0.25 * normalize(log(views))        # 신뢰도
      + 0.20 * recency_factor               # 최신성 (오래된 기술강의 감점)
      + 0.20 * keyword_match                # 제목·설명 부합도
```
- 강의당 상위 1~3개 선정. 15분 분량을 채우려면 5~8분짜리 영상 2개를 묶어도 됨.
- contentDetails.duration(ISO8601, 예 PT12M30s)을 초로 변환해 2분~60분만 통과.

## 실패 대응
- 검색 0건 → 키워드를 영어로 번역하거나 상위 개념어로 완화해 재검색.
- 할당량 초과(403/429) → `yt_search.py`가 자동으로 yt-dlp 폴백으로 우회한다(결과 JSON에 `"source": "yt-dlp-fallback"`). 폴백 결과는 최신성 필터가 적용되지 않고 `caption_flag`가 `null`이므로, 자막은 `yt_check.py`로 확정하고 최신성은 점수화에서 거른다.
