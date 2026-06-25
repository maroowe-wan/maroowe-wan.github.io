---
lecture_no: 2
title: Packaging Your App as a Container — Writing a Dockerfile and Running It Locally
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=gAkwW2tuIqE
  - https://www.youtube.com/watch?v=LQjaJINkQXY
  - https://www.youtube.com/watch?v=SnSH8Ht3MIc
---

# Packaging Your App as a Container — Writing a Dockerfile and Running It Locally

## Learning Objectives
- Understand why a container image is the unit we ship through the whole pipeline.
- Write a standard Dockerfile that turns a web app into an image.
- Build and run the image locally with `docker build` and `docker run`, then verify it works.

## Body

### Why we do this

A **container** packages your code with everything it needs to run — runtime, libraries, settings — so it runs identically on your laptop and on EC2. That kills "works on my machine." Three terms to keep straight:

- **Dockerfile** — the text recipe with build instructions.
- **Image** — the immutable snapshot built from the Dockerfile.
- **Container** — a running instance of an image.

> In this pipeline the image is the single artifact that travels from your laptop, through Jenkins, into ECR, and onto EC2. Everything we automate later is just "build this image, store it, run it somewhere." So the Dockerfile is the foundation.

### Step 1 — Write the Dockerfile

Create a file named exactly `Dockerfile` (no extension) in your project root. This example uses Node.js, but the shape applies to any language.

```dockerfile
# Start from an official slim base image with your runtime
FROM node:20-alpine

# Working directory inside the image
WORKDIR /app

# Copy dependency manifest FIRST, then install — so this layer is cached
COPY package.json package-lock.json ./
RUN npm install

# Now copy the rest of the source
COPY . .

# Document the port the app listens on
EXPOSE 8080

# Command that runs when the container starts
CMD ["node", "index.js"]
```

Three things that matter here:

- **`FROM` — use a slim official image.** `node:20-alpine` is built on Alpine Linux (~5 MB), keeping your image small and fast to push/pull.
- **Layer caching dictates the order.** Each instruction is a cached layer, and Docker rebuilds only what changed. Dependencies change rarely, source changes constantly — so copy `package.json` and run `npm install` *before* `COPY . .`. Reverse it and every code change forces a full reinstall.
- **`CMD` uses exec (array) form** — `["node", "index.js"]`, not a string. It runs the process directly instead of through a shell, so signals and shutdown behave correctly.

### Step 2 — Add a .dockerignore

`COPY . .` copies *everything*, including local `node_modules` and any stray secrets. Exclude them just like `.gitignore`:

```
node_modules
.git
*.env
```

This keeps the image small and keeps secrets out of a layer anyone who pulls the image could inspect.

### Step 3 — Build the image

The `-t` flag tags it; the trailing `.` points Docker at the current directory.

```bash
docker build -t myapp:local .
```

Verify it was created:

```bash
docker images
```

### Step 4 — Run it and verify

```bash
docker run -p 5000:8080 myapp:local
```

The `-p 5000:8080` flag is essential. Container ports are *not* reachable by default; this maps host port `5000` to container port `8080` (the one we `EXPOSE`d). The format is `host:container`. Open `http://localhost:5000` and you should see your app.

To run in the background and manage it:

```bash
docker run -d -p 5000:8080 myapp:local   # detached
docker ps                                # what's running
docker logs <container>                  # read logs
docker stop <container>                  # stop it
```

You now have a reproducible image and proof it runs. Every step you just did by hand becomes a Jenkins stage in the lectures ahead.

## Key Takeaways
- A container bundles your app with its whole environment — one artifact that runs the same everywhere.
- The chain: a **Dockerfile** builds an **image**, and an **image** runs as a **container**.
- Order the Dockerfile for layer caching (deps before source), use a slim base, and add `.dockerignore`.
- Build with `docker build -t name .`, run with `docker run -p host:container name`; port mapping is required to reach the app.

## Sources
- https://www.youtube.com/watch?v=gAkwW2tuIqE
- https://www.youtube.com/watch?v=LQjaJINkQXY
- https://www.youtube.com/watch?v=SnSH8Ht3MIc
