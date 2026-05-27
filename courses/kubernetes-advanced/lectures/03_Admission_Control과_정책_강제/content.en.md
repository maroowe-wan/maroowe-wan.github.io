---
lecture_no: 3
title: Admission Control and Policy Enforcement — Webhooks, OPA/Kyverno, and Pod Security
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=urvSPmlU69k
  - https://www.youtube.com/watch?v=ocSgbSCX34M
  - https://www.youtube.com/watch?v=iZTQv4F7Djk
---

# Admission Control and Policy Enforcement — Webhooks, OPA/Kyverno, and Pod Security

## Learning Objectives
- Understand where Validating and Mutating Admission Webhooks sit in the API request processing pipeline
- Define policies with OPA Gatekeeper or Kyverno to block or mutate non-compliant resources
- Apply Pod Security Admission to enforce security standards at the namespace level

## Content

### Where Does an API Request Get Inspected?

When you run `kubectl apply`, the request passes through a series of checkpoints before it is persisted to etcd. Knowing the exact order is the starting point for this lecture.

1. **Authentication** — Who is making this request?
2. **Authorization (RBAC)** — Does this identity have permission to perform this action?
3. **Mutating Admission** — **Transforms** the request object (field injection, default value assignment).
4. **Schema Validation (OpenAPI)** — Is the object structure valid?
5. **Validating Admission** — **Allows or denies** the object against defined policies.
6. **etcd persistence**

The flowchart below shows the checkpoint order and where a request stops when each stage rejects it. Note that **Mutating Admission can also reject a request**: if a registered webhook server is unavailable (e.g., the service is down) and `failurePolicy: Fail` is set, the request is rejected right there. In other words, admission can block a request at both the Mutating and Validating stages.

```mermaid API Request Processing Flow — Auth, Admission, and Rejection Paths
flowchart LR
    R["kubectl request"] --> AUTHN["Authentication"]
    AUTHN --> AUTHZ["Authorization (RBAC)"]
    AUTHZ --> MUT["Mutating Admission - transform object"]
    MUT --> SCHEMA["Schema Validation (OpenAPI)"]
    SCHEMA --> VAL["Validating Admission - allow/deny"]
    VAL --> ETCD["etcd persistence"]
    AUTHN -. failure .-> X["Request rejected"]
    AUTHZ -. failure .-> X
    MUT -. "failure (failurePolicy: Fail / policy violation)" .-> X
    SCHEMA -. failure .-> X
    VAL -. denial .-> X
```

Steps 3 and 5 constitute the Admission Control phase. Where RBAC asks "can this user create a Pod?", Admission asks "does the **content** of this Pod comply with our policies?" Even with the right permission, a request is blocked if the content violates the rules.

**Mutating runs before Validating** for a clear reason: the object must first be corrected (e.g., inject a missing label, add a sidecar), and then the finalized form is validated for consistency. Sidecar injection and default resource limit injection are typical examples of what happens at the Mutating stage.

> Both webhooks can reject a request, but their **roles** differ. Think of Validating Admission as a "checkpoint" and Mutating Admission as a "transformation step." If any Validating Webhook denies the request, the entire request is rejected. Multiple Mutating Webhooks run sequentially and each cumulatively transforms the object — but a webhook can also reject mid-transformation, or fail entirely when `failurePolicy: Fail` is set, causing the request to be blocked at that point.

### `failurePolicy` — What Happens When a Webhook Is Down?

A webhook server is an external service and can go down. `failurePolicy` tells the API server how to handle a failed webhook call.

- **`Fail` (default)** — If the webhook call fails, the request is **rejected**. Use this for security policies where "no exceptions" is the requirement. The downside is that if the webhook server goes down, all resource creation guarded by it is blocked.
- **`Ignore`** — If the webhook call fails, the request **proceeds**. Availability takes priority, but policies will not be enforced during the outage, leaving a window of exposure.

This is a security vs. availability trade-off. The standard approach is to set critical security webhooks to `Fail` while operating the webhook server itself in a highly available configuration.

### How Admission Webhooks Work

Kubernetes uses `ValidatingWebhookConfiguration` and `MutatingWebhookConfiguration` resources to plug an external service into the admission pipeline. When a specified operation arrives (e.g., `CREATE` on `pods`), the API server sends an `AdmissionReview` request over HTTPS to the registered webhook server and processes the `allowed: true/false` response (or a JSON patch for mutations).

Implementing a webhook server directly is powerful but burdensome — TLS certificate management, high availability, and logic authoring all add overhead. In practice, the standard approach is to run a **policy engine** (OPA Gatekeeper or Kyverno) as the webhook server and write policies declaratively.

### Defining and Enforcing Policies with OPA Gatekeeper

OPA (Open Policy Agent) Gatekeeper operates on a CRD-based model. You need to understand two resource types:

- **ConstraintTemplate** — A reusable template that encodes policy *logic* in the Rego language (analogous to a parameterized function).
- **Constraint** — An instance that specifies *where and with what parameters* to apply the template.

For example, the policy "every Namespace must have a `team` label" looks like this:

```yaml
# ConstraintTemplate: policy logic (Rego)
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items: { type: string }
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels
        violation[{"msg": msg}] {
          required := input.parameters.labels
          provided := input.review.object.metadata.labels
          missing := required[_]
          not provided[missing]
          msg := sprintf("Required label missing: %v", [missing])
        }
```

```yaml
# Constraint: apply the template above to Namespaces
apiVersion: constraints.gatekeeper.sh/v1
kind: K8sRequiredLabels
metadata:
  name: ns-must-have-team
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Namespace"]
  parameters:
    labels: ["team"]
```

> The `apiVersion` for a Constraint in current versions of Gatekeeper is `constraints.gatekeeper.sh/v1`. Older examples commonly show `v1beta1`, which remains compatible, but for anything written today the stable `v1` API is the recommended practice.

After applying these, attempting to create a Namespace without the `team` label is denied at the admission stage:

```
admission webhook "validation.gatekeeper.sh" denied the request:
[ns-must-have-team] Required label missing: team
```

> Set Gatekeeper's `enforcementAction` to `dryrun` or `warn` to record or warn about violations without blocking them. When introducing policies to an existing cluster, always start with `dryrun` to **audit how many existing resources are affected**, then switch to `deny` once you have confirmed it is safe. Jumping straight to `deny` can block running deployments.

### Kyverno — Policies Written in YAML

Kyverno's appeal is that policies are written in **standard Kubernetes YAML syntax** rather than Rego. The learning curve is low, adoption is fast, and validate, mutate, and generate (automatic creation of subordinate resources) are all handled by a single tool.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-team-label
spec:
  validationFailureAction: Enforce   # Audit means warn only
  rules:
    - name: check-team-label
      match:
        any:
          - resources: { kinds: ["Pod"] }
      validate:
        message: "Pod requires a 'team' label."
        pattern:
          metadata:
            labels:
              team: "?*"             # requires a non-empty value
```

In summary: OPA Gatekeeper excels at complex rules thanks to Rego's expressiveness, while Kyverno wins on ease of operation with its YAML-native syntax and integrated mutate/generate support. Choose based on your organization's needs.

### Pod Security Admission — Built-In Security Standards

Even without installing a webhook or policy engine, Kubernetes ships with **Pod Security Admission (PSA)** built in (the successor to PodSecurityPolicy). PSA evaluates Pod specs against three standard profiles:

- **privileged** — No restrictions (for system and infrastructure workloads)
- **baseline** — Minimum protections against known privilege escalation vectors
- **restricted** — Strongly hardened (enforces non-root, blocks privilege escalation, etc.)

Applying PSA requires nothing more than **namespace labels**. The recommended practice is to use all three modes together (`enforce`/`audit`/`warn`).

```bash
kubectl label namespace payments \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

Now any attempt to run a root-privileged Pod in the `payments` namespace will be rejected, and `warn` will surface a warning in kubectl output even before `enforce` blocks it. This lets you enforce a namespace-level security tier without installing any additional components, making it an excellent first line of defense before deploying a full policy engine.

## Key Takeaways
- API requests are processed in the order: Authentication → Authorization (RBAC) → Mutating → Schema Validation → Validating → etcd. Admission inspects and transforms **content**; RBAC checks **permissions** — they serve different roles.
- Mutating Webhooks transform objects (e.g., sidecar injection); Validating Webhooks allow or deny requests. Mutating runs first. **Both stages can reject a request** — particularly if `failurePolicy: Fail` is set and the webhook is unreachable.
- OPA Gatekeeper enforces policies through a ConstraintTemplate (Rego logic) + Constraint (application) structure. Use `constraints.gatekeeper.sh/v1` for the Constraint `apiVersion`, and start with `dryrun`/`audit` before enabling `deny`.
- Kyverno provides validate, mutate, and generate in a unified tool using familiar Kubernetes YAML syntax, resulting in a low learning curve.
- Pod Security Admission is a built-in feature that enforces security standards via namespace labels (privileged/baseline/restricted × enforce/audit/warn) without any additional components.
