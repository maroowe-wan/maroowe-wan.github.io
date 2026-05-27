---
name: transcript-extract
description: yt-dlp로 YouTube 자막을 추출하고 봇 차단을 대응하는 방법. transcript-extractor 에이전트가 참조.
---

# 자막 추출 스킬

## 핵심 명령
```bash
python scripts/yt_transcript.py --video-id <ID> --lang ko,en --out <경로>/sub_<ID>.txt
```

## 봇 차단 대응 (2026년 현재 가장 중요한 이슈)
YouTube는 자동화 트래픽을 차단한다. 에러 메시지: `Sign in to confirm you're not a bot`.

- **로컬 PC 환경(이 프로젝트)**: 데이터센터 IP가 아니므로 대부분 차단 없이 동작한다.
- **차단 발생 시**: 브라우저 쿠키를 넘긴다.
  ```bash
  python scripts/yt_transcript.py --video-id <ID> --cookies-from-browser chrome --out <경로>
  ```
  Chrome이 설치돼 로그인돼 있으면 대개 해결. Chrome 실패 시 `firefox`, `edge`로 시도.
- **주의**: PO 토큰 방식은 2026년 현재 대부분 봇 체크를 우회하지 못하므로 의존하지 말 것. 쿠키 방식이 현실적.
- yt-dlp는 자주 업데이트되므로 차단이 잦으면 `pip install -U yt-dlp` 로 최신화.

## 자막 우선순위
- `ko`(한국어) > `en`(영어) > 자동생성 순으로 채택.
- 자동생성 자막은 노이즈(중복 줄, [음악] 등)가 많아 yt_transcript.py가 정리하지만, 품질이 낮으면 4단계 content-writer가 일반 지식으로 보완하게 한다.

## 저작권 주의
- 추출한 자막은 **원본 그대로 컨텐츠에 쓰지 않는다.** 4단계에서 반드시 재작성한다.
- 자막 파일은 중간 산출물이며 최종 배포물에 포함하지 않는다.
