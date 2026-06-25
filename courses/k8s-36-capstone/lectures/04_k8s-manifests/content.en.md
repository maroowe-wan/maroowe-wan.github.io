---
lecture_no: 4
title: Writing Kubernetes Manifests for the Flask App
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=6IPu3WU_M0o
  - https://www.youtube.com/watch?v=fqfieWP1jY4
  - https://www.youtube.com/watch?v=P7mHN_PUz_w
---

# Writing Kubernetes Manifests for the Flask App

## Learning Objectives
- Write the Deployment, Service, and ConfigMap YAML manifests that run our `flask-capstone:1.0` image.
- Make labels and selectors (`matchLabels`) line up correctly, and set `replicas`, the container image, and `containerPort`.
- Wire up lightweight readiness and liveness probes against the `/healthz` endpoint, and move runtime settings out of the image into a ConfigMap.

## Body

### Where we are in the journey

So far this capstone has moved through three clear stages. In Lecture 1 we built a small Flask app with a couple of routes, including a `/healthz` health-check endpoint that simply returns HTTP 200. In Lecture 2 we wrapped that app in a Docker image and tagged it `flask-capstone:1.0`. In Lecture 3 we spun up a local cluster (minikube or kind) and loaded that exact image into the cluster so we don't need an external registry.

Right now the image is sitting inside the cluster, but nothing is running it. Kubernetes does not "just run" an image — you have to *describe* what you want, and Kubernetes makes reality match that description. That description is a **manifest**: a YAML file that declares the desired state of an object. In this lecture we write three of them. We won't apply them yet (that's Lecture 5) — the goal here is to author correct, well-structured YAML and understand every field.

> A manifest is declarative. You don't tell Kubernetes *how* to start your app step by step; you tell it *what* you want to exist, and the cluster continuously works to keep that true.

The three objects we need, and the role each one plays, are as follows:

- **Deployment** — runs and supervises copies (replicas) of our Flask Pod. If a Pod dies, the Deployment recreates it.
- **Service** — gives those Pods one stable network address so other things can reach them, even as individual Pods come and go.
- **ConfigMap** — holds configuration values (like an environment name) outside the image, so we can change settings without rebuilding.

Let's build them one at a time.

### The ConfigMap: configuration out of the image

A core principle from the source material is worth repeating: **don't bake configuration into your image.** If the database URL or the environment name lives inside the container image, then changing it means rebuilding and re-shipping the whole image. A ConfigMap fixes this by storing those values separately and injecting them into the Pod at runtime — think of it as a small dictionary of settings that your Pods can read.

We'll keep it simple and store two values: an environment name and a greeting message.

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flask-config
  labels:
    app: flask-capstone
data:
  APP_ENV: "production"
  APP_GREETING: "Hello from Kubernetes!"
```

`data` is just key/value pairs. In the next section we'll inject these into the container as environment variables, so inside the running app `os.environ["APP_ENV"]` would read `"production"`. The payoff: when you later want to flip `APP_ENV` to `staging`, you edit this one file (and restart the Pods) — the image never changes.

### The Deployment: running the app

The Deployment is the heart of this lecture. Its job, stated plainly, is to declare how many copies of our Pod should be running and to keep that true. Here is the full manifest, then we'll walk through it.

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flask-capstone
  labels:
    app: flask-capstone
spec:
  replicas: 2
  selector:
    matchLabels:
      app: flask-capstone
  template:
    metadata:
      labels:
        app: flask-capstone
    spec:
      containers:
        - name: flask
          image: flask-capstone:1.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 5000
          envFrom:
            - configMapRef:
                name: flask-config
          readinessProbe:
            httpGet:
              path: /healthz
              port: 5000
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /healthz
              port: 5000
            initialDelaySeconds: 10
            periodSeconds: 10
```

Let's unpack the important fields.

**`replicas: 2`** asks for two identical Pods. Running more than one copy is the standard way to avoid downtime — if one Pod (or the node under it) fails, the other keeps serving while Kubernetes replaces the lost one.

**`image: flask-capstone:1.0`** is the exact name and tag we built in Lecture 2. Note there's no registry prefix (like `docker.io/...`); that's deliberate, because the image lives locally inside the cluster.

**`imagePullPolicy: IfNotPresent`** is essential for our setup. It tells the kubelet: *use the image already present on the node; only pull from a registry if it's missing.* Because we side-loaded the image in Lecture 3, there is no registry to pull from. If we left the default (which pulls every time for a `:latest`-style image), Kubernetes would try to fetch `flask-capstone:1.0` from a registry, fail, and leave the Pod stuck in `ImagePullBackOff`.

> `imagePullPolicy: IfNotPresent` is the line that makes locally loaded images work. Forget it and your Pods will sit in `ImagePullBackOff` looking for a registry that doesn't have your image.

**`containerPort: 5000`** documents the port the Flask process listens on inside the container. (Flask's development server defaults to 5000.) This is informational — it doesn't open the port by itself — but the Service and the probes both target this port.

**`envFrom` / `configMapRef`** pulls *every* key from the `flask-config` ConfigMap and exposes it as an environment variable in the container. So `APP_ENV` and `APP_GREETING` become available to the app at runtime, with no values hardcoded in the manifest.

### How labels and selectors match up

This is the part beginners most often get wrong, so it deserves a careful look. Three label-related blocks appear in the Deployment, and they are *not* redundant — they each do a different job:

1. `metadata.labels` (top level) — labels on the **Deployment object itself**. Useful for organizing and querying Deployments. It does not control which Pods are managed.
2. `spec.selector.matchLabels` — the rule that says *"this Deployment owns Pods carrying these labels."*
3. `spec.template.metadata.labels` — the labels **stamped onto each Pod** the Deployment creates.

The hard requirement: **`spec.selector.matchLabels` must match `spec.template.metadata.labels`.** In our file both say `app: flask-capstone`, so the Deployment's selector matches the Pods it stamps out, and it correctly adopts and supervises them. If these two disagree, the API server rejects the manifest — the Deployment would have no way to recognize the Pods it just created. The flow of ownership is as follows: the Deployment's selector points at the Pod template's labels, and those same labels later let the Service find the Pods.

### The Service: a stable address for the Pods

Pods are disposable. Each gets its own IP, and that IP changes whenever a Pod is recreated. So we never talk to a Pod directly — we put a **Service** in front of the group. A Service has a stable name and IP, and it forwards traffic to whatever Pods currently match its selector.

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: flask-capstone
  labels:
    app: flask-capstone
spec:
  type: ClusterIP
  selector:
    app: flask-capstone
  ports:
    - port: 80
      targetPort: 5000
      protocol: TCP
```

The key link here is **`selector: app: flask-capstone`**. The Service uses this to find Pods — and it matches the very labels the Deployment stamps onto each Pod (`spec.template.metadata.labels`). That's how a Service and a Deployment connect: not by referencing each other by name, but by agreeing on a label. This is also why the readiness probe matters: only Pods that report *ready* are added to the Service's pool of endpoints.

The two ports play different roles. **`port: 80`** is the port the Service exposes to the rest of the cluster — other Pods reach our app at `flask-capstone:80`. **`targetPort: 5000`** is the port on the container that traffic is forwarded to, which is exactly the `containerPort` our Flask app listens on. We chose `type: ClusterIP` (the default), which keeps the Service reachable only from inside the cluster; in Lecture 5 we'll expose it to our laptop.

Putting all three objects side by side, the diagram below shows how the `app: flask-capstone` label is the single piece of glue that ties the Deployment, its Pods, and the Service together — and how a client request flows through the ClusterIP down to port 5000 on each container.

```mermaid Label/selector glue and traffic flow across Deployment, Pods, and Service
flowchart TB
    Client["Other Pod in cluster"]
    subgraph Deploy["Deployment flask-capstone (replicas 2)"]
        Sel["spec.selector.matchLabels<br/>app: flask-capstone"]
        Tpl["spec.template.metadata.labels<br/>app: flask-capstone"]
        Sel -. "must match" .- Tpl
    end
    Pod1["Pod 1<br/>label app: flask-capstone<br/>containerPort 5000"]
    Pod2["Pod 2<br/>label app: flask-capstone<br/>containerPort 5000"]
    Svc["Service flask-capstone<br/>ClusterIP, port 80"]

    Tpl -- "stamps label onto" --> Pod1
    Tpl -- "stamps label onto" --> Pod2
    Svc -- "selector app: flask-capstone<br/>matches Pod labels" --> Pod1
    Svc -- "selector app: flask-capstone<br/>matches Pod labels" --> Pod2
    Client -- "request to flask-capstone:80" --> Svc
    Svc -- "forwards to targetPort 5000" --> Pod1
    Svc -- "forwards to targetPort 5000" --> Pod2
```

### Connecting `/healthz` to the probes

In Lecture 1 we added a `/healthz` route that returns 200. Now it earns its keep. Kubernetes uses two kinds of health checks here, and they are genuinely different:

- **Readiness probe** — *"Is this Pod ready to receive traffic yet?"* If the probe fails, Kubernetes does **not** kill the Pod; it simply removes the Pod from the Service's endpoints so no requests are routed to it until it recovers. This is what prevents traffic from hitting a Pod that's still warming up.
- **Liveness probe** — *"Is this Pod still healthy, or is it stuck?"* If the probe fails repeatedly, Kubernetes **restarts** the container. This is the automatic recovery for a deadlocked or silently unresponsive app.

Both of ours use `httpGet` against `path: /healthz` on `port: 5000` — Kubernetes makes a simple HTTP GET, and a 200 means healthy. The timing fields keep the probes gentle: `initialDelaySeconds` gives the app a moment to boot before the first check, and `periodSeconds` sets how often to re-check afterward. We start the liveness check a little later and a little less often than readiness, because we want to route traffic away from a slow Pod quickly, but we don't want to restart Pods over a brief hiccup.

> Readiness controls *traffic*; liveness controls *restarts*. Pointing both at a lightweight `/healthz` that just returns 200 is a safe, common pattern. Avoid putting heavy work (like deep database queries) behind a liveness probe — a slow check can trigger needless restarts.

### What we'll do with these files next

You should now have three files in a folder: `configmap.yaml`, `deployment.yaml`, and `service.yaml`. They describe a complete, self-contained deployment of our Flask app — two replicas, fed by a ConfigMap, fronted by a Service, and kept healthy through `/healthz` probes. In Lecture 5 we'll bring them to life with `kubectl apply`, watch the Pods come up with `kubectl get` and `kubectl describe`, reach the app from our machine, and then perform a rolling update and a rollback.

## Key Takeaways
- A manifest declares **desired state**; the three core objects here are the **Deployment** (runs replicas), the **Service** (stable address), and the **ConfigMap** (externalized settings).
- `spec.selector.matchLabels` **must** equal `spec.template.metadata.labels`, and the Service's `selector` must match those same Pod labels — labels are the glue, not name references.
- Set `image: flask-capstone:1.0` with `imagePullPolicy: IfNotPresent` so the cluster uses the locally loaded image instead of trying (and failing) to pull from a registry.
- `containerPort: 5000` on the Pod and `targetPort: 5000` on the Service must agree; the Service's `port: 80` is what other clients call.
- Readiness probes gate **traffic**, liveness probes trigger **restarts** — point both at the lightweight `/healthz` endpoint with sensible delays.
- Keep configuration in a ConfigMap injected via `envFrom`, so changing a setting doesn't require rebuilding the image.
