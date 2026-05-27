---
lecture_no: 5
title: Deploying with YAML Manifests - Declarative Configuration in Practice
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=YZ3cdDBYY9I
  - https://www.youtube.com/watch?v=Dn3RkWlPDAk
  - https://www.youtube.com/watch?v=HkVYcfva9vw
---

# Deploying with YAML Manifests - Declarative Configuration in Practice

## Learning Objectives
- Understand the difference between imperative and declarative deployment approaches
- Write YAML manifests for a Deployment and a Service from scratch
- Apply manifests with `kubectl apply` and verify the results

## Lecture

### Why Deploy with YAML?

In Lectures 3 and 4 we created Pods and Deployments using commands like `kubectl run` and `kubectl create deployment`. One line and you are done — fast and convenient. In real-world environments, however, resources are almost never created this way. Instead, teams **describe the desired state in a YAML file** and apply that file to the cluster. In this lecture you will learn why, and practice the technique hands-on.

> YAML (YAML Ain't Markup Language) is a human-readable configuration file format. In Kubernetes, it acts as a blueprint that specifies "what resource to run and what it should look like."

### Imperative vs. Declarative — The Core Difference

The distinction between the two approaches comes down to one sentence:

- **Imperative**: You tell Kubernetes *what to do*, step by step. Examples: `kubectl run`, `kubectl create`, `kubectl delete`. You explicitly dictate each action.
- **Declarative**: You tell Kubernetes *what the end state should look like*. Examples: YAML file + `kubectl apply`. Kubernetes figures out on its own how to get there.

Think of it like ordering at a restaurant. The imperative approach is walking into the kitchen and barking orders: "Light the burner, grill the patty, toast the bun." The declarative approach is simply saying **"One cheeseburger, please."** The kitchen (Kubernetes) compares the current state to the desired state and fills in whatever is missing.

This continuous process of **adjusting the current state to match the desired state** is called the **reconciliation loop**. It is exactly what makes the declarative approach so powerful. Applying the same YAML file two or three times always produces the same result (idempotency), and if someone deletes a Pod, Kubernetes automatically restores the declared state.

As shown in the diagram below, the reconciliation loop endlessly repeats: compare desired state to current state → adjust if there is a difference → compare again.

```mermaid Reconciliation loop that continuously enforces the declared state
flowchart LR
    A["Desired State<br/>(YAML declaration)"] --> B{"Does it match<br/>current state?"}
    C["Current State<br/>(live cluster)"] --> B
    B -- "Match" --> D["No action needed"]
    B -- "Mismatch" --> E["Create or delete resources<br/>to close the gap"]
    E --> C
    D --> B
```

The practical advantages of the declarative approach:

- **Version control**: Store YAML files in Git to track changes and roll back when needed.
- **Reproducibility**: Use the same file to deploy identical configurations across development, staging, and production.
- **Collaboration**: Share the file with teammates and anyone can recreate the exact same resources.
- **Reviewability**: Changes can go through code review (pull requests) before being applied to the cluster.

> For experimentation and learning, `kubectl run` works just fine. For production, YAML + `kubectl apply` is the right approach.

### The Common Structure of Every Manifest

Regardless of whether the resource is a Pod, a Deployment, or a Service, every manifest starts with the same four top-level fields:

| Field | Description |
|-------|-------------|
| `apiVersion` | The Kubernetes API version to use (varies by resource type) |
| `kind` | The type of resource to create (Pod, Deployment, Service, etc.) |
| `metadata` | Identifying information such as the resource name and labels |
| `spec` | The actual specification describing the desired state of the resource |

The field beginners get wrong most often is `apiVersion`, because the value differs by resource type. Pods and Services use `v1`; Deployments use `apps/v1`. YAML also **uses indentation (2 spaces) to represent hierarchy**, so always use spaces instead of tabs and leave exactly one space after each colon (`:`).

### Exercise 1 — Writing a Deployment Manifest

Let's write a Deployment that runs the nginx web server with 2 replicas. Create a file called `nginx-deployment.yaml`.

```yaml
apiVersion: apps/v1          # Deployments use apps/v1
kind: Deployment
metadata:
  name: nginx-deployment      # The name of this Deployment
  labels:
    app: nginx
spec:
  replicas: 2                 # Number of Pods to run (desired state)
  selector:
    matchLabels:
      app: nginx              # Pods with this label are managed by this Deployment
  template:                   # Blueprint for the Pods to be created
    metadata:
      labels:
        app: nginx            # Must match the selector above
    spec:
      containers:
        - name: nginx         # Container list — uses '-' because it is a YAML sequence
          image: nginx:1      # The tag nginx project maintains as the latest in the major-1 line
          ports:
            - containerPort: 80
```

The critical rule is that the label in `selector` and the label in `template` **must match exactly**. The Deployment uses this label to identify which Pods it is responsible for. A mismatch produces an error at apply time.

> **A note on image tags:** A tag is not a mechanism that automatically tracks version updates — it is simply a **movable pointer** (alias) that points to a specific image. The reason `nginx:1` refers to the latest image in the nginx 1.x line is that **the nginx project has a policy of continually moving the `1` tag to the newest 1.x release** — not because any single-digit tag universally means "latest in that major line." Tag conventions vary by image: writing `image:2` for some other image does not guarantee it will always resolve to the latest 2.x release. Furthermore, because `nginx:1` can resolve to a different actual version over time, it reduces reproducibility. For production, pin the full version explicitly — for example, `nginx:1.27.4` — so every deployment pulls exactly the same image regardless of when it runs.

### Exercise 2 — Writing a Service Manifest

Pods created by a Deployment are only reachable inside the cluster, and their IPs change every time they are replaced. To allow external access, you need a **Service** — a stable entry point. Create `nginx-service.yaml`.

```yaml
apiVersion: v1               # Services use v1
kind: Service
metadata:
  name: nginx-service
spec:
  type: NodePort             # Expose the Service on a port of each node (ClusterIP also assigned automatically)
  selector:
    app: nginx               # Forward traffic to Pods with this label
  ports:
    - port: 80               # The port the Service listens on
      targetPort: 80         # The port to forward to inside the Pod (container)
      nodePort: 30080        # The node port accessible from outside (30000–32767)
```

The Service uses the same `selector` label (`app: nginx`) to find its target Pods. Because this matches the label on the Pods created by the Deployment, the Service automatically distributes traffic across those 2 Pods. You do not need to know any Pod's IP, and even when a Pod is replaced, the label match keeps traffic flowing seamlessly.

> **A note on `nodePort`:** Hardcoding a value like `30080` can cause `kubectl apply` to fail if that port is already in use by another Service. In production, the safest approach is to **omit the `nodePort` field entirely** — Kubernetes will then auto-assign a free port in the 30000–32767 range. Run `kubectl get service nginx-service` and check the `PORT(S)` column to find the assigned port. For this course, however, keeping a fixed value (`30080`) is more convenient since you always know which port to hit. A good rule of thumb: **omit `nodePort` in production (let Kubernetes assign it), pin it in development and learning exercises.**

As shown in the diagram below, both the Deployment and the Service connect to the same Pod set through the shared `app: nginx` label. All connectivity depends on this label matching correctly.

```mermaid Deployment, Service, and Pod relationships linked by the app: nginx label
flowchart TB
    Dep["Deployment<br/>nginx-deployment<br/>replicas: 2"]
    Svc["Service<br/>nginx-service<br/>type: NodePort"]
    P1["Pod<br/>app=nginx"]
    P2["Pod<br/>app=nginx"]

    Dep -- "creates and manages<br/>via template" --> P1
    Dep -- "creates and manages<br/>via template" --> P2
    Svc -- "routes traffic via<br/>selector app=nginx" --> P1
    Svc -- "routes traffic via<br/>selector app=nginx" --> P2
```

### Exercise 3 — Applying Manifests with kubectl apply and Verifying Results

Apply the manifests to the cluster. Use `apply` rather than the imperative `create`:

```bash
kubectl apply -f nginx-deployment.yaml
kubectl apply -f nginx-service.yaml
```

```
deployment.apps/nginx-deployment created
service/nginx-service created
```

> `create` only creates a resource when it does not yet exist; `apply` means "make the cluster match this state." Edit the file and run `apply` again, and only the changed parts are updated. This is the essence of declarative operations.

Now verify the results:

```bash
kubectl get deployment
kubectl get pods
kubectl get service
```

```
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
nginx-deployment   2/2     2            2           20s

NAME                                READY   STATUS    RESTARTS   AGE
nginx-deployment-7d9c5b8f6c-abcde   1/1     Running   0          20s
nginx-deployment-7d9c5b8f6c-fghij   1/1     Running   0          20s

NAME            TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
nginx-service   NodePort   10.96.120.45    <none>        80:30080/TCP   18s
```

`READY 2/2` means both requested replicas are up. Look at the Pod names: `nginx-deployment-7d9c5b8f6c-abcde` is made of three parts — **`<Deployment name>-<ReplicaSet hash>-<Pod unique suffix>`**.

- `nginx-deployment` — the **Deployment's name**, exactly as we wrote it
- `7d9c5b8f6c` — a hash identifying the **ReplicaSet** the Deployment created automatically. All Pods spun out by the same ReplicaSet share this middle segment (you can verify with `kubectl get replicaset`, where you will find `nginx-deployment-7d9c5b8f6c`)
- `abcde` — a **random suffix unique to each Pod**. Even Pods from the same ReplicaSet have different suffixes

This three-part name directly reflects the three-tier ownership chain: Deployment → ReplicaSet → Pod. We will revisit this chain in a moment.

To see the declarative approach's power, force-delete one of those Pods:

```bash
kubectl delete pod nginx-deployment-7d9c5b8f6c-abcde
kubectl get pods
```

```
NAME                                READY   STATUS    RESTARTS   AGE
nginx-deployment-7d9c5b8f6c-fghij   1/1     Running   0          90s
nginx-deployment-7d9c5b8f6c-klmno   1/1     Running   0          5s
```

The moment the Pod is deleted, Kubernetes brings up a new one to restore the count to 2. Notice that the new Pod shares the same ReplicaSet hash (`7d9c5b8f6c`) but has a new unique suffix (`klmno`) — the same ReplicaSet created a fresh replacement. The reconciliation loop continuously enforces "2 replicas" as declared.

Finally, verify everything is working:

```bash
curl http://localhost:30080
```

If you see `Welcome to nginx!` in the response, the deployment is a success. When you are finished with the exercise, clean up:

```bash
kubectl delete -f nginx-service.yaml -f nginx-deployment.yaml
```

### The Full Apply Flow — Deployment → ReplicaSet → Pod

Let's be precise about what happens inside the cluster when you apply a manifest. There is a common misconception here: **a Deployment does not create Pods directly.** Responsibility is delegated down a three-tier chain:

1. The user sends a YAML (desired state) to the **API Server** via `kubectl apply`.
2. The API Server stores the desired state in **etcd**.
3. The **Deployment controller** detects the Deployment. Rather than creating Pods itself, it creates a **ReplicaSet object**. (A ReplicaSet is a simpler controller whose only job is "keep N identical Pods running." Deployment wraps ReplicaSet to add version management and rolling updates on top.)
4. The **ReplicaSet controller** detects the new ReplicaSet and creates the **Pod objects** specified in `replicas`.
5. The **Scheduler** finds the unscheduled Pods and assigns each one to an appropriate node.
6. The **kubelet** on each selected node picks up its assigned Pods and starts the actual containers, then reports status back to the API Server.

The chain of responsibility is: **Deployment (version management and rollouts) → ReplicaSet (replica count maintenance) → Pod (actual execution)**. The three-part Pod name you saw earlier mirrors this chain exactly. The "self-healing" from Lecture 4 actually happens at the ReplicaSet level; Deployment sits above it and handles new-version rollouts by creating a new ReplicaSet and gradually shifting traffic over.

The sequence diagram below shows this flow in chronological order. Notice that the Deployment controller and ReplicaSet controller are listed as separate participants, illustrating how responsibility is handed off one step at a time.

```mermaid A single kubectl apply flows through Deployment → ReplicaSet → Pod delegation to reach a running container
sequenceDiagram
    participant U as User (kubectl)
    participant API as API Server
    participant ETCD as etcd
    participant DC as Deployment Controller
    participant RC as ReplicaSet Controller
    participant SCH as Scheduler
    participant KUBELET as kubelet (node)

    U->>API: kubectl apply — send YAML desired state
    API->>ETCD: persist desired state
    API-->>U: acknowledgment (created)
    DC->>API: detect Deployment
    DC->>API: request ReplicaSet creation
    RC->>API: detect ReplicaSet
    RC->>API: request Pod creation (replicas count)
    SCH->>API: find unscheduled Pods, assign nodes
    KUBELET->>API: check Pods assigned to this node
    KUBELET->>KUBELET: start containers
    KUBELET->>API: report status (Running)
```

## Key Takeaways
- The imperative approach instructs Kubernetes *what actions to perform* (`kubectl run/create`); the declarative approach declares *what the desired state should be* (YAML + `kubectl apply`).
- The declarative approach is better for version control, reproducibility, and team collaboration. The reconciliation loop guarantees idempotency and self-healing.
- Every manifest has four fields: `apiVersion`, `kind`, `metadata`, and `spec`. Pods and Services use `v1`; Deployments use `apps/v1`.
- Both Deployments and Services find their target Pods through `selector` labels — label matching is critical.
- Omitting `nodePort` lets Kubernetes auto-assign a free port in the 30000–32767 range, avoiding port conflicts — the recommended approach for production. You can find the assigned port with `kubectl get service`. For learning and exercises, pinning a fixed value like `30080` is more convenient. The rule of thumb: **omit in production, pin in development.**
- An image tag is a **movable pointer** to a specific image, not an automatic version-tracking mechanism. `nginx:1` refers to the latest in the 1.x line because that is the **nginx project's own tagging policy** — it is not a universal rule. Tag conventions vary by image, and because the resolved version can change over time, always pin an explicit patch version (e.g., `nginx:1.27.4`) in production for reproducible deployments.
- Pod names follow the **`<Deployment name>-<ReplicaSet hash>-<Pod unique suffix>`** structure. The middle segment identifies the ReplicaSet; the last segment is unique to each Pod.
- A Deployment does not create Pods directly. The chain is **Deployment → ReplicaSet → Pod**: the ReplicaSet handles replica count maintenance (self-healing), while the Deployment manages versions and rollouts by creating and replacing ReplicaSets.
- Apply with `kubectl apply -f` and verify with `kubectl get`. Running `apply` again after editing the file updates only the changed portions.
