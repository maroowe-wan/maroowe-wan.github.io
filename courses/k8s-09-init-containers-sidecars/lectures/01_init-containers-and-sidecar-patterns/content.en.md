---
lecture_no: 1
title: Kubernetes Init Containers and the Sidecar Pattern
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=2PCz6Ds0vwo
  - https://www.youtube.com/watch?v=O6fiE2eFX1o
  - https://www.youtube.com/watch?v=48lsKjtLUjQ
---

# Kubernetes Init Containers and the Sidecar Pattern

## Learning Objectives
- Explain how init containers work — they run before your application containers, one at a time, in the order you define them, and each must finish successfully before the next starts — and recognize common use cases such as preparing configuration or waiting on dependencies.
- Describe the sidecar pattern and its typical jobs (log shipping, proxies, config sync), and distinguish it from an ordinary multi-container Pod.
- Write and validate a Kubernetes 1.28+ **native sidecar** (an init container with `restartPolicy: Always`) in YAML, and explain its lifecycle advantages over the old hand-rolled sidecar approach.

## Body

### Why a single container is rarely enough

A Kubernetes Pod is the smallest deployable unit, and it can hold more than one container. That's deliberate. In real systems, your application almost never runs alone: something has to fetch its configuration first, ship its logs somewhere, encrypt its outbound traffic, or sync secrets in the background. You *could* cram all of that into your main image, but then every concern is tangled together and impossible to update independently.

Kubernetes gives you two clean tools for this: **init containers** for one-time setup that must happen *before* your app starts, and **sidecars** for helper processes that run *alongside* your app for its entire life. They look similar in YAML, but they solve opposite halves of the problem — startup versus runtime. Let's take them one at a time.

### Init containers: the Pod's startup checklist

An init container is a startup container that you declare as part of the Pod spec. The defining rule is simple but strict: **it must complete successfully, or no other container in the Pod will ever launch.** If an init container exits with an error, the Pod is considered failed, and Kubernetes will (depending on your restart policy) keep retrying it.

A useful mental model is a *pre-flight checklist*. Before the "real" work begins, you verify that every prerequisite is met. Is the database reachable? Is the config volume populated? Can we find today's Kafka broker? Do we have valid credentials? If any item on the checklist fails, there's no point continuing — so the Pod simply doesn't start. If you've done object-oriented programming, this is the same discipline as a constructor: you never let a half-initialized object exist, and init containers make sure you never run a half-initialized Pod.

> Init containers run **sequentially, in the exact order you list them**, and each one runs to completion before the next begins. App containers start only after *all* init containers have succeeded.

Common use cases:

- **Waiting on dependencies** — block startup until a service like a database or message broker is actually ready, so your app doesn't crash-loop on first launch.
- **Preparing data and config** — `git clone` a repository, render templates into a shared volume, or download assets the app needs.
- **Volume initialization** — create directory structures, set permissions, or seed a shared `emptyDir` volume that the app container then reads.

One nice detail: init containers share the same fields as regular containers (`name`, `image`, `command`, `args`, and so on) with one exception — they don't take liveness or readiness probes. Probes are for long-running processes; an init container is expected to start, do its job, and stop, so there's nothing to keep probing.

Here is a Pod that waits for two dependencies before the application is allowed to run. The structure is two init containers that each loop until a Service resolves, followed by the real app container:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp-pod
  labels:
    app: myapp
spec:
  # Init containers run first, one at a time, in this order.
  initContainers:
    - name: init-myservice
      image: busybox:1.36
      # Block until DNS for "myservice" resolves, then exit 0.
      command: ['sh', '-c', "until nslookup myservice; do echo waiting for myservice; sleep 2; done"]
    - name: init-mydb
      image: busybox:1.36
      command: ['sh', '-c', "until nslookup mydb; do echo waiting for mydb; sleep 2; done"]
  # The app container starts ONLY after both init containers succeed.
  containers:
    - name: myapp
      image: nginx:1.27
      ports:
        - containerPort: 80
```

If `myservice` and `mydb` aren't reachable, the Pod sits patiently in the `Init:` state instead of crash-looping — exactly the behavior you want. The strict one-at-a-time ordering for this Pod is shown in the diagram below.

```mermaid Init containers run sequentially, and any failure blocks the app
flowchart TD
    Start([Pod scheduled]) --> Init1["init-myservice runs"]
    Init1 --> Check1{Exited 0?}
    Check1 -->|No| Retry1["Restart per restartPolicy"]
    Retry1 --> Init1
    Check1 -->|Yes| Init2["init-mydb runs"]
    Init2 --> Check2{Exited 0?}
    Check2 -->|No| Retry2["Restart per restartPolicy"]
    Retry2 --> Init2
    Check2 -->|Yes| App["App container myapp starts"]
    App --> Ready([Pod Running])
```

### The sidecar pattern, and what it really means

A **sidecar** is a helper container that runs *next to* your main application and extends its functionality without changing the main image. The name comes from a motorcycle sidecar: a separate seat bolted to the bike, going wherever the bike goes.

Typical sidecar jobs:

- **Log shipping** — the app writes logs to a shared volume; the sidecar tails that file and forwards it to your logging backend.
- **Proxies / service mesh** — a sidecar (for example, Envoy) intercepts all network traffic to add mutual TLS, retries, and observability without the app knowing.
- **Config sync** — the sidecar watches a remote config source and keeps a local file fresh, so the app always reads up-to-date settings.

The key difference from an *ordinary* multi-container Pod is intent and lifecycle coupling. In a plain multi-container Pod, the containers are peers — each is part of the core function. A sidecar is explicitly *subordinate*: it exists only to support the main app, and it should live and die in step with it.

### The dirty secret of "classic" sidecars

Here's the awkward part that surprises many newcomers: **for most of its history, Kubernetes had no actual concept of a sidecar.** We talked about sidecars constantly, but technically they were just a second entry in the `containers:` list with no special status. Kubernetes treated all containers in that list as equal peers and started them roughly in parallel — with no guarantee about ordering.

That gap caused real, painful bugs:

- **The startup race.** The motorcycle could roar 10 miles down the road before the sidecar was even attached. If your app started before its proxy sidecar was ready, early requests failed, alerts fired into PagerDuty, and canary deployments broke — all because the app didn't wait.
- **The shutdown problem.** With Jobs, the Pod is supposed to finish when the main task completes. But a proxy or logging sidecar runs forever by design, so it would keep the Pod alive indefinitely and the Job would never report "done."

For years, teams worked around this with hacks: shared "ready" flag files, shell loops that polled for the sidecar, or `preStop` tricks. They worked, but they were fragile and every team reinvented them.

### Native sidecars in Kubernetes 1.28+

Kubernetes 1.28 finally gave sidecars first-class support — and the implementation is delightfully clever. There's no new `sidecars:` field. Instead, you declare your sidecar as an **init container with `restartPolicy: Always`**.

That sounds contradictory at first, so unpack the two halves:

1. **It's an init container**, so it starts *before* the main app container — solving the startup race. The app is guaranteed not to begin until the sidecar is up.
2. **`restartPolicy: Always`** changes the rule "an init container must run to completion." Now Kubernetes doesn't wait for it to finish; it considers the init phase complete once this container is *started*, then moves on to the app container. Because the restart policy is `Always`, the sidecar keeps running for the whole life of the Pod, and if it crashes it's automatically restarted.

The lifecycle benefits this unlocks:

- **Guaranteed startup ordering** — the sidecar is ready before the app, so no more first-request failures.
- **Clean shutdown** — when the main app finishes, Kubernetes waits for it, then sends a graceful termination signal to the sidecar so it can flush logs and close connections before exiting.
- **Jobs finally work** — because the sidecar is no longer a peer in `containers:`, it no longer blocks a Job from completing. The Job ends when the app's work is done, and the sidecar is cleaned up afterward.

You can think of a native sidecar as a *never-ending init container* that the rest of the Pod gets to run alongside. Here is the same idea in YAML — a log-shipping sidecar declared the native way:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-native-sidecar
spec:
  initContainers:
    # A NATIVE SIDECAR: it's in initContainers, but restartPolicy: Always
    # makes it start before the app and keep running for the Pod's lifetime.
    - name: log-shipper
      image: busybox:1.36
      restartPolicy: Always   # <-- this is what makes it a sidecar
      command: ['sh', '-c', 'tail -F /var/log/app/app.log']
      volumeMounts:
        - name: logs
          mountPath: /var/log/app
  containers:
    - name: myapp
      image: busybox:1.36
      command: ['sh', '-c', 'while true; do echo "$(date) request handled" >> /var/log/app/app.log; sleep 5; done']
      volumeMounts:
        - name: logs
          mountPath: /var/log/app
  volumes:
    - name: logs
      emptyDir: {}
```

The flow at startup is as follows: Kubernetes starts `log-shipper` first; because of `restartPolicy: Always` it doesn't wait for it to finish, it just confirms it's running, then starts `myapp`. The app writes to the shared `emptyDir` volume, and the sidecar tails and forwards those lines. When the app ends, the sidecar is shut down gracefully. The diagram below traces this start-before, run-alongside, shut-down-after lifecycle in time order.

```mermaid Native sidecar lifecycle: starts before the app, runs alongside, shuts down after
sequenceDiagram
    participant K as Kubelet
    participant S as log-shipper sidecar
    participant A as myapp container
    participant V as Shared emptyDir volume
    K->>S: Start sidecar (restartPolicy Always)
    S-->>K: Started (not waited to completion)
    K->>A: Start app container
    A->>V: Append log lines
    S->>V: Tail and forward log lines
    Note over A: App finishes its work
    A-->>K: App exited
    K->>S: Graceful termination signal
    S-->>K: Flushed logs and exited
```

### A note on cost and the bigger picture

Sidecars are powerful, but they aren't free. A full service mesh adds one proxy container *per Pod*, and at scale those proxies can consume a startling share of your CPU, memory, and budget. That's why the industry is exploring lighter alternatives like eBPF-based meshes that move this work into the kernel instead of a per-Pod container. None of that retires the sidecar pattern — extending an app with logging, proxies, and config helpers remains fundamental — but it's worth right-sizing your use of it rather than reaching for a heavy mesh by default.

## Key Takeaways
- **Init containers** run before your app, sequentially in declared order, and each must succeed or the Pod won't start — ideal for dependency waits, config preparation, and volume setup. They use the same fields as normal containers but no probes.
- **Sidecars** are helper containers that run alongside the main app to add capabilities (logging, proxies, config sync) without modifying the app image; they differ from ordinary multi-container Pods by being lifecycle-coupled and subordinate to the main app.
- **Classic sidecars** were just regular containers with no ordering guarantees, causing startup races and Jobs that never finished.
- **Native sidecars (1.28+)** are init containers with `restartPolicy: Always`: they start before the app, keep running for the Pod's whole life, restart on failure, shut down gracefully, and no longer block Jobs from completing.
