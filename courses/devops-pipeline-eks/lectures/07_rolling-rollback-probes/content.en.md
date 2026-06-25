---
lecture_no: 7
title: "Rolling Updates, Rollbacks, and Health Checks"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=fqfieWP1jY4
  - https://www.youtube.com/watch?v=lxc4EXZOOvE
  - https://www.youtube.com/watch?v=wWA9JgAvuqw
---

# Rolling Updates, Rollbacks, and Health Checks

## Learning Objectives
- Configure readiness and liveness probes so rollouts gate on real health.
- Inspect and control a deployment with `kubectl rollout`, and roll back in one command.
- Verify a zero-downtime rolling deployment and recover from a broken release.

## Body

Your pipeline now deploys automatically. This lecture makes those deploys **safe**: replace versions gradually with no downtime, teach Kubernetes how to tell a healthy Pod from a sick one, and undo a bad release in seconds. Work through the four tasks below in order.

### Task 1 — Tune the rolling update pace

**What & why.** Changing a Deployment's image triggers a `RollingUpdate` by default: Kubernetes brings up new Pods, waits for them to be ready, then retires old ones, so there is always a working set serving traffic. Two knobs bound the pace — set them small for a slow, extra-safe rollout.

- **`maxSurge`** — how many *extra* Pods above the desired count (how far you go *over*).
- **`maxUnavailable`** — how many Pods may be *down* below the desired count (how far you dip *under*).

Both default to `25%`. With 4 replicas and defaults, at most 1 Pod is down (3 keep serving) and the total never exceeds 5.

```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
```

> Mnemonic: **`maxSurge` = how far over you may go; `maxUnavailable` = how far under you may dip.**

**Verify.** Apply, then watch Pods cut over without dropping below capacity:

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/my-app   # blocks until done or stuck
```

### Task 2 — Add readiness and liveness probes

**What & why.** A rolling update is only safe if Kubernetes can tell whether a new Pod is healthy *before* sending it traffic. That is the job of probes — and the two you must not confuse are:

- **Readiness probe = traffic control.** On failure, the Pod is **removed from the Service endpoints** (not killed); no new requests reach it until it passes. This is what gates a rollout — a new Pod only receives user traffic once it is ready (warmed up, DB connected).
- **Liveness probe = restart control.** On failure, Kubernetes **kills and restarts the container** — recovering from deadlocks or stuck-but-not-crashed processes.

> Swapping them is a classic, painful bug: a too-aggressive *liveness* probe restarts Pods that were merely slow to warm up, and under load this can cascade into a cluster-wide restart storm.

```yaml
        livenessProbe:
          httpGet:
            path: /healthz       # alive? restart if not
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready         # ready for traffic? hold traffic if not
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

`initialDelaySeconds` waits before the first check; `periodSeconds` is the repeat interval. (Probes can also be `tcpSocket` or `exec` a command.) For slow-booting apps, add a **startup probe**, which simply delays the other two until boot finishes.

> Without a readiness probe, Kubernetes assumes a Pod is ready the instant its container starts and routes traffic immediately — so users hit errors on every deploy.

**Verify.** Endpoints should stay empty until the Pod is actually ready:

```bash
kubectl apply -f deployment.yaml
kubectl get endpoints my-app -w   # IP appears only after readiness passes
```

### Task 3 — Inspect and control a rollout

**What & why.** `kubectl rollout` gives live visibility and control over an in-flight update (works for Deployments, StatefulSets, DaemonSets). Use `pause`/`resume` to halt mid-rollout if you spot trouble.

```bash
kubectl rollout status  deployment/my-app   # wait for success/failure (your pipeline uses this)
kubectl rollout history deployment/my-app   # list past revisions
kubectl rollout pause   deployment/my-app   # freeze mid-rollout
kubectl rollout resume  deployment/my-app   # continue
```

### Task 4 — Roll back a bad release

**What & why.** Kubernetes keeps a revision history, so a bad release is one command to undo. This is the safety net that makes automated deployment tolerable.

```bash
kubectl rollout undo deployment/my-app                  # back to previous revision
kubectl rollout undo deployment/my-app --to-revision=3  # to a specific revision
```

The payoff comes from combining everything above. Deploy an image tag that does not exist (or one that crash-loops):

```bash
kubectl set image deployment/my-app app=my-app:does-not-exist
kubectl rollout status deployment/my-app   # reports "waiting" — it's stuck
```

The new Pods never pass readiness, so `maxUnavailable` stops Kubernetes from retiring the old healthy Pods — your old version keeps serving the entire time. Clear the bad Pods:

```bash
kubectl rollout undo deployment/my-app     # old version restored; users never noticed
```

### Wiring it into the pipeline

Configure probes in your manifest so rollouts gate on real health, let Jenkins run `kubectl rollout status` so a stuck rollout fails the build, and keep `kubectl rollout undo` ready — run by an on-call engineer or automated on failure. (A GitOps revert in Git is the more mature path, but built-in `rollout undo` is the direct tool here.)

## Key Takeaways
- A rolling update replaces Pods gradually with zero downtime; `maxSurge` bounds how far over desired count you go, `maxUnavailable` how far under (both default 25%).
- **Readiness = traffic control** (failure removes the Pod from the Service, gating the rollout); **liveness = restart control** (failure restarts the container). Do not confuse them; the startup probe just delays both for slow-booting apps.
- `kubectl rollout status/history/pause/resume` give visibility and control; `kubectl rollout undo` reverts in one command.
- Gradual rollout + readiness gating + one-command rollback = a broken release leaves the old version serving and is trivially undone.
