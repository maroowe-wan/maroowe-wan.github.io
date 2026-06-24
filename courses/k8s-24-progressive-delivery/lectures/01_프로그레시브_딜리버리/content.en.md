---
lecture_no: 6
title: Progressive Delivery — Canary, Blue-Green, and PodDisruptionBudget
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=hIL0E2gLkf8
  - https://www.youtube.com/watch?v=84Ky0aPbHvY
  - https://www.youtube.com/watch?v=6zWfVqkKuyI
---

# Progressive Delivery — Canary, Blue-Green, and PodDisruptionBudget

## Learning Objectives
- Understand the differences between Canary, Blue-Green, and other progressive deployment strategies and when to apply each
- Use Argo Rollouts to split traffic progressively and deploy a new version in stages
- Explain how a PodDisruptionBudget (PDB) preserves availability during deployments and node drains

## Content

### Why RollingUpdate Alone Is Not Enough

The default `RollingUpdate` strategy replaces old Pods with new ones one at a time. While this achieves zero downtime, it has real limitations. Once the rollout begins, **all users gradually start receiving the new version**, and if the new version contains a bug, the tools for precisely controlling or stopping traffic are limited. By the time an issue surfaces, a significant portion of users may already be affected.

**Progressive Delivery** adds two capabilities on top of this. It provides **fine-grained control** over the fraction of traffic routed to the new version, and it **automatically advances or rolls back** based on observed metrics such as error rate and latency. The two primary strategies are Canary and Blue-Green.

- **Blue-Green** — Both the old version (Blue) and the new version (Green) are **deployed in full simultaneously**. Once validation is complete, all traffic is switched to Green at once. Rollback is instant — just flip the switch back to Blue. The trade-off is that twice the resources are needed briefly, and all traffic hits the new version at the moment of cutover.
- **Canary** — A small fraction (e.g., 5%) of the new version is deployed and a slice of traffic is sent to it. If no issues arise, the percentage is gradually increased: 10% → 25% → 50% → 100%. Real users validate the new version safely, so risk is kept tightly controlled — but this requires stage management and a traffic-splitting mechanism.

> **Choosing between them:** Use Blue-Green when **instant full cutover and fast rollback** are the priority; use Canary when you want to **validate with real users incrementally** and minimize risk. Blue-Green fits cases where two versions cannot coexist (e.g., schema migrations); Canary is well-suited for rolling out stateless web services.

### Implementing Canary with Argo Rollouts

The standard Deployment resource cannot handle this level of fine-grained control. **Argo Rollouts** provides a `Rollout` CRD and controller that replaces Deployment, letting you manage Canary and Blue-Green deployments declaratively. The migration is minimal: keep nearly everything the same, change `kind: Deployment` to `kind: Rollout`, and add a `strategy` block.

Before configuring a Canary, there is one important fact you must understand. Argo Rollouts' Canary has **two distinct modes**, and the `steps` keywords available differ between them.

- **Replica-based Canary — out of the box (no traffic provider).** Without an external traffic provider like Istio or NGINX, traffic is approximated using the **ratio of new-version Pod counts**. In this mode, use **`setCanaryScale`** (not `setWeight`) to progressively increase "what fraction of Pods run the new version." Traffic is distributed by the Service's default load balancing across those Pods, so the ratio is an **approximation**.
- **Weight-based Canary — requires a traffic provider.** To specify an **exact request percentage** with `setWeight: 20`, the Rollout must be integrated with a traffic provider such as Istio, NGINX Ingress, SMI, or ALB. `setWeight` instructs the provider to send exactly 20% of requests to the new version — **it does not work in isolation without that integration.**

> A common pitfall: writing `setWeight` without a connected traffic provider means the weight does not take effect as intended. **In environments without an external mesh or ingress controller, start with `setCanaryScale`**, then move to `setWeight` once a traffic provider is in place. That is the correct progression.

Here is a replica-based Canary example that works in a **default environment (no traffic provider)**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: web
spec:
  replicas: 5
  selector:
    matchLabels: { app: web }
  template:                       # identical to a Deployment Pod template
    metadata:
      labels: { app: web }
    spec:
      containers:
        - name: web
          image: our-org/web:v2
  strategy:
    canary:
      steps:
        - setCanaryScale:         # progressively increase the fraction of new-version Pods
            weight: 20            # roughly 20% of all Pods run v2
        - pause: { duration: 5m } # observe for 5 minutes
        - setCanaryScale:
            weight: 50
        - pause: {}               # indefinite pause → wait for manual promotion
        - setCanaryScale:
            weight: 100
```

`pause: {}` (no duration) is a **gate that waits for manual human approval**. An operator reviews metrics and then advances the rollout.

If precise traffic splitting is needed and a provider like Istio is integrated, use `setWeight` in the same position (this is the form used together with Istio in the next lecture):

```yaml
  strategy:
    canary:
      trafficRouting:             # requires an integrated traffic provider
        istio:
          virtualService: { name: web-vsvc }
      steps:
        - setWeight: 20           # the mesh routes exactly 20% of requests to v2
        - pause: { duration: 5m }
        - setWeight: 50
        - pause: {}
        - setWeight: 100
```

The flowchart below shows how the `steps` definition incrementally increases the new-version share, and how each stage can pause or roll back. The flow is identical whether you use `setCanaryScale` (replica ratio) or `setWeight` (exact request ratio with a traffic provider) — only the mechanism that enforces the percentage differs.

```mermaid Canary Staged Traffic Transition Flow — setCanaryScale / setWeight
flowchart TD
    S["Deployment start: v2 launched"] --> W20["20% stage: setCanaryScale or setWeight 20"]
    W20 --> P1["pause: observe for 5 minutes"]
    P1 --> C1{"Metrics healthy?"}
    C1 -->|"Issue detected"| RB["abort → immediate rollback (v1 100%)"]
    C1 -->|"Healthy"| W50["50% stage: expand to 50"]
    W50 --> P2["pause: waiting for operator approval"]
    P2 --> C2{"Promote?"}
    C2 -->|"abort"| RB
    C2 -->|"promote"| W100["100% stage: cutover complete"]
```

```bash
# Watch status in real time (kubectl plugin)
kubectl argo rollouts get rollout web --watch
# Advance past a manual pause
kubectl argo rollouts promote web
# Roll back immediately if an issue is detected
kubectl argo rollouts abort web
```

Going further, attaching an `analysis` step causes Prometheus (or another metrics source) to be automatically evaluated at each stage. If the error rate exceeds a threshold, the rollout **rolls back without human intervention**. This is the fully realized form of progressive delivery.

### Traffic Splitting — Who Actually Guarantees the Percentage?

To summarize the two mechanisms for achieving "send only 20% to the new version":

- **Replica-ratio based (default, `setCanaryScale`)** — Approximates the ratio using Pod counts. With 5 Pods and 1 running the new version, roughly 20% of traffic goes there. No additional infrastructure required, but the result is not precise (it assumes uniform request distribution across Pods).
- **Traffic provider integration (`setWeight` + `trafficRouting`)** — Integrates with Istio, NGINX Ingress, SMI, etc. to enforce the **exact percentage**. `setWeight: 20` guarantees that exactly 20% of requests go to the new version, enforced by the mesh or ingress controller.

For precise Canary delivery, combining Argo Rollouts with a service mesh like Istio (the next lecture's topic) is the natural approach. Rollouts orchestrates the stages; the mesh enforces accurate traffic splitting.

### PodDisruptionBudget — A Safety Net Against Voluntary Disruptions

Separately from deployments and rollouts, **voluntary disruptions** happen regularly during normal operations: `kubectl drain` for node upgrades, node removal by the Cluster Autoscaler, Pod eviction by VPA, and so on. If too many Pods from a service are taken down simultaneously, availability can collapse momentarily.

A **PodDisruptionBudget (PDB)** declares "during voluntary disruption, always keep at least N Pods (or allow at most M to be disrupted) for this workload."

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
spec:
  minAvailable: 3              # at least 3 must remain running at all times
  # alternatively: maxUnavailable: 1   # at most 1 may be down at once
  selector:
    matchLabels:
      app: web
```

With this PDB in place, Kubernetes will not drain all `web` Pods from a node at once during a drain operation. Instead, it **serializes evictions to maintain at least 3 running at all times**. Eviction requests that would violate the constraint are temporarily rejected.

> Important: A PDB only protects against **voluntary** disruptions. **Involuntary** disruptions such as hardware failures are not covered (those are handled by replica count and node distribution). Also, setting a PDB too tightly — for example, `minAvailable` equal to the total replica count — can permanently block node drains and freeze cluster maintenance. Always leave headroom. Progressive delivery protects "availability during deployment"; PDB protects "availability during operations." The two work as a pair.

## Key Takeaways
- Progressive delivery provides fine-grained traffic control and metric-driven advance/rollback, addressing the limitations of RollingUpdate.
- Blue-Green deploys both versions simultaneously and switches all traffic at once (instant rollback, 2× resources); Canary expands incrementally from a small fraction (controlled risk, requires stage management).
- Argo Rollouts' Canary has two modes. **Without a traffic provider, use `setCanaryScale` (replica-ratio approximation)**; with Istio, NGINX, or similar integrated, use **`setWeight` (exact request percentage)**. `setWeight` does not work without a connected traffic provider.
- Control flow with `promote`/`abort`; add `analysis` for automatic metric-based rollback.
- A PodDisruptionBudget guarantees a minimum number of available Pods during voluntary disruptions such as node drains and autoscaler scale-down. It does not protect against involuntary failures, and being too restrictive can block maintenance operations.
