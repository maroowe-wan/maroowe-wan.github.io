---
lecture_no: 8
title: "매니페스트/시크릿 관리와 마무리"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=LWbbL3jZcgo
  - https://www.youtube.com/watch?v=O6Uhe9bItkI
  - https://www.youtube.com/watch?v=X-pjSFVKnlY
---

# 매니페스트/시크릿 관리와 마무리

## 학습 목표
- ConfigMap과 Secret으로 설정값과 민감한 값을 이미지에서 분리해 Pod에 주입한다.
- Helm과 Kustomize로 매니페스트를 규모 있게 관리하는 접근 방법을 개관한다.
- 완성된 파이프라인을 점검하고 자신의 코드에 적용하는 방법을 정리한다.

## 본문

### 마지막으로 빠진 조각: 설정

파이프라인이 안전하게 배포하지만, 실제 앱에는 *설정*이 필요하다 — 데이터베이스 URL, 기능 플래그, API 키, 패스워드. 이 값들을 이미지에 굽거나(환경마다 다른 이미지가 필요해진다) Deployment 매니페스트에 하드코딩해서는 **절대 안 된다**(특히 시크릿은 그대로 Git 저장소에 평문으로 남게 된다). 쿠버네티스는 설정을 코드에서 분리해 주는 두 가지 오브젝트를 제공한다. **ConfigMap**은 민감하지 않은 설정을, **Secret**은 민감한 값을 담는다. 이 분리 덕분에 이미지 하나로 개발·스테이징·프로덕션 환경을 넘나들 수 있다.

### ConfigMap: 민감하지 않은 설정

**ConfigMap**은 설정을 키-값 쌍으로 저장한다. *암호화되지 않으며* 포트, 로그 레벨, 기능 플래그처럼 기밀이 아닌 데이터에 적합하다. 커맨드라인에서 리터럴로 생성할 수 있다.

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=NGINX_PORT=8080
```

저장소에 커밋하는 선언형 YAML 방식은 다음과 같다.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "info"
  NGINX_PORT: "8080"
```

Pod가 ConfigMap을 소비하는 방법은 두 가지이며, Secret도 동일하게 동작한다.

**환경 변수로 주입.** 특정 키를 `env`/`valueFrom`으로 주입하거나, `envFrom`으로 모든 키를 한꺼번에 가져온다.

```yaml
        envFrom:
          - configMapRef:
              name: app-config        # 모든 키가 환경 변수가 된다
        # 또는 특정 키 하나만:
        env:
          - name: LOG_LEVEL
            valueFrom:
              configMapKeyRef:
                name: app-config
                key: LOG_LEVEL
```

**마운트된 파일로 주입.** ConfigMap을 볼륨으로 마운트하면 각 키가 파일이 된다(예: `/etc/config/` 아래). 환경 변수 대신 설정 파일을 읽는 앱에 적합하다.

### Secret: 민감한 값 — 그리고 "base64"의 진짜 의미

**Secret**은 ConfigMap과 거의 동일하게 생겼지만 패스워드, 토큰, TLS 인증서, DB 자격증명 같은 민감한 데이터를 담기 위한 것이다.

```bash
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=S3cr3t123
```

주입 방법도 같다(ConfigMap 대신 `secretKeyRef` / `secretRef`를 사용한다는 점만 다르다).

```yaml
        env:
          - name: DB_PASSWORD
            valueFrom:
              secretKeyRef:
                name: db-secret
                key: password
```

쿠버네티스 전체에서 가장 많이 오해받는 부분이 있다.

> **Base64는 인코딩이지 암호화가 아니다.** `kubectl get secret db-secret -o yaml`로 Secret을 검사하면 값이 뒤죽박죽으로 보이지만 — 단지 base64로 인코딩된 것이며, `echo <value> | base64 --decode`로 누구나 즉시 되돌릴 수 있다. Secret은 **기본적으로 보안이 적용되지 않는다.** 평문 패스워드와 동일하게 조심스럽게 다루어야 한다.

그렇다면 Secret이 ConfigMap보다 실제로 더 안전한 이유는 무엇이고, 어떻게 제대로 보호하는가?

- **클러스터에서 저장 시 암호화(encryption at rest)를 활성화**하면 etcd(쿠버네티스의 데이터 저장소) 안에서 값이 암호화된다. 이 설정 없이는 etcd 접근 권한이 있으면 누구나 평문으로 읽을 수 있다. EKS에서는 KMS 키로 엔벨로프 암호화를 활성화할 수 있다.
- **실제 Secret YAML을 Git에 커밋하지 않는다.** 플레이스홀더를 사용하거나, 저장소에 *암호화된* 버전을 안전하게 저장하는 Sealed Secrets 같은 도구를 사용한다.
- **프로덕션에서는 외부 시크릿 관리자로 옮기는 것이 최선이다** — AWS Secrets Manager, HashiCorp Vault, 또는 External Secrets Operator. 실제 값을 클러스터에 전혀 저장하지 않고 런타임에 쿠버네티스가 가져오게 한다. EKS에서는 AWS Secrets and Configuration Provider(ASCP)가 Secrets Manager 값을 직접 마운트할 수 있다.
- **시크릿은 정기적으로 교체한다.** 자격증명은 시간이 지나면 위험해진다. 교체는 유출 피해를 제한한다.

### 규모 있는 매니페스트 관리: Helm과 Kustomize

지금까지 하나의 환경을 위해 손으로 작성한 YAML 파일 몇 개가 있다. 실제 시스템은 개발·스테이징·프로덕션에 걸쳐 소소한 차이를 두고 같은 앱을 실행한다(프로덕션은 레플리카 더 많이, 다른 이미지 태그, 환경별 도메인 이름). 환경별로 YAML을 복사-붙여넣기하면 빠르게 관리 불가능해진다. 두 가지 도구가 이를 해결한다.

**Kustomize**는 *템플릿 없는* 도구로, `kubectl`에 내장되어 있다(`kubectl apply -k`). 순수 쿠버네티스 YAML로 된 **base** 디렉터리와, 달라지는 것만 패치하는 환경별 **overlay**를 유지한다 — 네임스페이스, 레플리카 수, 이미지 태그. 템플릿 플레이스홀더가 없으므로 base 파일이 여전히 유효하고 읽기 쉬운 쿠버네티스 매니페스트다. 편리한 기능으로 `configMapGenerator`/`secretGenerator`가 있다. 데이터가 바뀌면 오브젝트 이름에 해시를 붙여, ConfigMap 편집만으로는 트리거되지 않는 *롤링 업데이트를 자동으로 트리거*한다. 많은 팀에서 Kustomize는 단순함과 강력함의 균형을 잘 맞춘다.

**Helm**은 *템플릿* 패키지 관리자다. 매니페스트를 `values.yaml` 파라미터 파일이 있는 재사용 가능하고 버전화된 **차트**로 묶는다. 같은 앱을 다른 값으로 설치할 수 있다. Helm은 기성 소프트웨어(데이터베이스, 모니터링 스택)를 패키징하고 재사용 가능한 차트를 공유할 때 빛을 발한다. 트레이드오프는 유연해지려면 많은 필드를 파라미터화해야 해서 그 자체로 복잡성이 생긴다는 것이다.

오늘 당장 둘 중 하나를 도입할 필요는 없다 — 앱 하나, 환경 하나라면 손으로 작성한 YAML로도 충분하다. 하지만 선택지를 알아두자. 자신의 앱을 최소한의 번거로움으로 환경별 변형이 필요할 때는 **Kustomize**를, 재사용이나 서드파티 소프트웨어 설치를 패키징할 때는 **Helm**을 찾는다.

### 완성된 파이프라인 — 그리고 내 코드에 적용하기

이 강좌에서 무엇을 만들었는지 뒤돌아보자. 엔드-투-엔드 흐름은 다음과 같다.

1. `Dockerfile`로 앱을 **컨테이너화**하고 **ECR** 리포지토리를 만든다(2강).
2. **GitLab에 푸시** → **웹훅**이 **Jenkins**를 트리거하고, 체크아웃·테스트·빌드를 거쳐 **커밋 SHA 태그 이미지**를 ECR에 푸시한다(3강).
3. **Deployment와 Service 매니페스트**로 워크로드를 기술하고 이미지 태그가 주입된다(4강).
4. **IAM 역할을 RBAC 그룹에 매핑**해 Jenkins가 **EKS**에 접근한다(5강).
5. Jenkins의 **배포 스테이지**가 이미지를 갱신(`kubectl apply` 또는 `set image`)하고 `kubectl rollout status`로 기다린다(6강).
6. EKS가 **readiness/liveness 프로브**로 게이팅되는 **롤링 업데이트**를 수행하고, `kubectl rollout undo`가 원클릭 롤백으로 대기한다(7강).
7. **ConfigMap과 Secret**이 설정을 이미지에서 분리하고, **Kustomize 또는 Helm**으로 규모 있게 관리한다(이번 강의).

*자신의* 애플리케이션을 이 파이프라인에 통과시키려면 커스터마이징할 부분이 작고 명확하다. `Dockerfile`, `deployment.yaml`/`service.yaml`(이미지 참조, 컨테이너 포트, 레플리카 수, 프로브), 환경별 값을 위한 ConfigMap/Secret, `Jenkinsfile`의 환경 변수(AWS 계정 ID, 리전, ECR 리포지토리 이름, 클러스터 이름). 파이프라인의 *형태* — 웹훅 → 빌드 → 푸시 → 배포 → 확인 — 는 바뀌지 않는다. 이 재사용성이 핵심이다. 한 번 설정하면 이후 모든 프로젝트가 안전하고 자동화된 추적 가능한 배포를 상속받는다.

## 핵심 정리
- 이미지와 매니페스트에서 설정을 분리하라. 민감하지 않은 설정은 ConfigMap에, 민감한 것은 Secret에. 환경 변수 또는 마운트된 파일로 주입한다.
- Secret은 base64로 *인코딩*되었을 뿐 암호화된 게 아니다 — 누구나 디코딩할 수 있다. 저장 시 암호화, Git에서 제외, 가능하면 외부 관리자(AWS Secrets Manager, Vault) 사용, 정기적 교체로 실제 시크릿을 보호하라.
- 환경 간 매니페스트 관리는 **Kustomize**(템플릿 없는 base + overlay, `kubectl`에 내장) 또는 **Helm**(템플릿, 버전화된 차트)으로. 시작할 때는 손으로 작성한 YAML도 괜찮다.
- 완성된 파이프라인은 단일 푸시로 안전하고 추적 가능한 무중단 EKS 배포를 만든다. 새 앱에 적용할 때 바꿔야 하는 것은 Dockerfile, 매니페스트, 설정/시크릿, 그리고 `Jenkinsfile` 변수 몇 개뿐이다.
