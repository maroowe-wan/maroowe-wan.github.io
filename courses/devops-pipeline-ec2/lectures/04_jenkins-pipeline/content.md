---
lecture_no: 4
title: Jenkins 설치와 첫 파이프라인(Jenkinsfile)
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=ACG_jYCpYXg
  - https://www.youtube.com/watch?v=IhGtoHY5Wws
  - https://www.youtube.com/watch?v=wBvoerbHWEU
---

# Jenkins 설치와 첫 파이프라인(Jenkinsfile)

## 학습 목표
- Jenkins를 기동하고 파이프라인 잡을 생성한다.
- Pipeline as Code(Jenkinsfile)와 `stage`/`step` 구조를 이해한다.
- GitLab에서 소스를 가져오는 checkout 스테이지를 작성한다.

## 본문

### 트리거에서 실행으로

이전 강의에서 GitLab이 push마다 Jenkins에 *알림*을 보내도록 설정했다. 하지만 지금 Jenkins는 그 알림을 받아도 아무 유용한 일을 하지 않는다. 이번 강의에서 Jenkins에 지시사항을 전달한다. 그리고 그 지시사항을 코드로 작성한다. 애플리케이션 코드와 나란히 같은 저장소에 있는 파일로.

### Jenkins 실행하기

이 컨테이너 중심 강좌에 가장 잘 맞고 가장 빠르게 Jenkins를 띄우는 방법은 Jenkins 자체를 Docker 컨테이너로 실행하는 것이다.

```bash
docker run -d --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

몇 가지 설명을 덧붙인다. `-p 8080:8080`은 브라우저로 접속하는 **웹 UI**를 `localhost:8080`에 노출한다. `-p 50000:50000`은 인바운드 빌드 에이전트가 Jenkins 컨트롤러에 연결할 때 사용하는 **에이전트(JNLP) 포트**다. 나중에 에이전트를 추가할 때 컨테이너를 다시 만들지 않아도 되도록 지금 매핑해 둔다. 두 포트는 서로 다른 역할을 한다는 점에 주의한다. 에이전트 포트를 `8080`에 연결하면 브라우저와 에이전트가 같은 포트를 놓고 충돌한다. 볼륨 마운트 `-v jenkins_home:/var/jenkins_home`은 Jenkins 설정과 잡을 지속시켜 컨테이너가 재시작되어도 사라지지 않게 한다. 볼륨 없이 컨테이너를 중지하면 설정이 모두 날아간다. 처음 실행하면 Jenkins가 로그에 초기 관리자 비밀번호를 출력한다(`docker logs jenkins`). 그 비밀번호로 잠금을 해제하고, 권장 플러그인을 설치하고, 관리자 계정을 만들면 된다.

> Jenkins를 컨테이너로 실행하면 호스트가 깔끔하게 유지되고 설정이 재현 가능해진다. 앱에 적용한 것과 같은 철학이다. 단, 볼륨을 잊지 말자. 볼륨 없이 컨테이너를 재시작하면 공들여 설정한 잡이 모두 사라진다.

### Freestyle 잡과 파이프라인 — 파이프라인이 더 나은 이유

Jenkins는 여러 잡 유형을 제공한다. **Freestyle** 잡은 웹 폼을 클릭해 완전히 설정하는 방식이다. 일회성 작업엔 괜찮지만 설정이 Jenkins 서버 안에만 존재한다. **Pipeline** 잡은 반면 코드로 정의한다.

왜 중요할까? **Pipeline as Code**는 Freestyle 잡이 줄 수 없는 세 가지를 제공하기 때문이다.

- **버전 관리** — 빌드 프로세스가 저장소에 있으므로 애플리케이션 코드처럼 모든 변경이 추적되고, 리뷰할 수 있고, 되돌릴 수 있다.
- **생존성** — Jenkins 서버가 날아가도 파이프라인은 사라지지 않는다. Git에 저장되어 있기 때문이다.
- **기능** — 파이프라인은 조건문, 반복문, 병렬 실행을 지원한다.

이 코드는 저장소 루트에 커밋하는 **Jenkinsfile**이라는 파일에 담긴다.

### Jenkinsfile의 구조

Jenkins는 두 가지 파이프라인 문법을 지원한다. **스크립트 방식**(구형, 유연성 높음)과 **선언적 방식**(신형, 읽기 쉬움). 이 강좌에서는 선언적 방식을 사용한다. 구조는 단순한 중첩 형태다.

- **`pipeline`** — 모든 것을 감싸는 최외부 블록.
- **`agent`** — 파이프라인이 *어디서* 실행될지. `agent any`는 "사용 가능한 Jenkins 워커 어디서나"를 뜻한다.
- **`stages`** — 순서가 있는 스테이지 목록을 담는 컨테이너.
- **`stage`** — 빌드의 논리적 단계에 이름을 붙인 것(예: "Checkout", "Build", "Test"). 스테이지 이름이 Jenkins 스테이지 뷰의 열(column)이 된다.
- **`steps`** — 스테이지 안에서 실행되는 개별 명령.

흐름은 엄격하게 위에서 아래로 진행된다. `pipeline`이 `stages`를 포함하고, `stages`가 각 `stage`를 포함하고, 각 `stage`가 `steps`를 포함한다. 실제로 동작하는 가장 작은 파이프라인은 다음과 같다.

```groovy
pipeline {
    agent any
    stages {
        stage('Hello') {
            steps {
                echo 'Pipeline is alive!'
            }
        }
    }
}
```

Jenkins에서 새 **Pipeline** 잡을 만들고(**New Item → Pipeline**), 인라인 스크립트 박스에 이것을 붙여 넣고 **Build Now**를 클릭하면 스테이지 뷰에 초록색 "Hello" 박스가 나타난다. 실패하면 **Console Output** 링크에 어느 줄에서 문제가 생겼는지 정확히 나온다. 앞으로 모든 문제를 거기서 진단하게 될 테니 익숙해지자.

### GitLab에서 Jenkinsfile을 가져오도록 설정하기

스크립트를 인라인으로 붙여 넣는 것은 Pipeline as Code의 목적을 스스로 무너뜨린다. 실제 설정은 **"Pipeline script from SCM"**이다. 잡 설정의 **Pipeline** 섹션에서 **Pipeline script from SCM**을 선택하고, **Git**을 고른 뒤 GitLab 저장소 URL과 자격증명을 입력하고 브랜치를 설정하고 **Script Path**를 `Jenkinsfile`로 지정한다. 이제 Jenkins가 실행될 때마다 저장소에서 직접 파이프라인 정의를 읽는다. 빌드 프로세스 변경이 곧 커밋이 된다는 뜻이다.

### Checkout 스테이지 작성하기

실제 파이프라인이 맨 처음 해야 할 일은 최신 코드를 가져오는 것이다. 바로 **checkout** 스테이지다. Jenkinsfile을 "SCM에서 읽어오는" 방식으로 설정하면 Jenkins는 내장 스텝 하나로 소스를 가져올 수 있다. 이미 어디서 Jenkinsfile을 로드했는지 알고 있으므로 URL을 다시 지정할 필요도 없다.

```groovy
pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
    }
}
```

`checkout scm`은 이 빌드를 트리거한 정확한 커밋을 클론한다. 다른 저장소를 명시적으로 체크아웃해야 할 때는 다음과 같이 직접 지정할 수 있다.

```groovy
git branch: 'main',
    url: 'https://gitlab.com/<namespace>/<project>.git',
    credentialsId: 'gitlab-creds'
```

이 Jenkinsfile을 커밋하고 푸시하면 이전 강의에서 설정한 웹훅이 빌드를 트리거하고, 이번엔 실제로 코드를 가져오는 파이프라인이 실행된다. 루프가 닫혔다. 푸시가 Jenkins를 트리거하고 Jenkins가 저장소에 정의된 파이프라인의 첫 번째 동작으로 코드를 pull한다. 이제부터는 스테이지를 추가하기만 하면 된다.

## 핵심 정리
- 영구 볼륨을 사용해 Docker 컨테이너로 Jenkins를 실행하면 깔끔하고 재현 가능한 환경이 만들어진다. `8080:8080`은 웹 UI, `50000:50000`은 에이전트(JNLP) 포트다.
- Freestyle 잡보다 **Pipeline as Code(Jenkinsfile)**를 쓴다. 버전 관리가 되고 서버가 날아가도 남아 있으며 실제 로직을 지원한다.
- 선언적 파이프라인은 `pipeline → agent → stages → stage → steps` 형태로 중첩되고, 스테이지 이름이 Jenkins 스테이지 뷰에 표시된다.
- **"Pipeline script from SCM"**을 사용해 Jenkins가 저장소에서 Jenkinsfile을 읽게 하고, `checkout scm`을 첫 번째 스테이지로 만들어 트리거된 커밋을 가져온다.
