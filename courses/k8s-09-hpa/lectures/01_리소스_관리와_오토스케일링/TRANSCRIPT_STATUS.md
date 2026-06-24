# 자막 추출 상태 보고 (4강: 리소스 관리와 오토스케일링)

## 요약
- 선정된 영상: 4개
- 성공: 1개 (25%)
- 실패: 3개 (75%)
- 실패 원인: YouTube HTTP 429 (Too Many Requests) - IP 기반 Rate Limiting

## 상세 결과

### ✅ 성공
1. **V-Ib-DdconY** (한국어)
   - 제목: K8S HPA 강의 제대로 듣고 있었습니까? 정신 차리십시오 | Kubernetes Autoscaling with HPA
   - 자막 파일: sub_V-Ib-DdconY.txt
   - 크기: 11,140자
   - 언어: 한국어 (수동 자막)
   - URL: https://www.youtube.com/watch?v=V-Ib-DdconY

### ❌ 실패 (HTTP 429 Too Many Requests)
1. **lKH1K5R3kqg** (한국어)
   - 제목: 12분 안에 알아야 할 모든 것: 쿠버네티스의 포드 요청 및 제한
   - URL: https://www.youtube.com/watch?v=lKH1K5R3kqg
   - 에러: YouTube가 자막 다운로드 요청에 HTTP 429 응답

2. **jyBDbm1FHiM** (영어)
   - 제목: Autoscaling in Kubernetes
   - URL: https://www.youtube.com/watch?v=jyBDbm1FHiM
   - 에러: YouTube가 자막 다운로드 요청에 HTTP 429 응답

3. **2CrprvnzPXY** (영어)
   - 제목: Kubernetes CPU Limits & Requests EXPLAINED (Stop Wasting Resources!)
   - URL: https://www.youtube.com/watch?v=2CrprvnzPXY
   - 에러: YouTube가 자막 다운로드 요청에 HTTP 429 응답

## 원인 분석
- yt-dlp --list-subs로 확인했을 때 모든 영상에 자동생성 자막이 존재함
- 하지만 자막 다운로드 시에만 HTTP 429 에러 발생
- 이는 YouTube의 **IP 레벨 Rate Limiting**으로 추정
- 단순 "봇 차단(Sign in to confirm)" 이 아님
- 사용자의 브라우저 쿠키를 사용한 재시도도 실패

## 권장 대응
이 문제를 해결하려면:
1. **IP 차단 해제 대기** (보통 몇 시간~하루)
2. **다른 네트워크/VPN 사용** (구글 정책상 권장하지 않음)
3. **youtube-scout에게 보고** - 동일 주제의 대체 영상 재검색 요청
4. **나중에 재시도** - 충분한 시간 경과 후 다시 시도

## 참고
- yt_check.py, yt_search_ytdlp.py는 현재 untracked 상태이며, youtube-scout 단계의 도구임
- transcript-extractor는 이미 선정된 영상의 자막만 추출하는 역할
- 영상 재검색은 youtube-scout의 책임
