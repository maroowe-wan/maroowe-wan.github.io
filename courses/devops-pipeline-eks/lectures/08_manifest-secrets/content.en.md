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
- Manage manifests at scale with Kustomize (and know when to reach for Helm).
- Review the finished pipeline and how to apply it to your own code.

## Body

Real apps need configuration — database URLs, feature flags, API keys, passwords — that you should **never** bake into an image or hardcode in a manifest. Kubernetes keeps configuration separate from code with two objects: **ConfigMap** (non-sensitive) and **Secret** (sensitive). This is what makes one image portable across dev, staging, and production. Below, each task is a short *what/why*, the command or YAML, then a verification step.

### Create a ConfigMap

A **ConfigMap** stores non-sensitive settings as key-value pairs. Create it imperatively for quick tests, or declaratively (YAML) for anything you commit to Git.

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=NGINX_PORT=8080
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "info"
  NGINX_PORT: "8080"
```

Verify:

```bash
kubectl get configmap app-config -o yaml
```

### Inject a ConfigMap into a Pod

Pods consume a ConfigMap two ways (the same two work for Secrets): as **environment variables** or as **mounted files**. Use `envFrom` to pull in every key at once, or `env`/`valueFrom` for one specific key.

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

To mount as files instead, attach the ConfigMap as a volume; each key becomes a file under your mount path (e.g. `/etc/config/`). Verify inside the Pod:

```bash
kubectl exec -it <pod> -- env | grep LOG_LEVEL
# or, for file mounts:
kubectl exec -it <pod> -- ls /etc/config
```

### Create and inject a Secret

A **Secret** is for sensitive values — passwords, tokens, TLS certs, DB credentials. It looks almost identical to a ConfigMap, but signals intent and supports extra protections (see below).

```bash
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=S3cr3t123
```

Inject it just like a ConfigMap, but with `secretKeyRef` / `secretRef`:

```yaml
        env:
          - name: DB_PASSWORD
            valueFrom:
              secretKeyRef:
                name: db-secret
                key: password
```

Verify:

```bash
kubectl exec -it <pod> -- env | grep DB_PASSWORD
```

### Understand "base64" — and protect Secrets properly

When you inspect a Secret, the values look scrambled. They are not. This is the single most misunderstood point in Kubernetes.

```bash
kubectl get secret db-secret -o yaml
echo 'UzNjcjN0MTIz' | base64 --decode   # → S3cr3t123
```

> **Base64 is encoding, not encryption.** Anyone can reverse it instantly. A Secret is **not** secured by default — treat its YAML as carefully as a plaintext password.

To make Secrets genuinely safe:
- **Enable encryption at rest** so values are encrypted inside etcd (Kubernetes' datastore). On EKS, use envelope encryption with a KMS key.
- **Never commit real Secret YAML to Git.** Use placeholders, or Sealed Secrets (stores an *encrypted* version safely in the repo).
- **For production, offload to an external manager** — AWS Secrets Manager, HashiCorp Vault, or the External Secrets Operator — so the real values never live in the cluster. On EKS, the AWS Secrets and Configuration Provider (ASCP) can mount Secrets Manager values directly.
- **Rotate secrets regularly** to limit the damage of a leak.

### Manage manifests at scale with Kustomize

Running the same app across dev/staging/prod with small differences (replica count, image tag, namespace) makes copy-pasting YAML unmaintainable. **Kustomize** solves this and is built into `kubectl` (`apply -k`). It is **template-free**: a **base** of plain Kubernetes YAML plus per-environment **overlays** that patch only what differs — so your base files stay valid, readable manifests.

Lay it out like this:

```
base/
  deployment.yaml
  kustomization.yaml      # resources: [deployment.yaml]
overlays/
  staging/kustomization.yaml
  production/kustomization.yaml
```

A production overlay patches just the differences and points back to the base:

```yaml
# overlays/production/kustomization.yaml
namespace: production
resources:
  - ../../base
replicas:
  - name: nginx
    count: 20
images:
  - name: nginx
    newTag: 1.21.6
```

Apply and verify:

```bash
kubectl apply -k overlays/production
kubectl get pods -n production
```

A key bonus is `configMapGenerator`/`secretGenerator`: when the data changes, Kustomize appends a content hash to the object's name, which **automatically triggers a rolling update** — plain ConfigMap edits do not.

```yaml
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=info
secretGenerator:
  - name: db-secret
    literals:
      - password=S3cr3t123
```

> **When to use Helm instead.** **Helm** is a *templating* package manager that bundles manifests into versioned, reusable **charts** with a `values.yaml`. Reach for Helm when packaging software for reuse or installing third-party apps (databases, monitoring); reach for **Kustomize** for per-environment variants of your own app with minimal ceremony. Hand-written YAML is perfectly fine to start.

### The finished pipeline — and applying it to your code

Step back at what you built across this course. End to end:

1. **Containerize** your app with a `Dockerfile`; stand up an **ECR** repository (L2).
2. **Push to GitLab** → a **webhook** triggers **Jenkins**, which tests, builds, and pushes a **commit-SHA-tagged image** to ECR (L3).
3. Describe the workload with **Deployment + Service manifests** taking the injected image tag (L4).
4. Give Jenkins **EKS** access via an **IAM role mapped to an RBAC group** (L5).
5. Jenkins' **deploy stage** updates the image and waits with `kubectl rollout status` (L6).
6. EKS runs a **rolling update**, gated by **readiness/liveness probes**, with **`kubectl rollout undo`** as one-command rollback (L7).
7. **ConfigMaps and Secrets** keep config out of the image, managed at scale with **Kustomize or Helm** (this lecture).

To run *your own* app through this pipeline, the parts you customize are small: your `Dockerfile`; your `deployment.yaml`/`service.yaml` (image reference, port, replicas, probes); your ConfigMap/Secret; and a few `Jenkinsfile` variables (AWS account ID, region, ECR repo, cluster name). The *shape* — webhook → build → push → deploy → verify — never changes. You set it up once, and every project afterward inherits safe, automated, traceable deployments.

## Key Takeaways
- Keep configuration out of the image: **ConfigMap** for non-sensitive settings, **Secret** for sensitive ones; inject either as environment variables (`envFrom`/`valueFrom`) or as mounted files.
- A Secret is base64-*encoded*, not encrypted — anyone can decode it. Protect real secrets with encryption at rest, by keeping them out of Git, and ideally with an external manager (AWS Secrets Manager, Vault) plus rotation.
- **Kustomize** (template-free base + overlays, built into `kubectl`) manages per-environment variants; its generators hash data to auto-trigger rollouts. Use **Helm** for reusable/third-party charts.
- The finished pipeline turns a single push into a safe, traceable, zero-downtime EKS deployment; adapting it to a new app means changing only the Dockerfile, manifests, config/secrets, and a few `Jenkinsfile` variables.
