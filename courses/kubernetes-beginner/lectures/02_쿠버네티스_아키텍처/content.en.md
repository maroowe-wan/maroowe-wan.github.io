---
lecture_no: 2
title: Kubernetes Architecture - Control Plane and Worker Nodes
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=TlHvYWVUZyc
  - https://www.youtube.com/watch?v=vZ9gEqeddxQ
  - https://www.youtube.com/watch?v=VQUZF6k6g88
---

# Kubernetes Architecture - Control Plane and Worker Nodes

## Learning Objectives
- Distinguish the roles of a cluster, the control plane (formerly called "master"), and worker nodes
- Understand what each core component — API Server, Scheduler, etcd, kubelet — is responsible for
- Trace the sequence of steps a user command goes through inside the cluster

## Lecture

### Why You Need to Understand the Architecture

In Lecture 1 we learned that "Kubernetes automatically places containers and restarts them when they crash." But if you do not understand what that "automatically" actually means, you will be at a loss whenever something goes wrong. When a Pod fails to start, which component has stopped doing its job?

Kubernetes is not a magic black box — it is **a system of many small programs (processes) that communicate and cooperate with each other**. Once you have this structure clear in your mind, every hands-on exercise that follows becomes much easier. This lecture has no commands to run, but it lays the most important conceptual foundation for everything ahead.

Think of a Kubernetes cluster as **a large logistics company**. There are warehouses (worker nodes) where workers actually move and stack goods, and there is a central control room (the control plane) that tells those workers what to do, where, and how many.

### Cluster, Control Plane, and Worker Nodes

Let's start with the big picture.

- **Cluster**: The overall system that groups multiple machines (servers) together to run containerized applications. Think of it as the entire company. An organization might run several clusters simultaneously — one for production, one for testing, and so on.
- **Node**: A single machine that makes up the cluster. It can be a cloud virtual machine (e.g., EC2), a physical server, or even your laptop.

Nodes are divided into two types based on their role:

- **Control Plane (formerly called "master")**: The **brain** that manages the entire cluster and makes decisions. It receives user requests, decides where to run each container, stores the cluster's state data, and responds to failures. It does not run your applications directly — it is the command-and-control layer.
- **Worker Node**: The **workfloor** where your applications actually **run**. It receives instructions from the control plane and starts and maintains containers.

> In production environments, if the brain goes down the entire cluster is at risk, so the control plane is typically distributed across multiple nodes to ensure high availability. For testing purposes, it is perfectly fine to run both the control plane and workers on a single machine.

One important fact: **worker nodes do not run containers directly — they run units called Pods.** If Docker's smallest unit is a container, Kubernetes' smallest deployable unit is a Pod. A Pod contains one or more containers, and to scale up an application you simply run more Pods. (Pods are covered in detail in Lecture 3.)

### The 4 Core Components of the Control Plane

Inside the control room (control plane) there are four programs, each with a distinct role.

**1. API Server (the front desk)**
The **sole entry point** for every request entering the cluster. When you issue a command with `kubectl` (the Kubernetes CLI) or through the dashboard, you are actually talking to the API Server. Even the components on worker nodes communicate exclusively through the API Server. As the front desk, it also handles **authentication (verifying who you are) and authorization (verifying what you are allowed to do)**, as well as validating that requests are properly formed.

**2. etcd (the company ledger)**
A **key-value store** that holds all of the cluster's state data. Which nodes exist, which Pods are running where, what the user has requested — every "current fact" is recorded in etcd. This is why etcd is called the cluster's **single source of truth**. When you create a Pod, that information is written to etcd; when you delete it, it is removed from etcd.

**3. Scheduler (the placement coordinator)**
Decides **which worker node a newly created Pod should run on**. Rather than simply finding any open slot, the Scheduler considers the CPU and memory a Pod requires, the available resources on each node, and any constraints such as "keep this Pod near that Pod," then picks the most suitable node. It solves what is essentially a bin-packing problem — fitting multiple applications optimally onto a limited set of servers.

**4. Controller Manager (the floor supervisor)**
A set of background processes that continuously tries to **bring the system back to the user's desired state**. For example, if you declared via a Deployment or ReplicaSet that "3 Pods must be running" and one dies, the controller detects this and creates new Pod objects to restore the count. There are dedicated controllers for each resource type — a Node Controller that detects downed nodes, a Deployment Controller that manages rollouts, and so on. Kubernetes' self-healing capability lives here.

> The Controller Manager's job is to ensure the declared number of Pod *objects* exist — it does not directly start a Pod on a specific node. A Pod created by the controller starts out in a Pending state with no node assigned; it is only after the Scheduler selects a node that the kubelet on that node actually starts it.

> When running in a cloud environment, a Cloud Controller Manager is added to delegate cloud-specific tasks — such as provisioning virtual machines for nodes — to the cloud provider (AWS, GCP, or Azure).

### The 3 Core Components of a Worker Node

Each worker node (workfloor) runs three programs that together keep Pods running.

**1. kubelet (the on-site crew leader)**
An agent that runs on every worker node. It communicates with the control plane (API Server) to receive instructions about which Pods to run on its node, and takes responsibility for keeping those Pods alive and healthy. Think of it as the liaison connecting a node to the brain.

**2. Container Runtime (the container execution engine)**
The software that actually runs containers. It pulls images from a registry, starts and stops containers, and manages their resources. Docker comes to mind first, but it is only one of several available runtimes. Kubernetes can work with any runtime — containerd, CRI-O, and others — as long as it conforms to the standard **CRI (Container Runtime Interface)**. The kubelet directs this runtime to carry out actual execution.

**3. kube-proxy (the network traffic director)**
Manages the network rules on each node so that traffic — from inside and outside the cluster — is correctly routed and load-balanced to the right Pod.

The full cluster layout described above is summarized in the diagram below. Check where the control plane's four components and the worker node's three components each belong, and notice that **all communication arrows ultimately point to the API Server**. The Scheduler, Controller Manager, and each node's kubelet all **watch** (maintain a persistent subscription to) the API Server; when something changes, the API Server pushes that information back through those subscriptions. In other words, components reach out to the API Server, and the API Server sends back responses and events — the direction of connection runs from the components toward the API Server.

```mermaid Kubernetes cluster architecture — all components watch the API Server in a hub-and-spoke model
flowchart TB
    User["사용자 (kubectl)"]

    subgraph Cluster["쿠버네티스 클러스터"]
        subgraph CP["컨트롤 플레인 (두뇌)"]
            API["API Server<br/>유일한 정문·인증"]
            ETCD["etcd<br/>상태 저장소"]
            SCH["Scheduler<br/>노드 배치 결정"]
            CM["Controller Manager<br/>자가 치유"]
        end

        subgraph W1["워커 노드 1"]
            KL1["kubelet"]
            CR1["Container Runtime"]
            KP1["kube-proxy"]
            POD1["Pod"]
        end

        subgraph W2["워커 노드 2"]
            KL2["kubelet"]
            CR2["Container Runtime"]
            KP2["kube-proxy"]
            POD2["Pod"]
        end
    end

    User -->|명령 요청| API
    API <-->|상태 읽기·쓰기| ETCD
    SCH -->|watch·결정 쓰기| API
    CM -->|watch·결정 쓰기| API
    KL1 -->|watch·상태 보고| API
    KL2 -->|watch·상태 보고| API
    API -.->|변경 이벤트 응답| SCH
    API -.->|변경 이벤트 응답| KL1
    API -.->|변경 이벤트 응답| KL2
    KL1 -->|실행 지시| CR1
    KL2 -->|실행 지시| CR2
    CR1 -->|컨테이너 실행| POD1
    CR2 -->|컨테이너 실행| POD2
```

### How a User Command Is Processed

Now let's see how these components work together. Follow a "create a Pod" request as it moves through the cluster. **The key point is that every communication passes through the API Server.** The flow goes like this:

1. The user sends a "run this container as a Pod" request to the **API Server** via `kubectl`.
2. The API Server verifies authentication, authorization, and request format, then writes the Pod information to **etcd**. At this point the Pod is in a **Pending** state — no node has been assigned yet.
3. The **Scheduler** notices the unassigned Pending Pod, analyzes resource availability across worker nodes, picks the best fit, and writes that binding decision back to the API Server (which in turn saves it to etcd).
4. The **kubelet** on the selected worker node has been continuously watching the API Server. When it sees a Pod assigned to its node, it takes over and starts the Pod.
5. The kubelet instructs the node's **Container Runtime** to pull the image and launch the container — the Pod comes up.
6. The kubelet reports "this Pod is now Running" back to the API Server, and that state change is saved to etcd. Now when the user runs `kubectl get pod`, they see "Running."

Here is how to summarize the control plane's division of labor in a single sentence: **the Controller Manager ensures "what and how many" Pod objects exist, the Scheduler decides "where" each Pod goes, and the kubelet handles "actually running" it.** That is why the Controller Manager does not appear in the single Pod creation flow above — we explicitly created one Pod, so there is nothing for the Controller Manager to count or reconcile. Instead, the Scheduler assigns a node directly, and the kubelet on that node starts the Pod on its own.

The Controller Manager steps in under different circumstances: when a Deployment or ReplicaSet declares "keep N Pods running," it **creates Pod objects** to fill any shortfall. Crucially, the controller only creates the Pod *objects* to meet the declared count — it does not decide which node they go to. Those newly created Pods are also born in a Pending state with no node assigned, and they must go through **steps 3–6 above (Scheduler assigns a node → kubelet starts the Pod)** before they come up on any node. The Scheduler is a mandatory gate that every Pod, regardless of how it was created, must pass through.

Here is a critical detail about how watching works. Rather than the Scheduler and kubelet repeatedly polling the API Server asking "any new work?", they each set up a persistent **watch** subscription at startup. Whenever something relevant changes, the API Server pushes the event to them. That is why the arrows in the diagram represent a continuous subscription stream rather than one-off queries.

```mermaid Pod creation request flowing through the cluster in 6 steps — watch-based event delivery
sequenceDiagram
    participant U as 사용자(kubectl)
    participant API as API Server
    participant ETCD as etcd
    participant SCH as Scheduler
    participant KL as kubelet
    participant CR as Container Runtime

    Note over SCH,KL: 시작 시 API Server에 watch(지속 구독)를 걸어 둠
    SCH->>API: watch 구독 시작(미배치 Pod 감시)
    KL->>API: watch 구독 시작(내 노드 Pod 감시)

    U->>API: 1. Pod 실행 요청
    API->>API: 2. 인증·인가·형식 검증
    API->>ETCD: 2. Pod 정보 기록
    API-->>SCH: 3. 미배치 Pod 이벤트 푸시
    SCH->>API: 3. 최적 노드 선정 결과 쓰기(바인딩)
    API-->>KL: 4. 내 노드 배정 Pod 이벤트 푸시
    KL->>CR: 5. 컨테이너 실행 지시
    CR-->>KL: 5. Pod 실행 완료
    KL->>API: 6. 상태 보고(Running)
    API->>ETCD: 6. 상태 변화 저장
    U->>API: kubectl get pod
    API-->>U: Running
```

One more scenario worth thinking through. What happens if a Pod launched via a Deployment suddenly crashes? The **Controller Manager** detects that "the desired state (N Pods running) no longer matches the current state (N-1 Pods)" and creates a new Pod object to fill the gap. That new Pod is born in a Pending state with no node assigned, so it takes exactly the same path: **the Scheduler assigns a node (step 3) → the kubelet starts and reports the Pod (steps 4–6)**. This is how the cluster heals itself without any manual intervention.

## Key Takeaways
- A **cluster** is a collection of nodes, split into the **control plane** (makes decisions) and **worker nodes** (run applications).
- Control plane's 4 components: **API Server** (sole entry point · authentication), **etcd** (single source of truth for cluster state), **Scheduler** (decides which node a Pod runs on), **Controller Manager** (self-healing — ensures the declared number of Pod objects exists).
- Worker node's 3 components: **kubelet** (watches the API Server and directly starts/maintains Pods on its node), **Container Runtime** (actually runs containers), **kube-proxy** (network routing).
- Worker nodes run **Pods**, not bare containers.
- Every request and every internal message **must go through the API Server**. A single Pod creation flows: API Server → etcd → Scheduler (node assignment) → kubelet on that node (starts the Pod) → Container Runtime.
- The control plane's division of labor: **Controller Manager** ("what and how many" Pod objects exist) → **Scheduler** ("where" each Pod goes) → **kubelet** ("actually running" it). Pods created by the Controller Manager also start out Pending with no node assigned and must pass through the **Scheduler's node-assignment step** before the kubelet can start them — the Scheduler is a mandatory gate for every Pod, no matter how it was created.
