---
lecture_no: 1
title: Building Least-Privilege Containers with Kubernetes SecurityContext
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=ZoTKkmY6VSw
  - https://www.youtube.com/watch?v=fyMiIM_UReU
  - https://www.youtube.com/watch?v=Nppym_oFdYQ
---

# Building Least-Privilege Containers with Kubernetes SecurityContext

## Learning Objectives
- Understand the difference between Pod-level and container-level `securityContext`, and how the two merge so you place each setting where it belongs.
- Explain the meaning and security impact of the core fields: `runAsNonRoot`/`runAsUser`, `allowPrivilegeEscalation`, `readOnlyRootFilesystem`, capability `drop`/`add`, and `seccompProfile`.
- Combine those fields into a least-privilege container manifest that strips root and unnecessary kernel capabilities, then verify the result inside a running Pod.

## Body

### Why secure a Pod at all?

Kubernetes makes it trivially easy to run a container, but it does nothing to *secure* that container by default. Spin up a plain Pod, exec into it, and run `id` — chances are you are **UID 0**, the root user, a member of the `root` and `wheel` groups. In other words, the process inside your container has administrator-equivalent power within its namespace.

That default is the opposite of how production systems should be built. The guiding rule of container security is the **principle of least privilege**: grant a process only the permissions it actually needs, and nothing more. Running as root violates that rule in several concrete ways:

- **Privilege escalation.** If an attacker compromises a root container, they already hold root inside it and can attempt to break out toward the host kernel.
- **Host exposure.** In environments without user namespaces or strict isolation, a root container can reach elevated access to the underlying node.
- **Accidental damage.** A workload that only needs to read data has no business being able to overwrite system files. Root makes those mistakes possible.
- **Compliance.** Many third-party security standards explicitly require workloads to run as non-root. If your platform must meet them, this is not optional.

> The cost of hardening a container is a few lines of YAML. The cost of *not* hardening it is the entire blast radius of a container breakout. Make least privilege your baseline, not an afterthought.

Kubernetes gives you two tools to enforce this: the **`securityContext`** (settings that constrain users, filesystems, and privileges) and **Linux capabilities** (fine-grained slices of root power that you can grant or deny individually).

### Pod-level vs. container-level securityContext

A `securityContext` block can live in two places, and knowing the difference is the whole game:

- **Pod-level** — under `spec.securityContext`. It applies to *every* container in the Pod and is the right home for settings that should be uniform across the workload.
- **Container-level** — under `spec.containers[].securityContext`. It applies to a single container.

Think of the fields as falling into three buckets:

| Bucket | Where it can be set | Examples |
|--------|--------------------|----------|
| Pod-only | Pod level only | `fsGroup` |
| Pod **and** container | Either, container wins on conflict | `runAsUser`, `runAsGroup`, `runAsNonRoot`, `seccompProfile` |
| Container-only | Container level only | `allowPrivilegeEscalation`, `readOnlyRootFilesystem`, `privileged`, `capabilities` |

The **merge rule** is the key takeaway: when a field is set in *both* places, the container-level value overrides the Pod-level value for that container. So a common, clean pattern is to set safe organization-wide defaults at the Pod level, then override them per container only where a specific workload genuinely needs something different.

The merge behavior works like this, as the diagram below shows for the `runAsUser` field:

- Set `runAsUser: 1000` at the Pod level → all containers run as 1000.
- One container also sets `runAsUser: 2000` at its own level → that container runs as 2000; the others still run as 1000.

```mermaid How Pod-level and container-level securityContext merge per container
flowchart TD
    Pod["Pod-level securityContext\nrunAsUser: 1000"] --> Q{"Container also sets\nthis field?"}
    Q -->|"No (Container A)"| Inherit["Inherit Pod value\nruns as UID 1000"]
    Q -->|"Yes (Container B sets runAsUser 2000)"| Override["Container value wins\nruns as UID 2000"]
```

### The core fields, one by one

**`runAsUser` / `runAsGroup`.** Force the container's processes to run with a specific numeric UID and GID. Linux cares about numbers, not names — if no matching username exists, `id` will print `uid=1000(unknown)`, which is normal, not an error.

**`runAsNonRoot: true`.** A safety gate. It does not pick a UID for you; it simply refuses to start the container if the resolved user would be root (UID 0). If you apply this to a stock `nginx` image (which defaults to root) without also providing a non-root `runAsUser`, the Pod will fail to start — that failure is the feature working as intended.

**`allowPrivilegeEscalation: false`.** Prevents a process from gaining *more* privileges than its parent. Without it, a `setuid`-root binary could let a UID-1000 process execute with root power inside the container. Setting it to `false` closes that door and should be your default.

**`privileged: false`.** `privileged: true` hands the container near-total access to the host, including kernel-level operations. In production this should essentially always be `false` (which is also the default).

**`readOnlyRootFilesystem: true`.** Mounts the container's root filesystem (`/`) as read-only, so the process cannot create or modify files there. If your app only reads, give it nothing to write. When the app *does* need a writable path — logs, caches, mounted data — you carve out exactly that path with a volume instead of leaving the whole filesystem open.

**`fsGroup`.** A Pod-level field that sets the group owner of mounted volumes. It is the companion to `readOnlyRootFilesystem`: the root filesystem stays read-only, but a volume owned by `fsGroup` becomes writable by the container's user, because that user is a member of the group.

**`capabilities` (drop / add).** Root is not one monolithic permission; it is a bundle of distinct kernel powers called *capabilities* — `CHOWN` (change file ownership), `NET_ADMIN` (modify network interfaces and routing), `SYS_TIME` (change the system clock), and many more. The least-privilege pattern is **`drop: ["ALL"]`** to revoke every capability, then **`add`** back only the specific ones the workload provably needs. Start by dropping everything; if the app breaks, read its error, and add the single capability that fixes it. Never start from `add: ["ALL"]`.

**`seccompProfile`.** Seccomp filters which Linux *syscalls* a process may make, shrinking the kernel attack surface further. Setting `type: RuntimeDefault` applies the container runtime's curated default filter and is the recommended baseline for almost every workload.

### Putting it together: a least-privilege manifest

Here is a Pod that combines all of the above into a hardened, least-privilege workload. Defaults that should be uniform live at the Pod level; the write-sensitive flags live at the container level.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  securityContext:                  # Pod-level: applies to every container
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000                   # mounted volumes are group-owned by 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: busybox:1.36
      command: ["sleep", "3600"]
      securityContext:              # container-level: overrides + container-only fields
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]             # remove every kernel capability
      volumeMounts:
        - name: writable
          mountPath: /writable      # the one path the app may write to
  volumes:
    - name: writable
      emptyDir: {}
```

What this manifest guarantees:

- The process runs as UID 1000 / GID 3000, never as root, and the Pod will refuse to start if anything would force root.
- No privilege escalation, no extra capabilities, a default seccomp filter — the kernel attack surface is minimal.
- The root filesystem is read-only, **except** `/writable`, which is backed by an `emptyDir` volume group-owned by `fsGroup` 2000, so UID 1000 can write there.

### Verifying the result

Apply it and inspect the running container:

```bash
kubectl apply -f secure-app.yaml
kubectl exec -it secure-app -- sh
```

Inside the Pod, run these checks:

```text
$ id
uid=1000 gid=3000 ...            # confirmed non-root; "unknown" name is fine

$ mkdir /test
mkdir: can't create directory '/test': Read-only file system

$ touch /writable/hello
$ ls -l /writable
-rw-r--r--  1 1000  2000  ...    # owner 1000, group 2000 — writable as designed
```

The denial on `/test` proves `readOnlyRootFilesystem` is enforced; the success on `/writable` proves `fsGroup` granted exactly the access you intended. Because capabilities were dropped, a command like `chown 0:0 /writable/hello` returns `Operation not permitted` — the container has no `CHOWN` capability to change ownership.

You can also let the cluster enforce these rules for you. **Pod Security Admission** can reject any manifest that omits these settings at the namespace level, so a deployment with an empty `securityContext` is denied before it ever runs. That turns least privilege from a convention developers must remember into a guardrail the platform enforces.

## Key Takeaways
- Containers run as **root by default** — least privilege means stripping that root and every capability the workload does not strictly need.
- `securityContext` lives at two levels; when a field is set in both, **container-level overrides Pod-level**. Set uniform defaults at the Pod level, override per container only when required.
- The hardening baseline is: `runAsNonRoot: true` + a non-root `runAsUser`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]`, and `seccompProfile.type: RuntimeDefault`.
- Use `fsGroup` plus a mounted volume to grant writes to exactly one path while keeping the root filesystem read-only.
- For capabilities, **drop all, then add back only what breaks** — never start from `add: ["ALL"]`.
- Verify with `kubectl exec` (`id`, a write attempt on `/`, a write on the volume), and enforce the policy cluster-wide with Pod Security Admission.
