---
lecture_no: 2
title: "앱 컨테이너화와 Amazon ECR 준비"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=lOdrdV0eDrs
  - https://www.youtube.com/watch?v=Hv5UcBYseus
  - https://www.youtube.com/watch?v=OihC0CS43AI
---

# 앱 컨테이너화와 Amazon ECR 준비

## 학습 목표
- `Dockerfile`로 웹 애플리케이션을 컨테이너 이미지로 패키징한다.
- Amazon ECR 리포지토리를 생성하고 이미지를 푸시한다.
- 푸시한 이미지가 모든 쿠버네티스 배포의 *입력값*임을 이해한다.

## 본문

쿠버네티스는 소스 코드가 아닌 **컨테이너 이미지**를 실행한다. 따라서 가장 먼저 할 일은 앱을 이미지로 만들어, EKS가 가져올 수 있는 곳에 저장하는 것이다. 그 저장소가 바로 **Amazon ECR(Elastic Container Registry)** — AWS의 프라이빗 Docker 레지스트리로, IAM으로 접근을 제어한다. 컨테이너는 언어에 무관하므로, 아래 방법은 Node, Go, Python, Java 어느 앱이든 동일하게 적용된다.

### 1. Dockerfile 작성

`Dockerfile`은 일반 텍스트로 된 레시피로, 각 명령이 레이어 하나를 만든다. 핵심은 **의존성 매니페스트를 소스보다 먼저 복사**하는 것이다. 그러면 코드만 바뀌었을 때 Docker가 의존성 설치 레이어를 캐시해 재설치를 건너뛴다.

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

> 프로덕션에서는 **멀티 스테이지 빌드**를 권한다. 첫 번째 스테이지에서 앱을 컴파일하고, 두 번째 경량 스테이지(예: Google의 'distroless')에서 완성된 바이너리만 복사한다. 이미지가 작아지고 공격 표면도 줄어든다.

### 2. 로컬에서 빌드 및 테스트

AWS를 연동하기 전에 이미지가 제대로 동작하는지 먼저 확인한다.

```bash
docker build -t my-app:dev .
docker run -p 3000:3000 my-app:dev
# 확인: http://localhost:3000 을 브라우저나 curl로 열어 응답을 검증한다.
```

### 3. ECR 리포지토리 생성

하나의 리포지토리에 동일한 서비스의 여러 태그 버전을 보관한다. 보통 서비스당 리포지토리를 하나 만든다. 콘솔에서 생성하려면 "ECR" 검색 후 *리포지토리 생성*을 누른다. CLI로는 다음과 같이 실행한다.

```bash
aws ecr create-repository \
  --repository-name my-app \
  --region us-east-1
# 확인: repositoryUri가 반환된다.
# 형태: <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app
```

### 4. 인증, 태그, 푸시

ECR은 프라이빗이므로 Docker가 먼저 로그인해야 한다(토큰은 단기 유효). ECR 콘솔의 *푸시 명령 보기*에서도 동일한 명령을 확인할 수 있다. 태그는 `latest` 대신 **Git 커밋 SHA**를 사용한다.

```bash
# 로그인
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 빌드 후 전체 ECR 주소와 커밋 SHA로 태그
docker build -t my-app .
docker tag my-app:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)

# 푸시
docker push \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)
```

이미지 이름의 형태는 `<account-id>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>` — 레지스트리, 리포지토리, 태그 순이다. 푸시 결과는 콘솔의 리포지토리 화면에서 확인하거나, CLI로 다음과 같이 조회한다.

```bash
aws ecr list-images --repository-name my-app --region us-east-1
```

### `latest` 대신 커밋으로 태그해야 하는 이유

`latest`는 움직이는 레이블이다. 다음 푸시가 조용히 덮어쓰므로, 실행 중인 클러스터를 봐도 *어떤* 코드가 올라가 있는지 알 수 없고 롤백은 추측에 의존하게 된다. 반면 커밋 SHA나 `v1.4.2` 같은 시맨틱 버전은 **불변이고 추적 가능**하다. `a1b9f3c`는 항상 그 코드만을 가리킨다. 이것이 7강 롤백을 신뢰할 수 있게 만드는 근거다.

### 쿠버네티스와의 연결

4강에서 작성할 Deployment 매니페스트는 바로 이 이미지를 참조한다.

```yaml
        image: <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

이것이 핵심이다. 여기서 빌드하고 푸시한 이미지가 배포의 **입력값**이 된다. 파이프라인의 역할은 새 이미지를 계속 만들고 이 한 줄을 갱신하는 것이다. 푸시 측은 3강 파이프라인에서, 풀/배포 측은 5강부터 연결한다 — 그 시점에 클러스터 노드가 ECR에서 이미지를 가져올 수 있도록 IAM 권한도 부여하게 된다.

## 핵심 정리
- 쿠버네티스는 이미지를 실행한다, 소스 코드가 아니다 — 컨테이너화가 첫 번째 단계다.
- Dockerfile 단계 순서를 지켜 의존성 설치가 캐시되도록 하고, 멀티 스테이지 빌드로 이미지를 최소화한다.
- 푸시 흐름: `get-login-password` → `docker login` → `build` → `tag`(전체 ECR 주소) → `push`.
- 태그는 커밋 SHA나 버전으로 — `latest`는 사용하지 않는다. 그래야 모든 Pod를 추적할 수 있다.
- 푸시된 이미지(전체 ECR 주소 + 태그)가 Deployment에서 소비하는 입력값이다.
