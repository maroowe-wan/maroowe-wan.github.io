---
lecture_no: 6
title: "Jenkins에서 EKS 자동 배포"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=h7k45phtZgc
  - https://www.youtube.com/watch?v=MSDqlQurfaI
  - https://www.youtube.com/watch?v=u5924Zxr8Vw
---

# Jenkins에서 EKS 자동 배포

## 학습 목표
- 새로 빌드된 이미지 태그로 매니페스트를 갱신하는 과정을 자동화한다.
- `kubectl apply` 또는 `kubectl set image`로 EKS에 롤아웃한다.
- 푸시 한 번으로 EKS까지 배포되는 파이프라인을 완성한다.

## 본문

### 루프 완성하기

이 강의에서 모든 것이 연결된다. 이미 있는 것들은 이렇다. 커밋 태그 이미지를 빌드하고 ECR에 푸시하는 CI 파이프라인(3강), 배포를 기술하는 매니페스트(4강), RBAC 그룹에 매핑된 IAM 역할을 통해 EKS에 인증된 Jenkins(5강). 빠진 마지막 조각은 새로 빌드된 태그를 가져다 EKS에 실행하라고 지시하는 **배포 스테이지**다. 이것만 추가하면, `git push` 하나로 사람의 개입 없이 실행 중인 Pod까지 흐름이 이어진다 — 진정한 지속적 배포다.

이 스테이지의 과제는 하나의 질문으로 요약된다. **새 이미지 태그를 어떻게 클러스터의 Deployment에 넣는가?** 두 가지 깔끔한 방법이 있으며, 둘 다 알아야 한다.

### 방법 A: 매니페스트를 다시 작성한 후 `kubectl apply`

이미지 태그는 `deployment.yaml`의 한 줄에 있다. 가장 투명한 방법은 해당 파일에 새 태그를 대입한 뒤 적용하는 것이다. 빌드에서 이미 `IMAGE_TAG`(커밋 SHA)를 export했으므로, 배포 스테이지가 즉석에서 매니페스트를 수정할 수 있다.

```groovy
stage('Deploy to EKS') {
    steps {
        sh """
          aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER}
          sed -i 's|IMAGE_PLACEHOLDER|${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}|' deployment.yaml
          kubectl apply -f deployment.yaml
          kubectl apply -f service.yaml
        """
    }
}
```

`deployment.yaml`에는 이미지 자리에 플레이스홀더(`image: IMAGE_PLACEHOLDER`)를 두고, `sed`가 적용 전에 실제 값으로 교체한다.

이 방법의 큰 장점은 매니페스트가 **단일 소스 오브 트루스(single source of truth)**로 유지된다는 것이다. 레플리카 수, 포트, 프로브, 리소스 제한 등 모든 필드가 함께 적용되므로 클러스터는 항상 저장소의 파일과 일치한다. 나중에 GitOps로 확장할 때도 자연스럽게 연결되는 방법으로, 권장하는 접근이다.

### 방법 B: `kubectl set image`

Deployment가 이미 존재하고 바뀌는 것이 *이미지 태그 하나뿐*이라면, YAML 파일을 건드리지 않고 그 필드만 직접 업데이트할 수 있다.

```bash
kubectl set image deployment/my-app \
  my-app=111122223333.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

"Deployment `my-app`에서 `my-app`이라는 컨테이너를 이 새 이미지로 설정하라"고 읽으면 된다. `=` 왼쪽의 컨테이너 이름은 Pod template의 `name:` 필드(4강)와 일치해야 한다.

간결하고 빠른 롤아웃에 좋지만, 미묘한 비용이 있다. *라이브* 상태와 *파일* 상태가 벌어질 수 있다. 클러스터는 `a1b9f3c` 태그를 실행하지만, Git의 `deployment.yaml`은 여전히 `IMAGE_PLACEHOLDER`나 이전 태그를 담고 있다. 학습 파이프라인이라면 `set image`로도 충분하다. 하지만 저장소를 정확하게 유지하고 싶다면 방법 A가 맞다.

### 롤아웃이 완료될 때까지 기다리기

두 명령 중 어느 것을 실행하든 롤아웃을 *시작*할 뿐이며, 거의 즉시 반환된다 — 새 Pod가 실제로 정상 상태가 될 때까지 기다리지 않는다. 파이프라인이 기다리게(그리고 롤아웃이 멈추면 실패하게) 하려면 다음을 추가한다.

```bash
kubectl rollout status deployment/my-app --timeout=120s
```

`kubectl rollout status`는 Deployment의 Pod가 모두 새 이미지로 정상 교체될 때까지 블로킹되고, 타임아웃 안에 완료되지 않으면 0이 아닌 종료 코드로 나온다. 이것이 중요하다. 없으면 파이프라인이 *배포를 요청한* 순간에 "성공"을 보고한다. 새 버전이 크래시 루프를 돌고 있어도. 있으면 문제가 있는 릴리스가 빌드를 빨간색으로 만든다 — 원하는 바로 그 것이다. 7강에서 거기서 롤백하는 방법을 보여준다.

완전한 배포 스테이지는 이렇다. 인증 → 이미지 갱신 → 롤아웃 성공 대기.

```groovy
stage('Deploy to EKS') {
    steps {
        sh """
          aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER}
          kubectl set image deployment/my-app my-app=${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
          kubectl rollout status deployment/my-app --timeout=120s
        """
    }
}
```

### 롤아웃이 실제로 어떻게 동작하는가

이미지를 변경하면 Deployment가 모든 것을 한꺼번에 종료하고 새로 시작하지 않는다. 기본적으로 **롤링 업데이트**를 수행한다. 새 이미지로 새 Pod를 시작하고, 준비가 됐는지 기다린 다음, 구버전 Pod를 조금씩 종료한다 — 항상 작동하는 버전이 트래픽을 받는다. 메커니즘(그리고 이를 게이팅하는 헬스체크)은 7강에서 자세히 다룬다. 지금 핵심은 한 줄의 이미지 변경이 신중하고 점진적인 무중단 교체를 트리거한다는 것이다.

### 커밋 SHA 태그가 여기서 빛을 발하는 이유

배포 스테이지가 `IMAGE_TAG` — 빌드가 생성한 바로 그 커밋 SHA — 를 클러스터로 바로 전달한다. 2강부터 추적해온 실이 여기서 팽팽해지는 순간이다. 푸시한 커밋이 빌드한 이미지를 결정하고, ECR의 태그를 결정하고, EKS가 실행하는 것을 정확히 결정한다. 태그가 고유하고 불변이므로, 바꾸면 *항상* 롤아웃이 트리거된다(Pod template이 바뀐 것을 쿠버네티스가 감지한다). 그리고 실행 중인 Pod를 보면 단일 커밋으로 추적할 수 있다.

> 흔한 함정: `latest` 태그로 배포하면 종종 **아무것도 일어나지 않는다.** 쿠버네티스 관점에서 Deployment spec이 바뀌지 않았으므로 롤아웃이 트리거되지 않는다. 고유한 커밋 SHA 태그는 이 함정을 완전히 피한다 — 2강에서 `latest`를 금지한 또 하나의 이유다.

### 완성된 그림

이제 엔드-투-엔드 파이프라인이 완성됐다. **GitLab에 푸시 → 웹훅 → Jenkins가 체크아웃·테스트·빌드·커밋 태그 이미지를 ECR에 푸시 → Jenkins가 EKS에 인증하고 Deployment를 갱신 → EKS가 롤링 업데이트 수행 → `kubectl rollout status`가 성공을 확인.** 한 번의 푸시, 완전 자동, 프로덕션까지.

이것을 *자신의* 코드에 적용하려면 프로젝트 특화 부분만 바꾸면 된다. `Dockerfile`, `deployment.yaml` / `service.yaml`(이미지와 포트), `Jenkinsfile`의 환경 변수(계정 ID, 리전, 리포지토리 이름, 클러스터 이름). 파이프라인 구조 자체는 바뀌지 않는다.

## 핵심 정리
- 배포 스테이지의 역할은 새 이미지 태그를 클러스터의 Deployment에 넣고, 롤아웃 완료를 기다리는 것이다.
- 이미지 업데이트 두 가지 방법: 매니페스트를 다시 작성하고 `kubectl apply -f`(파일을 소스 오브 트루스로 유지 — 권장), 또는 `kubectl set image deployment/<d> <container>=<image>:<tag>`(간결하지만 저장소와 벌어질 수 있다).
- 항상 `kubectl rollout status --timeout=...`를 따라붙여서 문제가 있는 릴리스가 파이프라인을 실패시키도록 한다. 조용히 "성공"하면 안 된다.
- 고유한 커밋 SHA 태그를 전달하면 롤아웃이 보장되고 모든 Pod를 추적할 수 있다. `latest`를 배포하면 아무것도 안 될 수 있다.
- 완성된 파이프라인은 GitLab 단일 푸시로 EKS의 롤링 배포까지, 수동 단계 없이 이어진다.
