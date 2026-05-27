---
lecture_no: 4
title: 고급 오토스케일링 — VPA·Cluster Autoscaler·KEDA
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=hsJ2qtwoWZw
  - https://www.youtube.com/watch?v=3lcaawKAv6s
  - https://www.youtube.com/watch?v=jM36M39MA3I
---

# 고급 오토스케일링 — VPA·Cluster Autoscaler·KEDA

## 학습 목표
- Vertical Pod Autoscaler(VPA)로 Pod의 requests/limits를 자동 조정하는 방식을 이해하고 HPA와의 차이를 설명한다
- Cluster Autoscaler가 노드 수준에서 자동 확장·축소하는 원리를 이해한다
- KEDA로 큐 길이·메시지 수 같은 이벤트 기반 메트릭에 따라 스케일링을 구성할 수 있다

## 본문

### 세 가지 축으로 나눠 보는 오토스케일링

여러분은 이미 HPA(Horizontal Pod Autoscaler)로 CPU/메모리에 따라 Pod 개수를 늘리고 줄여 봤다. 하지만 실제 운영에서 오토스케일링은 세 가지 서로 다른 축으로 일어난다. 이 셋을 혼동하지 않는 것이 출발점이다.

- **수평(Horizontal) — Pod 개수를 조절.** HPA, 그리고 이벤트 기반의 KEDA. "복제본을 몇 개 둘까"를 바꾼다.
- **수직(Vertical) — Pod 하나의 크기(requests/limits)를 조절.** VPA. **개수는 그대로 두고, 한 Pod에 줄 자원의 양을 바꾼다.**
- **노드(Cluster) — Pod가 들어갈 노드 수를 조절.** Cluster Autoscaler, Karpenter.

여기서 가장 흔한 오해를 먼저 바로잡자. **VPA는 HPA·KEDA와 같은 역할이 아니다.** HPA·KEDA가 "Pod를 몇 개 띄울까(개수)"를 정한다면, VPA는 "이 Pod 하나에 자원을 얼마나 줄까(크기)"를 정한다. 축이 직교(orthogonal)한다. HPA·KEDA는 수요가 늘면 Pod **수**를 늘려 새 Pod가 노드를 못 찾으면 Pending이 되고, 그때 Cluster Autoscaler가 노드를 추가한다. VPA는 Pod를 재시작하며 **크기**를 키웠을 때, 그 큰 Pod를 받아 줄 노드가 없으면 역시 Pending이 될 수 있다 — 즉 VPA도 결과적으로 노드 스케일을 유발할 수 있지만, 그 메커니즘은 "개수 증가"가 아니라 "크기 증가"다.

아래 구성도는 세 축의 스케일러가 각각 무엇을 조절하며(개수 vs 크기 vs 노드 수), 어떻게 서로를 보완하는지를 보여 준다. 수평(HPA·KEDA)과 수직(VPA)은 서로 직교한 별개의 축이며, 둘 다 노드 부족(Pending)을 유발하면 노드 축(CA)이 받쳐 준다.

```mermaid 오토스케일링의 세 직교 축 — 개수(HPA/KEDA)·크기(VPA)·노드 수(CA)
flowchart TD
    subgraph HORI["수평 축 — Pod 개수 조절"]
        HPA["HPA - CPU/메모리로 복제본 수 증감"]
        KEDA["KEDA - 이벤트/큐 길이로 복제본 수 증감"]
    end
    subgraph VERT["수직 축 — Pod 크기 조절 (개수는 그대로)"]
        VPA["VPA - requests/limits 키워 Pod 재생성"]
    end
    subgraph NODEAXIS["노드 축 — 노드 수 조절"]
        CA["Cluster Autoscaler / Karpenter - 노드 수 증감"]
    end
    HPA -->|"Pod 수 증가"| PENDING{"받아 줄 노드가 있는가?"}
    KEDA -->|"Pod 수 증가"| PENDING
    VPA -->|"더 큰 Pod 재생성"| PENDING
    PENDING -->|"없음 (Pending)"| CA
    CA --> ADD["노드 추가 후 Pod 배치"]
    PENDING -->|"있음"| SCHED["기존 노드에 스케줄"]
```

### VPA — Pod의 적정 사이즈를 자동으로

처음 Deployment를 만들 때 `requests`/`limits`를 얼마로 줘야 할지 정확히 아는 사람은 없다. 너무 낮게 잡으면 OOMKill·스로틀링이 나고, 너무 높게 잡으면 노드 자원을 낭비한다. VPA는 Pod의 실제 사용량을 관찰해 **적정 requests/limits를 추천하거나 자동 적용**한다.

VPA는 세 컴포넌트로 구성된다. **Recommender**가 사용량 이력을 보고 권장값을 계산하고, **Updater**가 권장값과 동떨어진 Pod를 축출(evict)하며, **Admission Controller**가 새로 뜨는 Pod에 권장값을 주입한다.

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: web-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  updatePolicy:
    updateMode: "Auto"        # Off / Initial / Auto
  resourcePolicy:
    containerPolicies:
      - containerName: "*"
        minAllowed: { cpu: "50m", memory: "64Mi" }
        maxAllowed: { cpu: "2",   memory: "2Gi" }
```

`updateMode`에는 세 가지 선택지가 있다.

- **`Off`** — 추천값만 계산해서 보여 주고 실제로는 건드리지 않는다(`kubectl describe vpa web-vpa`의 추천값 확인). 도입 초기에 가장 안전하다.
- **`Initial`** — Pod가 **새로 생성될 때만** 권장값을 적용하고, 운영 중인 Pod는 축출하지 않는다. `Auto`의 잦은 재시작이 부담스러운 워크로드에 좋은 절충안이다.
- **`Auto`** — 권장값과 동떨어진 Pod를 적극적으로 축출(evict)하고 새 크기로 재생성한다. 자동화 수준이 가장 높지만 Pod 재시작을 수반한다.

도입 초기엔 `Off`로 며칠 관찰한 뒤, 재시작 부담이 크면 `Initial`로, 완전 자동화를 원하면 `Auto`로 단계적으로 올리는 것이 안전하다.

> **HPA vs VPA — 가장 중요한 함정.** HPA와 VPA를 **같은 CPU/메모리 메트릭**에 동시에 걸면 안 된다. 둘이 서로의 결정을 무효화하며 충돌한다(HPA는 Pod 수를, VPA는 Pod 크기를 같은 신호로 바꾸려 한다). 핵심은 **"같은 메트릭을 두고 경쟁시키지 않는 것"**이지, 워크로드 유형에 따라 둘 중 하나만 골라야 한다는 뜻이 아니다. 부하 분산 워크로드에도 VPA로 개별 Pod의 효율적 크기를 찾을 수 있다. 실제 고급 패턴 하나는 **VPA를 `Off` 모드로 운영해 얻은 권장값으로 HPA의 `requests`와 `targetCPUUtilizationPercentage`를 튜닝**하는 것이다(VPA는 추천만, HPA는 개수 조절을 담당). 굳이 둘을 동시에 자동 적용하려면 신호를 분리하라 — 예: HPA는 커스텀/외부 메트릭으로, VPA는 메모리만. 또한 `Auto` 모드는 Pod를 재생성(evict)하므로 PodDisruptionBudget을 함께 설정해 가용성을 지켜야 한다.

### Cluster Autoscaler — 노드를 늘리고 줄인다

Cluster Autoscaler(CA)는 클러스터 안에서 **스케줄되지 못한 Pod(Pending)**를 감시한다. 자원 부족으로 Pending 상태인 Pod가 생기면, CA는 클라우드 제공자의 노드 그룹(AWS ASG, GKE node pool 등)에 노드 추가를 요청한다. 새 노드가 Ready가 되면 스케줄러가 대기하던 Pod를 그 위에 배치한다.

축소(scale-in)도 한다. CA는 다음 조건을 모두 만족할 때만 노드를 제거한다.

- 해당 노드의 자원 **요청(requests) 합이 일정 사용률 임계값 미만**(기본 약 50%)으로 떨어졌고,
- 그 노드 위의 Pod들을 **다른 노드로 옮길 수 있으며**(스케줄 가능 자리 존재),
- 옮길 때 **PodDisruptionBudget을 위반하지 않고**,
- 로컬 스토리지를 쓰거나 `safe-to-evict: false` 같은 보호 표시가 없는 Pod인 경우.

이 조건들을 통과하면 CA는 Pod를 안전하게 비운 뒤 노드를 제거해 비용을 절감한다. 즉 단순히 "한가하면 끈다"가 아니라, **가용성과 PDB를 지키면서** 빈 노드를 정리하는 것이다.

CA가 똑똑히 동작하려면 **모든 Pod에 합리적인 resource requests가 있어야** 한다. CA는 requests를 기준으로 "이 노드에 더 들어갈 자리가 있나", "이 노드를 비울 수 있나"를 계산하기 때문이다. requests가 없으면 CA는 노드가 비었다고 오판하거나, 반대로 자리 계산을 틀린다. 또한 노드 그룹의 `min`/`max` 크기를 설정해 폭주를 막아야 한다.

```yaml
# Pod에 requests가 있어야 CA의 노드 계산이 정확해진다
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
```

요즘은 **Karpenter**도 널리 쓰인다. Cluster Autoscaler가 미리 정의된 노드 그룹(ASG/node pool)의 크기를 늘렸다 줄였다 하는 데 비해, **Karpenter는 노드 그룹에 묶이지 않는다.** 대기 중인 Pod들의 실제 요구(CPU·메모리·아키텍처·존 등)를 보고 그 순간 가장 적합한 인스턴스 타입을 클라우드 API로 직접 골라 띄운다. 그래서 노드 그룹을 미리 잘게 나눠 둘 필요가 없고, 빈자리(bin-packing) 효율과 비용 최적화가 더 좋다. 개념은 같다 — "갈 곳 없는 Pod가 있으면 노드를 만들고, 빈 노드는 정리한다" — 다만 "어떤 노드를 만들지"를 그룹에 가두지 않고 워크로드에 맞춰 즉석에서 정한다는 점이 핵심 차이다.

### KEDA — 이벤트가 곧 스케일 신호

HPA는 본질적으로 CPU/메모리 같은 자원 메트릭에 반응한다. 하지만 메시지 큐 워커를 생각해 보자. CPU는 한가한데 **큐에 쌓인 메시지가 10만 건**일 수 있다. 이때 필요한 건 "큐 길이에 비례한 스케일"이다. **KEDA(Kubernetes Event-Driven Autoscaling)**가 이 문제를 푼다.

KEDA의 강력함은 두 가지다. 첫째, Kafka·RabbitMQ·AWS SQS·Prometheus 쿼리·Redis·cron 등 **수십 종의 외부 이벤트 소스(scaler)**를 기본 제공한다. 둘째, **0에서 1로(scale-to-zero)** 스케일할 수 있다. 이벤트가 없으면 Pod를 0개로 내려 자원을 아끼고, 메시지가 들어오면 즉시 깨운다. 순수 HPA는 최소 1개를 유지해야 하므로 이 점이 결정적 차이다.

내부적으로 KEDA는 외부 메트릭을 읽어 HPA가 이해할 수 있는 형태로 변환해 주는 어댑터다. 즉 KEDA가 이벤트 소스를 폴링해 메트릭을 만들고, 그 메트릭으로 HPA가 Pod 수를 조정한다.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-worker-scaler
spec:
  scaleTargetRef:
    name: order-worker          # 대상 Deployment
  minReplicaCount: 0            # 이벤트 없으면 0까지 (scale-to-zero)
  maxReplicaCount: 30
  triggers:
    - type: rabbitmq
      metadata:
        queueName: orders
        host: amqp://guest:guest@rabbitmq.default.svc:5672/
        queueLength: "20"       # Pod 1개당 처리할 메시지 목표치
```

위 설정은 "큐의 메시지를 Pod 1개당 20건씩 처리하도록 워커 수를 맞춰라"는 의미다. 메시지 200건이 쌓이면 약 10개로 확장되고, 큐가 비면 0으로 수렴한다.

> KEDA는 큐·스트림·배치 워커처럼 **외부 이벤트량이 부하를 결정하는** 워크로드에 최적이다. 사용자 요청을 직접 받는 웹 서버는 여전히 HPA(CPU/지연시간)나 Gateway 메트릭이 더 자연스럽다. 워크로드 성격에 맞춰 스케일 신호를 고르는 것이 핵심이다.

## 핵심 요약
- 오토스케일링은 세 축으로 나뉜다 — **수평(HPA·KEDA, Pod 개수)**, **수직(VPA, Pod 크기)**, **노드(Cluster Autoscaler·Karpenter, 노드 수)**. VPA는 HPA·KEDA와 역할이 다르다(크기 vs 개수).
- VPA는 사용량을 관찰해 requests/limits를 추천(`Off`)·생성 시 적용(`Initial`)·자동 적용(`Auto`)한다. HPA와 **같은 메트릭**에 동시 자동 적용하면 충돌하므로, 신호를 분리하거나 VPA 권장값으로 HPA를 튜닝하는 식으로 함께 쓴다.
- Cluster Autoscaler는 Pending Pod를 보고 노드를 추가하고, 사용률 임계값·PDB·Pod 이동 가능성을 따져 저사용 노드를 비워 제거한다. 정확한 동작을 위해 모든 Pod에 resource requests가 필요하다.
- Karpenter는 노드 그룹에 묶이지 않고 워크로드 요구에 맞는 인스턴스를 즉석에서 띄워 비용·효율을 높인다.
- KEDA는 큐 길이·메시지 수 등 외부 이벤트를 스케일 신호로 삼고, scale-to-zero(0↔N)를 지원한다. 내부적으로 HPA용 외부 메트릭을 만들어 동작한다.
