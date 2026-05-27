---
lecture_no: 5
title: "Continuous Delivery & Deployment Basics: Automating the Path to Production"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=skLJuksCRTw
  - https://www.youtube.com/watch?v=KTHZyV9yJGY
  - https://www.youtube.com/watch?v=4Nq8QbBtySU
---

# Continuous Delivery & Deployment Basics: Automating the Path to Production

## Learning Objectives
- Tell the difference between Continuous **Delivery** and Continuous **Deployment** (the two meanings of "CD").
- Understand how a pipeline carries a build from CI through staging and into production automatically.
- Walk through a simple deploy stage hands-on: **build the artifact → deploy it → verify it**.
- Recognize the common zero-downtime release patterns (Rolling, Blue-Green, Canary) at a beginner level.

## Body

### Where we left off: CI got us a tested build

In Lecture 4 we set up **Continuous Integration (CI)**: every time someone pushes code, the pipeline automatically builds the project and runs the tests. When CI is green, we know the code compiles and behaves as expected.

But a passing test suite sitting on a build server does nothing for your users. Someone still has to take that build and *put it on a running server*. That last mile, getting a verified build safely in front of real users, is what **CD** is about. CI answers "does the code work?"; CD answers "how do we ship it, reliably and repeatedly?"

> CI and CD are not two separate tools you bolt together. They are one continuous pipeline: CI is the front half (build and test), CD is the back half (release and deploy).

### Why bother automating deployment at all?

Here's a true story from the early days of this idea. A team rebuilding an ISP's system developed on Windows but deployed to Solaris servers. Their first deployment took **two weeks and failed**. Feedback on whether a change actually worked took another two or three weeks. Fixing anything was agony, and releases were dreaded weekend events.

They wrote a deployment script (they nicknamed it "Conan the Deployer") that automated the whole thing. Deployment time dropped from two weeks to about **one hour**, and rolling back a bad release took **under a second**. No more weekend deployments.

The lesson generalizes. When deploying is manual, slow, and scary, teams deploy rarely, in big risky batches. When deploying is automated, fast, and boring, teams deploy *often*, in small safe batches. And small, frequent deployments are actually **safer**, not riskier: when only a little changed since the last release, there's less that can break, and it's obvious where to look when something does. Flickr famously deployed more than ten times a day while staying highly available, proving that high deployment frequency and stability are not enemies.

This is the core DevOps insight behind CD: shorten the **lead time** (the clock from "code committed" to "running in production") and shrink the **batch size** of each release.

### The crucial distinction: Delivery vs. Deployment

Both expand to "CD," and people use them loosely, but they mean genuinely different things. The difference is **who pushes the final button to production.**

- **Continuous Delivery** — After CI, the pipeline automatically prepares a release and pushes it all the way to a staging environment, leaving production *one click away*. Every change is provably **ready** to ship at any moment, but a human decides *when* to actually release. Production deployment is automated but **manually triggered**.

- **Continuous Deployment** — One step further. There is no manual gate. Every change that passes all automated checks goes straight to production **automatically**, with no human in the loop.

The plain-language version: Continuous Delivery means *"the release is always ready; a person presses go."* Continuous Deployment means *"if the tests pass, it's already live."* The diagram below shows that the two paths are identical until the final step to production, where Delivery inserts a human gate that Deployment removes.

```mermaid Continuous Delivery vs. Continuous Deployment: the only difference is the gate to production
flowchart LR
    C[Commit] --> B[Build and Test CI]
    B --> S[Deploy to Staging]
    S --> D{Path to Production}
    D -->|Continuous Delivery| H[Human Approval Gate]
    H --> P1[Production]
    D -->|Continuous Deployment| P2[Production]
```

Continuous Deployment demands deep confidence in your automated tests, because nothing else stands between a commit and your users. Most teams adopt Continuous *Delivery* first (keep the human gate) and graduate to Continuous *Deployment* only once their test coverage and monitoring earn that trust.

> A handy memory hook: De**L**ivery keeps a human in the **L**oop before production. De**P**loyment **P**ushes straight through.

There's a third related idea worth knowing: **separating deploy from release**. You can *deploy* code to production servers without *releasing* the feature to users. A **feature toggle** (a runtime on/off switch) lets the new code sit live but dark, then turn on for 1% of users, then 10%, then everyone. Facebook does exactly this. Deploy is a technical event; release is a business decision, and decoupling them removes a lot of fear.

### The shape of a deployment pipeline

A pipeline is a chain of stages where each stage must pass before the next begins. If any stage fails, the pipeline stops and nothing reaches production. A typical flow looks like this:

1. **Source** — A push or merge to the main branch triggers the pipeline.
2. **Build** — Compile the code and produce an **artifact**: a single, versioned, deployable package (a `.jar`/`.war`, a Docker image, a zipped bundle). The artifact is built **once** and the *same* artifact is promoted through every later stage, so what you test is exactly what you ship.
3. **Test** — Run the automated checks: unit, integration, and end-to-end tests. (This is the CI portion.)
4. **Deploy to staging** — Push the artifact to a **staging** environment: a clone of production used for final verification.
5. **Verify** — Run smoke tests or health checks against staging to confirm the app actually came up and responds correctly.
6. **Deploy to production** — Promote the *same artifact* to production. Under Continuous Delivery this step waits for a human approval; under Continuous Deployment it runs automatically.

Stages can also branch and rejoin. For example, after the build, a static-code-quality scan and the unit tests can run **in parallel**, and only when *both* succeed does the deploy stage start. The diagram below traces this full gated flow, including the fail-fast exit that stops a bad build from reaching production. Real tools like Jenkins, GitHub Actions, GitLab CI, and CircleCI all model exactly this idea: sequential stages, optional parallelism, and a fail-fast gate at every step.

```mermaid Deployment pipeline: gated stages with a parallel check and a fail-fast exit
flowchart TB
    SRC[Source: push to main] --> BLD[Build artifact once]
    BLD --> SCAN[Static code scan]
    BLD --> UT[Unit and integration tests]
    SCAN --> GATE{Both passed?}
    UT --> GATE
    GATE -->|No| STOP[Stop pipeline, nothing ships]
    GATE -->|Yes| STG[Deploy same artifact to staging]
    STG --> VER[Verify with smoke tests]
    VER --> PROD[Promote same artifact to production]
```

### Getting to production without going down: zero-downtime patterns

If you naively stop the old version and start the new one, users hit errors during the gap. Three common patterns avoid that:

- **Rolling deployment** — Replace instances a few at a time. While some servers run the new version, the rest keep serving the old one, so the service never fully goes down. Simple and the default in many platforms.
- **Blue-Green deployment** — Run two complete environments. "Blue" serves live traffic while you deploy and test the new version on idle "Green." When Green checks out, you flip the router to send all traffic to Green. If something's wrong, flip back instantly. This is what made that "rollback in under a second" possible earlier.
- **Canary deployment** — Send the new version to a small slice of traffic first (the "canary"). Watch the metrics; if it's healthy, gradually widen to 100%. If error rates spike, pull it back before most users ever saw it.

The Blue-Green pattern is the easiest to picture: traffic only ever points at one environment, and "releasing" or "rolling back" is just flipping that pointer, as shown below.

```mermaid Blue-Green deployment: the router flips traffic between two complete environments
flowchart LR
    U[Users] --> R{Router}
    R -.->|"flip to release"| G[Green: new version]
    R ==>|"live traffic"| B[Blue: old version]
    B -. "stays live until Green proves itself" .-> G
```

You don't need to master these today. Just know that "deploy" doesn't have to mean "take the site offline," and that the safest patterns all share one trait: **the old version stays available until the new one has proven itself.**

## Hands-On: a build → deploy → verify pipeline

Let's make the three-step deploy stage concrete with **GitHub Actions** (the same tool from Lecture 4). The flow follows the curriculum's spec exactly: produce an **artifact**, **deploy** it, then **verify** it.

The key design choice is that we **build the artifact in one job and hand it to the deploy jobs**, rather than rebuilding in each environment. In GitHub Actions, each job runs on a fresh machine and they don't share files automatically, so we use two built-in actions to pass the package along: `actions/upload-artifact` (in the build job) saves `app.tar.gz` into GitHub's artifact store, and `actions/download-artifact` (in each deploy job) pulls *that exact file* back down. This is how "built once, promoted unchanged" becomes real instead of just a slogan.

```yaml
# .github/workflows/deploy.yml
name: CD Pipeline

on:
  push:
    branches: [ main ]          # every merge to main triggers a release

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      # 1) Get the code
      - uses: actions/checkout@v4

      # 2) BUILD THE ARTIFACT (built once, reused everywhere downstream)
      - name: Build artifact
        run: |
          npm ci
          npm run build           # produces ./dist as our deployable artifact
          tar -czf app.tar.gz dist # package it into a single versioned bundle

      # 3) UPLOAD the artifact so later jobs can promote the SAME bundle
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: app-bundle        # the name other jobs will download by
          path: app.tar.gz

  deploy-staging:
    needs: build                  # waits for the build job to finish
    runs-on: ubuntu-latest
    steps:
      # 4) DOWNLOAD the exact artifact the build job produced (no rebuild!)
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: app-bundle        # same name we uploaded above

      # 5) DEPLOY that downloaded artifact to staging
      - name: Deploy to staging
        run: |
          echo "Shipping the prebuilt app.tar.gz to staging server..."
          scp app.tar.gz deploy@staging.example.com:/var/www/app/
          ssh deploy@staging.example.com 'cd /var/www/app && tar -xzf app.tar.gz && systemctl restart app'

      # 6) VERIFY the deployment actually works (smoke test)
      - name: Smoke test
        run: |
          sleep 5
          curl --fail https://staging.example.com/health || exit 1
          echo "Deployment verified: app is up and healthy."
```

Read it as a story:

- **`on: push` to `main`** is the trigger, the start of the pipeline.
- **`build`** turns source into `app.tar.gz` and uploads it as `app-bundle`. This is the *only* place the code is compiled and packaged.
- **`deploy-staging`** downloads `app-bundle`, the very same package the build job made, and ships it. Notice it never runs `npm run build`: there is nothing to rebuild because the artifact already exists.
- **Smoke test** hits a `/health` endpoint. The `--fail` flag makes `curl` return an error on a bad HTTP status, and `|| exit 1` fails the whole job. **If verification fails, the pipeline is red and you know before your users do.**

To turn this into **Continuous Delivery** rather than full Continuous Deployment, add a third job that promotes to *production* but requires a manual approval first, using a GitHub **environment** with a required reviewer. Crucially, it downloads the *same* `app-bundle` again, so production gets byte-for-byte what staging verified:

```yaml
  deploy-production:
    needs: deploy-staging         # only after staging succeeded and was verified
    runs-on: ubuntu-latest
    environment:
      name: production            # configure this environment to require approval
    steps:
      # Pull the SAME artifact the build job produced, no rebuild, no new package
      - name: Download artifact
        uses: actions/download-artifact@v4
        with:
          name: app-bundle        # identical bundle that staging already verified

      - name: Promote to production
        run: |
          echo "Promoting the staging-verified app.tar.gz to production..."
          scp app.tar.gz deploy@prod.example.com:/var/www/app/
          ssh deploy@prod.example.com 'cd /var/www/app && tar -xzf app.tar.gz && systemctl restart app'
```

That `environment: production` with a required reviewer **is** the human-in-the-loop gate that defines Continuous Delivery. Remove the approval requirement and you've crossed into Continuous Deployment.

> Notice the artifact is built once in the `build` job and *downloaded* into both deploy jobs. Never rebuild between staging and production, rebuilding risks shipping something subtly different from what you tested.

## Key Takeaways
- **CI** verifies the code works; **CD** gets that verified build safely and repeatedly to users.
- **Continuous Delivery** keeps every change *ready* to ship with a human pressing the final button; **Continuous Deployment** ships automatically with no manual gate. The difference is whether a human approves the production step.
- A deployment pipeline is a chain of gated stages: **source → build (artifact) → test → deploy to staging → verify → deploy to production**. Build the artifact once and promote the *same* one forward (in GitHub Actions, upload it once and download it in each deploy job).
- Small, frequent, automated deployments are **safer** than rare big-bang releases: less changes, easier rollback, faster feedback (shorter lead time).
- **Deploy ≠ release**: feature toggles let you deploy dark and turn features on gradually.
- Zero-downtime patterns, **Rolling**, **Blue-Green**, and **Canary**, all keep the old version live until the new one proves itself.
