---
lecture_no: 8
title: 헬스체크, 롤백, 시크릿/환경변수 관리
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=z7nLsJvEyMY
  - https://www.youtube.com/watch?v=oWrwi1NiViw
  - https://www.youtube.com/watch?v=J9JbzsufemE
---

# 헬스체크, 롤백, 시크릿/환경변수 관리

## 학습 목표
- 헬스체크로 배포 성공 여부를 판단하고 실패 시 이전 이미지로 롤백한다.
- 환경변수와 시크릿을 코드와 분리해 안전하게 주입하는 방법을 익힌다.
- 완성된 파이프라인을 점검하고 내 코드에 적용하는 방법을 정리한다.

## 본문

### 파이프라인에 아직 남은 빈 곳

이전 강의의 파이프라인은 작동한다. 하지만 낙관적이다. 새 이미지를 pull하고 컨테이너를 교체하고 모든 것이 잘 됐다고 가정한다. 새 버전이 시작 시 충돌하거나 응답하지 않으면, 작동하는 앱을 망가진 앱으로 교체했는데 아무도 모른다. 어떤 테스트도 나쁜 배포의 마지막 1% 가능성을 완전히 없애지 못한다. 이번 강의에서 작동하는 파이프라인을 신뢰할 수 있는 파이프라인으로 만드는 안전망을 추가한다.

### 1단계 — 헬스체크: 믿지 말고 검증하라

**헬스체크**는 방금 배포된 앱에 "실제로 살아 있고 서비스 중이야?"라고 묻는 작은 테스트다. 단순한 방법은 몇 초 `sleep`하고 나서 프로브를 보내는 것이지만, 고정 sleep은 **경쟁 조건(race condition)**이다. 너무 짧으면 앱이 준비되기 전에 프로브를 보내(오탐 실패), 너무 길면 모든 배포에서 시간을 낭비한다. 견고한 방법은 앱이 응답하거나 시도 횟수가 소진될 때까지 재시도로 엔드포인트를 **폴링**하는 것이다. 앱이 준비되는 즉시 성공하고, 진짜 제한된 타임아웃 후에만 실패한다.

bash로 그 폴링 루프를 직접 작성할 수도 있지만 Docker Compose가 이미 해준다. 서비스에 컨테이너 수준 `healthcheck`를 정의하면 Compose가 자체 스케줄로 프로브를 실행하고 각 컨테이너의 헬스 상태를 추적한다.

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

`healthcheck`가 정의되면 `docker compose up -d --wait`으로 배포를 시작한다. `--wait` 플래그는 모든 서비스가 **healthy**를 보고할 때까지 블로킹했다가 `0`으로 종료한다. 서비스가 재시도 횟수 안에 healthy 상태가 되지 않으면 **0이 아닌 값**으로 종료한다. 이 명령 하나가 *곧* 헬스체크다. 폴링, 제한된 타임아웃, 통과/실패 판정을 한 번에 처리한다. 따라서 파이프라인은 그 종료 코드만 믿으면 된다.

> `--wait`는 서비스에 `healthcheck`가 정의된 경우에만 작동한다. 없으면 Compose는 컨테이너가 *시작*되기만 기다릴 뿐 *healthy* 상태가 되길 기다리지 않는다. healthcheck를 정의하고 `docker compose up -d --wait`를 실행해 그 종료 코드로 성공/실패를 판정한다. 앱 시작 시간과 경쟁하는 고정 `sleep`은 절대 쓰지 않는다.

### 2단계 — 롤백: 검증된 마지막 버전으로

헬스체크가 실패하면, 즉 `docker compose up -d --wait`이 0이 아닌 값으로 종료하면 어떻게 할까? 롤백한다. **이전** 작동 이미지를 다시 배포한다. 강의 6에서 커밋 SHA로 이미지를 태그한 이유가 바로 이것이다. 과거 모든 버전이 ECR에 각자의 불변 태그로 남아 있어서 "이전 버전"은 항상 `docker compose up` 한 번으로 닿을 수 있다.

까다로운 점은 파이프라인이 마지막으로 작동했던 태그를 *기억*해야 한다는 것이다. `failure` 블록이 그것을 마법처럼 알 수는 없다. 방법은 이것이다. **검증이 완료된 배포에서만 배포된 태그를 서버의 파일에 기록하고, 실패 시 그 파일을 읽어 다시 배포한다.** 그 파일이 "이번 시도 이전에 작동했던 것"의 내구성 있는 기록이다.

아래 순서도는 그 판단을 보여 준다. 배포 명령과 헬스체크가 이제 하나의 단계다. `docker compose up -d --wait`이 `0`으로 종료하면(healthy) 새 버전을 유지하고 태그를 기록한다. 0이 아닌 값으로 종료하면(unhealthy) 저장된 태그를 읽어 다시 배포한다.

```mermaid 한 단계에서 배포와 검증, 0이 아닌 종료 코드 시 자동 롤백
flowchart TD
    Deploy["docker compose up -d --wait\n(배포 + 헬스체크 폴링을 한 단계에서)"] -->|종료 0 (healthy)| Keep["새 버전 유지 + 태그를 last_good에 기록"]
    Deploy -->|0이 아닌 종료 (unhealthy)| Rollback["last_good 태그를 읽어 해당 이미지 재배포"]
    Rollback --> Restored["마지막 정상 버전 복원 완료"]
```

작동하는 로직은 다음과 같다. `docker compose up -d --wait`이 배포이자 검증이다. 성공으로 반환되면 스크립트가 계속 진행되어 새 태그를 기록하고, 실패하면 셸 명령이 실패하고 스테이지가 실패하며 `post { failure }` 블록이 저장된 태그를 읽어 다시 배포한다.

```groovy
stage('Deploy & Verify') {
    environment { COMMIT = "${env.GIT_COMMIT}" }   // 새 이미지 태그
    steps {
        sshagent(['ec2-ssh-key']) {
            sh '''
                ssh ec2-user@<EC2_HOST> "
                    export IMAGE=<registry>/myapp:${COMMIT}
                    # --wait가 헬스체크 통과까지 블로킹했다가 종료한다
                    # 실패하면 ssh가 0이 아닌 값을 반환해 스테이지가 실패하고
                    # 아래 post { failure } 블록이 롤백을 처리한다.
                    docker compose up -d --wait
                    # healthy한 배포가 검증됐을 때만 실행됨:
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
                            echo 'No known-good tag recorded yet; cannot auto-roll back' >&2
                            exit 1
                        fi
                    "
                '''
            }
        }
    }
}
```

메커니즘은 자기 교정적이다. 태그는 배포가 healthy하게 검증된 **후에만** 기록되므로 `last_good_tag`는 항상 진짜 작동했던 버전을 가리킨다. 실패한 배포는 그것을 절대 덮어쓰지 않아 롤백이 항상 진짜 마지막 정상 이미지를 대상으로 한다. (서버에 파일을 유지하지 않으려면 현재 실행 중인 이미지를 교체 전에 `docker inspect`로 조회하거나 Jenkins 빌드 아티팩트로 태그를 저장하는 방법도 있다.)

진정한 무중단 전환을 위해 팀들은 **블루-그린 배포**(두 개의 동일 환경을 운영하고 트래픽을 이전 "블루"에서 새 "그린"으로 전환해 필요 시 즉시 되돌리는 방식)나 **카나리 배포**(처음에 트래픽의 일부만 새 버전에 라우팅하고 100%로 가기 전에 지켜보는 방식)를 사용한다. 이것들은 다음 단계의 전략이다. EC2 단일 호스트에서는 빠른 헬스체크+롤백만으로 대부분의 위험을 제거할 수 있고, `docker compose up -d`의 롤링 교체가 가용성이 끊기는 시간을 최소화한다.

### 3단계 — 코드에서 시크릿 분리하기

앱에는 민감한 값이 필요하다. 데이터베이스 비밀번호, API 키, ECR 레지스트리 주소. 철칙은 **절대 시크릿을 저장소에 커밋하지 않는다는 것이다.** Git에 있는 모든 것은 영구적이고 접근 권한이 있는 모든 사람에게 보인다. "삭제"한 뒤에도 기록에서는 남아 있다.

시크릿을 코드와 분리하고 런타임에 주입한다.

- **Jenkins에서** — 내장 자격증명 저장소에 시크릿을 저장하고 `withCredentials`로 가져온다. 빌드 로그에서 시크릿이 마스킹된다.

  ```groovy
  withCredentials([string(credentialsId: 'db-password', variable: 'DB_PASS')]) {
      sh 'deploy-using $DB_PASS'
  }
  ```

- **컨테이너 수준에서** — 서버에 존재하고 *git에서 무시*되며 절대 커밋되지 않는 `.env` 파일에서 소싱한 환경변수를 Compose로 전달한다.

  ```yaml
  services:
    web:
      image: ${IMAGE}
      env_file: /home/ec2-user/app.env
  ```

같은 시크릿이 두 곳에 있어서는 안 된다. Jenkins는 *배포*에 필요한 시크릿을 보관하고, 서버는 앱이 *실행*될 때 필요한 시크릿을 보관한다. 도구가 허용하는 모든 곳에서 시크릿을 보호·마스킹 처리해 로그에 누출되지 않게 한다.

### 완성된 파이프라인, 처음부터 끝까지

지금까지 8개 강의에 걸쳐 조립한 것을 돌아보자. 전체 흐름은 다음과 같다.

1. **GitLab**에 코드를 push한다.
2. **Webhook**이 **Jenkins**를 트리거한다.
3. Jenkins가 코드를 **체크아웃**하고 **빌드·테스트**한다. 뭔가 잘못되면 즉시 멈춘다.
4. 테스트가 통과하면 Jenkins가 커밋 SHA로 태그된 **Docker 이미지**를 빌드한다.
5. Jenkins가 **AWS ECR**에 인증하고 이미지를 **push**한다.
6. Jenkins가 **EC2에 SSH**로 접속해 이미지를 pull하고 **docker compose**로 컨테이너를 교체한다.
7. **헬스체크**가 성공을 확인한다. 실패하면 파이프라인이 이전 이미지로 **롤백**한다. 시크릿은 코드 밖에 있고 안전하게 주입된다.

### 내 코드에 적용하기

예제 앱은 의도적으로 범용으로 만들었지만 이 파이프라인은 그렇지 않다. 내 프로젝트에 맞게 바꾸려면 Dockerfile의 베이스 이미지와 시작 명령을 내 언어의 것으로 교체하고, 실제 테스트 명령으로 바꾸고, ECR 저장소와 EC2 호스트를 내 인프라로 바꾸고, 앱의 실제 시크릿을 자격증명 저장소와 `.env` 파일에 등록하면 된다. Dockerfile, Jenkinsfile, 배포 로직이 이전 가능한 기술이다. 나머지는 설정일 뿐이다. 이제 `git push` 한 번으로 검증되고 복구 가능한 live 배포까지 어떤 애플리케이션이든 자동으로 배포하는 재현 가능한 청사진을 갖게 됐다.

## 핵심 정리
- 배포는 **헬스체크**가 새 컨테이너가 실제로 서비스 중임을 증명할 때 완료된다. 컨테이너 `healthcheck`를 정의하고 `docker compose up -d --wait`을 실행하면 프로브를 폴링하고 앱이 healthy 상태가 되지 않으면 0이 아닌 값으로 종료한다. 고정 `sleep`은 절대 쓰지 않는다.
- **롤백**은 모든 이미지가 ECR에 커밋 SHA로 태그되어 유지되기 때문에 가능하다. 검증이 완료된 배포 *후에만* 서버 파일에 태그를 기록하고, `post { failure { ... } }` 블록이 그 파일을 읽어 마지막 정상 태그를 다시 배포한다.
- **시크릿을 절대 커밋하지 않는다.** 배포 시 시크릿은 Jenkins 자격증명(`withCredentials`)으로, 런타임 시크릿은 git에서 무시되는 `.env`로 런타임에 주입한다. 각 시크릿을 정확히 한 곳에만 보관한다.
- 완성된 파이프라인은 `git push`에서 빌드, 테스트, ECR 이미지 push, 검증된 EC2 배포까지 어떤 앱이든 자동으로 처리한다. Dockerfile, Jenkinsfile, 배포 로직은 내 프로젝트에 그대로 적용할 수 있다.
