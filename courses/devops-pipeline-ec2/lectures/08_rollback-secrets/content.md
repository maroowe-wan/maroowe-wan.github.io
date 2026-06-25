---
lecture_no: 8
title: 헬스체크, 롤백, 시크릿 관리
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=z7nLsJvEyMY
  - https://www.youtube.com/watch?v=oWrwi1NiViw
  - https://www.youtube.com/watch?v=J9JbzsufemE
---

# 헬스체크, 롤백, 시크릿 관리

## 학습 목표
- 헬스체크로 배포 성공 여부를 확인하고, 실패 시 이전 이미지로 롤백한다.
- 시크릿과 환경변수를 코드에서 분리해 안전하게 주입하는 방법을 익힌다.
- 완성된 파이프라인의 전체 흐름을 파악한다.

## 본문

지금까지의 파이프라인은 새 이미지를 pull하고 컨테이너를 교체한 뒤 배포가 성공했다고 가정한다. 그런데 새 버전이 시작 시 바로 죽어버리면, 멀쩡하게 돌던 앱을 망가진 버전으로 교체하고도 아무도 모르는 상황이 된다. 이번 강의에서는 이 빈틈을 메운다. 헬스체크로 결과를 검증하고, 실패 시 자동으로 롤백하며, 시크릿을 코드 밖에서 관리하는 방법을 다룬다.

### 1단계 — 헬스체크 추가

**헬스체크**는 새로 뜬 컨테이너에 "지금 실제로 요청을 받을 수 있어?"라고 묻는 작은 탐침이다. 고정 `sleep`은 쓰지 않는다. 앱 시작 시간과 경쟁하는 구조라 탐침을 너무 일찍 보내거나, 불필요하게 오래 기다리게 된다. 대신 Docker Compose에게 폴링을 맡긴다. 서비스에 `healthcheck`를 정의하면 된다.

```yaml
services:
  web:
    image: ${IMAGE}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 3s
      retries: 3
```

그리고 `--wait` 옵션으로 배포한다. 이 플래그는 모든 서비스가 **healthy** 상태가 될 때까지 블로킹했다가 `0`으로 종료한다. 어느 서비스라도 끝내 healthy 상태가 되지 않으면 **0이 아닌 값**으로 종료한다. 이 명령 한 줄이 곧 검증 단계다.

```bash
docker compose up -d --wait
```

> `--wait`는 서비스에 `healthcheck`가 정의된 경우에만 제대로 작동한다. `healthcheck`가 없으면 Compose는 컨테이너가 *시작*되기만 기다릴 뿐, *healthy* 상태가 되는지는 확인하지 않는다. `docker compose up -d --wait`의 종료 코드가 배포 성공·실패의 판단 기준이다.

### 2단계 — 실패 시 롤백

헬스체크가 실패하면, 즉 `docker compose up -d --wait`이 0이 아닌 값으로 종료하면 **이전** 정상 이미지를 다시 배포한다. 강의 6에서 모든 이미지를 커밋 SHA로 태그해 두었기 때문에, 과거의 모든 버전이 ECR에 각자의 태그로 남아 있어 언제든 재배포할 수 있다.

까다로운 점은 파이프라인이 마지막으로 검증된 태그를 *기억*해야 한다는 것이다. 방법은 간단하다. **검증이 완료된 배포에서만 해당 태그를 서버 파일에 기록하고, 실패 시 그 파일을 읽어 재배포한다.** 파일은 성공한 배포 이후에만 갱신되므로, 항상 실제로 작동했던 버전을 가리킨다.

```groovy
stage('Deploy & Verify') {
    environment { COMMIT = "${env.GIT_COMMIT}" }   // 새 이미지 태그
    steps {
        sshagent(['ec2-ssh-key']) {
            sh '''
                ssh ec2-user@<EC2_HOST> "
                    export IMAGE=<registry>/myapp:${COMMIT}
                    # --wait가 배포와 검증을 함께 처리한다. 0이 아닌 종료 코드 => 스테이지 실패
                    docker compose up -d --wait
                    # healthy 검증이 완료됐을 때만 실행됨:
                    echo ${COMMIT} > /home/ec2-user/last_good_tag
                "
            '''
        }
    }
    post {
        failure {
            sshagent(['ec2-ssh-key']) {
                sh '''
                    ssh ec2-user@<EC2_HOST> "
                        PREV=\\$(cat /home/ec2-user/last_good_tag 2>/dev/null)
                        if [ -n \\"\\$PREV\\" ]; then
                            export IMAGE=<registry>/myapp:\\$PREV
                            docker compose up -d --wait
                        else
                            echo 'No known-good tag recorded; cannot auto-roll back' >&2
                            exit 1
                        fi
                    "
                '''
            }
        }
    }
}
```

무중단 배포가 필요하다면 **블루-그린**(두 환경을 운영하다가 트래픽을 전환하는 방식)이나 **카나리**(트래픽 일부를 먼저 새 버전으로 보내는 방식)를 쓰기도 한다. EC2 단일 호스트라면 헬스체크+롤백만으로도 대부분의 위험을 충분히 줄일 수 있다.

### 3단계 — 시크릿을 코드 밖에서 관리하기

**시크릿을 저장소에 절대 커밋하지 않는다.** Git에 들어간 내용은 영구적이며, 삭제해도 이력에 남는다. 시크릿은 코드와 분리해 런타임에 주입해야 한다.

**배포 시 시크릿(Jenkins)** — 자격증명 저장소에 보관하고 `withCredentials`로 불러온다. 빌드 로그에서 자동으로 마스킹된다.

```groovy
withCredentials([string(credentialsId: 'db-password', variable: 'DB_PASS')]) {
    sh 'deploy-using $DB_PASS'
}
```

**런타임 시크릿(서버)** — 서버에만 존재하고 git에서 무시되는 `.env` 파일로 컨테이너에 전달한다.

```yaml
services:
  web:
    image: ${IMAGE}
    env_file: /home/ec2-user/app.env
```

각 시크릿은 한 곳에만 둔다. Jenkins는 *배포*에 필요한 시크릿을, 서버는 앱 *실행*에 필요한 시크릿을 각각 보관한다. 도구가 허용하는 모든 곳에서 보호·마스킹 설정을 켜 두자.

### 완성된 파이프라인

1. **GitLab**에 코드를 push한다.
2. **Webhook**이 **Jenkins**를 트리거한다.
3. Jenkins가 코드를 **체크아웃**하고 **빌드·테스트**한다. 오류가 있으면 즉시 멈춘다.
4. 테스트가 통과하면 커밋 SHA로 태그된 **Docker 이미지**를 빌드한다.
5. **ECR**에 인증한 뒤 이미지를 **push**한다.
6. **EC2에 SSH**로 접속해 **docker compose**로 컨테이너를 교체한다.
7. **헬스체크**가 성공을 확인하고, 실패 시 파이프라인이 자동으로 **롤백**한다. 시크릿은 코드 밖에서 안전하게 관리된다.

이 파이프라인을 내 앱에 적용하려면 Dockerfile의 베이스 이미지와 시작 명령, 실제 테스트 명령, ECR 저장소와 EC2 호스트, 그리고 앱의 시크릿만 바꾸면 된다. Dockerfile, Jenkinsfile, 배포 로직은 그대로 가져다 쓸 수 있다.

## 핵심 정리
- 배포는 **헬스체크**가 컨테이너가 실제로 서비스 중임을 확인해야 끝난 것이다. `healthcheck`를 정의하고 `docker compose up -d --wait`으로 배포하라. 고정 `sleep`은 절대 쓰지 않는다.
- **롤백**이 가능한 이유는 모든 이미지가 SHA 태그로 ECR에 보존되기 때문이다. 검증이 완료된 배포 *이후에만* 서버 파일에 태그를 기록하고, `post { failure { ... } }` 블록이 그 태그를 읽어 재배포한다.
- **시크릿을 절대 커밋하지 않는다.** 배포 시 시크릿은 Jenkins `withCredentials`로, 런타임 시크릿은 git에서 무시되는 `.env` 파일로 주입한다. 각 시크릿은 한 곳에만 보관한다.
- 완성된 파이프라인은 `git push`부터 빌드, 테스트, ECR push, 검증된 EC2 배포까지 어떤 앱이든 자동으로 처리한다.

## 출처
- https://www.youtube.com/watch?v=z7nLsJvEyMY
- https://www.youtube.com/watch?v=oWrwi1NiViw
- https://www.youtube.com/watch?v=J9JbzsufemE
