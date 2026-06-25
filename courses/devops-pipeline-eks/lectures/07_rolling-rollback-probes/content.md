---
lecture_no: 7
title: "롤링 업데이트, 롤백, 헬스체크"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=fqfieWP1jY4
  - https://www.youtube.com/watch?v=lxc4EXZOOvE
  - https://www.youtube.com/watch?v=wWA9JgAvuqw
---

# 롤링 업데이트, 롤백, 헬스체크

## 학습 목표
- readiness/liveness 프로브를 설정해 롤아웃이 실제 헬스 상태를 기준으로 진행되도록 한다.
- `kubectl rollout`으로 Deployment를 조회·제어하고, 명령 한 줄로 롤백한다.
- 무중단 롤링 배포를 직접 검증하고, 깨진 릴리스에서 복구한다.

## 본문

파이프라인이 이제 자동으로 배포한다. 이 강의는 그 배포를 **안전**하게 만드는 방법을 다룬다. 버전을 점진적으로 교체해 다운타임을 없애고, 쿠버네티스가 정상 Pod와 비정상 Pod를 구별하게 하며, 잘못된 릴리스를 몇 초 만에 되돌린다. 아래 네 가지 태스크를 순서대로 진행한다.

### 태스크 1 — 롤링 업데이트 속도 조정

**무엇을, 왜.** Deployment의 이미지를 변경하면 기본적으로 `RollingUpdate` 전략이 실행된다. 쿠버네티스는 새 Pod를 올리고, 준비 상태가 되길 기다린 뒤, 구 Pod를 내린다. 그 동안 항상 작동하는 Pod 집합이 트래픽을 받는다. 두 개의 조절 값이 교체 속도를 제어하며, 작게 설정할수록 느리고 안전한 롤아웃이 된다.

- **`maxSurge`** — 원하는 Pod 수를 *초과해* 허용하는 추가 Pod 수 (위로 얼마나 올라갈 수 있는가).
- **`maxUnavailable`** — 원하는 Pod 수 *아래로* 허용하는 미가용 Pod 수 (아래로 얼마나 내려갈 수 있는가).

둘 다 기본값은 `25%`다. 레플리카 4개와 기본값 기준으로, 최대 1개 Pod가 내려가고(3개는 계속 서비스) 전체 Pod는 5개를 넘지 않는다.

```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
```

> 기억법: **`maxSurge` = 위로 얼마나 올라갈 수 있는가; `maxUnavailable` = 아래로 얼마나 내려갈 수 있는가.**

**확인.** 적용 후 Pod가 용량을 유지하면서 전환되는지 확인한다.

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/my-app   # 완료 또는 멈춤까지 블로킹
```

### 태스크 2 — readiness/liveness 프로브 추가

**무엇을, 왜.** 롤링 업데이트가 안전하려면 쿠버네티스가 새 Pod에 트래픽을 보내기 *전에* 실제로 정상인지 판단할 수 있어야 한다. 이 판단을 프로브가 담당한다. 혼동하면 안 되는 두 가지는 다음과 같다.

- **Readiness 프로브 = 트래픽 제어.** 실패 시 Pod가 **Service 엔드포인트에서 제거**된다(종료되지 않음). 다시 통과할 때까지 새 요청이 전달되지 않는다. 이것이 롤아웃의 게이트 역할을 한다. 새 Pod는 준비 상태가 된 후(웜업 완료, DB 연결 성공 등)에만 사용자 트래픽을 받는다.
- **Liveness 프로브 = 재시작 제어.** 실패 시 쿠버네티스가 **컨테이너를 종료하고 재시작**한다. 데드락이나 멈췄지만 충돌하지 않은 프로세스 상황에서 복구할 때 쓴다.

> 둘을 바꾸면 전형적이고 고통스러운 버그로 이어진다. 너무 공격적인 *liveness* 프로브는 단지 웜업이 느린 Pod를 재시작하고, 부하 상황에서 클러스터 전체의 연쇄 재시작으로 번질 수 있다.

```yaml
        livenessProbe:
          httpGet:
            path: /healthz       # 앱이 살아있는가? 아니면 재시작
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready         # 트래픽 받을 준비가 됐는가? 아니면 트래픽 보류
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

`initialDelaySeconds`는 첫 번째 체크 전 대기 시간이고, `periodSeconds`는 반복 주기다. (프로브는 `tcpSocket`이나 명령 실행(`exec`) 방식도 쓸 수 있다.) 부팅이 느린 앱에는 **startup 프로브**를 추가하면 되는데, 부팅이 끝날 때까지 나머지 두 프로브를 유예시킨다.

> readiness 프로브가 없으면 쿠버네티스는 컨테이너가 시작하는 순간 Pod가 준비됐다고 가정하고 즉시 트래픽을 보낸다. 그러면 매 배포마다 사용자가 오류를 경험하게 된다.

**확인.** Pod가 실제로 준비될 때까지 엔드포인트가 빈 상태여야 한다.

```bash
kubectl apply -f deployment.yaml
kubectl get endpoints my-app -w   # readiness 통과 후에만 IP가 나타남
```

### 태스크 3 — 롤아웃 조회 및 제어

**무엇을, 왜.** `kubectl rollout`은 진행 중인 업데이트를 실시간으로 확인하고 제어하는 명령이다(Deployment, StatefulSet, DaemonSet에 모두 동작한다). 롤아웃 도중 문제가 발견되면 `pause`/`resume`으로 멈추고 확인할 수 있다.

```bash
kubectl rollout status  deployment/my-app   # 성공/실패까지 블로킹 (파이프라인에서 사용)
kubectl rollout history deployment/my-app   # 과거 리비전 목록
kubectl rollout pause   deployment/my-app   # 롤아웃 중간에 일시정지
kubectl rollout resume  deployment/my-app   # 재개
```

### 태스크 4 — 잘못된 릴리스 롤백

**무엇을, 왜.** 쿠버네티스는 리비전 기록을 보관하므로 잘못된 릴리스는 명령 하나로 되돌릴 수 있다. 자동화된 배포를 프로덕션에서 믿고 쓸 수 있게 해주는 안전망이다.

```bash
kubectl rollout undo deployment/my-app                  # 이전 리비전으로
kubectl rollout undo deployment/my-app --to-revision=3  # 특정 리비전으로
```

여기서 앞의 모든 개념이 하나로 연결된다. 존재하지 않는 이미지 태그(혹은 시작하자마자 충돌하는 이미지)를 배포해 보자.

```bash
kubectl set image deployment/my-app app=my-app:does-not-exist
kubectl rollout status deployment/my-app   # "waiting" 보고 — 멈춘 상태
```

새 Pod가 readiness를 통과하지 못하므로 `maxUnavailable` 제약 때문에 쿠버네티스는 정상적인 구 Pod를 종료하지 않는다. 구 버전이 계속 전체 트래픽을 처리한다. 다음 명령으로 롤백한다.

```bash
kubectl rollout undo deployment/my-app     # 구 버전 복원; 사용자는 아무것도 눈치채지 못함
```

### 파이프라인에 통합하기

매니페스트에 프로브를 설정해 롤아웃이 실제 헬스 상태를 기준으로 게이팅되도록 하고, Jenkins에서 `kubectl rollout status`를 실행해 롤아웃이 멈추면 빌드가 실패하게 한다. `kubectl rollout undo`는 온콜 엔지니어가 수동으로 실행하거나 장애 시 자동 실행되도록 준비해 둔다. (Git에 revert를 올리고 GitOps 컨트롤러가 처리하는 방식이 더 성숙한 경로지만, 내장 `rollout undo`가 가장 직접적인 도구다.)

## 핵심 정리
- 롤링 업데이트는 Pod를 점진적으로 교체해 무중단을 보장한다. `maxSurge`는 원하는 수 위로 얼마나 올라갈 수 있는지, `maxUnavailable`은 아래로 얼마나 내려갈 수 있는지를 제한한다(둘 다 기본값 25%).
- **Readiness = 트래픽 제어** (실패 시 Pod가 Service에서 제거되어 롤아웃이 게이팅됨); **Liveness = 재시작 제어** (실패 시 컨테이너가 재시작됨). 둘을 혼동하지 않도록 주의. startup 프로브는 부팅이 느린 앱을 위해 나머지 두 프로브를 유예시킨다.
- `kubectl rollout status/history/pause/resume`으로 가시성과 제어를, `kubectl rollout undo`로 명령 하나에 이전 리비전으로 복원할 수 있다.
- 점진적 롤아웃 + readiness 게이팅 + 명령 하나로 롤백 = 깨진 릴리스가 있어도 구 버전이 계속 서비스되며 즉시 복구된다.
