---
lecture_no: 3
title: "GitLab + Jenkins 파이프라인 구성"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=361bfIvXMBI
  - https://www.youtube.com/watch?v=rcZoPygiI8o
---

# GitLab + Jenkins 파이프라인 구성

## 학습 목표
- GitLab 웹훅으로 Jenkins 파이프라인을 자동으로 트리거한다.
- checkout, test, build, 이미지 푸시 스테이지를 갖춘 `Jenkinsfile`을 작성한다.
- GitLab에 푸시하면 ECR에 컨테이너 이미지가 자동으로 생성되는 CI 골격을 완성한다.

## 본문

이미지를 직접 빌드해서 ECR에 푸시하는 것은 한 번쯤은 할 수 있다. 하지만 커밋마다 반복하면 금방 고통스러워진다. 이 강의에서는 그 과정을 자동화한다. 개발자가 GitLab에 푸시하면 Jenkins가 자동으로 깨어나, 테스트하고, 빌드하고, ECR에 이미지를 푸시한다 — 사람이 개입하지 않아도. 이것이 **CI 골격**(지속적 통합)이다. EKS 배포 단계는 6강에서 추가한다.

두 역할을 명확히 구분해야 한다. **GitLab**은 소스 호스트로, 저장소를 관리하고 푸시가 발생하면 이벤트를 발생시킨다. **Jenkins**는 엔진으로, 그 이벤트를 수신하고 `Jenkinsfile`에 정의된 작업을 실행한다.

### 1단계 — 웹훅으로 GitLab과 Jenkins 연결

**웹훅**은 특정 이벤트(예: `main` 브랜치에 푸시)가 발생할 때 GitLab이 지정된 URL로 보내는 HTTP 요청이다. 그 URL을 Jenkins로 향하게 하면 푸시가 곧바로 빌드를 트리거한다. 설정할 부분은 양쪽 모두에 있다.

**Jenkins 쪽**에서는 Pipeline 잡을 만들고, 필요하면 GitLab 플러그인을 설치한 뒤, GitLab 웹훅 트리거를 활성화해 잡이 웹훅 요청을 수신하도록 설정한다. Jenkins는 다음 경로에서 웹훅 POST 요청을 받는다.

```
http://<jenkins-host>:8080/project/<job-name>
```

**GitLab 쪽**에서는 프로젝트의 *설정 → 웹훅*으로 이동해 Jenkins URL을 붙여넣고, **Push events**와 **Merge request events**를 선택한다. 저장한다.

**검증:** 웹훅을 믿기 전에, Jenkins에서 **지금 빌드**를 한 번 눌러 잡이 정상적으로 실행되는지 먼저 확인하라. 그다음 GitLab의 **Test** 버튼으로 샘플 이벤트를 발송해 Jenkins가 응답하는지 검증한다.

> 수동 빌드를 먼저 통과시킨 다음 트리거를 검증하라. "파이프라인이 동작하는가?"와 "웹훅이 제대로 발화하는가?"를 동시에 디버깅하면 두 배로 복잡해진다.

Jenkins가 클라우드 VM에서 실행된다면, 보안 그룹에서 Jenkins 포트(기본 8080)의 인바운드 트래픽을 허용해야 한다. 그렇지 않으면 웹훅 전달이 연결 오류로 실패한다.

### 2단계 — Jenkinsfile로 파이프라인 정의

Jenkins UI를 클릭해 빌드 단계를 구성하는 대신, 저장소에 **`Jenkinsfile`**을 두고 그 안에 작성한다. 이것이 "파이프라인 as 코드"다 — 빌드 프로세스가 버전 관리되고, 리뷰 가능하며, 프로젝트와 함께 이동한다. 선언형 `Jenkinsfile`은 논리적 단계인 **스테이지**로 구성된다.

```groovy
pipeline {
    agent any

    environment {
        AWS_REGION = 'us-east-1'
        ACCOUNT_ID = '111122223333'
        ECR_REPO   = 'my-app'
        REGISTRY   = "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        IMAGE_TAG  = "${env.GIT_COMMIT.take(7)}"   // 짧은 커밋 SHA, 'latest' 아님
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm   // GitLab이 막 푸시한 코드를 가져온다
            }
        }

        stage('Test') {
            steps {
                sh 'npm install && npm test'   // 테스트 실패 시 빠르게 종료
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build -t ${REGISTRY}/${ECR_REPO}:${IMAGE_TAG} ."
            }
        }

        stage('Push to ECR') {
            steps {
                sh """
                  aws ecr get-login-password --region ${AWS_REGION} \
                    | docker login --username AWS --password-stdin ${REGISTRY}
                  docker push ${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
                """
            }
        }
    }
}
```

각 스테이지가 하는 일:

- **Checkout**은 빌드를 트리거한 정확한 커밋을 가져온다. Jenkins는 해당 커밋의 SHA를 `GIT_COMMIT`으로 노출하며, 이를 줄여 이미지 태그로 재사용한다 — `latest`를 쓰지 않으므로 모든 아티팩트를 추적할 수 있다.
- **Test**는 테스트 수트를 빌드 *전에* 실행한다. 테스트가 실패하면 파이프라인이 일찍 종료되어, 어차피 배포하지 않을 이미지를 빌드하는 데 시간을 낭비하지 않는다.
- **Build Image**는 `docker build`를 실행하며, 전체 ECR 주소와 커밋 SHA로 태깅한다.
- **Push to ECR**은 `get-login-password`로 ECR에 인증하고 이미지를 푸시한다.

**검증:** 사소한 변경(예: `test.txt` 추가)을 커밋하고 Jenkins가 *대기 중* 에서 *성공*으로 전환되는 것을 확인한다. 그런 다음 ECR 리포지토리에 커밋 태그가 붙은 새 이미지가 나타났는지 확인한다.

### 3단계 — AWS 자격증명을 안전하게 제공하기

Push 스테이지는 ECR과 통신할 권한이 필요하다. 액세스 키를 `Jenkinsfile`에 직접 붙여넣으면 **절대 안 된다** — 시크릿이 저장소에 그대로 유출된다. 대신:

- Jenkins가 EC2 인스턴스에서 실행된다면, 해당 인스턴스에 ECR 푸시/풀 권한이 있는 **IAM 역할**을 연결한다. AWS CLI가 정적 키 없이 자동으로 역할을 감지한다.
- 그렇지 않다면 **Jenkins Credentials**에 자격증명을 저장하고 잡에 주입한다.

IAM 권한은 최소로 유지하라. 인증 토큰 발급과 푸시/풀 — 가능하면 계정 전체가 아닌 이 리포지토리만으로 범위를 좁히는 것이 이상적이다. "머신에 IAM 아이덴티티가 있다"는 이 개념은 5강에서 Jenkins가 EKS 자체에 인증할 때도 그대로 적용된다.

### 지금까지 만든 것

CI 골격이 완성됐다. **GitLab에 푸시 → 웹훅 → Jenkins가 체크아웃, 테스트, 빌드, 커밋 태그 이미지를 ECR에 푸시 — 완전 자동으로.** 모든 커밋이 레지스트리에 추적 가능하고 배포 가능한 아티팩트를 남긴다.

아직 빠진 것은 *전달(delivery)* 단계다. EKS에 새 이미지를 실행하라고 알리는 것이 없다. 이를 위해서는 매니페스트(4강)와 Jenkins가 클러스터에 인증하는 방법(5강)이 필요하고, 그 다음 6강에서 최종 배포 스테이지를 추가한다.

## 핵심 정리
- GitLab 웹훅은 `git push`를 자동 Jenkins 빌드로 전환한다. Jenkins에서 트리거를 설정하고 GitLab에 웹훅 URL을 등록한 뒤 양쪽을 테스트하라.
- `Jenkinsfile`은 파이프라인을 버전화된 코드로 정의하며 스테이지로 구성된다: Checkout → Test → Build Image → Push to ECR.
- 커밋 SHA(`GIT_COMMIT`)를 이미지 태그로 재사용해 모든 아티팩트를 추적 가능하게 하고, 빌드 전에 테스트를 실행해 실패 시 빠르게 종료한다.
- `Jenkinsfile`에 AWS 키를 하드코딩하지 말라. Jenkins 호스트의 IAM 역할이나 Jenkins 관리 자격증명을 사용하라.
- 결과물은 완성된 CI 골격이다 — EKS 배포 단계는 5강과 6강에서 추가된다.
