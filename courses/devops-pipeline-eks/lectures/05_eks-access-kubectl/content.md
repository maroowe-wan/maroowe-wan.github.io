---
lecture_no: 5
title: "EKS 클러스터 접근과 kubectl 설정"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=6COvT1Zu9o0
  - https://www.youtube.com/watch?v=6ZALmrssgfc
  - https://www.youtube.com/watch?v=rFtaknmZiaM
---

# EKS 클러스터 접근과 kubectl 설정

## 학습 목표
- `aws eks update-kubeconfig`로 EKS 클러스터에 연결하고 접근을 확인한다.
- EKS 접근의 두 계층, AWS IAM(클러스터 도달)과 쿠버네티스 RBAC(내부 권한)을 이해한다.
- IAM 아이덴티티를 쿠버네티스 그룹에 매핑해 Jenkins가 무인으로 배포하도록 구성한다.

## 본문

파이프라인이 이미지를 빌드하고(3강), 매니페스트를 작성하는(4강) 단계까지 왔다. 그런데 아직 EKS에 *인증*한 주체가 없다. 기억할 핵심 규칙은 하나다. EKS 접근에는 **두 개의 독립적인 계층**이 있다. AWS IAM이 클러스터에 도달할 수 있는지를 결정하고, 쿠버네티스 RBAC이 안에서 무엇을 할 수 있는지를 결정한다. 둘 다 갖춰야 한다.

### Task 1: kubectl을 클러스터에 연결하기

`kubectl`은 쿠버네티스 CLI다. 어떤 클러스터에, 어떤 엔드포인트로, 어떤 아이덴티티로 연결할지 등 접속 설정을 **kubeconfig** 파일(기본값 `~/.kube/config`)에서 읽는다. EKS에서는 이 파일을 직접 편집하지 않는다. AWS가 올바른 항목을 자동으로 생성해 준다. 다음 명령은 클러스터의 API 엔드포인트와 인증서를 kubeconfig에 기록하고, 인증용 단기 AWS 토큰을 발급받도록 설정한다.

```bash
aws eks update-kubeconfig --region us-east-1 --name my-cluster
```

접근을 확인한다.

```bash
kubectl get nodes
kubectl get pods -A
```

노드 목록이 보이면 연결된 것이다. "Unauthorized" 또는 "로그인 필요" 오류가 나오면 **두 번째 계층**이 말하는 것이다. IAM 아이덴티티는 클러스터에 도달했지만 RBAC이 아직 권한을 부여하지 않은 상태다.

> 클러스터를 전환하거나, AWS 프로파일을 바꾸거나, 다른 머신으로 이동할 때마다 `aws eks update-kubeconfig`를 다시 실행하라. 멱등적이라 반복 실행해도 안전하다. `--profile <이름>`을 추가하면 특정 AWS 아이덴티티로 연결할 수 있다.

### 1계층: IAM — 클러스터에 도달할 수 있는가

kubeconfig는 `kubectl`에 현재 **IAM 아이덴티티**(사용자 또는 역할)로 AWS에서 토큰을 발급받도록 지시하고, EKS가 이를 검증한다. 첫 번째 관문이다. 최소한의 IAM 정책은 `eks:DescribeCluster`를 허용하는 것으로, `update-kubeconfig`가 엔드포인트를 가져올 수 있게 된다. 클러스터에 *도달*하기에는 충분하지만, 안에서 무언가를 할 수 있는 권한은 전혀 부여하지 않는다.

### 2계층: RBAC — 안에서 무엇을 할 수 있는가

토큰이 수락되면 쿠버네티스가 **RBAC(Role-Based Access Control)**을 적용한다. RBAC은 두 부분으로 구성된다.

- **Role**(네임스페이스 범위) 또는 **ClusterRole**(클러스터 전체)은 권한을 나열한다 — `pods`, `deployments`, `secrets` 등의 리소스에 대한 `get`, `list`, `create` 같은 동사.
- **RoleBinding** / **ClusterRoleBinding**은 Role을 아이덴티티(사용자, 그룹, 서비스 어카운트)에 연결한다.

### Task 2: 읽기 전용 뷰어 역할과 그룹 만들기

모든 네임스페이스에서 Pod, Service, Deployment를 `get`, `list`, `watch`할 수 있는 읽기 전용 ClusterRole이다. 규칙을 **API group별로 분리**하는 방식에 주목하라. `pods`와 `services`는 코어 그룹(`apiGroups: [""]`)에 속하고, `deployments`는 `apps` 그룹에 속한다. `deployments`를 코어 그룹에 나열하는 것은 흔한 실수다. 적용은 되지만 Deployment 접근이 조용히 `Forbidden`으로 실패한다. 해당 그룹에 그런 리소스가 존재하지 않기 때문이다.

```yaml
# viewer.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: viewer
rules:
  - apiGroups: [""]                              # 코어 그룹
    resources: ["pods", "services", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]                          # apps 그룹
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: viewer-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: viewer
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: my-viewer        # IAM과 매핑할 쿠버네티스 그룹
```

```bash
kubectl apply -f viewer.yaml
```

이 설정은 `viewer` ClusterRole을 `my-viewer`라는 쿠버네티스 그룹에 바인딩한다. 아직 그룹에 멤버가 없다. 다음 Task에서 IAM과 연결한다.

### Task 3: IAM 아이덴티티를 쿠버네티스 그룹에 매핑하기

AWS는 IAM 아이덴티티를 알고, 쿠버네티스는 자체 사용자와 그룹을 안다. 두 세계를 **매핑**하는 무언가가 필요하다 — 예컨대 "IAM 역할 `...:role/jenkins-deploy`를 쿠버네티스 그룹 `my-viewer`로 취급하라"고 선언하는 것. 현대적이고 감사 가능한 방법인 **EKS access entries**를 사용한다(예전의 `aws-auth` ConfigMap은 레거시 클러스터에 남아 있지만 deprecated다).

```bash
# IAM 주체를 클러스터에 등록
aws eks create-access-entry \
  --cluster-name my-cluster \
  --principal-arn arn:aws:iam::111122223333:role/jenkins-deploy \
  --kubernetes-groups my-viewer
```

이제 전체 체인이 완성된다. **IAM 아이덴티티 → access entry → 쿠버네티스 그룹 → 바인딩 → Role의 권한.** 어느 한 연결 고리가 끊어지면 `Unauthorized`가 난다.

### Task 4: 권한 확인하기

`kubectl auth can-i`는 권한 질문에 직접 답해주는 가장 빠른 디버깅 도구다.

```bash
kubectl auth can-i get pods           # -> yes
kubectl auth can-i get nodes          # -> no (viewer는 클러스터 범위 노드 접근 권한 없음)
kubectl auth can-i '*' '*'            # -> no (관리자 아님)
```

### Task 5: Jenkins 인증 설정(진짜 목표)

지금까지는 *나*(개인)에게 적용한 내용이다. 이제 *Jenkins*에 적용할 차례다. Jenkins는 사람이 자격증명을 입력하지 않아도 EKS에 무인으로 `kubectl`을 실행할 수 있어야 한다. 3강의 원칙이 여기서도 적용된다. **머신은 IAM 역할로 인증하고, 잡에 정적 키를 쓰지 않는다.**

- **IRSA / EKS Pod Identity** — Jenkins가 EKS *안에서* 실행된다면, Jenkins의 서비스 어카운트에 IAM 역할을 연결한다. Pod가 단기 자격증명을 자동으로 받으며, 어디에도 시크릿이 저장되지 않는다.
- **인스턴스/노드 IAM 역할** — Jenkins가 EC2에서 실행된다면, 인스턴스에 IAM 역할을 연결한다. AWS CLI가 자동으로 이를 감지한다.

해당 IAM 역할을 배포 권한이 있는 RBAC 그룹에 매핑한다(보통 특정 네임스페이스의 Deployment에 `get`/`update`/`patch` 권한). 그러면 배포 스테이지는 단순히 이렇게 실행된다.

```bash
aws eks update-kubeconfig --region us-east-1 --name my-cluster
kubectl apply -f deployment.yaml
```

IAM 역할이 인식되고(1계층 + 매핑), 올바른 RBAC 권한이 있기 때문에(2계층) EKS가 이를 수락한다.

> Jenkins의 RBAC 범위를 최소 권한으로 유지하라 — 한 네임스페이스에서 Deployment를 업데이트하는 권한이면 충분하고, `cluster-admin`은 불필요하다. 파이프라인이 침해되더라도 범위가 좁은 역할은 피해 반경을 제한한다.

## 핵심 정리
- `aws eks update-kubeconfig --region <r> --name <cluster>`는 클러스터 엔드포인트와 인증 정보를 kubeconfig에 기록한다. `kubectl get nodes`로 접근을 확인한다.
- EKS 접근에는 두 계층이 있다. **IAM**이 클러스터 도달 가능 여부를 결정하고, **RBAC**이 안에서 할 수 있는 일을 결정한다. "Unauthorized"는 대개 IAM은 통과했지만 RBAC이 부여되지 않은 것이다.
- RBAC 규칙에서 리소스는 올바른 API group에 나열해야 한다. `pods`/`services`/`configmaps`는 코어 그룹(`""`), `deployments`/`replicasets`/`statefulsets`/`daemonsets`는 `apps` 그룹이다. 잘못된 그룹에 넣으면 `Forbidden`이 난다.
- IAM 아이덴티티는 **EKS access entries**(현대적 방법)로 쿠버네티스 그룹에 매핑한다. 체인은 IAM → 매핑 → 그룹 → 바인딩 → 권한이다.
- Jenkins는 IAM 역할로 인증한다 — 클러스터 내부라면 IRSA/Pod Identity, EC2라면 인스턴스 역할을 쓰고, 절대 정적 키를 사용하지 않는다. 해당 역할은 최소 권한의 RBAC 그룹에 매핑한다.
- `kubectl auth can-i <동사> <리소스>`로 권한을 빠르게 디버깅한다.
