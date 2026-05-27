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
- Package a web application of any language into a container image using a `Dockerfile`.
- Create an Amazon ECR repository to store those images.
- Understand that the image is the *input* to every Kubernetes deployment.

## Body

### Why we start here

Kubernetes does not run your source code. It runs **container images**. So before any pipeline, manifest, or cluster matters, you need a repeatable way to turn your app into an image and a reliable place to keep it. That is this lecture: a `Dockerfile` to build the image, and an **Amazon ECR** repository to store it. Once an image with a known tag sits in ECR, the rest of the course is about getting EKS to run it.

A nice property of containers is that they are **language-agnostic**. Whether your app is Node.js, Go, Python, or Java, the recipe is the same: describe the build in a `Dockerfile`, run `docker build`, then `docker push`. The pipeline does not care what language you wrote — it only cares that a `Dockerfile` exists.

### Anatomy of a Dockerfile

A `Dockerfile` is a plain-text recipe. Each line is an instruction that produces a layer of the image. Here is a minimal example for a Node.js web app:

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

Reading it line by line:

- `FROM node:18-alpine` — start from an official base image that already has Node installed. `alpine` is a tiny Linux distribution that keeps the image small.
- `WORKDIR /app` — set the working directory inside the image.
- `COPY package*.json ./` then `RUN npm install` — copy *just* the dependency manifests first and install. Doing this before copying the rest of the code means Docker can cache the dependency layer and skip re-installing when only your source changes. This ordering is a small habit that saves a lot of build time.
- `COPY . .` — copy the application source.
- `EXPOSE 3000` — document that the app listens on port 3000.
- `CMD [...]` — the command that runs when the container starts.

> A practical upgrade you will see in real projects is a **multi-stage build**: one stage compiles the app (with all the build tools), and a second, slim stage copies only the finished binary into a minimal image such as Google's "distroless" base. The result contains your app and nothing else — no shell, no package manager — which is smaller and has a smaller attack surface.

Build and test it locally:

```bash
docker build -t my-app:dev .
docker run -p 3000:3000 my-app:dev
```

### Creating an ECR repository

**Amazon ECR (Elastic Container Registry)** is AWS's private Docker registry. Think of it as your team's secure shelf for images — like Docker Hub, but inside your AWS account with IAM-controlled access.

Create a repository from the AWS Console (search for "ECR" → *Create repository*), or from the CLI:

```bash
aws ecr create-repository \
  --repository-name my-app \
  --region us-east-1
```

A repository is essentially one named bucket that holds many versions (tags) of the *same* application. You typically have one ECR repository per service.

### Pushing an image to ECR

ECR repositories are private, so Docker has to authenticate before it can push. The ECR console even shows you the exact commands under *View push commands*. The flow has four steps: log in, build, tag, push.

```bash
# 1. Authenticate Docker to your ECR registry (the login token is short-lived)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 2. Build the image
docker build -t my-app .

# 3. Tag it with the full ECR address and a meaningful tag
docker tag my-app:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)

# 4. Push
docker push \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:$(git rev-parse --short HEAD)
```

The full image name has a strict shape: `<account-id>.dkr.ecr.<region>.amazonaws.com/<repo-name>:<tag>`. The part before the last `/` is the **registry** (your account, in your region); after it is the **repository name**; after the `:` is the **tag**.

### Tag by commit, not `latest`

Notice we used `$(git rev-parse --short HEAD)` — the Git commit SHA — as the tag instead of `latest`. This is one of the most important habits in the whole course.

`latest` is a label that moves. If two builds both push `latest`, the second silently overwrites the first, and now "latest" means something different than it did a minute ago. When you look at a running cluster and it says it is running `latest`, you have no idea *which* code that actually is — and rolling back becomes guesswork.

A commit-based tag (or a semantic version like `v1.4.2`) is **immutable and traceable**: the tag `a1b9f3c` always points to exactly that code, forever. You can look at any Pod, read its image tag, and know precisely what is deployed. This is what makes Lecture 7's rollbacks reliable.

### How this connects to Kubernetes

When you later write a Deployment manifest (Lecture 4), the most important field is the image reference:

```yaml
        image: <account-id>.dkr.ecr.us-east-1.amazonaws.com/my-app:a1b9f3c
```

That is the whole point of this lecture. The image you build and push here becomes the **input** to your deployment. The pipeline's job, in essence, is to keep producing new images and updating that one line so EKS pulls and runs the new version.

One more thing worth knowing: in production, you usually give your *cluster* (its nodes or a service identity) permission to pull from ECR, so EKS can fetch images on its own — and AWS also offers features like cross-region replication and pull-through caching to keep image pulls fast and reliable as you scale. We will wire up the *push* side in the pipeline (Lecture 3) and the *pull/deploy* side starting in Lecture 5.

## Key Takeaways
- Kubernetes runs images, not source — so containerizing your app is step zero.
- A `Dockerfile` is a layered recipe; order your steps so dependency installation is cached, and prefer multi-stage builds for small, secure images.
- ECR is your private AWS registry. The push flow is: `get-login-password` → `docker login` → `build` → `tag` (with full ECR address) → `push`.
- Tag images by commit SHA or version, never just `latest`, so every running Pod is traceable and rollbacks are reliable.
- The pushed image — referenced by its full ECR address and tag — is the input that your Kubernetes Deployment will consume.
