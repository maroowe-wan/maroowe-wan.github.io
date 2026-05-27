---
lecture_no: 2
title: "앱 컨테이너화와 ECR 준비"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=lOdrdV0eDrs
  - https://www.youtube.com/watch?v=Hv5UcBYseus
  - https://www.youtube.com/watch?v=OihC0CS43AI
---

# 앱 컨테이너화와 ECR 준비

## 학습 목표
- `Dockerfile`을 사용해 언어에 관계없이 웹 애플리케이션을 컨테이너 이미지로 패키징한다.
- Amazon ECR 리포지토리를 생성해 이미지를 보관할 위치를 준비한다.
- 이미지가 모든 쿠버네티스 배포의 *입력값*임을 이해한다.

## 본문

### 왜 여기서 시작하는가

쿠버네티스는 소스코드를 실행하지 않는다. **컨테이너 이미지**를 실행한다. 따라서 파이프라인이나 매니페스트, 클러스터를 논하기 전에, 앱을 이미지로 변환하는 반복 가능한 방법과 이미지를 안정적으로 보관할 공간이 필요하다. 이 강의에서 다루는 것이 바로 그것이다. `Dockerfile`로 이미지를 빌드하고, **Amazon ECR** 리포지토리에 저장한다. 특정 태그의 이미지가 ECR에 올라가고 나면, 이후 강의는 EKS가 그 이미지를 실행하도록 하는 과정이다.

컨테이너의 장점 중 하나는 **언어에 무관하다**는 점이다. Node.js든, Go든, Python이든, Java든 방법은 같다. `Dockerfile`에 빌드를 기술하고, `docker build`를 실행하고, `docker push`한다. 파이프라인은 어떤 언어로 작성했는지 신경 쓰지 않는다. `Dockerfile`이 존재하기만 하면 된다.

### Dockerfile의 구조

`Dockerfile`은 일반 텍스트로 된 레시피다. 각 줄이 이미지의 레이어를 하나씩 만드는 명령이다. Node.js 웹 앱을 위한 최소한의 예시는 다음과 같다.

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

줄별로 살펴보면:

- `FROM node:18-alpine` — Node가 이미 설치된 공식 베이스 이미지에서 시작한다. `alpine`은 이미지 크기를 작게 유지하는 경량 Linux 배포판이다.
- `WORKDIR /app` — 이미지 내부의 작업 디렉터리를 설정한다.
- `COPY package*.json ./` 다음 `RUN npm install` — 의존성 매니페스트만 먼저 복사하고 설치한다. 나머지 코드를 복사하기 전에 이 순서로 하면, 소스만 바뀌었을 때 Docker가 의존성 레이어를 캐시해 재설치를 건너뛴다. 이 순서를 지키는 습관 하나가 빌드 시간을 크게 단축한다.
- `COPY . .` — 애플리케이션 소스를 복사한다.
- `EXPOSE 3000` — 앱이 3000번 포트에서 수신한다는 것을 문서화한다.
- `CMD [...]` — 컨테이너가 시작될 때 실행하는 명령이다.

> 실제 프로젝트에서 자주 볼 수 있는 발전된 형태가 **멀티 스테이지 빌드**다. 첫 번째 스테이지에서 앱을 컴파일하고(모든 빌드 도구 포함), 두 번째 경량 스테이지에서는 완성된 바이너리만 Google의 'distroless' 같은 최소 이미지로 복사한다. 결과물에는 앱 외에 아무것도 없다 — 셸도, 패키지 매니저도 없어 더 작고 공격 표면도 줄어든다.

로컬에서 빌드하고 테스트한다.

```bash
docker build -t my-app:dev .
docker run -p 3000:3000 my-app:dev
```

### ECR 리포지토리 생성

**Amazon ECR(Elastic Container Registry)**은 AWS의 프라이빗 도커 레지스트리다. Docker Hub와 비슷하지만 AWS 계정 안에서 IAM으로 접근을 제어하는 팀 전용 이미지 보관소라 생각하면 된다.

AWS 콘솔에서 생성하려면 "ECR" 검색 후 *리포지토리 생성*을 누른다. CLI로는 다음과 같다.

```bash
aws ecr create-repository \
  --repository-name my-app \
  --region us-east-1
```

리포지토리는 같은 애플리케이션의 여러 버전(태그)을 담는 하나의 명명된 버킷이다. 보통 서비스당 ECR 리포지토리를 하나 만든다.

### ECR에 이미지 푸시하기

ECR 리포지토리는 프라이빗이므로, 푸시 전에 Docker가 인증해야 한다. ECR 콘솔의 *푸시 명령 보기*에서 정확한 명령어를 확인할 수 있다. 흐름은 로그인 → 빌드 → 태그 → 푸시, 네 단계다.

```bash
# 1. Docker를 ECR 레지스트리에 인증한다 (로그인 토큰은 단기 유효)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 2. 이미지를 빌드한다
docker build -t my-app .

# 3. 전체 ECR 주소와 의미 있는 태그로 태깅한다
docker tag my-app:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)

# 4. 푸시한다
docker push \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)
```

전체 이미지 이름의 형태는 `<account-id>.dkr.ecr.<region>.amazonaws.com/<repo-name>:<tag>`다. 마지막 `/` 앞부분이 **레지스트리**(내 계정, 내 리전), 그 뒤가 **리포지토리 이름**, `:` 뒤가 **태그**다.

### `latest` 대신 커밋으로 태그하라

`$(git rev-parse --short HEAD)` — Git 커밋 SHA — 를 `latest` 대신 태그로 사용했다. 이것은 이 강좌 전체에서 가장 중요한 습관 중 하나다.

`latest`는 움직이는 레이블이다. 두 빌드가 모두 `latest`를 푸시하면, 두 번째 빌드가 첫 번째를 조용히 덮어쓰고 `latest`는 방금 전과 다른 무언가를 가리키게 된다. 실행 중인 클러스터를 보면 `latest`를 실행 중이라고 나오지만, 그게 *어떤* 코드인지는 알 수 없다 — 롤백이 추측 작업이 된다.

커밋 기반 태그(또는 `v1.4.2` 같은 시맨틱 버전)는 **불변이고 추적 가능**하다. `a1b9f3c`라는 태그는 항상 정확히 그 코드를 가리키며, 영원히 바뀌지 않는다. 어떤 Pod든 이미지 태그를 보면 정확히 무엇이 배포됐는지 알 수 있다. 이것이 7강의 롤백을 신뢰할 수 있게 만드는 이유다.

### 쿠버네티스와의 연결

이후에 Deployment 매니페스트를 작성할 때(4강), 가장 중요한 필드는 이미지 참조다.

```yaml
        image: <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

이것이 이 강의의 핵심이다. 여기서 빌드하고 푸시한 이미지가 배포의 **입력값**이 된다. 파이프라인의 역할은 본질적으로 새 이미지를 계속 생성하고 이 한 줄을 갱신해서 EKS가 새 버전을 풀하고 실행하도록 하는 것이다.

한 가지 더 알아두면 좋은 점이 있다. 프로덕션에서는 보통 클러스터(노드나 서비스 ID)에 ECR에서 이미지를 풀할 수 있는 권한을 부여한다. EKS가 자체적으로 이미지를 가져올 수 있도록 하는 것이다. AWS는 규모에 따라 이미지 풀을 빠르고 안정적으로 유지하는 리전 간 복제 및 풀-스루 캐싱 기능도 제공한다. *푸시* 측면은 3강 파이프라인에서, *풀/배포* 측면은 5강부터 연결한다.

## 핵심 정리
- 쿠버네티스는 이미지를 실행한다, 소스코드가 아니다 — 앱을 컨테이너화하는 것이 첫 번째 단계다.
- `Dockerfile`은 레이어 구조의 레시피다. 의존성 설치 단계가 캐시되도록 순서를 지키고, 작고 안전한 이미지를 위해 멀티 스테이지 빌드를 사용하길 권한다.
- ECR은 프라이빗 AWS 레지스트리다. 푸시 흐름은 `get-login-password` → `docker login` → `build` → `tag`(전체 ECR 주소 사용) → `push`다.
- 이미지 태그는 커밋 SHA나 버전으로, `latest`는 절대 사용하지 않는다. 그래야 실행 중인 모든 Pod를 추적할 수 있고 롤백이 신뢰할 수 있다.
- 푸시된 이미지 — 전체 ECR 주소와 태그로 참조되는 — 가 쿠버네티스 Deployment가 소비하는 입력값이다.
