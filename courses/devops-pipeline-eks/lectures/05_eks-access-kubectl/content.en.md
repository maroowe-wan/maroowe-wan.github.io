---
lecture_no: 5
title: "Accessing the EKS Cluster and Configuring kubectl"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=6COvT1Zu9o0
  - https://www.youtube.com/watch?v=6ZALmrssgfc
  - https://www.youtube.com/watch?v=rFtaknmZiaM
---

# Accessing the EKS Cluster and Configuring kubectl

## Learning Objectives
- Connect to an EKS cluster with `aws eks update-kubeconfig` and verify access.
- Understand the two access layers: AWS IAM (reach the cluster) and Kubernetes RBAC (act inside it).
- Map an IAM identity to a Kubernetes group so Jenkins can deploy unattended.

## Body

Your pipeline can build images (Lecture 3) and write manifests (Lecture 4), but nothing has *authenticated* to EKS yet. The one rule to remember: EKS access has **two independent layers**. AWS IAM decides whether you can reach the cluster at all; Kubernetes RBAC decides what you can do once inside. You need both.

### Task 1: Connect kubectl to the cluster

`kubectl` is the CLI for Kubernetes. It reads its connection settings (which cluster, which endpoint, which identity) from a **kubeconfig** file, by default `~/.kube/config`. For EKS you never hand-edit it — AWS generates the right entry for you. This command writes the cluster's API endpoint and certificate into your kubeconfig and configures it to fetch a short-lived AWS token for authentication.

```bash
aws eks update-kubeconfig --region us-east-1 --name my-cluster
```

Verify the connection:

```bash
kubectl get nodes
kubectl get pods -A
```

If nodes appear, you are in. If you get `Unauthorized` or "You must be logged in," that is **layer two** talking: your IAM identity reached the cluster, but RBAC has granted it nothing yet.

> Re-run `aws eks update-kubeconfig` whenever you switch clusters, AWS profiles, or machines. It is idempotent and safe to repeat. Add `--profile <name>` to connect as a specific AWS identity.

### Layer one: IAM — can you reach the cluster?

The kubeconfig tells `kubectl` to mint a token from your current **IAM identity** (a user or, better, a role), and EKS validates it against AWS. So the first gate is whether that identity may connect. A minimal policy grants `eks:DescribeCluster` so `update-kubeconfig` can fetch the endpoint. That is enough to *reach* the cluster — it grants no power *inside* it.

### Layer two: RBAC — what can you do inside?

Once your token is accepted, Kubernetes applies **RBAC (Role-Based Access Control)**, which has two halves:

- A **Role** (namespace-scoped) or **ClusterRole** (cluster-wide) lists permissions — verbs like `get`, `list`, `create` on resources like `pods`, `deployments`, `secrets`.
- A **RoleBinding** / **ClusterRoleBinding** attaches that Role to an identity (user, group, or service account).

### Task 2: Create a read-only viewer role and group

A read-only ClusterRole that can `get`, `list`, and `watch` pods, services, and deployments across all namespaces. Note how the rules are split by **API group**: `pods` and `services` live in the core group (`apiGroups: [""]`), while `deployments` lives in the `apps` group. Listing `deployments` under the core group is a common mistake — apply it and the deployment access silently fails with `Forbidden`, because no such resource exists in that group.

```yaml
# viewer.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: viewer
rules:
  - apiGroups: [""]                              # core group
    resources: ["pods", "services", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]                          # apps group
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: viewer-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: viewer
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: my-viewer        # the Kubernetes group we will map IAM to
```

```bash
kubectl apply -f viewer.yaml
```

This binds the `viewer` ClusterRole to a Kubernetes group named `my-viewer`. The group has no members yet — that link is made in the next task.

### Task 3: Map an IAM identity to the Kubernetes group

AWS knows IAM identities; Kubernetes knows its own users and groups. Something must **map** one to the other — for example, "IAM role `...:role/jenkins-deploy` is treated as the Kubernetes group `my-viewer`." Use **EKS access entries**, the modern, auditable approach (the older `aws-auth` ConfigMap still exists on legacy clusters but is deprecated).

```bash
# Register the IAM principal with the cluster
aws eks create-access-entry \
  --cluster-name my-cluster \
  --principal-arn arn:aws:iam::111122223333:role/jenkins-deploy \
  --kubernetes-groups my-viewer
```

The full chain is now: **IAM identity → access entry → Kubernetes group → binding → Role's permissions.** Break any link and you get `Unauthorized`.

### Task 4: Verify permissions

`kubectl auth can-i` answers permission questions directly — the fastest way to debug a binding:

```bash
kubectl auth can-i get pods           # -> yes
kubectl auth can-i get nodes          # -> no (viewer has no cluster-scoped node access)
kubectl auth can-i '*' '*'            # -> no (not an admin)
```

### Task 5: Let Jenkins authenticate (the real target)

Everything above applies to *you*; now apply it to *Jenkins*, which must run `kubectl` with no human typing credentials. The principle from Lecture 3 holds: **authenticate the machine via an IAM role, never static keys in a job.**

- **IRSA / EKS Pod Identity** — if Jenkins runs *inside* EKS, associate its service account with an IAM role; the Pod receives short-lived credentials automatically, with no secrets stored.
- **An instance/node IAM role** — if Jenkins runs on EC2, attach a role to the instance; the AWS CLI picks it up automatically.

Map that IAM role to an RBAC group scoped to deploy (typically `get`/`update`/`patch` on Deployments in one namespace). Then the deploy stage is just:

```bash
aws eks update-kubeconfig --region us-east-1 --name my-cluster
kubectl apply -f deployment.yaml
```

EKS accepts it because the IAM role is recognized (layer 1 + mapping) and has the right RBAC permissions (layer 2).

> Scope Jenkins to least privilege — update Deployments in one namespace, not `cluster-admin`. If the pipeline is compromised, a tight role limits the blast radius.

## Key Takeaways
- `aws eks update-kubeconfig --region <r> --name <cluster>` writes the cluster endpoint and auth into kubeconfig; `kubectl get nodes` confirms it.
- EKS access has two layers: **IAM** to reach the cluster, **RBAC** to act inside. `Unauthorized` usually means IAM worked but RBAC was not granted.
- In RBAC rules, group resources by their correct API group: `pods`/`services`/`configmaps` are core (`""`), while `deployments`/`replicasets`/`statefulsets`/`daemonsets` are `apps`. Misfiling a resource yields `Forbidden`.
- Map an IAM identity to a Kubernetes group with **EKS access entries** (modern) — chain is IAM → mapping → group → binding → permissions.
- Jenkins authenticates via an IAM role (IRSA/Pod Identity in-cluster, or an instance role on EC2), never static keys, scoped to least privilege.
- Use `kubectl auth can-i <verb> <resource>` to debug permissions fast.
