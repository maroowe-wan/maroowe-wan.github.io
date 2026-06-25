---
lecture_no: 2
title: "Containerizing Your App and Preparing Amazon ECR"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=lOdrdV0eDrs
  - https://www.youtube.com/watch?v=Hv5UcBYseus
  - https://www.youtube.com/watch?v=OihC0CS43AI
---

# Containerizing Your App and Preparing Amazon ECR

## Learning Objectives
- Package a web application into a container image with a `Dockerfile`.
- Create an Amazon ECR repository and push an image to it.
- See why the pushed image is the *input* to every Kubernetes deployment.

## Body

Kubernetes runs **container images**, not source code. So step zero is turning your app into an image and storing it somewhere EKS can pull from. That "somewhere" is **Amazon ECR (Elastic Container Registry)** — AWS's private Docker registry, gated by IAM. Containers are language-agnostic, so the recipe below is the same whether your app is Node, Go, Python, or Java.

### 1. Write a Dockerfile

A `Dockerfile` is a plain-text recipe; each instruction adds a layer. Copy the dependency manifests *before* the source so Docker can cache the install layer and skip it when only your code changes.

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

> For production, prefer a **multi-stage build**: one stage compiles the app, a second slim stage (e.g. Google's "distroless") copies only the finished binary — smaller image, smaller attack surface.

### 2. Build and test locally

Confirm the image runs before involving AWS.

```bash
docker build -t my-app:dev .
docker run -p 3000:3000 my-app:dev
# Verify: open http://localhost:3000 (or curl it) and check the response.
```

### 3. Create an ECR repository

One repository holds many tagged versions of the *same* service — typically one repo per service. Create it from the Console (search "ECR" -> *Create repository*) or the CLI.

```bash
aws ecr create-repository \
  --repository-name my-app \
  --region us-east-1
# Verify: returns the repositoryUri, shaped
# <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app
```

### 4. Authenticate, tag, and push

ECR is private, so Docker must log in first (the token is short-lived). The ECR console also lists these exact commands under *View push commands*. Tag with the **Git commit SHA**, not `latest`.

```bash
# Log in
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build, then tag with the full ECR address + commit SHA
docker build -t my-app .
docker tag my-app:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)

# Push
docker push \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)
```

The image name is strict: `<account-id>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>` — registry, then repo, then tag. Verify the push in the Console under your repository, or with the CLI:

```bash
aws ecr list-images --repository-name my-app --region us-east-1
```

### Why commit tags, not `latest`

`latest` is a label that moves: the next push silently overwrites it, so a running cluster reporting `latest` tells you nothing about *which* code is live, and rollbacks become guesswork. A commit SHA (or a semver tag like `v1.4.2`) is **immutable and traceable** — `a1b9f3c` always means exactly that code. This is what makes Lecture 7's rollbacks reliable.

### How this feeds Kubernetes

The Deployment manifest you write in Lecture 4 references this exact image:

```yaml
        image: <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

That is the whole point: the image you push here is the **input** to your deployment. The pipeline's job is to keep producing new images and updating that one line. We wire up the *push* side in Lecture 3 and the *pull/deploy* side from Lecture 5 — at which point you grant the cluster's nodes IAM permission to pull from ECR.

## Key Takeaways
- Kubernetes runs images, not source — containerizing is step zero.
- Order Dockerfile steps so dependency installs are cached; prefer multi-stage builds.
- Push flow: `get-login-password` -> `docker login` -> `build` -> `tag` (full ECR address) -> `push`.
- Tag by commit SHA or version, never `latest`, so every Pod is traceable.
- The pushed image (full ECR address + tag) is what your Deployment consumes.
