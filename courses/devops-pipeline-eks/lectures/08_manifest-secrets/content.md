---
lecture_no: 8
title: "매니페스트·시크릿 관리와 마무리"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=LWbbL3jZcgo
  - https://www.youtube.com/watch?v=O6Uhe9bItkI
  - https://www.youtube.com/watch?v=X-pjSFVKnlY
---

# 매니페스트·시크릿 관리와 마무리

## 학습 목표
- ConfigMap과 Secret으로 설정값과 민감 정보를 이미지에서 분리해 Pod에 주입한다.
- Kustomize로 매니페스트를 규모 있게 관리하고, Helm이 필요한 상황을 구분한다.
- 완성된 파이프라인 전체를 점검하고 자신의 코드에 적용하는 법을 정리한다.

## 본문

실제 앱에는 데이터베이스 URL, 기능 플래그, API 키, 패스워드 같은 설정이 반드시 필요하다. 이 값들을 이미지에 굽거나 매니페스트에 하드코딩해서는 **절대 안 된다.** 쿠버네티스는 설정을 코드에서 분리해 주는 오브젝트를 두 가지 제공한다. **ConfigMap**은 민감하지 않은 설정을, **Secret**은 민감한 값을 담는다. 이 분리 덕분에 이미지 하나로 개발·스테이징·프로덕션 환경을 모두 운영할 수 있다. 아래 각 작업은 '무엇/왜', 명령어 또는 YAML, 그리고 검증 단계 순서로 정리했다.

### ConfigMap 만들기

**ConfigMap**은 민감하지 않은 설정을 키-값 쌍으로 저장한다. 빠른 테스트에는 명령형(커맨드라인)으로, Git에 커밋할 것은 선언형(YAML)으로 만든다.

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=NGINX_PORT=8080
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "info"
  NGINX_PORT: "8080"
```

확인:

```bash
kubectl get configmap app-config -o yaml
```

### ConfigMap을 Pod에 주입하기

Pod가 ConfigMap을 소비하는 방법은 두 가지이며, Secret도 동일하게 동작한다. **환경 변수**로 주입하거나 **마운트된 파일**로 주입한다. `envFrom`으로 모든 키를 한꺼번에 가져오거나, `env`/`valueFrom`으로 특정 키 하나만 선택할 수 있다.

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

파일로 마운트하려면 ConfigMap을 볼륨으로 연결한다. 각 키가 마운트 경로(예: `/etc/config/`) 아래의 파일이 된다. Pod 안에서 확인:

```bash
kubectl exec -it <pod> -- env | grep LOG_LEVEL
# 파일 마운트 방식이면:
kubectl exec -it <pod> -- ls /etc/config
```

### Secret 만들고 주입하기

**Secret**은 패스워드, 토큰, TLS 인증서, DB 자격증명 같은 민감한 값을 담는다. 생김새는 ConfigMap과 거의 같지만, 용도를 명확히 구분하고 추가 보호 수단을 적용할 수 있다(아래 참조).

```bash
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=S3cr3t123
```

주입 방법도 ConfigMap과 같다. `secretKeyRef` / `secretRef`를 쓰는 점만 다르다.

```yaml
        env:
          - name: DB_PASSWORD
            valueFrom:
              secretKeyRef:
                name: db-secret
                key: password
```

확인:

```bash
kubectl exec -it <pod> -- env | grep DB_PASSWORD
```

### "base64"의 실체 — 그리고 Secret을 제대로 보호하는 법

Secret을 조회하면 값이 뒤죽박죽처럼 보인다. 하지만 실제로는 그렇지 않다. 쿠버네티스에서 가장 많이 오해받는 지점이다.

```bash
kubectl get secret db-secret -o yaml
echo 'UzNjcjN0MTIz' | base64 --decode   # → S3cr3t123
```

> **Base64는 인코딩이지 암호화가 아니다.** 누구나 즉시 되돌릴 수 있다. Secret은 **기본적으로 보안이 적용되지 않는다** — Secret YAML을 평문 패스워드와 동일하게 조심스럽게 다뤄야 한다.

Secret을 실제로 안전하게 만들려면:
- **저장 시 암호화(encryption at rest)를 활성화**하면 etcd(쿠버네티스 데이터 저장소) 안에서 값이 암호화된다. EKS에서는 KMS 키로 엔벨로프 암호화를 적용한다.
- **실제 Secret YAML을 Git에 커밋하지 않는다.** 플레이스홀더를 쓰거나, 저장소에 *암호화된* 버전을 안전하게 보관하는 Sealed Secrets를 사용한다.
- **프로덕션에서는 외부 시크릿 관리자에 위임하는 것이 최선이다** — AWS Secrets Manager, HashiCorp Vault, 또는 External Secrets Operator. 실제 값이 클러스터 안에 존재하지 않는다. EKS에서는 AWS Secrets and Configuration Provider(ASCP)가 Secrets Manager 값을 직접 마운트할 수 있다.
- **시크릿은 정기적으로 교체한다.** 유출 피해를 최소화할 수 있다.

### Kustomize로 매니페스트 규모 있게 관리하기

개발·스테이징·프로덕션에 걸쳐 조금씩 다른 설정(레플리카 수, 이미지 태그, 네임스페이스)으로 같은 앱을 운영하다 보면 YAML을 환경마다 복사-붙여넣기하는 방식은 금세 감당이 안 된다. **Kustomize**가 이 문제를 해결하며, `kubectl`에 내장되어 있다(`apply -k`). **템플릿이 없다**는 점이 핵심이다. 순수 쿠버네티스 YAML로 된 **base**에, 달라지는 것만 패치하는 환경별 **overlay**를 덮는다. 덕분에 base 파일이 여전히 유효하고 읽기 쉬운 매니페스트로 남는다.

폴더 구조는 다음과 같다.

```
base/
  deployment.yaml
  kustomization.yaml      # resources: [deployment.yaml]
overlays/
  staging/kustomization.yaml
  production/kustomization.yaml
```

프로덕션 overlay는 달라지는 부분만 정의하고 base를 참조한다.

```yaml
# overlays/production/kustomization.yaml
namespace: production
resources:
  - ../../base
replicas:
  - name: nginx
    count: 20
images:
  - name: nginx
    newTag: 1.21.6
```

적용 및 확인:

```bash
kubectl apply -k overlays/production
kubectl get pods -n production
```

Kustomize의 또 다른 강점은 `configMapGenerator`/`secretGenerator`다. 데이터가 바뀌면 오브젝트 이름에 콘텐츠 해시를 붙여, ConfigMap 편집만으로는 트리거되지 않는 **롤링 업데이트를 자동으로 일으킨다.**

```yaml
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
secretGenerator:
  - name: db-secret
    literals:
      - password=S3cr3t123
```

> **Helm을 써야 할 때.** **Helm**은 *템플릿* 방식의 패키지 관리자로, 매니페스트를 `values.yaml`이 있는 버전화된 재사용 가능한 **차트**로 묶는다. 소프트웨어를 재사용 패키지로 배포하거나 서드파티 앱(데이터베이스, 모니터링)을 설치할 때 Helm이 어울린다. 자신의 앱을 환경별로 변형해 운영할 때는 번거로움이 적은 **Kustomize**가 낫다. 처음에는 손으로 작성한 YAML로 충분하다.

### 완성된 파이프라인 — 내 코드에 적용하기

이 강좌에서 만든 것을 되돌아보자. 전체 흐름은 다음과 같다.

1. `Dockerfile`로 앱을 **컨테이너화**하고 **ECR** 리포지토리를 만든다(2강).
2. **GitLab에 푸시** → **웹훅**이 **Jenkins**를 트리거하고, 테스트·빌드를 거쳐 **커밋 SHA 태그 이미지**를 ECR에 푸시한다(3강).
3. **Deployment와 Service 매니페스트**로 워크로드를 기술하고 이미지 태그를 주입한다(4강).
4. **IAM 역할을 RBAC 그룹에 매핑**해 Jenkins에 **EKS** 접근 권한을 부여한다(5강).
5. Jenkins의 **배포 스테이지**가 이미지를 갱신하고 `kubectl rollout status`로 완료를 기다린다(6강).
6. EKS가 **readiness/liveness 프로브**로 게이팅되는 **롤링 업데이트**를 수행하고, `kubectl rollout undo`로 즉시 롤백할 수 있다(7강).
7. **ConfigMap과 Secret**이 설정을 이미지에서 분리하고, **Kustomize 또는 Helm**으로 규모 있게 관리한다(이번 강의).

*자신의* 앱을 이 파이프라인에 통과시키려면 바꿔야 할 부분은 작다. `Dockerfile`, `deployment.yaml`/`service.yaml`(이미지 참조, 포트, 레플리카 수, 프로브), ConfigMap/Secret, 그리고 `Jenkinsfile` 변수 몇 개(AWS 계정 ID, 리전, ECR 리포지토리, 클러스터 이름). 파이프라인의 *형태* — 웹훅 → 빌드 → 푸시 → 배포 → 확인 — 는 바뀌지 않는다. 한 번 갖춰 두면 이후 모든 프로젝트가 안전하고 자동화된 추적 가능한 배포를 그대로 이어받는다.

## 핵심 정리
- 설정은 이미지 밖에 두어야 한다. 민감하지 않은 설정은 **ConfigMap**에, 민감한 값은 **Secret**에. 환경 변수(`envFrom`/`valueFrom`) 또는 마운트된 파일로 주입한다.
- Secret은 base64로 *인코딩*되었을 뿐 암호화된 것이 아니다 — 누구나 디코딩할 수 있다. 저장 시 암호화, Git 외부 보관, 가능하면 외부 관리자(AWS Secrets Manager, Vault) 활용, 정기 교체로 실제 시크릿을 보호하자.
- **Kustomize**(템플릿 없는 base + overlay, `kubectl` 내장)는 환경별 매니페스트 변형에 쓰고, 해시 기반 생성기로 롤링 업데이트를 자동화한다. **Helm**은 재사용 가능한 차트나 서드파티 앱 설치에 어울린다.
- 완성된 파이프라인은 코드 한 번 푸시로 안전하고 추적 가능한 무중단 EKS 배포를 완성한다. 새 앱에 적용할 때 바꿔야 하는 것은 Dockerfile, 매니페스트, 설정/시크릿, `Jenkinsfile` 변수 몇 개뿐이다.
