---
lecture_no: 3
title: 로컬 쿠버네티스 클러스터 준비
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=7tWJbsGglYA
  - https://www.youtube.com/watch?v=qBudNa-j7as
  - https://www.youtube.com/watch?v=hDBgeUuPgXo
---

# 로컬 쿠버네티스 클러스터 준비

## 학습 목표
- **minikube** 또는 **kind**를 설치하고 노트북에 쿠버네티스 클러스터를 직접 띄운다.
- **kubectl**로 해당 클러스터에 접속한 뒤 `kubectl get nodes`와 `kubectl cluster-info`로 정상 여부를 확인한다.
- 2강에서 빌드한 이미지(`flask-capstone:1.0`)를 `minikube image load` 또는 `kind load docker-image`로 **클러스터 내부에 직접 로드**해, 레지스트리 없이 배포할 수 있는 상태를 만든다.

## 본문

### 지금 캡스톤 어디쯤 와 있나

지금까지 동작하는 앱과 그것을 패키징하는 방법이 갖춰졌다. 1강에서는 `/healthz` 엔드포인트를 가진 소규모 Flask 애플리케이션을 작성했고, 2강에서는 그것을 Docker 이미지로 감싸 `flask-capstone:1.0`으로 태그했다. 그 이미지는 지금 내 컴퓨터에 있고, 언제든 실행할 준비가 되어 있다.

빠진 조각은 *쿠버네티스 방식으로* 그 이미지를 실행할 환경이다. 이 강의에서 만드는 것이 바로 그것이다. 노트북 안에서 완전히 동작하는 작고 진짜인 쿠버네티스 클러스터다. 이 강의가 끝나면 실행 중인 클러스터, 연결된 `kubectl`, 그리고 클러스터 내부에 로드된 `flask-capstone:1.0` 이미지까지 갖추게 된다. 이 준비가 끝나야 4강에서 Deployment와 Service 매니페스트를 작성해 실제로 스케줄링할 수 있다.

> 이 강의의 핵심은 원격 레지스트리를 한 번도 거치지 않고 로컬 이미지를 클러스터 *안으로* 옮기는 것이다. 이 한 가지 기법이 로컬 쿠버네티스 개발을 빠르고 무료로 만든다.

### 로컬 클러스터를 쓰는 이유

프로덕션 쿠버네티스 클러스터는 무거운 인프라다. 고가용성을 위한 컨트롤 플레인 노드 3대에 워커 노드가 여러 대, 각각 별도의 물리 또는 가상 머신이 필요하다. 컨트롤 플레인은 *무엇을 어디서 실행할지* 결정하고, 워커는 실제로 컨테이너를 실행한다. Flask 앱 하나 테스트하자고 이걸 전부 띄울 이유는 없다.

학습과 로컬 개발에는 **단일 노드 클러스터**를 쓴다. 한 머신이 컨트롤 플레인과 워커 역할을 동시에 맡는 구성이다. 이를 위한 도구는 두 가지가 있고, 둘 중 **하나만** 고르면 된다.

- **minikube** — 완성도 높은 단일 노드 클러스터 도구. 내 머신에서 Docker 컨테이너(또는 VM) 안에 쿠버네티스를 실행하며, `minikube service`나 애드온 같은 편의 기능도 함께 제공한다.
- **kind** — "**K**ubernetes **in** **D**ocker"의 약자. 쿠버네티스 노드 하나하나를 Docker 컨테이너로 실행한다. 가볍고 기동이 빠르며, CI 환경에서도 많이 쓴다.

둘 다 동일한 `kubectl` 경험을 제공한다. 어느 쪽을 골라도 나머지 캡스톤 과정은 똑같이 진행된다.

> 두 도구 모두 전제 조건이 하나 있다. **Docker가 설치되어 실행 중이어야 한다.** minikube(Docker 드라이버)와 kind 모두 Docker를 엔진으로 사용하므로, Docker Desktop이나 Docker 데몬을 먼저 시작해 두어야 한다.

### kubectl: 클러스터를 조종하는 도구

클러스터를 시작하기 전에, 이를 제어하는 도구를 이해해 두자. **kubectl**(발음: "kube-control" 또는 "kube-cuttle")은 쿠버네티스 커맨드라인 클라이언트다. Pod 생성, Service 조회, 로그 확인 등 모든 작업은 클러스터의 **API 서버**로 요청을 보내는 방식으로 이루어진다. API 서버는 모든 변경 사항이 통과하는 단일 창구다. kubectl은 그 요청을 편리하게 만들어주는 도구다.

좋은 점은 kubectl이 minikube나 kind에 종속되지 않는다는 것이다. 같은 도구로 EKS, GKE, AKS 같은 관리형 클라우드 클러스터에도 똑같이 접속할 수 있다. 여기서 배운 kubectl 사용법은 어디서든 그대로 통한다.

minikube와 kind 모두 kubectl을 의존성으로 함께 설치하므로, 클러스터 도구를 설치하면 대부분 kubectl도 자동으로 따라온다. 설치 여부는 다음 명령으로 확인한다.

```bash
kubectl version --client
```

### 경로 A — minikube 사용

**1. 설치 및 시작.** macOS에서는 Homebrew(`brew install minikube`), Windows에서는 공식 설치 프로그램이나 `winget`/Chocolatey, Linux에서는 minikube 사이트에서 바이너리를 내려받아 설치한다. 그런 다음 Docker 드라이버로 클러스터를 시작한다.

```bash
minikube start --driver=docker
```

이 명령은 노드 이미지를 내려받고, Docker 컨테이너 안에 단일 노드 클러스터를 부팅한다. 기본값이 단일 노드이므로 별도로 지정할 필요는 없다.

**2. 정상 여부 확인.**

```bash
minikube status
kubectl get nodes
kubectl cluster-info
```

`minikube status`는 host, kubelet, apiserver가 모두 `Running`으로 표시되어야 한다. `kubectl get nodes`는 상태가 `Ready`인 노드 하나를 보여주어야 한다. `kubectl cluster-info`는 API 서버 URL을 출력하는데, 이것이 kubectl이 클러스터에 연결된 증거다.

**3. 이미지 로드.** 핵심 단계다. `flask-capstone:1.0` 이미지는 내 로컬 Docker에만 있고, 클러스터는 별도의 이미지 저장소를 사용하므로 아직 보이지 않는다. minikube는 이를 복사하는 한 줄짜리 명령을 제공한다.

```bash
minikube image load flask-capstone:1.0
```

이 명령 후 이미지가 클러스터 내부에 존재하게 된다. 다음 명령으로 확인할 수 있다.

```bash
minikube image ls | grep flask-capstone
```

### 경로 B — kind 사용

**1. 설치 및 생성.** Homebrew, Go 툴체인, 또는 릴리스 바이너리로 kind를 설치한 뒤 클러스터를 생성한다.

```bash
kind create cluster --name capstone
```

이 명령은 쿠버네티스 노드를 Docker 컨테이너로 띄우고, kubectl이 자동으로 해당 클러스터를 가리키도록 설정한다.

**2. 정상 여부 확인.**

```bash
kubectl get nodes
kubectl cluster-info --context kind-capstone
```

마찬가지로 `Ready` 상태의 노드 하나와 API 서버 URL이 출력되어야 한다. kind는 kubectl 컨텍스트를 `kind-<이름>` 형식으로 설정하는데, 여기서는 `kind-capstone`이 된다.

**3. 이미지 로드.**

```bash
kind load docker-image flask-capstone:1.0 --name capstone
```

이 명령은 로컬 Docker에 있는 이미지를 kind 노드의 컨테이너 런타임으로 복사한다. 이제 클러스터는 레지스트리 없이 이 이미지를 실행할 수 있다.

### 레지스트리를 건너뛰는 이유와 `imagePullPolicy`의 역할

이미지를 쿠버네티스에 올리는 "정석" 방법은 Docker Hub나 Amazon ECR 같은 레지스트리에 푸시한 뒤 클러스터가 다시 내려받게 하는 것이다. 개발 중에는 이 사이클이 번거롭다. 코드를 바꿀 때마다 *빌드 → 푸시 → 풀*을 반복해야 하고, 비공개 레지스트리는 비용도 들고 인증도 관리해야 한다.

이미지를 직접 로드하면 이 모든 과정을 건너뛸 수 있다. 다만 4강을 위해 반드시 알아두어야 할 함정이 있다. 기본적으로 쿠버네티스는 여전히 이미지를 원격 레지스트리에서 **풀**하려 시도할 수 있다. 특히 태그가 `:latest`일 때 그런 경향이 강하다. `flask-capstone:1.0`은 레지스트리에 한 번도 올라간 적이 없으므로 풀에 실패하고, Pod가 `ImagePullBackOff` 상태에 빠진다. 쿠버네티스가 "이미지를 가져오지 못했다"고 신호를 보내는 방식이다.

해결책은 컨테이너 스펙의 **`imagePullPolicy`** 필드다.

- `imagePullPolicy: IfNotPresent` — 이미지가 이미 있으면 로컬 복사본을 사용하고, 없을 때만 풀한다. 이미지를 *로드*했으므로 이미 존재하고, 쿠버네티스는 레지스트리에 요청하지 않고 그것을 바로 사용한다.
- `imagePullPolicy: Never` — 절대 풀하지 않고, 로컬에 없으면 실패한다. 여기서도 동작하지만 더 엄격한 옵션이다.

> 이 캡스톤에서는 고정 태그(`flask-capstone:1.0`, `:latest` 아님)를 사용하고 `imagePullPolicy: IfNotPresent`를 설정한다. 고정 태그는 쿠버네티스가 "항상 풀"로 기본 설정되는 것을 막고, 정책 덕분에 로드한 이미지를 그대로 사용한다. 4강에서 이 조합을 기억해 두면 Pod가 멈추는 문제를 피할 수 있다.

한 가지 참고할 점이 있다. minikube의 예전 방법인 `eval $(minikube docker-env)` 트릭(Docker 클라이언트를 minikube 내부 데몬으로 전환하는 방식)은 **단일 노드** 클러스터에서만 동작한다. 앞서 소개한 `minikube image load`와 `kind load docker-image` 명령은 더 간단하고 어떤 구성에서도 동일하게 작동하므로 이 방식을 권한다.

### 지금 일어난 일: 구조 이해

구조를 정리하면 다음과 같다. 노트북에서는 Docker가 실행 중이고, 2강에서 빌드한 `flask-capstone:1.0` 이미지가 그 안에 있다. 클러스터 도구(minikube 또는 kind)는 단일 쿠버네티스 노드를 Docker 컨테이너 안에서 실행한다. 이 노드는 노트북의 Docker와 분리된 자체 이미지 저장소를 갖는다. `image load` 명령은 이 경계를 넘어 이미지를 복사한다. kubectl은 노트북에서 실행되며 노드의 API 서버에 명령을 보낸다. 이미지가 노드 안에 들어오고 kubectl이 연결되면, 4강에서 그 이미지로 Pod를 스케줄링할 모든 준비가 완료된다. 아래 다이어그램은 이 두 경계와 그 사이를 오가는 두 흐름을 보여준다.

```mermaid 로컬 클러스터 구조: kubectl은 API 서버를 제어하고, image load는 노트북-클러스터 경계를 넘어 이미지를 복사한다
flowchart LR
    subgraph Laptop["노트북"]
        Kubectl["kubectl"]
        Docker["Docker<br/>flask-capstone:1.0 보관"]
    end
    subgraph Node["단일 노드 클러스터 (minikube / kind 컨테이너)"]
        API["API 서버"]
        Kubelet["kubelet"]
        Store["노드 이미지 저장소"]
    end
    Kubectl -->|"명령"| API
    API --> Kubelet
    Docker -->|"image load"| Store
    Kubelet -->|"Pod 실행"| Store
```

## 핵심 정리
- **단일 노드 로컬 클러스터**(minikube 또는 kind)를 사용하면 노트북에서 실제 쿠버네티스 환경을 쓸 수 있다. 도구 하나를 골라 Docker가 실행된 상태에서 시작하면 된다.
- `kubectl get nodes`(`Ready` 상태 확인)와 `kubectl cluster-info`가 kubectl이 살아있는 클러스터에 연결되어 있는지 확인하는 두 가지 빠른 점검법이다.
- 2강의 이미지는 `minikube image load flask-capstone:1.0` 또는 `kind load docker-image flask-capstone:1.0 --name <클러스터명>`으로 로드해 **레지스트리 없이 배포**한다.
- **고정 태그**(`:1.0`, `:latest` 아님)와 **`imagePullPolicy: IfNotPresent`**를 함께 사용해야 쿠버네티스가 로드된 이미지를 그대로 사용한다. 풀을 시도했다가 실패하는 일이 생기지 않는다. 4강의 매니페스트 작성을 위한 핵심 준비 사항이다.
