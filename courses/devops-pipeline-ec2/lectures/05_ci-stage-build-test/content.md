---
lecture_no: 5
title: CI 스테이지 — 빌드, 테스트, 이미지 생성
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=ESQC5tH5Aow
  - https://www.youtube.com/watch?v=WyH_ihsIaik
  - https://www.youtube.com/watch?v=wBvoerbHWEU
---

# CI 스테이지 — 빌드, 테스트, 이미지 생성

## 학습 목표
- Jenkinsfile에 `build`·`test` 스테이지를 추가해, 문제가 생기는 즉시 파이프라인이 멈추도록 한다.
- 테스트를 통과한 경우에만 Docker 이미지를 빌드한다.
- CI가 자동 품질 게이트 역할을 한다는 개념을 이해한다.

## 본문

파이프라인은 이미 push를 감지해 코드를 체크아웃한다. 이제 CI를 실질적으로 가치 있게 만드는 스테이지를 추가할 차례다: **build**, **test**, **build image**. 핵심 원칙은 **빠른 실패(fail fast)**다. 각 스테이지는 게이트 역할을 하며, 선언형 Jenkinsfile에서는 어떤 단계든 0이 아닌 종료 코드를 반환하면 해당 스테이지가 실패하고 이후 모든 단계가 취소된다. 스테이지는 위에서 아래로 순서대로 실행되므로, 순서만 올바르게 배치하면 테스트를 거치지 않은 코드가 이미지가 되는 상황을 원천 차단할 수 있다.

> 파이프라인을 빨간색으로 만드는 실패한 테스트는 문제가 아니다 — 파이프라인이 가장 중요한 역할을 제대로 수행하고 있다는 신호다.

### 1. 빌드 스테이지 추가

**목적:** 빌드 스테이지는 코드와 의존성을 조립한다. '빌드'의 구체적인 내용은 언어마다 다르지만, 형태는 언제나 같다 — 명령을 실행하고, 0이 아닌 종료 코드가 나오면 스테이지를 실패 처리한다.

```groovy
stage('Build') {
    steps {
        sh 'npm ci'
        sh 'npm run build'
    }
}
```

`sh` 단계는 에이전트에서 셸 명령을 실행한다(Windows 에이전트에서는 `bat` 사용). 둘 중 하나라도 실패하면 파이프라인은 여기서 멈춘다 — 빌드조차 안 된 코드를 테스트할 이유가 없기 때문이다.

**확인:** 파이프라인을 실행해 Jenkins 스테이지 뷰에서 Build 스테이지가 녹색으로 표시되는지 확인한다.

### 2. 테스트 스테이지 추가

**목적:** 버그를 잡아내는 게이트다. 자동화 테스트를 스테이지로 실행하면, 테스트 하나라도 실패할 경우 해당 스테이지가 실패하고 이후 모든 단계가 취소된다.

```groovy
stage('Test') {
    steps {
        sh 'npm test'
    }
}
```

단위 테스트, 통합 테스트, 린트/포맷 검사 모두 여기에 넣을 수 있다. 테스트가 실패하더라도 리포트는 항상 수집되도록 `post { always { ... } }` 블록을 활용하면, 어떤 테스트가 깨졌는지 언제든 확인할 수 있다:

```groovy
stage('Test') {
    steps {
        sh 'npm test'
    }
    post {
        always {
            junit 'reports/**/*.xml'
        }
    }
}
```

**확인:** 의도적으로 실패를 만들어본다(예: 테스트가 단언하는 값을 바꿔본다). 파이프라인이 빨간색으로 바뀌고 이미지 빌드 전에 멈추는지 확인한 뒤, 원래 코드로 되돌린다.

### 3. 이미지 빌드 — 테스트 통과 후에만

**목적:** 실패한 스테이지가 파이프라인을 멈추는 구조 덕분에, 이미지 빌드를 테스트 스테이지 *다음*에 배치하는 것만으로 초록 테스트를 통과한 코드에서만 이미지가 만들어진다는 것을 보장할 수 있다. 여기서 생성된 Docker 이미지는 다음 강의에서 레지스트리에 push하고 배포하게 된다.

```groovy
stage('Build Image') {
    steps {
        sh 'docker build -t myapp:${BUILD_NUMBER} .'
    }
}
```

꼭 지켜야 할 습관이 두 가지 있다. 첫째, **파이프라인 이미지에는 절대 `latest` 태그를 쓰지 않는다** — 유동적인 태그는 어떤 빌드가 어디서 실행 중인지 알 수 없게 만들고, 깔끔한 롤백도 불가능하게 한다. `${BUILD_NUMBER}`처럼 고유하고 추적 가능한 값을 사용한다(Jenkins 내장 변수이며, 다음 강의에서 커밋 SHA로 전환한다). 둘째, 에이전트가 Docker 데몬에 접근할 수 있어야 한다 — 일반적으로 호스트의 Docker 소켓을 Jenkins 컨테이너에 마운트하는 방식을 쓴다.

**확인:** 파이프라인이 녹색으로 완료된 뒤, 호스트에서 `docker images`를 실행해 빌드 번호가 태그로 붙은 `myapp` 이미지가 보이는지 확인한다.

### 지금까지의 전체 파이프라인

```groovy
pipeline {
    agent any
    stages {
        stage('Checkout')    { steps { checkout scm } }
        stage('Build')       { steps { sh 'npm ci'; sh 'npm run build' } }
        stage('Test')        { steps { sh 'npm test' } }
        stage('Build Image') { steps { sh 'docker build -t myapp:${BUILD_NUMBER} .' } }
    }
}
```

위에서 아래로 읽으면 CI의 본질이 그대로 보인다: 모든 push는 체크아웃되고, 빌드되고, 테스트되며 — 이 모든 과정을 통과해야만 — 배포 가능한 이미지로 만들어진다. 이 이미지는 이제 레지스트리에 올릴 준비가 됐으며, 바로 다음 강의에서 그 과정을 다룬다.

## 핵심 정리
- 스테이지 순서는 Build → Test → Build Image로 배치한다. 선언형 파이프라인에서는 0이 아닌 종료 코드가 기본적으로 스테이지를 실패 처리하므로, 이 순서만으로 테스트를 통과한 코드에서만 이미지가 나온다는 것을 보장할 수 있다.
- **빠른 실패(fail fast)** — 스테이지가 실패하면 파이프라인이 멈추고 팀에 알림이 간다.
- 실제 자동화 테스트를 실행하고 리포트를 발행한다(예: `junit`). 모든 빌드에서 결과를 바로 확인할 수 있어야 한다.
- 이미지 태그에는 빌드 번호나 커밋 SHA처럼 고유하고 추적 가능한 값을 사용한다 — 유동적인 `latest`는 절대 쓰지 않는다.

## 출처
- https://www.youtube.com/watch?v=ESQC5tH5Aow
- https://www.youtube.com/watch?v=WyH_ihsIaik
- https://www.youtube.com/watch?v=wBvoerbHWEU
