---
lecture_no: 1
title: "Pod Troubleshooting: From CrashLoopBackOff to Ephemeral Containers"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=hixs2GIGrUw
  - https://www.youtube.com/watch?v=gKuu1toptm8
  - https://www.youtube.com/watch?v=xE_nlt8Lyk4
---

# Pod Troubleshooting: From CrashLoopBackOff to Ephemeral Containers

## Learning Objectives
- Tell apart the most common Pod failure states — CrashLoopBackOff, ImagePullBackOff, Pending, and OOMKilled — and explain the root cause behind each one.
- Apply a repeatable diagnostic flow using `kubectl describe`, events, and `kubectl logs --previous` to narrow down why a Pod is broken.
- Use `kubectl debug` and ephemeral containers to inspect a live, running Pod — even one with no shell — and pinpoint runtime, networking, or resource problems.

## Body

### Why this matters

Sooner or later, every Kubernetes operator stares at a Pod that simply will not behave. The deployment looks fine, the YAML applied cleanly, and yet `kubectl get pods` shows a status you didn't ask for: `CrashLoopBackOff`, `ImagePullBackOff`, `Pending`, or a container that was just `OOMKilled`. The good news is that Kubernetes is unusually honest about what went wrong — the information is almost always there. The skill is knowing **where to look and in what order**.

The golden rule is to debug **from the bottom up**. Start at the Pod, the lowest healthy unit of work, and only move up the stack to Services and Ingress once you've confirmed the Pod itself is actually running and ready. Chasing an Ingress problem when your Pod is crash-looping is wasted effort. This same bottom-up instinct applies to Deployments, StatefulSets, DaemonSets, Jobs, and CronJobs alike.

In this lecture we'll first learn to read the four headline failure states, then walk a standard diagnostic flow, and finally reach for live-debugging tools when the logs alone don't tell the whole story.

### The status field is your first clue

Run this and read the `STATUS` column carefully — it is the single most useful signal you have:

```bash
kubectl get pods
kubectl get pods -o wide        # adds node and Pod IP
kubectl get pods -w             # watch status change in real time
```

Each status points you toward a different family of root causes. Let's take them one at a time.

#### CrashLoopBackOff — the container keeps dying after it starts

A Pod has a **restart policy**, and by default it is `Always`. When a container exits, Kubernetes faithfully restarts it to keep your app available. But if the container crashes *again right after starting* — say, your new build throws an exception during initialization — you fall into a loop: start, crash, restart, crash. To avoid hammering the system, Kubernetes waits a little longer before each restart attempt: roughly a few seconds, then ten seconds, then a minute, and so on, capped at five minutes. That growing delay is the **back-off**, and the whole start-crash-restart cycle is what you see reported as `CrashLoopBackOff`.

> CrashLoopBackOff is not itself an error — it's a symptom. It tells you the container starts but then exits repeatedly. The real bug is *why* it exits, and that's almost always visible in the logs of the crashed container.

Typical culprits: a bug in application code, a missing environment variable or config file, a failing database connection at startup, a misconfigured command/entrypoint, or a liveness probe that kills a container that was actually healthy but slow to boot.

#### ImagePullBackOff (and ErrImagePull) — the image never arrived

Here the container never even starts because the kubelet couldn't pull the image. `ErrImagePull` is the first failed attempt; `ImagePullBackOff` means Kubernetes is now backing off and retrying. Common causes: a typo in the image name or tag, an image tag that doesn't exist, a private registry with no `imagePullSecret` configured, or rate limits and network issues reaching the registry. The fix is almost always in the image reference or your registry credentials — not in your application.

#### Pending — the Pod can't be scheduled

A `Pending` Pod has been accepted by the cluster but has not been placed on a node. The scheduler couldn't find a node that satisfies the Pod's requirements. Usual reasons: not enough CPU or memory available across nodes (insufficient resources), node selectors / affinity / taints that no node tolerates, or a PersistentVolumeClaim that can't be bound. Pending is a *scheduling* problem, so the answer lives in the Pod's events and in node capacity — not in the container image or code.

#### OOMKilled — the container exceeded its memory limit

When a container tries to use more memory than its configured `limits.memory`, the Linux kernel's out-of-memory killer terminates it, and Kubernetes records the reason as `OOMKilled` (exit code 137). This often *looks* like a crash loop, because the container restarts and then gets killed again under load. The fix is either to raise the memory limit, fix a memory leak in the app, or right-size the workload. Always check the container's `State` and `Last State` reason to distinguish a true application crash from an OOM kill.

### The standard diagnostic flow

Whatever the status, the investigation follows the same three-step rhythm. Learn it once and you'll use it for years.

**Step 1 — `describe` the Pod.** This is your richest source of truth. It shows each container's current `State`, its `Last State` (with the exit code and reason — this is where you'll spot `OOMKilled`), restart counts, the resolved image, probe configuration, and — crucially — the **Events** at the bottom.

```bash
kubectl describe pod <pod-name>
```

Read the Events section from the bottom up. `Failed to pull image`, `Insufficient memory`, `Back-off restarting failed container`, and `Liveness probe failed` each point you straight at the right failure family.

**Step 2 — read the events, including the broader picture.** Pod-level events are in `describe`, but cluster events give context (for example, scheduling failures or node pressure):

```bash
kubectl get events --sort-by=.lastTimestamp
kubectl get events --field-selector involvedObject.name=<pod-name>
```

**Step 3 — read the logs, including the *previous* container.** For a CrashLoopBackOff, the live container may be too young to have logged anything useful — it just restarted. The exception you need is in the container instance that *just died*. That's exactly what `--previous` gives you:

```bash
kubectl logs <pod-name>                     # current container instance
kubectl logs <pod-name> --previous          # the container that just crashed — key for CrashLoopBackOff
kubectl logs <pod-name> -c <container-name>  # a specific container in a multi-container Pod
kubectl logs <pod-name> -f                   # follow live
```

> For CrashLoopBackOff, `kubectl logs --previous` is the command that most often hands you the answer. The current container has nothing yet; the crashed one has the stack trace.

The flow, then, is: read the **status** to pick the failure family, run **describe** to see state and events, then pull **logs (with `--previous` when crash-looping)** to read the actual error. Most Pod problems surrender to these three commands, as the diagnostic flow below summarizes.

```mermaid Bottom-up Pod diagnostic flow: status to describe to events to logs
flowchart TD
    A["kubectl get pods (read STATUS)"] --> B{"Which status?"}
    B -->|CrashLoopBackOff| C["kubectl describe pod (State, Last State, Events)"]
    B -->|ImagePullBackOff| C
    B -->|Pending| C
    B -->|OOMKilled| C
    C --> D["kubectl get events (scheduling, node pressure context)"]
    D --> E{"Crash-looping?"}
    E -->|Yes| F["kubectl logs --previous (read the crashed container)"]
    E -->|No| G["kubectl logs (read the current container)"]
    F --> H["Root cause found"]
    G --> H
```

### When logs aren't enough: live debugging with `kubectl debug`

Sometimes the logs are silent and you need to get *inside* a running Pod — to check what processes are alive, test network connectivity to another service, or inspect files. The classic move is `kubectl exec -it <pod> -- sh`. But there's a catch that's increasingly common in production: **distroless images have no shell**.

Distroless containers are stripped down to little more than your application binary. That makes them small and fast to pull, cheaper to store, and quicker to start — but with no `sh`, `curl`, or `ps` baked in, there's nothing to `exec` into. So how do you debug a live Pod that has no shell?

The answer is **ephemeral containers**, driven by `kubectl debug`. Instead of taking the Pod down, you *attach a temporary container* into the existing Pod. That debug container brings its own toolset (busybox, curl, ps, netcat, whatever you choose), and — because it joins the same Pod — it shares the network namespace and (with shared process namespace enabled) can even see the troubled container's processes. You're debugging the *actual* Pod with the problem, not a replica.

```bash
# Attach a busybox debug container to a running Pod and drop into a shell
kubectl debug -it <pod-name> --image=busybox --target=<container-name>
```

The `--target` flag points the ephemeral container at the troubled container so they share a process namespace. Once you're in, you can investigate live:

```bash
# Inside the ephemeral container:
ps aux                          # see processes in the target container
nslookup my-service             # check DNS resolution to another Service
wget -qO- http://my-service:80  # test connectivity to another Pod/Service
```

Because the ephemeral container lives in the same network context as the broken one, networking problems become tractable: you can ping and `telnet` around to discover *why* the app can't reach the service it depends on. This same `kubectl debug` family can also copy a Pod for safe experimentation or attach a debug shell onto a node — but the day-to-day win is inspecting a live, shell-less Pod without disrupting it.

### Tying it back to the bigger picture

Once the Pod is genuinely running and ready, *then* you climb the stack. If the app still doesn't respond, suspect the Service (check that its selector matches the Pod labels and that its endpoints are populated) and then the Ingress (verify the `service.name` and `service.port`, and confirm the backend isn't empty). A quick way to isolate an Ingress or infrastructure problem is to `kubectl port-forward` directly to the Pod or the Ingress controller Pod and see whether the app answers when you bypass the outer layers. But that's the *next* step — and you only earn the right to take it after the bottom-up flow has proven the Pod itself is healthy.

## Key Takeaways
- **Read the status first.** CrashLoopBackOff = container starts then keeps dying; ImagePullBackOff = the image couldn't be pulled; Pending = the scheduler can't place the Pod; OOMKilled = the container blew past its memory limit (exit code 137).
- **CrashLoopBackOff is a symptom, not the bug.** The real cause is in the logs of the crashed container — reach for `kubectl logs --previous`.
- **Follow one repeatable flow:** `kubectl describe pod` (state + events) → `kubectl get events` → `kubectl logs [--previous]`. Most Pod failures fall out of these three commands.
- **Debug from the bottom up:** confirm the Pod is running and ready before chasing Service or Ingress problems.
- **For live, shell-less Pods, use `kubectl debug` with ephemeral containers.** You attach a tool-rich container into the running Pod, share its network and process namespace, and debug the real problem in place — no shell required, no Pod restart needed.
