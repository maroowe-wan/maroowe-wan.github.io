---
lecture_no: 6
title: 이미지 레지스트리에 푸시(AWS ECR)
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=lOdrdV0eDrs
  - https://www.youtube.com/watch?v=D8ym8RP1yvo
  - https://www.youtube.com/watch?v=jg9sUceyGaQ
---

# 이미지 레지스트리에 푸시(AWS ECR)

## 학습 목표
- 컨테이너 레지스트리(ECR)가 필요한 이유를 이해한다.
- Jenkins에서 ECR 인증을 처리하고 이미지를 푸시한다.
- Git 커밋 SHA로 이미지를 태깅해 추적성을 확보한다.

## 본문

이전 강의에서 Jenkins가 빌드한 이미지는 Jenkins 에이전트 위에만 존재한다. EC2가 Jenkins 안으로 들어가 이미지를 가져올 수는 없으니, 양쪽이 모두 접근할 수 있는 공유 저장소가 필요하다. **Amazon ECR(Elastic Container Registry)**은 AWS의 프라이빗 Docker 레지스트리다. Jenkins가 이미지를 **push**하면 EC2가 나중에 **pull**해서 실행한다. ECR은 파이프라인의 CI 절반(빌드)과 CD 절반(배포) 사이의 중간 지점이다.

> 레지스트리는 이미지를 *빌드*하는 것과 *실행*하는 것을 분리한다. Jenkins는 서버에 대해 아무것도 알 필요가 없고, 서버는 빌드 도구가 필요 없다. 완성된 불변 이미지를 태그로 pull하기만 하면 된다.

### 1단계 — ECR 저장소 만들기

AWS 콘솔에서 **ECR**을 열고 앱 이름(예: `myapp`)으로 저장소를 만든다. ECR이 다음 형태의 저장소 URI를 제공한다.

```
<aws_account_id>.dkr.ecr.<region>.amazonaws.com/myapp
```

이 전체 URI는 태그가 **아니다**. **레지스트리 호스트**(`<aws_account_id>.dkr.ecr.<region>.amazonaws.com`)와 **저장소 경로/이미지명**(`/myapp`)을 합친 것이다. 태그는 콜론(`:`) 뒤에 붙는 식별자다(`:latest`, `:<커밋-sha>`). Docker는 이미지명에 포함된 **레지스트리 호스트**를 보고 push 대상을 결정한다. 따라서 전체 참조는 `호스트/이미지:태그` 형태, 즉 저장소 URI 뒤에 태그를 붙여 구성한다.

```
<aws_account_id>.dkr.ecr.<region>.amazonaws.com/myapp:<태그>
```

### 2단계 — Jenkins에서 ECR 인증하기

프라이빗 레지스트리에 push하려면 신원을 증명해야 한다. ECR 인증은 두 단계다. AWS 자격증명으로 단기 비밀번호를 얻은 뒤 그것을 `docker login`에 전달한다. AWS 자격증명은 반드시 Jenkins에 저장하고(코드에 하드코딩 금지), 파이프라인에서 아래처럼 사용한다.

```bash
aws ecr get-login-password --region <region> \
  | docker login --username AWS --password-stdin \
    <aws_account_id>.dkr.ecr.<region>.amazonaws.com
```

`get-login-password`는 임시 토큰을 반환하고, `--password-stdin`으로 전달하면 빌드 로그에 토큰이 노출되지 않는다. ECR의 사용자 이름은 항상 문자 그대로 `AWS`다.

> 프로덕션에서는 Jenkins 인스턴스에 **IAM 역할**을 연결해 ECR 권한을 자동으로 부여하는 것이 좋다. 장기 키를 저장하거나 교체할 필요가 없어진다. 학습 목적이라면 정적 키도 괜찮지만 권한 범위를 최소화한다.

### 3단계 — 커밋 SHA로 태깅하고 푸시하기

`latest` 태그는 이미지에 *어떤 코드*가 담겨 있는지 아무것도 알려 주지 않는다. 업계 표준은 **Git 커밋 SHA**로 태깅하는 것이다. 실행 중인 컨테이너에서 정확히 어떤 소스 커밋으로 빌드됐는지 역추적할 수 있는 영구적인 연결 고리가 생긴다. Jenkinsfile에서 짧은 SHA를 캡처해 태그로 쓴다.

```groovy
stage('Push to ECR') {
    steps {
        script {
            def registry = "<aws_account_id>.dkr.ecr.<region>.amazonaws.com"
            def commit = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
            sh """
                aws ecr get-login-password --region <region> \
                  | docker login --username AWS --password-stdin ${registry}
                docker tag myapp:${BUILD_NUMBER} ${registry}/myapp:${commit}
                docker push ${registry}/myapp:${commit}
            """
        }
    }
}
```

`docker tag` 줄을 주목하자. 로컬 이미지(`myapp:${BUILD_NUMBER}`)를 ECR 전체 참조로 재지정한다. 레지스트리 경로를 이미지명에 붙이고(`${registry}/myapp`), 커밋 SHA를 콜론 뒤 태그로 붙이는 것이다. 실전에서는 같은 이미지에 태그 두 개를 함께 push하는 경우가 많다. 추적성과 롤백을 위한 불변 태그 `${commit}`과, 배포 스크립트가 참조할 "이 브랜치의 최신 이미지" 포인터 역할의 유동 태그(예: 브랜치명 `main`)를 함께 쓰는 것이다.

### 4단계 — 푸시 확인하기

ECR 콘솔에서 저장소를 열면 커밋 SHA 태그와 "pushed" 타임스탬프가 달린 이미지를 확인할 수 있다. 방금 빌드·테스트한 산출물이 내구성 있는 프라이빗 레지스트리에 저장돼, 권한 있는 서버라면 어디서든 pull할 준비가 됐다는 증거다.

이제 파이프라인은 서버에서 실행하는 단계만 빼고 모든 것을 처리한다. GitLab 푸시 → 체크아웃 → 빌드 → 테스트 → 이미지 → ECR. 그 이미지를 EC2에 올려 실행하는 것이 다음 강의에서 완성하는 내용이다.

## 핵심 정리
- **ECR**은 Jenkins가 push하고 EC2가 pull하는 공유 저장소로, 이미지 *빌드*와 *실행*을 분리한다.
- ECR 인증은 두 단계다. `aws ecr get-login-password`로 임시 토큰을 얻은 뒤 `docker login`에 전달한다. 프로덕션에서는 정적 키보다 IAM 역할을 선호한다.
- Docker는 이미지명에 포함된 **레지스트리 호스트**를 보고 push 대상을 결정한다. 따라서 이미지 태그는 `<저장소-URI>:<태그>` 형태로 구성한다(URI는 호스트+이미지명, 태그는 콜론 뒤).
- **Git 커밋 SHA**로 태깅해 추적성을 확보하고, 필요에 따라 브랜치명 유동 태그를 추가한다.

## 출처
- https://www.youtube.com/watch?v=lOdrdV0eDrs
- https://www.youtube.com/watch?v=D8ym8RP1yvo
- https://www.youtube.com/watch?v=jg9sUceyGaQ
