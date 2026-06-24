---
lecture_no: 6
title: NetworkPolicy - Controlling Pod-to-Pod Traffic and Default Deny
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=IYB7fpBjXgA
  - https://www.youtube.com/watch?v=knnn2fPEL0M
---

# NetworkPolicy - Controlling Pod-to-Pod Traffic and Default Deny

## Learning Objectives
- Understand the flat network model that allows all traffic by default, and why controlling it is necessary
- Define allowed traffic using label selector-based ingress and egress rules
- Apply a default deny policy and write a NetworkPolicy that permits only specific communications

## Content

### The Default Is "Everything Goes Through" — The Risk of a Flat Network

Kubernetes networking rests on one simple premise: **every Pod in the cluster can communicate freely with every other Pod.** Each Pod receives a unique IP address, and any Pod can send traffic to any other Pod's IP or Service — regardless of namespace or node. This is called the **flat network model**.

When you are first learning Kubernetes, this is convenient. Without any extra configuration, a frontend can reach the backend, and the backend can reach the database. From a security standpoint, however, this is like an **office with no locks**. It means a test Pod from a completely unrelated team can freely connect to the DB Pod belonging to your payment service.

> The default network model is not "traffic passes unless there is a reason to block it" — it is "everything passes regardless of whether it should." If a security incident starts in one Pod, a flat network becomes a highway for attackers to perform lateral movement across the entire cluster.

The core security principle for containers is **zero trust** — "trust nothing by default; only open communications that are explicitly allowed." The Kubernetes tool that enforces this is **NetworkPolicy**. A NetworkPolicy is an object that uses label-based rules to declare which Pods may send traffic to or receive traffic from a given Pod (ingress and egress).

### NetworkPolicy in Context — A Different Layer from Ingress (L7)

It is easy to confuse **Ingress** (covered in the Intermediate Part 1 course) with **NetworkPolicy**, since both sound like "traffic control." However, they operate at entirely different layers.

| | Ingress (Intermediate Part 1) | NetworkPolicy (this lecture) |
|---|---|---|
| Layer | L7 (HTTP/HTTPS path and host) | L3/L4 (IP, port, protocol) |
| Direction | Routing **external → internal** traffic into the cluster | Allowing or blocking traffic **between Pods inside** the cluster |
| Question answered | "Which Service should handle this URL?" | "Who is this Pod allowed to talk to?" |
| Analogy | Reception desk at the building entrance | Access control on each individual office door |

In short, Ingress is a **router** that directs external HTTP requests to the appropriate Service based on path rules; NetworkPolicy is a **firewall** that allows or drops packets at the IP and port level as they flow between Pods. They are not competing solutions — they work together at different layers.

### A Critical Prerequisite — The CNI Must Support It

There is a trap that learners commonly fall into with NetworkPolicy. **Creating a NetworkPolicy object does not, by itself, enforce anything. The enforcement is performed by the CNI plugin, not by Kubernetes itself.** CNI (Container Network Interface) is the plugin specification responsible for connecting Pods to the network.

The Kubernetes API server accepts and stores a NetworkPolicy, but the actual work of dropping packets is done by the CNI. If you use **a CNI that does not support NetworkPolicy** (for example, certain plugins in their default configurations), even the most carefully crafted policy will be **silently ignored** and all traffic will continue to flow. No error is raised, which leads to the frustrating situation of "I applied the policy — why is nothing being blocked?"

> Before applying any NetworkPolicy, verify that your cluster's CNI supports it. **Calico, Cilium, and Weave Net** all support it. For managed services, you often need to explicitly enable the policy engine — for example, Azure Network Policy or Calico in AKS, or the VPC CNI policy engine in EKS. For local practice, start minikube with `--cni=calico`.

```bash
# Start a minikube cluster with Calico CNI for hands-on practice
minikube start --cni=calico

# Verify that Calico Pods are running
kubectl get pods -n kube-system | grep calico
```

### Setting Up the Lab — Creating the Test Targets

Let's create the "protected target" first. In production, workloads are managed as **Deployments rather than standalone Pods.** A Deployment keeps the desired number of replicas running, reschedules Pods if they crash, and supports rolling updates and rollbacks. We will follow that recommended practice here and create the backend as a Deployment. All work takes place in a dedicated namespace.

```bash
kubectl create namespace demo
```

Create the backend as an nginx Deployment and expose it as a Service. Because NetworkPolicy selects targets by **label**, the key detail is ensuring the Pod carries the `app=nginx` label.

Option 1 — Imperative approach (`kubectl create deployment` + `kubectl expose`):

```bash
# 1) Create the backend Deployment
kubectl create deployment backend --image=nginx -n demo

# 2) Add the app=nginx label to the Deployment (to match the policy selector)
#    kubectl create deployment sets app=backend by default, so we override it explicitly
kubectl label deployment backend app=nginx --overwrite -n demo
kubectl rollout restart deployment backend -n demo   # propagate the new label to the Pod

# 3) Expose the Deployment as a Service named backend
kubectl expose deployment backend --name=backend --port=80 -n demo
```

Option 2 — YAML manifest (lets you set labels correctly from the start — cleaner):

```yaml
# backend-deploy.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx         # ← the label NetworkPolicy will select
    spec:
      containers:
        - name: nginx
          image: nginx
          ports:
            - containerPort: 80
```

```bash
kubectl apply -f backend-deploy.yaml
kubectl expose deployment backend --name=backend --port=80 -n demo
```

> A standalone Pod (`kubectl run`) is fine for quickly spinning up a single instance to verify a concept in a learning context, but in practice it is rarely used — no controller manages its lifecycle, restarts, or scaling. This lecture uses a Deployment for the protected target. The short-lived client Pods used for testing, on the other hand, are single Pods launched with `--rm`; that is appropriate for one-off tests.

Now spin up a client Pod to attempt connections. Since it is only needed for a brief test, a standalone Pod is sufficient.

```bash
# A client Pod with curl available
kubectl run client --image=curlimages/curl -n demo -it --rm -- sh
```

Inside the `client` Pod, connect to the backend Service. Since no policy exists yet, the nginx welcome page comes back. This is proof of the "allow all" default state.

```sh
# Inside the client container shell
curl backend     # Outputs nginx default page HTML → communication works
```

### Step 1: Applying a Default Deny Ingress Policy

The security best practice is: **lock everything down first, then open only what is needed.** Start by applying a default deny policy that blocks all inbound (ingress) traffic.

Two fields are central to this. `podSelector` selects **which Pods the policy applies to**, and `policyTypes` specifies **which direction(s) to control** (Ingress/Egress). If you list `Ingress` in `policyTypes` but **write no ingress rules at all**, that itself means "no allowed inbound traffic = block everything."

```yaml
# default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: demo
spec:
  podSelector: {}          # {} = apply to all Pods in the namespace
  policyTypes:
    - Ingress              # Control the inbound direction
  # No ingress rules → all incoming traffic is blocked
```

```bash
kubectl apply -f default-deny.yaml
```

Now if you run `curl backend` from the `client` Pod, no response comes back — it **hangs and then times out.** NetworkPolicy is doing its job.

> `podSelector: {}` (an empty selector) means "no label condition = select all Pods in the namespace." The moment a Pod falls under a policy's selector, its traffic in that direction switches to "only explicitly allowed traffic passes." Remember that NetworkPolicy operates as a **whitelist (allow list)**.

### Step 2: Allowing Specific Traffic (Ingress Rules)

With the door locked, let's open exactly the one communication path we need. We will create a rule that says: "only Pods with the `access=granted` label may connect to nginx (`app=nginx`)."

```yaml
# allow-frontend.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-nginx
  namespace: demo
spec:
  podSelector:
    matchLabels:
      app: nginx           # The protected target: Pods labeled app=nginx
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              access: granted   # Only allow traffic from Pods with this label
      ports:
        - protocol: TCP
          port: 80              # Only on port 80
```

```bash
kubectl apply -f allow-frontend.yaml
```

Run a side-by-side test to confirm the policy works precisely:

```bash
# (a) Client with the correct label → connection succeeds
kubectl run good --image=curlimages/curl --labels="access=granted" \
  -n demo -it --rm -- curl --max-time 5 backend
# → Returns nginx HTML

# (b) Client without the label → blocked (timeout)
kubectl run bad --image=curlimages/curl \
  -n demo -it --rm -- curl --max-time 5 backend
# → No response, times out
```

The `access=granted` label acts as an **access badge**. Because policy rules match on labels rather than IP addresses or Pod names, the rule remains valid even when a Pod dies and is rescheduled with a new IP — as long as the label is present. This is why label selector-based control is so powerful in the dynamic world of Kubernetes. Running the backend as a Deployment makes this especially clear: every time a Pod is replaced, its IP changes, but the `app=nginx` label defined in the Pod template stays constant, so the policy applies without interruption. As the flow below shows, once default deny is in place, only traffic from matching labels passes through; everything else is dropped.

```mermaid Inbound traffic allow/deny decision flow after default deny is applied
flowchart TD
    A["client Pod attempts to connect to backend (app=nginx)"] --> B{"Is there a policy applied<br/>to the app=nginx Pod?"}
    B -->|"No"| C["Default allow<br/>(flat network)"]
    B -->|"default deny applied"| D{"Does the source Pod<br/>have the access=granted label?"}
    D -->|"Yes"| E{"Is the target port<br/>TCP 80?"}
    D -->|"No"| F["Blocked (timeout)"]
    E -->|"Yes"| G["Allowed → nginx responds"]
    E -->|"No"| F
```

Inside the `from` block, you can combine `podSelector` with the following:

- `namespaceSelector` — allow traffic from **namespaces** carrying a specific label (e.g., only the `team=frontend` namespace)
- `ipBlock` — allow a specific **IP/CIDR range** (external systems, node IPs, etc.)

> Writing `podSelector` and `namespaceSelector` inside **a single list item** in `from` creates an **AND** condition: "that Pod inside that namespace." Splitting them into **separate list items** creates an **OR** condition: "this Pod or that namespace." A single level of YAML indentation changes the semantics entirely — pay close attention.

### Step 3: Controlling Egress (Outbound Traffic)

So far we have dealt with "who is allowed in (ingress)." To tighten security further, you also need to restrict "where this Pod is allowed to go (egress)." This is useful, for example, to prevent application Pods from exfiltrating data to unknown external destinations.

The most common trap in egress control is **DNS**. If egress is locked down, Pods can no longer perform DNS lookups to resolve domain names — Kubernetes uses CoreDNS on port 53 — and the result is that "nothing reachable by name works anymore." When locking down egress, **always open DNS (UDP/TCP port 53) at the same time.**

A common security mistake here is opening port 53 with `to: - namespaceSelector: {}` — which allows port 53 to every Pod in every namespace. That is effectively opening cluster-wide port 53 traffic, violating the principle of least privilege. DNS queries only need to reach the **CoreDNS Pods in the `kube-system` namespace**, so the destination should be narrowed to exactly that. CoreDNS Pods typically carry the `k8s-app: kube-dns` label, and to identify the `kube-system` namespace in a selector, you need a label on it (for example, `kubernetes.io/metadata.name: kube-system`).

> Version and distribution compatibility note: The example below assumes the `kube-system` namespace carries the `kubernetes.io/metadata.name: kube-system` label and that CoreDNS Pods carry the `k8s-app: kube-dns` label. The `kubernetes.io/metadata.name` label is **automatically applied to all namespaces starting from Kubernetes 1.21 (beta) / 1.22 (GA)**, but it may be absent on older versions or certain custom distributions, and the DNS Pod label may also vary by distribution. Before applying this policy, verify the actual labels in your environment with `kubectl get ns kube-system --show-labels` and `kubectl get pods -n kube-system --show-labels | findstr dns` (use `grep dns` on Linux/macOS). If the label is missing, add it manually with `kubectl label namespace kube-system kubernetes.io/metadata.name=kube-system`, or adjust the selector in the example to match your actual labels.

```yaml
# allow-egress.yaml — backend may only reach CoreDNS and a specific DB (e.g., port 5432)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-egress
  namespace: demo
spec:
  podSelector:
    matchLabels:
      app: nginx
  policyTypes:
    - Egress
  egress:
    - to:                       # Allow DNS — scoped to CoreDNS in kube-system only
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    - to:                       # Allow communication to the database only
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
```

Notice that in the first `to` block for DNS, `namespaceSelector` and `podSelector` are placed **inside the same list item**. As explained earlier, this is an AND condition — the destination is precisely "CoreDNS Pods inside the `kube-system` namespace."

To put it all together: you lock every door with default deny, then use ingress and egress rules to open exactly the communication paths you need. The diagram below illustrates how NetworkPolicy controls bidirectional traffic for a Pod.

```mermaid Selectively allowing inbound and outbound channels over a default deny baseline
flowchart LR
    subgraph IN["Inbound (ingress)"]
        F1["Pod with access=granted"]
        F2["Pod without label"]
    end

    subgraph POD["Protected target (app=nginx)<br/>default deny applied"]
        NG["backend Pod"]
    end

    subgraph OUT["Outbound (egress)"]
        D1["CoreDNS (53)"]
        D2["postgres DB (5432)"]
        D3["All other destinations"]
    end

    F1 -->|"TCP 80 allowed"| NG
    F2 -.->|"blocked"| NG
    NG -->|"UDP/TCP 53 allowed"| D1
    NG -->|"TCP 5432 allowed"| D2
    NG -.->|"blocked"| D3
```

### Common Gotchas

- **Silent failure with an unsupported CNI.** As emphasized earlier, policies are silently ignored on CNIs that do not support NetworkPolicy — no error, no warning. If traffic that should be blocked is passing through, suspect the CNI first.
- **Policies are namespace-scoped.** A NetworkPolicy applies only to Pods in the namespace specified in its metadata. To restrict Pods in another namespace, create a separate policy in that namespace or reference it with `namespaceSelector`.
- **Multiple policies are unioned (OR/additive).** When multiple NetworkPolicies apply to a single Pod, the **union** of all their allowed traffic is permitted. There are no "deny" rules — NetworkPolicy is purely additive. The only way to block traffic is to never add an allow rule for it, using default deny as the baseline.
- **Each direction is independent.** Blocking ingress leaves egress wide open, and vice versa. To control both directions, specify both in `policyTypes`.
- **Do not over-broaden the DNS egress destination.** Opening port 53 with `namespaceSelector: {}` allows it to every Pod in the cluster — a security risk. Narrow the destination to the CoreDNS Pods in `kube-system` (`k8s-app: kube-dns`) as shown above. Keep in mind that the namespace and Pod labels used in the selector may differ across environments — verify actual labels before applying.
- **Omitting ports opens all ports.** If you write a `from`/`to` clause without a `ports` block, all ports to or from that source are allowed. Always specify only the ports you need.

## Key Takeaways
- Kubernetes uses a **flat network model where all Pods can communicate freely by default.** Zero-trust control is required for security, and the tool for it is **NetworkPolicy (L3/L4)**. It operates at a different layer from Ingress (L7, external routing).
- NetworkPolicy only works if the **CNI plugin (Calico, Cilium, Weave Net, etc.) supports and enforces it.** On an unsupported CNI, policies are silently ignored — always verify CNI support before relying on policies.
- Policies follow a **whitelist** model. Use `podSelector` to select target Pods, `policyTypes` to choose a direction, and leave the rules block empty to block all traffic in that direction (default deny).
- In production, manage protected workloads as **Deployments with a label (`app=nginx`) that the policy selects.** A standalone Pod (`kubectl run`) is suitable only for learning or one-off tests. Because the label is defined in the Pod template, it persists across restarts and rescheduling — policies apply regardless of IP changes.
- Allow rules are defined using **label selectors** (`podSelector` / `namespaceSelector`), `ipBlock`, and ports. Because rules match labels rather than IPs, they survive Pod rescheduling.
- When locking down egress, **always open DNS (port 53) as well** — but narrow the destination to the CoreDNS Pods in `kube-system` (`k8s-app: kube-dns`). Using `namespaceSelector: {}` to open port 53 to everyone is a security risk. The `kubernetes.io/metadata.name` label is automatically added to namespaces from Kubernetes 1.21 onward — verify labels in older or custom environments before applying. Multiple policies are applied as the union of all their allow rules.

## Sources
- Alta3 Research, "Navigating Kubernetes Networking: Tips and Tricks for Developers" — https://www.youtube.com/watch?v=IYB7fpBjXgA
- Microsoft Azure, "Securing traffic between pods using policies in Azure Kubernetes Service | Azure Tips and Tricks" — https://www.youtube.com/watch?v=knnn2fPEL0M
