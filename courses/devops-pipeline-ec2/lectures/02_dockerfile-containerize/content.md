---
lecture_no: 2
title: 앱을 컨테이너로 패키징하기 — Dockerfile 작성과 로컬 실행
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=gAkwW2tuIqE
  - https://www.youtube.com/watch?v=LQjaJINkQXY
  - https://www.youtube.com/watch?v=SnSH8Ht3MIc
---

# 앱을 컨테이너로 패키징하기 — Dockerfile 작성과 로컬 실행

## 학습 목표
- 왜 컨테이너 이미지가 전체 파이프라인의 배포 단위인지 이해한다.
- 웹앱을 이미지로 만드는 표준 Dockerfile 패턴을 익힌다.
- `docker build`와 `docker run`으로 이미지를 로컬에서 빌드·실행하고 동작을 확인한다.

## 본문

### 왜 컨테이너를 쓰나

**컨테이너**는 코드와 실행에 필요한 모든 것 — 런타임, 라이브러리, 설정 — 을 하나로 묶는다. 덕분에 내 노트북에서도, EC2에서도 똑같이 실행된다. "내 로컬에서는 되는데요"는 더 이상 통하지 않는다. 세 가지 용어를 먼저 정리해 두자.

- **Dockerfile** — 빌드 명령이 담긴 텍스트 레시피.
- **이미지(Image)** — Dockerfile로 빌드한 불변 스냅샷.
- **컨테이너(Container)** — 이미지의 실행 인스턴스.

> 이 파이프라인에서 이미지는 내 노트북에서 Jenkins를 거쳐 ECR로, 다시 EC2로 이동하는 단 하나의 배포 산출물이다. 이후에 자동화하는 모든 것은 결국 "이 이미지를 빌드하고, 저장하고, 어딘가에서 실행한다"는 흐름이다. Dockerfile이 그 모든 것의 기초다.

### 1단계 — Dockerfile 작성

프로젝트 루트에 확장자 없이 `Dockerfile`이라는 이름으로 파일을 만든다. 아래 예제는 Node.js 기준이지만 구조 자체는 어떤 언어에든 적용된다.

```dockerfile
# 런타임이 포함된 공식 slim 베이스 이미지를 지정한다
FROM node:20-alpine

# 이미지 안의 작업 디렉터리를 설정한다
WORKDIR /app

# 의존성 목록을 먼저 복사하고 설치한다 — 이 레이어가 캐시된다
COPY package.json package-lock.json ./
RUN npm install

# 나머지 소스 코드를 복사한다
COPY . .

# 앱이 리스닝하는 포트를 명시한다
EXPOSE 8080

# 컨테이너가 시작될 때 실행할 명령을 지정한다
CMD ["node", "index.js"]
```

핵심 포인트 세 가지:

- **`FROM` — slim 공식 이미지를 쓴다.** `node:20-alpine`은 Alpine Linux(약 5 MB) 기반이라 이미지를 작고 빠르게 유지한다.
- **레이어 캐싱이 순서를 결정한다.** 각 명령은 캐시되는 레이어다. Docker는 변경된 레이어부터만 재빌드하므로, 의존성은 앞에 두고 소스는 뒤에 둬야 한다. 의존성은 거의 안 바뀌지만 소스는 수시로 바뀐다 — `package.json`을 복사하고 `npm install`을 먼저 실행해 두면, 코드만 고쳤을 때 설치 단계를 건너뛸 수 있다. 순서를 뒤집으면 코드 한 줄 바꿀 때마다 전체 재설치가 강제된다.
- **`CMD`는 배열(exec) 형식을 쓴다** — 문자열 대신 `["node", "index.js"]`. shell을 거치지 않고 프로세스를 직접 실행하므로 시그널 처리와 종료 동작이 올바르게 작동한다.

### 2단계 — .dockerignore 추가

`COPY . .`은 로컬 `node_modules`나 혹시 있을 시크릿 파일까지 *모든 것*을 복사한다. `.gitignore`처럼 제외 목록을 만든다.

```
node_modules
.git
*.env
```

이미지를 작게 유지하고, 이미지를 pull하는 누군가가 레이어를 들여다봤을 때 시크릿이 노출되지 않도록 막아 준다.

### 3단계 — 이미지 빌드

`-t` 플래그로 이름을 붙이고, 끝의 `.`으로 현재 디렉터리를 빌드 컨텍스트로 지정한다.

```bash
docker build -t myapp:local .
```

빌드된 이미지를 확인한다.

```bash
docker images
```

### 4단계 — 실행 및 확인

```bash
docker run -p 5000:8080 myapp:local
```

`-p 5000:8080` 플래그가 핵심이다. 컨테이너 포트는 기본적으로 외부에서 *접근할 수 없다*. 이 플래그가 호스트 포트 `5000`을 컨테이너 포트 `8080`(`EXPOSE`한 포트)에 연결한다. 형식은 `호스트:컨테이너`다. `http://localhost:5000`을 열면 앱이 보여야 한다.

백그라운드에서 실행하고 관리하려면 아래 명령을 쓴다.

```bash
docker run -d -p 5000:8080 myapp:local   # 백그라운드 실행
docker ps                                # 실행 중인 컨테이너 확인
docker logs <container>                  # 로그 확인
docker stop <container>                  # 중지
```

이제 재현 가능한 이미지가 만들어졌고 로컬에서 동작도 확인했다. 지금 수동으로 한 모든 단계가 이후 강의에서 Jenkins 스테이지로 바뀐다.

## 핵심 정리
- 컨테이너는 앱과 실행 환경 전체를 묶어 어디서든 동일하게 동작하는 단 하나의 배포 산출물을 만든다.
- **Dockerfile** → **이미지** → **컨테이너** 의 흐름을 기억한다.
- Dockerfile은 레이어 캐싱을 고려해 의존성을 소스 *앞에* 두고, slim 베이스 이미지와 `.dockerignore`로 이미지를 작고 안전하게 유지한다.
- `docker build -t 이름 .`으로 빌드하고, `docker run -p 호스트:컨테이너 이름`으로 실행한다. 포트 매핑 없이는 앱에 접근할 수 없다.

## 출처
- https://www.youtube.com/watch?v=gAkwW2tuIqE
- https://www.youtube.com/watch?v=LQjaJINkQXY
- https://www.youtube.com/watch?v=SnSH8Ht3MIc
