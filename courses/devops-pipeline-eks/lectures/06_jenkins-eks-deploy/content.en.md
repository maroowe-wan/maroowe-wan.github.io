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
- Automate updating the manifest with the newly built image tag.
- Roll out to EKS using `kubectl apply` or `kubectl set image`.
- Complete a pipeline where a single push deploys all the way to EKS.

## Body

### Closing the loop

This is the lecture where everything connects. You already have: a CI pipeline that builds a commit-tagged image and pushes it to ECR (Lecture 3), manifests that describe the deployment (Lecture 4), and Jenkins authenticated to EKS via an IAM role mapped to an RBAC group (Lecture 5). The only missing piece is a **deploy stage** that takes the freshly built tag and tells EKS to run it. Add that, and a single `git push` flows all the way to a running Pod with zero manual steps — true continuous deployment.

The whole challenge of this stage reduces to one question: **how do we get the new image tag into the cluster's Deployment?** There are two clean ways, and you should understand both.

### Approach A: rewrite the manifest, then `kubectl apply`

The image tag lives in one line of `deployment.yaml`. The most transparent approach is to substitute the new tag into that file, then apply it. Because the build already exported `IMAGE_TAG` (the commit SHA), the deploy stage can patch the manifest on the fly:

```groovy
stage('Deploy to EKS') {
    steps {
        sh """
          aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER}
          sed -i 's|IMAGE_PLACEHOLDER|${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}|' deployment.yaml
          kubectl apply -f deployment.yaml
          kubectl apply -f service.yaml
        """
    }
}
```

Here `deployment.yaml` keeps a placeholder where the image goes (`image: IMAGE_PLACEHOLDER`), and `sed` swaps in the real value before applying.

The big advantage is that the manifest remains the **single source of truth**. Every field — replicas, ports, probes, resource limits — is applied together, so the cluster always matches the file in your repository. This is the approach that scales into GitOps later, and it is the one to prefer.

### Approach B: `kubectl set image`

If the Deployment already exists and the *only* thing changing is the image tag, you can update that one field directly, without touching the YAML file:

```bash
kubectl set image deployment/my-app \
  my-app=111122223333.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

Read this as: in the Deployment named `my-app`, set the container named `my-app` to this new image. The container name on the left of `=` must match the `name:` of the container in your Pod template (Lecture 4).

This is concise and great for quick rollouts, but it has a subtle cost: now the *live* state and your *file* state can drift. The cluster runs tag `a1b9f3c`, but `deployment.yaml` in Git still says `IMAGE_PLACEHOLDER` or an old tag. For a learning pipeline `set image` is perfectly fine; just be aware that Approach A keeps your repo honest.

### Watching the rollout finish

Issuing either command *starts* a rollout, but it returns almost immediately — it does not wait for the new Pods to actually be healthy. To make the pipeline wait (and fail if the rollout stalls), add:

```bash
kubectl rollout status deployment/my-app --timeout=120s
```

`kubectl rollout status` blocks until the Deployment has successfully replaced its Pods, or exits non-zero if it does not finish within the timeout. This is important: without it, your pipeline reports "success" the instant it *asked* for a deploy, even if the new version is crash-looping. With it, a broken release turns the build red — which is exactly what you want, because Lecture 7 shows how to roll back from there.

So the complete deploy stage is: authenticate → update the image → wait for the rollout to succeed.

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

### How the rollout actually behaves

When you change the image, the Deployment does **not** kill everything and start over. By default it performs a **rolling update**: it starts new Pods with the new image, waits for them to become ready, and only then terminates old ones — a few at a time — so there is always a working version serving traffic. We dig into the mechanics (and the health checks that gate it) in Lecture 7. For now, the takeaway is that your one-line image change triggers a careful, gradual, no-downtime replacement.

### Why the commit-SHA tag pays off here

Notice that the deploy stage feeds `IMAGE_TAG` — the same commit SHA the build produced — straight into the cluster. This is the moment the thread we have been tracking since Lecture 2 pulls taut: the commit you pushed determines the image you built, which determines the tag in ECR, which determines exactly what EKS runs. Because the tag is unique and immutable, changing it *always* triggers a rollout (Kubernetes notices the Pod template changed), and you can look at any running Pod and trace it back to a single commit.

> A common gotcha: deploying with the `latest` tag often does **nothing**, because the Deployment's spec did not change from Kubernetes' point of view, so no rollout is triggered. The unique commit-SHA tag avoids this trap entirely — yet another reason we banned `latest` back in Lecture 2.

### The complete picture

You now have an end-to-end pipeline: **push to GitLab → webhook → Jenkins checks out, tests, builds, and pushes a commit-tagged image to ECR → Jenkins authenticates to EKS and updates the Deployment → EKS performs a rolling update → `kubectl rollout status` confirms success.** One push, fully automated, all the way to production.

To apply this to *your own* code, the only project-specific pieces are: your `Dockerfile`, your `deployment.yaml` / `service.yaml` (with your image and ports), and the environment values in the `Jenkinsfile` (account ID, region, repo name, cluster name). The pipeline structure stays the same.

## Key Takeaways
- The deploy stage's whole job is to get the new image tag into the cluster's Deployment, then wait for the rollout to finish.
- Two ways to update the image: rewrite the manifest and `kubectl apply -f` (keeps the file as source of truth — preferred), or `kubectl set image deployment/<d> <container>=<image>:<tag>` (concise but can drift from your repo).
- Always follow with `kubectl rollout status --timeout=...` so a broken release fails the build instead of silently "succeeding."
- Feeding the unique commit-SHA tag guarantees a rollout is triggered and keeps every Pod traceable; deploying `latest` may do nothing at all.
- The finished pipeline takes a single push from GitLab all the way to a rolling deployment on EKS, with no manual steps.
