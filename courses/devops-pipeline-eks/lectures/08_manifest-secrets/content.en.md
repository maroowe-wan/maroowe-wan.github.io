---
lecture_no: 8
title: "Managing Manifests and Secrets, and Wrapping Up"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=LWbbL3jZcgo
  - https://www.youtube.com/watch?v=O6Uhe9bItkI
  - https://www.youtube.com/watch?v=X-pjSFVKnlY
---

# Managing Manifests and Secrets, and Wrapping Up

## Learning Objectives
- Separate configuration and secret values from images using ConfigMaps and Secrets, and inject them into Pods.
- Survey approaches to managing manifests at scale with Helm and Kustomize.
- Review the finished pipeline and how to apply it to your own code.

## Body

### The last missing piece: configuration

Your pipeline deploys safely, but real apps need *configuration* — database URLs, feature flags, API keys, passwords. You should **never** bake these into the image (every environment would need a different image) or hardcode them in the Deployment manifest (especially secrets, which would then sit in your Git repo in plain text). Kubernetes gives you two objects to keep configuration separate from code: **ConfigMap** for non-sensitive settings and **Secret** for sensitive ones. This decoupling is what makes one image portable across dev, staging, and production.

### ConfigMap: non-sensitive configuration

A **ConfigMap** stores configuration as key-value pairs. It is *not* encrypted and is meant for non-confidential data like ports, log levels, or feature flags. Create one from literals on the command line:

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=NGINX_PORT=8080
```

…or declaratively in YAML, which is what you commit to your repo:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "info"
  NGINX_PORT: "8080"
```

There are two ways a Pod consumes a ConfigMap, and the same two work for Secrets:

**As environment variables.** Inject specific keys with `env`/`valueFrom`, or pull in every key at once with `envFrom`:

```yaml
        envFrom:
          - configMapRef:
              name: app-config        # all keys become env vars
        # or, one specific key:
        env:
          - name: LOG_LEVEL
            valueFrom:
              configMapKeyRef:
                name: app-config
                key: LOG_LEVEL
```

**As mounted files.** Mount the ConfigMap as a volume and each key becomes a file (e.g., under `/etc/config/`). This suits apps that read a config file rather than environment variables.

### Secret: sensitive values — and what "base64" really means

A **Secret** looks almost identical to a ConfigMap but is intended for sensitive data — passwords, tokens, TLS certificates, DB credentials:

```bash
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=S3cr3t123
```

Inject it the same way (note `secretKeyRef` / `secretRef` instead of the ConfigMap variants):

```yaml
        env:
          - name: DB_PASSWORD
            valueFrom:
              secretKeyRef:
                name: db-secret
                key: password
```

Now for the single most misunderstood point in all of Kubernetes:

> **Base64 is encoding, not encryption.** When you inspect a Secret with `kubectl get secret db-secret -o yaml`, the values look scrambled — but they are merely base64-encoded, which anyone can reverse instantly with `echo <value> | base64 --decode`. A Secret is **not** secured by default. Treat its YAML exactly as carefully as a plaintext password.

So what makes Secrets genuinely safer than ConfigMaps, and how do you protect them properly?

- **Enable encryption at rest** on the cluster so the values are encrypted inside etcd (Kubernetes' datastore). Without this, anyone with etcd access reads them in the clear. On EKS you can enable envelope encryption with a KMS key.
- **Never commit real Secret YAML to Git.** Use placeholders, or tooling like Sealed Secrets that stores an *encrypted* version safely in the repo.
- **For production, offload secrets to an external manager** — AWS Secrets Manager, HashiCorp Vault, or the External Secrets Operator — and let Kubernetes pull them in at runtime rather than storing the real values in the cluster at all. On EKS, the AWS Secrets and Configuration Provider (ASCP) can mount Secrets Manager values directly.
- **Rotate secrets regularly.** Credentials age; rotation limits the damage of a leak.

### Managing manifests at scale: Helm and Kustomize

So far you have a handful of hand-written YAML files for one environment. Real systems run the same app across dev, staging, and production with small differences (more replicas in prod, a different image tag, an environment-specific DNS name). Copy-pasting YAML per environment quickly becomes unmaintainable. Two tools solve this:

**Kustomize** is a *template-free* tool, built right into `kubectl` (`kubectl apply -k`). You keep a **base** directory of plain Kubernetes YAML and per-environment **overlays** that patch only what differs — namespace, replica count, image tag. Because there are no templating placeholders, your base files are still valid, readable Kubernetes manifests. A handy bonus is its `configMapGenerator`/`secretGenerator`: when the data changes, Kustomize appends a hash to the object's name, which *automatically triggers a rolling update* (plain ConfigMap edits do not). For many teams Kustomize hits the sweet spot of simple and powerful.

**Helm** is a *templating* package manager. It bundles your manifests into a reusable, versioned **chart** with a `values.yaml` file of parameters, so you (or others) can install the same app with different values. Helm shines for packaging off-the-shelf software (databases, monitoring stacks) and sharing reusable charts; the trade-off is that to be flexible you end up parameterizing many fields, which adds its own complexity.

You do not need to adopt either today — your hand-written manifests work fine for one app and one environment. But know the menu: reach for **Kustomize** when you need per-environment variants of your own app with minimal ceremony, and **Helm** when you are packaging something for reuse or installing third-party software.

### The finished pipeline — and applying it to your code

Step back and look at what you built across this course. The end-to-end flow is:

1. **Containerize** your app with a `Dockerfile` and stand up an **ECR** repository (Lecture 2).
2. **Push to GitLab** → a **webhook** triggers **Jenkins**, which checks out, tests, builds, and pushes a **commit-SHA-tagged image** to ECR (Lecture 3).
3. Describe the workload with **Deployment and Service manifests**, where the image tag is injected (Lecture 4).
4. Give Jenkins access to **EKS** via an **IAM role mapped to an RBAC group** (Lecture 5).
5. Jenkins' **deploy stage** updates the image (`kubectl apply` or `set image`) and waits with `kubectl rollout status` (Lecture 6).
6. EKS performs a **rolling update**, gated by **readiness/liveness probes**, with **`kubectl rollout undo`** ready as a one-command rollback (Lecture 7).
7. **ConfigMaps and Secrets** keep configuration out of the image, managed at scale with **Kustomize or Helm** (this lecture).

To run *your own* application through this pipeline, the pieces you customize are small and well-contained: your `Dockerfile`; your `deployment.yaml`/`service.yaml` (your image reference, container port, replica count, and probes); your ConfigMap/Secret for environment-specific values; and the environment variables in the `Jenkinsfile` (AWS account ID, region, ECR repo name, cluster name). The *shape* of the pipeline — webhook → build → push → deploy → verify — never changes. That reusability is the whole point: you set it up once and every project afterward inherits safe, automated, traceable deployments.

## Key Takeaways
- Keep configuration out of your image and manifest: ConfigMap for non-sensitive settings, Secret for sensitive ones; inject either as environment variables or mounted files.
- A Secret is base64-*encoded*, not encrypted — anyone can decode it. Protect real secrets with encryption at rest, by keeping them out of Git, and ideally with an external manager (AWS Secrets Manager, Vault) plus regular rotation.
- Manage manifests across environments with **Kustomize** (template-free base + overlays, built into `kubectl`) or **Helm** (templated, versioned charts); hand-written YAML is fine to start.
- The finished pipeline turns a single push into a safe, traceable, zero-downtime EKS deployment; adapting it to a new app means changing only the Dockerfile, manifests, config/secrets, and a few `Jenkinsfile` variables.
