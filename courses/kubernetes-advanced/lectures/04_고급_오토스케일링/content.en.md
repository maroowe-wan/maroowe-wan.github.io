---
lecture_no: 4
title: Advanced Autoscaling — VPA, Cluster Autoscaler, and KEDA
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=hsJ2qtwoWZw
  - https://www.youtube.com/watch?v=3lcaawKAv6s
  - https://www.youtube.com/watch?v=jM36M39MA3I
---

# Advanced Autoscaling — VPA, Cluster Autoscaler, and KEDA

## Learning Objectives
- Understand how Vertical Pod Autoscaler (VPA) automatically adjusts Pod requests/limits and explain its differences from HPA
- Understand how Cluster Autoscaler scales nodes up and down at the infrastructure level
- Configure KEDA to scale workloads based on event-driven metrics such as queue length or message count

## Content

### Three Orthogonal Axes of Autoscaling

You are already familiar with HPA (Horizontal Pod Autoscaler), which adjusts the number of Pods based on CPU or memory usage. In practice, however, autoscaling happens along three distinct axes. Keeping them straight from the start is essential.

- **Horizontal** — Adjusts the **number** of Pods. HPA, and the event-driven KEDA. Changes how many replicas to run.
- **Vertical** — Adjusts the **size** (requests/limits) of each individual Pod. VPA. **The replica count stays the same; the amount of resources given to each Pod changes.**
- **Node-level** — Adjusts the **number of nodes** available for Pods to run on. Cluster Autoscaler and Karpenter.

The most common misconception is worth addressing upfront. **VPA is not playing the same role as HPA or KEDA.** Where HPA/KEDA answer "how many Pods should we run?", VPA answers "how much resource should we give each Pod?". The axes are orthogonal. When HPA or KEDA scale out, newly created Pods need nodes to land on; if no node has capacity, they go Pending, and that is when Cluster Autoscaler adds nodes. Likewise, when VPA restarts a Pod at a larger size, if no node can accommodate it, the Pod also goes Pending — not because the count increased, but because the size did. VPA can therefore indirectly trigger node scaling, but through size increase rather than count increase.

The diagram below shows what each scaler adjusts (count vs. size vs. node count) and how they complement one another. Horizontal (HPA/KEDA) and vertical (VPA) are separate orthogonal axes; when either causes Pods to go Pending, the node axis (CA) steps in.

```mermaid Three Orthogonal Axes of Autoscaling — Count (HPA/KEDA), Size (VPA), Node Count (CA)
flowchart TD
    subgraph HORI["Horizontal Axis — Adjust Pod Count"]
        HPA["HPA - adjust replica count by CPU/memory"]
        KEDA["KEDA - adjust replica count by event/queue length"]
    end
    subgraph VERT["Vertical Axis — Adjust Pod Size (count stays the same)"]
        VPA["VPA - grow requests/limits, recreate Pod"]
    end
    subgraph NODEAXIS["Node Axis — Adjust Node Count"]
        CA["Cluster Autoscaler / Karpenter - adjust node count"]
    end
    HPA -->|"Pod count increases"| PENDING{"Is there a node available?"}
    KEDA -->|"Pod count increases"| PENDING
    VPA -->|"Larger Pod recreated"| PENDING
    PENDING -->|"No (Pending)"| CA
    CA --> ADD["Add node, then schedule Pod"]
    PENDING -->|"Yes"| SCHED["Schedule on existing node"]
```

### VPA — Automatically Right-Sizing Pods

Nobody knows exactly what `requests`/`limits` to set when first creating a Deployment. Set them too low and you get OOMKills and throttling; set them too high and you waste node resources. VPA observes a Pod's actual usage and either **recommends** or **automatically applies** appropriate requests and limits.

VPA consists of three components. The **Recommender** analyzes usage history and computes target values; the **Updater** evicts Pods whose resource allocation has drifted far from the recommendation; and the **Admission Controller** injects the recommended values into newly created Pods.

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

`updateMode` has three options:

- **`Off`** — Only computes and displays recommendations without touching running Pods (check with `kubectl describe vpa web-vpa`). The safest option when first introducing VPA.
- **`Initial`** — Applies the recommended values **only when a Pod is newly created**, without evicting running Pods. A good middle ground when the frequent restarts of `Auto` mode are disruptive.
- **`Auto`** — Actively evicts Pods that have drifted far from the recommendation and recreates them at the new size. The highest level of automation, but it involves Pod restarts.

The recommended approach is to start with `Off`, observe for a few days, then move to `Initial` if restarts are a concern, or `Auto` if you want full automation.

> **HPA vs VPA — The Most Important Pitfall.** Never apply HPA and VPA to the **same CPU/memory metric simultaneously**. They will invalidate each other's decisions (HPA tries to adjust Pod count, VPA tries to adjust Pod size, both driven by the same signal, creating a feedback loop). The key is **not letting them compete over the same metric** — it does not mean you can never use both for the same workload. One effective advanced pattern is to run **VPA in `Off` mode to get recommendations, then use those recommendations to tune HPA's `requests` and `targetCPUUtilizationPercentage`** (VPA recommends, HPA scales). If you must run both in automatic mode simultaneously, separate their signals — for example, give HPA a custom or external metric while letting VPA manage only memory. Also note that `Auto` mode evicts Pods, so always configure a PodDisruptionBudget alongside it to protect availability.

### Cluster Autoscaler — Adding and Removing Nodes

Cluster Autoscaler (CA) monitors **unschedulable (Pending) Pods** in the cluster. When Pods are stuck in the Pending state due to insufficient resources, CA requests that the cloud provider's node group (AWS ASG, GKE node pool, etc.) add a node. Once the new node becomes Ready, the scheduler places the waiting Pods on it.

CA also scales down. It removes a node only when **all** of the following conditions are met:

- The combined resource **requests** on that node fall below a utilization threshold (roughly 50% by default),
- All Pods on the node **can be rescheduled** on other nodes (capacity exists elsewhere),
- Doing so would **not violate any PodDisruptionBudget**, and
- None of the Pods on the node have local storage or a `safe-to-evict: false` annotation.

When all conditions pass, CA safely drains the Pods and removes the node to reduce cost. This is not simply "shut it down when idle" — it is **draining a node while respecting availability and PDB constraints**.

For CA to work correctly, **every Pod must have sensible resource requests**. CA uses requests to calculate "is there room on this node?" and "can this node be safely emptied?" Without requests, CA may incorrectly conclude a node has capacity, or miscalculate whether a node can be drained. Always set `min`/`max` sizes on the node group to cap both cost and scaling behavior.

```yaml
# Pods need requests for CA's node calculations to be accurate
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
```

**Karpenter** is increasingly popular and takes a different approach. Where Cluster Autoscaler adjusts the size of predefined node groups (ASG/node pool), **Karpenter is not bound to any node group**. It looks at the actual requirements of pending Pods (CPU, memory, architecture, availability zone, etc.) and directly selects the most suitable instance type from the cloud API on the fly. This eliminates the need to pre-partition node groups into fine-grained pools and improves bin-packing efficiency and cost optimization. The concept is the same — "if Pods have nowhere to go, provision a node; if a node is empty, remove it" — but the key difference is that "which node to provision" is decided dynamically based on workload requirements rather than being constrained to a predefined group.

### KEDA — Events as the Scaling Signal

HPA fundamentally reacts to resource metrics like CPU and memory. But consider a message queue worker: the CPU might be idle while **100,000 messages are backed up in the queue**. What is needed is scaling in proportion to queue depth. **KEDA (Kubernetes Event-Driven Autoscaling)** solves this problem.

KEDA's power comes from two features. First, it ships with **dozens of built-in event sources (scalers)** — Kafka, RabbitMQ, AWS SQS, Prometheus queries, Redis, cron, and more. Second, it supports **scale-to-zero**: when there are no events, Pods drop to 0 to save resources and wake up the moment messages arrive. Pure HPA must keep at least 1 replica running, which makes this a decisive difference.

Internally, KEDA acts as an adapter that reads external metrics and converts them into a form that HPA can consume. KEDA polls the event source, generates metrics, and HPA adjusts the Pod count based on those metrics.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-worker-scaler
spec:
  scaleTargetRef:
    name: order-worker          # target Deployment
  minReplicaCount: 0            # scale to zero when no events
  maxReplicaCount: 30
  triggers:
    - type: rabbitmq
      metadata:
        queueName: orders
        host: amqp://guest:guest@rabbitmq.default.svc:5672/
        queueLength: "20"       # target message count per Pod
```

This configuration means "keep enough workers so that each Pod handles roughly 20 messages." With 200 messages in the queue, it scales out to approximately 10 workers; when the queue is empty, it converges to 0.

> KEDA is optimal for workloads like queues, streams, and batch workers where **external event volume is what determines load**. For web servers that handle user requests directly, HPA with CPU/latency metrics or a gateway-level metric is usually more natural. The key is choosing the right scaling signal to match your workload's characteristics.

## Key Takeaways
- Autoscaling spans three axes — **horizontal** (HPA/KEDA, Pod count), **vertical** (VPA, Pod size), and **node-level** (Cluster Autoscaler/Karpenter, node count). VPA's role is distinct from HPA/KEDA (size vs. count).
- VPA observes usage and either recommends (`Off`), applies at creation time (`Initial`), or automatically applies and evicts (`Auto`). Running VPA and HPA on the same metric causes conflicts; separate their signals, or use VPA's recommendations to tune HPA instead.
- Cluster Autoscaler adds nodes in response to Pending Pods and removes underutilized nodes only after verifying PDB compliance and reschedulability. Accurate resource requests on every Pod are required for correct calculations.
- Karpenter goes beyond predefined node groups, dynamically selecting the most cost-efficient instance type for each workload.
- KEDA uses external events such as queue length and message count as scaling signals and supports scale-to-zero (0↔N). Internally it creates HPA-compatible external metrics.
