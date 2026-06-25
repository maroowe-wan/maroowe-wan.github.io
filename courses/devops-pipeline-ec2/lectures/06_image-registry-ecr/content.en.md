---
lecture_no: 6
title: Pushing the Image to a Registry (AWS ECR)
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=lOdrdV0eDrs
  - https://www.youtube.com/watch?v=D8ym8RP1yvo
  - https://www.youtube.com/watch?v=jg9sUceyGaQ
---

# Pushing the Image to a Registry (AWS ECR)

## Learning Objectives
- Understand why built images need a container registry (ECR).
- Authenticate Jenkins to ECR and push an image.
- Tag images by Git commit SHA for traceability.

## Body

The image Jenkins built in the last lecture only exists on the Jenkins agent. EC2 can't reach inside Jenkins to grab it, so we need a shared store both can access. **Amazon ECR (Elastic Container Registry)** is AWS's private Docker registry: Jenkins **pushes** images up, and EC2 later **pulls** them down. ECR is the hand-off point between the build half (CI) and the deploy half (CD).

> A registry decouples *building* an image from *running* it: Jenkins needs to know nothing about your servers, and your servers need no build tools — they just pull a finished, immutable image by its tag.

### Step 1 — Create an ECR repository

In the AWS console, open **ECR** and create a repository named after your app (e.g. `myapp`). ECR gives you a repository URI:

```
<aws_account_id>.dkr.ecr.<region>.amazonaws.com/myapp
```

This full URI is **not** a tag — it's the **registry host** (`<aws_account_id>.dkr.ecr.<region>.amazonaws.com`) plus the **repository path / image name** (`/myapp`). The tag is the identifier *after the colon* (`:latest`, `:<commit-sha>`). Docker decides where to push from the **registry host** embedded in the image name, so you build the full reference as `host/image:tag` — repository URI first, then the tag:

```
<aws_account_id>.dkr.ecr.<region>.amazonaws.com/myapp:<tag>
```

### Step 2 — Authenticate Jenkins to ECR

You can't push to a private registry without proving who you are. ECR login is two parts: use AWS credentials to get a short-lived password, then pipe it into `docker login`. Store AWS credentials in Jenkins (never hard-code them), then:

```bash
aws ecr get-login-password --region <region> \
  | docker login --username AWS --password-stdin \
    <aws_account_id>.dkr.ecr.<region>.amazonaws.com
```

`get-login-password` returns a temporary token; `--password-stdin` keeps it out of the build log. The username is always the literal `AWS`.

> In production, attach an **IAM role** to the Jenkins instance so it gets ECR permissions automatically — no long-lived keys to store or rotate. Static keys are fine for learning if scoped tightly.

### Step 3 — Tag by commit SHA and push

A `latest` tag tells you nothing about *which code* an image contains. The professional standard is to tag with the **Git commit SHA** — a permanent, traceable link from any running container back to the exact source commit. Capture the short SHA in the Jenkinsfile and use it as the tag:

```groovy
stage('Push to ECR') {
    steps {
        script {
            def registry = "<aws_account_id>.dkr.ecr.<region>.amazonaws.com"
            def commit = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
            sh """
                aws ecr get-login-password --region <region> \
                  | docker login --username AWS --password-stdin ${registry}
                docker tag myapp:${BUILD_NUMBER} ${registry}/myapp:${commit}
                docker push ${registry}/myapp:${commit}
            """
        }
    }
}
```

Notice the `docker tag` line: it re-points your local image (`myapp:${BUILD_NUMBER}`) at the full ECR reference, attaching the registry path to the image name (`${registry}/myapp`) and the commit SHA as the tag after the colon. A common refinement is to push *two* tags from the same image: the immutable `${commit}` tag for traceability and rollback, plus a moving tag like the branch name (`main`) as a stable "newest on this branch" pointer for deploy scripts.

### Step 4 — Verify

Open the ECR console and check the repository. You should see the image listed with its commit-SHA tag and a "pushed" timestamp — proof the artifact now lives in a durable, private registry, ready for any server with permission to pull it.

Your pipeline now does everything except run the new version on a server: push to GitLab → checkout → build → test → image → ECR. Getting that image onto EC2 and running it is what the next lecture completes.

## Key Takeaways
- **ECR** is the shared store that lets Jenkins push and EC2 pull, separating *building* from *running*.
- Authenticate in two steps: `aws ecr get-login-password` for a temporary token, then `docker login` — prefer an IAM role over static keys in production.
- Docker routes a push by the **registry host** in the image name, so tag your image as `<repository-URI>:<tag>` (the URI is the host + image name; the tag comes after the colon).
- Tag by **Git commit SHA** for traceability; optionally add a moving branch tag.

## Sources
- https://www.youtube.com/watch?v=lOdrdV0eDrs
- https://www.youtube.com/watch?v=D8ym8RP1yvo
- https://www.youtube.com/watch?v=jg9sUceyGaQ
