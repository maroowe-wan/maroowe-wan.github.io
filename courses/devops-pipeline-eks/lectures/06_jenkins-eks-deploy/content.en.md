---
lecture_no: 6
title: "Automated Deployment to EKS from Jenkins"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=h7k45phtZgc
  - https://www.youtube.com/watch?v=MSDqlQurfaI
  - https://www.youtube.com/watch?v=u5924Zxr8Vw
---

# Automated Deployment to EKS from Jenkins

## Learning Objectives
- Update the manifest (or the live Deployment) with the freshly built image tag.
- Roll out to EKS using `kubectl apply` or `kubectl set image`, then wait for the rollout to finish.
- Complete a pipeline where a single `git push` deploys all the way to EKS.

## Body

### What the deploy stage does

You already have the pieces: a CI pipeline that builds a commit-tagged image and pushes it to ECR, manifests that describe the Deployment, and Jenkins authenticated to EKS via an IAM role mapped to an RBAC group. The only missing step is a **deploy stage** that pushes the new tag into the cluster. The whole job reduces to one question: how do we get the new image tag into the cluster's Deployment? There are two clean ways.

### Approach A: rewrite the manifest, then `kubectl apply`

Keep a placeholder in `deployment.yaml` (`image: IMAGE_PLACEHOLDER`), substitute the real tag at deploy time, then apply. The manifest stays the single source of truth, so every field (replicas, ports, probes, limits) is applied together and the cluster always matches your repo. Prefer this; it scales into GitOps later.

```groovy
stage('Deploy to EKS') {
    steps {
        sh """
          aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER}
          sed -i 's|IMAGE_PLACEHOLDER|${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}|' deployment.yaml
          kubectl apply -f deployment.yaml
          kubectl apply -f service.yaml
          kubectl rollout status deployment/my-app --timeout=120s
        """
    }
}
```

### Approach B: `kubectl set image`

If the Deployment already exists and only the image tag changes, update that one field directly without touching the YAML:

```bash
kubectl set image deployment/my-app \
  my-app=111122223333.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

Read it as: in the Deployment `my-app`, set the container `my-app` to this image. The name on the left of `=` must match the container `name:` in your Pod template. Concise and great for quick rollouts, but the live state can now **drift** from your Git file. Fine for a learning pipeline; Approach A keeps the repo honest.

### Wait for the rollout to finish

Both commands only *start* a rollout and return immediately. Always block until the new Pods are actually healthy, or fail the build if they aren't:

```bash
kubectl rollout status deployment/my-app --timeout=120s
```

> Without `rollout status`, the pipeline reports "success" the instant it *asks* for a deploy, even if the new version is crash-looping. With it, a broken release turns the build red.

The complete `set image` deploy stage:

```groovy
stage('Deploy to EKS') {
    steps {
        sh """
          aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER}
          kubectl set image deployment/my-app my-app=${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
          kubectl rollout status deployment/my-app --timeout=120s
        """
    }
}
```

### How the rollout behaves, and why commit-SHA tags matter

Changing the image triggers a **rolling update**: Kubernetes starts new Pods, waits for them to become ready, then terminates old ones a few at a time, so there's always a working version serving traffic. No downtime from one line of change.

The diagram below traces the full deploy stage: how Jenkins authenticates with kubeconfig, applies the new image, and how the cluster rolls Pods over while `rollout status` blocks until success.

```mermaid Jenkins deploy stage authenticating to EKS and triggering a rolling update
sequenceDiagram
    participant J as Jenkins Deploy Stage
    participant AWS as aws eks update-kubeconfig
    participant API as EKS API Server
    participant CTL as Deployment Controller
    participant POD as Pods
    J->>AWS: Request kubeconfig credentials
    AWS-->>J: Write kubeconfig with EKS token
    J->>API: kubectl apply or kubectl set image
    Note over J,API: Authenticated via IAM role mapped to RBAC group
    API->>CTL: New image tag in Deployment spec
    CTL->>POD: Start new Pods with new image
    POD-->>CTL: New Pods ready
    CTL->>POD: Terminate old Pods gradually
    Note over CTL,POD: Rolling update keeps a version always serving
    J->>API: kubectl rollout status
    API-->>J: Rollout complete or timeout fails the build
```

The deploy stage feeds `IMAGE_TAG` (the commit SHA) straight into the cluster, so the commit you pushed determines exactly what EKS runs, and any running Pod traces back to one commit.

> Deploying with the `latest` tag often does **nothing**: the Deployment spec didn't change from Kubernetes' point of view, so no rollout is triggered. A unique commit-SHA tag always triggers a rollout and avoids this trap.

### The complete picture

End to end: **push to Git → webhook → Jenkins checks out, tests, builds, and pushes a commit-tagged image to ECR → Jenkins authenticates to EKS and updates the Deployment → EKS performs a rolling update → `kubectl rollout status` confirms success.** To reuse this for your own code, only the project-specific pieces change: your `Dockerfile`, your `deployment.yaml` / `service.yaml`, and the environment values in the `Jenkinsfile` (account ID, region, repo name, cluster name).

## Key Takeaways
- The deploy stage's whole job is to get the new image tag into the Deployment, then wait for the rollout.
- Two ways: rewrite the manifest + `kubectl apply -f` (source of truth, preferred), or `kubectl set image deployment/<d> <container>=<image>:<tag>` (concise but can drift).
- Always follow with `kubectl rollout status --timeout=...` so a broken release fails the build.
- Feed the unique commit-SHA tag: it guarantees a rollout and keeps every Pod traceable; `latest` may do nothing.
- The finished pipeline takes one `git push` all the way to a rolling deployment on EKS, with no manual steps.
