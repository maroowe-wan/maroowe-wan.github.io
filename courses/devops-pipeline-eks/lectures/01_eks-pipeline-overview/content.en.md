---
lecture_no: 1
title: "EKS Deployment Pipelines — From Push to Kubernetes"
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=TlHvYWVUZyc
  - https://www.youtube.com/watch?v=KOE_6QYQqA4
  - https://www.youtube.com/watch?v=aRXg75S5DWA
---

# EKS Deployment Pipelines — From Push to Kubernetes

## Learning Objectives
- Explain what Amazon EKS is and what "declarative, manifest-based deployment" means.
- Understand why a CI/CD pipeline ends with manifests being applied via `kubectl`.
- See how GitLab, Jenkins, Amazon ECR, and EKS fit into one end-to-end flow.

## Body

### The goal of this course

You push code, and a short while later the new version is running in production — safely, with no downtime, and with an easy way to roll back. This course builds the road between your `git push` and a healthy Pod serving traffic, using four tools:

- **GitLab** — hosts your application source code.
- **Jenkins** — the engine that builds and deploys.
- **Amazon ECR** — AWS's private registry that stores your container images.
- **Amazon EKS** — the managed Kubernetes cluster that runs them.

We treat Kubernetes as the **destination**, not the subject. You won't become a Kubernetes internals expert; you'll learn to ship to it automatically.

### Kubernetes and EKS in brief

Kubernetes (**k8s**) is a container orchestration platform: it runs the right number of container copies, restarts ones that crash, spreads them across machines, and replaces old versions with new ones gradually. A cluster has a **control plane** (the brain — holds the desired state and makes decisions) and **worker nodes** (the machines that actually run your containers). The smallest deployable unit is a **Pod** (one or more containers sharing networking and storage).

Operating a production control plane (API server, etcd, failover across zones) takes deep expertise. **Amazon EKS (Elastic Kubernetes Service)** is AWS's *managed* Kubernetes: AWS runs the control plane for you, and you bring the worker nodes and workloads. (GKE and AKS are the Google and Azure equivalents.)

### The key idea: declarative deployment

Traditional deployment is **imperative** — you script the steps ("stop the old process, copy the new build, start it"). If a step fails halfway, you're stuck in a broken state.

Kubernetes is **declarative**. You write the *desired end state* in a text file — a **manifest** (YAML), e.g. "run 3 copies of this image, reachable on port 80" — and the control plane continuously makes reality match it. If a Pod dies, it's recreated. Change the image version and re-apply, and Kubernetes figures out how to get there.

> Your deployment is a file that describes what you want, not a script of what to do. Version that file in Git and your infrastructure becomes reviewable, repeatable, and revertible.

Because the desired state is just text, the pipeline's final job is simple: point a manifest at the cluster and run `kubectl apply -f`. That's why "the end of the pipeline is applying manifests."

### How the four tools connect

The end-to-end flow this course builds, step by step:

1. **Push to GitLab.** GitLab hosts your source code.
2. **GitLab triggers Jenkins** via a webhook (an HTTP call saying "something changed, start working").
3. **Jenkins builds a container image** from your `Dockerfile`, tags it by commit SHA (never just `latest`), and **pushes it to Amazon ECR**.
4. **Jenkins updates the manifest** to point at the new image tag and runs `kubectl apply` (or `kubectl set image`) against the **EKS cluster**.
5. **EKS performs a rolling update**: it starts new Pods, waits until they report healthy, then retires the old ones — so users see no downtime. One command rolls it back if needed.

The diagram below traces this whole journey, from a developer's `git push` to running Pods inside the EKS cluster.

```mermaid End-to-end EKS deployment pipeline from git push to running Pods
flowchart LR
    Dev[Developer] -->|git push| GitLab[GitLab Repo]
    GitLab -->|webhook trigger| Jenkins[Jenkins]

    subgraph CI["Jenkins: build and test"]
        Build[Build image from Dockerfile] --> Test[Run tests]
        Test --> Tag[Tag image by commit SHA]
    end

    Jenkins --> Build
    Tag -->|docker push| ECR[Amazon ECR Registry]

    subgraph CD["Jenkins: deploy"]
        Manifest[Update manifest with new image tag] --> Apply[kubectl apply / set image]
    end

    Tag --> Manifest
    ECR -.image pulled by.-> Pods
    Apply -->|target cluster| EKS

    subgraph EKS["Amazon EKS Cluster"]
        ControlPlane[Control Plane] -->|rolling update| Pods[Pods on Worker Nodes]
    end
```

The **image tag** is the thread tying it together: *produced* in the build, *stored* in ECR, *consumed* by the manifest at deploy time.

### Principles we'll reinforce

- **Tag by commit, not `latest`.** A SHA or `v1.4.2` tells you exactly what's running; `latest` makes rollbacks and debugging miserable.
- **Authenticate machines, not humans.** Jenkins reaches AWS/EKS via an IAM role (Lecture 5), not pasted personal credentials.
- **Let health checks gate the rollout.** Kubernetes only shifts traffic to a new version once readiness checks pass — if you configure them (Lecture 7).

## Key Takeaways
- The pipeline turns `git push` into a safe, repeatable deployment on Kubernetes.
- Kubernetes is declarative: describe the desired state in a manifest, and the control plane makes it real. The pipeline's final act is `kubectl apply`.
- EKS is AWS-managed Kubernetes — AWS runs the control plane, you run the workloads.
- Flow: GitLab → webhook → Jenkins builds & pushes image to ECR → Jenkins applies manifest to EKS → rolling update.
- The commit-based image tag connects build, registry, and deploy.

## Sources
- https://www.youtube.com/watch?v=TlHvYWVUZyc
- https://www.youtube.com/watch?v=KOE_6QYQqA4
- https://www.youtube.com/watch?v=aRXg75S5DWA
