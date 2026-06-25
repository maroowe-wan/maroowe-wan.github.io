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
- Jenkinsfile과 `stage`/`step` 구조를 이해한다.
- GitLab에서 소스를 가져오는 checkout 스테이지를 작성한다.

## 본문

이전 강의에서 GitLab이 push마다 Jenkins에 알림을 보내도록 설정했다. 하지만 Jenkins는 그 알림을 받아도 아직 아무것도 하지 않는다. 이번에는 Jenkins에 지시사항을 전달한다 — 저장소 안에 **Jenkinsfile**이라는 파일로 코드를 작성하는 방식으로.

### 1. Jenkins 실행하기

**무엇을·왜:** Jenkins 자체를 Docker 컨테이너로 실행해 설정을 깔끔하고 재현 가능하게 유지한다.

```bash
docker run -d --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

- `8080` → 웹 UI(브라우저로 접속), `50000` → 빌드 에이전트(JNLP) 포트. 두 포트는 용도가 다르므로 반드시 구분한다.
- `-v jenkins_home:/var/jenkins_home` 볼륨은 잡과 설정을 컨테이너 재시작 후에도 보존한다 — 빠뜨리면 모든 것이 사라진다.

**확인:** 로그에서 초기 관리자 비밀번호를 복사해 `http://<호스트>:8080`의 잠금 해제 화면에 입력한다.

```bash
docker logs jenkins   # 잠금 해제 비밀번호 복사
```

권장 플러그인을 설치하고 관리자 계정을 만들면 준비 완료다.

> `jenkins_home` 볼륨은 반드시 유지한다. 없으면 컨테이너를 재시작할 때마다 설정한 잡이 모두 날아간다.

### 2. Pipeline 잡 만들기 (Freestyle 말고)

**무엇을·왜:** Jenkins에는 Freestyle 잡(웹 폼으로 설정, 서버 안에만 저장)과 Pipeline 잡(코드로 정의)이 있다. **Pipeline**을 쓴다 — 버전 관리가 되고 서버가 날아가도 남아 있으며 조건문·반복문·병렬 스테이지를 지원한다.

Jenkins에서 **New Item → 이름 입력 → Pipeline → OK** 순으로 선택한다.

### 3. 동작하는 가장 작은 파이프라인

**무엇을·왜:** 선언적 파이프라인은 `pipeline → agent → stages → stage → steps` 형태로 중첩된다. `agent any`는 사용 가능한 워커라면 어디서든 실행하겠다는 뜻이고, 각 `stage`는 스테이지 뷰의 열(column)이 된다.

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

**확인:** 인라인 Pipeline 스크립트 박스에 붙여 넣고 **Build Now**를 클릭한다. 스테이지 뷰에 초록색 "Hello" 열이 보이면 성공이다. 실패하면 **Console Output**에서 어느 줄이 문제인지 바로 확인할 수 있다.

### 4. GitLab에서 Jenkinsfile 읽어오기

**무엇을·왜:** 스크립트를 인라인으로 붙여 넣으면 Pipeline as Code의 목적이 무너진다. Jenkins가 저장소에서 직접 Jenkinsfile을 읽도록 설정하면 빌드 프로세스 변경이 곧 커밋이 된다.

잡 설정의 **Pipeline** 섹션에서 다음과 같이 지정한다.
- Definition: **Pipeline script from SCM**
- SCM: **Git**
- Repository URL + credentials: GitLab 저장소 주소와 자격증명
- Branch: 예) `main`
- Script Path: `Jenkinsfile`

### 5. Checkout 스테이지 작성하기

**무엇을·왜:** 파이프라인이 맨 처음 해야 할 일은 최신 코드를 가져오는 것이다 — 바로 **checkout** 스테이지다. SCM에서 읽어오는 방식으로 설정했으면 Jenkins는 이미 소스 위치를 알고 있으므로, 내장 스텝 하나로 트리거된 정확한 커밋을 클론할 수 있다. 이 파일을 `Jenkinsfile`이라는 이름으로 저장소 루트에 커밋한다.

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

다른 저장소를 명시적으로 체크아웃해야 할 때는 다음처럼 직접 지정한다.

```groovy
git branch: 'main',
    url: 'https://gitlab.com/<namespace>/<project>.git',
    credentialsId: 'gitlab-creds'
```

**확인:** Jenkinsfile을 푸시한다. 이전 강의에서 설정한 웹훅이 빌드를 트리거하고, 이번에는 실제로 코드를 클론하는 파이프라인이 실행된다. 스테이지 뷰에 초록색 Checkout 열이 보이면 루프가 완성된 것이다. push → 트리거 → checkout. 이후 스테이지는 여기에 이어 붙이기만 하면 된다.

## 핵심 정리
- 영구 `jenkins_home` 볼륨을 사용해 Docker 컨테이너로 Jenkins를 실행한다. `8080`은 웹 UI, `50000`은 에이전트 포트다.
- Freestyle 대신 **Pipeline**을 선택한다 — 코드로 관리되고, 버전이 추적되며, 서버에 종속되지 않는다.
- 선언적 문법은 `pipeline → agent → stages → stage → steps` 형태로 중첩된다.
- **Pipeline script from SCM**으로 설정하고 `checkout scm`을 첫 번째 스테이지로 만들어 트리거된 커밋을 가져온다.

## 출처
- https://www.youtube.com/watch?v=ACG_jYCpYXg
- https://www.youtube.com/watch?v=IhGtoHY5Wws
- https://www.youtube.com/watch?v=wBvoerbHWEU
