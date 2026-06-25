---
lecture_no: 3
title: Preparing a Local Kubernetes Cluster
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=7tWJbsGglYA
  - https://www.youtube.com/watch?v=qBudNa-j7as
  - https://www.youtube.com/watch?v=hDBgeUuPgXo
---

# Preparing a Local Kubernetes Cluster

## Learning Objectives
- Install **minikube** or **kind** and start a Kubernetes cluster on your own laptop.
- Connect to that cluster with **kubectl** and confirm it is healthy using `kubectl get nodes` and `kubectl cluster-info`.
- Load the image you built in Lecture 2 (`flask-capstone:1.0`) **directly into the cluster** with `minikube image load` or `kind load docker-image` — so you can deploy without ever pushing to a registry.

## Body

### Where we are in the capstone

So far in this capstone you have a working app and a way to package it. In Lecture 1 you wrote a small Flask application with a `/healthz` endpoint, and in Lecture 2 you wrapped it in a Docker image and tagged it `flask-capstone:1.0`. That image is sitting on your machine right now, ready to run.

The missing piece is a place to run it *as Kubernetes would*. That is what this lecture builds: a small, real Kubernetes cluster that lives entirely on your laptop. By the end you will have a running cluster, a working `kubectl` connection, and your `flask-capstone:1.0` image loaded inside the cluster — primed for Lecture 4, where you will write the Deployment and Service manifests that actually schedule it.

> The whole point of this lecture is to get your local image *inside* the cluster without touching a remote registry. That single trick is what makes local Kubernetes development fast and free.

### Why a local cluster (and why not a real one)

A production Kubernetes cluster is a serious thing: typically three control-plane nodes for high availability plus a fleet of worker nodes, each on its own physical or virtual machine. The control plane decides *what should run where*; the workers actually run your containers. You would never spin that up just to test one Flask app.

For learning and local development we use a **single-node cluster** instead — one machine that plays both the control-plane and the worker role at the same time. There are two popular tools for this, and you only need to pick **one**:

- **minikube** — a mature, batteries-included single-node cluster. It runs Kubernetes inside a Docker container (or a VM) on your machine and ships with handy extras like `minikube service` and addons.
- **kind** — "**K**ubernetes **in** **D**ocker." It runs each Kubernetes node as a Docker container. It is lightweight, starts quickly, and is the tool many CI systems use.

Both give you the same `kubectl` experience. Choose whichever you like — the rest of this capstone works identically on either.

> Prerequisite for both: **Docker must be installed and running.** Both minikube (with the Docker driver) and kind use Docker as their engine, so start Docker Desktop or the Docker daemon before you continue.

### Meet kubectl, your remote control

Before we start a cluster, understand the tool you will drive it with. **kubectl** (pronounced "kube-control" or "kube-cuttle") is the command-line client for Kubernetes. Every action — create a Pod, inspect a Service, read logs — is sent as a request to the cluster's **API server**, the single front door through which all changes flow. kubectl simply formats those requests for you.

A nice bonus: kubectl is not tied to minikube or kind. The exact same tool talks to a managed cloud cluster (EKS, GKE, AKS) too. Learn it here and you have learned it everywhere.

Both minikube and kind install kubectl as a dependency, so installing the cluster tool usually gives you kubectl for free. Verify it with:

```bash
kubectl version --client
```

### Path A — Using minikube

**1. Install and start.** On macOS you can use Homebrew (`brew install minikube`); on Windows use the official installer or `winget`/Chocolatey; on Linux grab the binary from the minikube site. Then start a cluster with the Docker driver:

```bash
minikube start --driver=docker
```

This downloads a node image and boots a one-node cluster inside a Docker container. A single node is the default, so you don't need to ask for one explicitly.

**2. Confirm it's healthy.**

```bash
minikube status
kubectl get nodes
kubectl cluster-info
```

`minikube status` should report the host, kubelet, and apiserver as `Running`. `kubectl get nodes` should list one node with status `Ready`. `kubectl cluster-info` prints the API server URL — proof that kubectl is wired up to the cluster.

**3. Load your image.** This is the key step. Your `flask-capstone:1.0` image lives in your *local* Docker, but the cluster has its own separate image store and cannot see it. minikube gives you a one-line command to copy it in:

```bash
minikube image load flask-capstone:1.0
```

After this, the image exists inside the cluster. You can verify it:

```bash
minikube image ls | grep flask-capstone
```

### Path B — Using kind

**1. Install and create.** Install kind (Homebrew, the Go toolchain, or the release binary), then create a cluster:

```bash
kind create cluster --name capstone
```

This spins up a Kubernetes node as a Docker container and automatically points kubectl at it.

**2. Confirm it's healthy.**

```bash
kubectl get nodes
kubectl cluster-info --context kind-capstone
```

You should again see one `Ready` node and a printed API server URL. kind sets your kubectl context to `kind-<name>` (here `kind-capstone`).

**3. Load your image.**

```bash
kind load docker-image flask-capstone:1.0 --name capstone
```

This copies the image from your local Docker into the kind node's container runtime. Now the cluster can run it without any registry.

### Why we skip the registry — and what `imagePullPolicy` has to do with it

The "normal" way to get an image into Kubernetes is to push it to a registry like Docker Hub or Amazon ECR, then let the cluster pull it back down. During development that loop is painful: every code change means *build → push → pull*, over and over, and a private registry can cost money and require credentials.

Loading the image directly sidesteps all of that. But there's a catch you must understand for Lecture 4. By default, Kubernetes may still try to **pull** an image from a remote registry — especially if the tag is `:latest` — and since `flask-capstone:1.0` was never pushed anywhere, that pull fails and your Pod gets stuck in `ImagePullBackOff` (Kubernetes' way of saying "I couldn't fetch the image").

The fix is a field on the container spec called **`imagePullPolicy`**:

- `imagePullPolicy: IfNotPresent` — use the local copy if it already exists; only pull if it's missing. Because we *loaded* the image, it is already present, so Kubernetes uses it directly and never reaches out to a registry.
- `imagePullPolicy: Never` — never pull at all; fail if the image isn't local. Also works here, but stricter.

> For this capstone we use a fixed tag (`flask-capstone:1.0`, not `:latest`) and set `imagePullPolicy: IfNotPresent`. The fixed tag stops Kubernetes from defaulting to "always pull," and the policy lets it use the image you loaded. Remember this for Lecture 4 — it's exactly the line that keeps your Pod from getting stuck.

One quick caveat from the source material: minikube's older `eval $(minikube docker-env)` trick (which retargets your Docker client at minikube's internal daemon) only works on **single-node** clusters. The `minikube image load` and `kind load docker-image` commands shown above are simpler and work the same way regardless, so we prefer them.

### A mental model of what just happened

The structure is as follows. Your laptop runs Docker, which holds the `flask-capstone:1.0` image you built in Lecture 2. Your cluster tool (minikube or kind) runs a single Kubernetes node inside a Docker container; that node has its *own* image store, separate from your laptop's Docker. The `image load` command copies the image across that boundary. kubectl, meanwhile, sits on your laptop and sends commands to the node's API server. Once the image is on the node and kubectl is connected, everything is in place for Kubernetes to schedule a Pod from that image — which is exactly what Lecture 4 will do. The diagram below shows these two boundaries and the two flows that cross between them.

```mermaid Local cluster layout: kubectl drives the API server while image load copies the image across the laptop-to-cluster boundary
flowchart LR
    subgraph Laptop["Your laptop"]
        Kubectl["kubectl"]
        Docker["Docker<br/>holds flask-capstone:1.0"]
    end
    subgraph Node["Single-node cluster (minikube / kind container)"]
        API["API server"]
        Kubelet["kubelet"]
        Store["Node image store"]
    end
    Kubectl -->|"commands"| API
    API --> Kubelet
    Docker -->|"image load"| Store
    Kubelet -->|"runs Pod from"| Store
```

## Key Takeaways
- A **single-node local cluster** (minikube or kind) gives you a real Kubernetes environment on your laptop; pick one tool and start it with Docker running.
- `kubectl get nodes` (look for `Ready`) and `kubectl cluster-info` are your two quick health checks that kubectl is connected to a live cluster.
- Load your Lecture 2 image with `minikube image load flask-capstone:1.0` or `kind load docker-image flask-capstone:1.0 --name <cluster>` to deploy **without a registry**.
- Pair a **fixed tag** (`:1.0`, not `:latest`) with **`imagePullPolicy: IfNotPresent`** so Kubernetes uses the loaded image instead of trying — and failing — to pull it. This sets you up cleanly for the manifests in Lecture 4.
