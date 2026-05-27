---
lecture_no: 8
title: Health Checks, Rollback, and Managing Secrets
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=z7nLsJvEyMY
  - https://www.youtube.com/watch?v=oWrwi1NiViw
  - https://www.youtube.com/watch?v=J9JbzsufemE
---

# Health Checks, Rollback, and Managing Secrets

## Learning Objectives
- Use a health check to confirm a deploy succeeded, and roll back to the previous image if it didn't.
- Keep secrets and environment variables out of your code and inject them safely.
- Review the finished pipeline and understand how to adapt it to your own application.

## Body

### The gap our pipeline still has

The pipeline from the last lecture works — but it's optimistic. It pulls the new image, swaps the container, and assumes everything is fine. If the new version crashes on startup or fails to respond, you've just replaced a working app with a broken one and nobody noticed. No amount of testing eliminates that last 1% chance of a bad deploy. This lecture adds the safety net that turns a working pipeline into a trustworthy one.

### Step 1 — Health checks: don't trust, verify

A **health check** is a small test that asks the freshly deployed app, "are you actually alive and serving?" The naive version is to `sleep` for a few seconds and then probe — but a fixed sleep is a **race condition**: too short and you probe before the app is ready (a false failure); too long and you waste time on every deploy. The robust idea is to **poll** the endpoint with retries until it answers or you run out of attempts — succeed the instant the app is ready, and only fail after a real, bounded timeout.

You *could* hand-write that polling loop in bash, but Docker Compose already does it for you. Define a container-level `healthcheck` on the service, and Compose will run that probe on its own schedule and track each container's health status:

```yaml
services:
  web:
    image: ${IMAGE}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 3s
      retries: 3
```

Once the `healthcheck` is defined, start the deploy with `docker compose up -d --wait`. The `--wait` flag blocks until every service reports **healthy**, then exits `0`; if any service never becomes healthy within its retry budget, it exits **non-zero**. That single command *is* your health check: it does the polling, the bounded timeout, and the pass/fail decision in one step — so the pipeline just trusts its exit code.

> `--wait` only works if the service has a `healthcheck` defined — otherwise Compose only waits for the container to *start*, not to become *healthy*. Define the healthcheck, run `docker compose up -d --wait`, and let its exit code decide success or failure. Never trust a fixed `sleep`, which races the app's startup time.

### Step 2 — Rollback: a known-good escape hatch

What happens when the health check fails — that is, when `docker compose up -d --wait` exits non-zero? You roll back — redeploy the **previous** working image. This is exactly why we tagged images with the commit SHA back in lecture 6: every past version still sits in ECR under its own immutable tag, so "the previous version" is always one `docker compose up` away.

The catch is that the pipeline has to *remember* which tag was the last known-good one. A `failure` block can't magically know it — so the trick is: **on a successful, verified deploy, write the deployed tag to a file on the server; on failure, read that file back and redeploy it.** That file is the durable record of "what was working before this attempt."

The flowchart below shows the decision. The deploy command and the health check are one step now: `docker compose up -d --wait` either exits `0` (healthy — promote the new version and record its tag) or non-zero (unhealthy — read the saved tag and redeploy it).

```mermaid Deploy-and-verify in one step, with automatic rollback on a non-zero exit code
flowchart TD
    Deploy["docker compose up -d --wait\n(deploy + poll healthcheck in one step)"] -->|exit 0 (healthy)| Keep["Keep new version live + record tag to last_good"]
    Deploy -->|exit non-zero (unhealthy)| Rollback["Read last_good tag, redeploy that image"]
    Rollback --> Restored["Last known-good version restored"]
```

Here is the working logic. `docker compose up -d --wait` is both the deploy and the verification: if it returns successfully the script continues and records the new tag; if it fails, the shell command fails, the stage fails, and the `post { failure }` block reads the saved tag and redeploys it:

```groovy
stage('Deploy & Verify') {
    environment { COMMIT = "${env.GIT_COMMIT}" }   // the new image tag
    steps {
        sshagent(['ec2-ssh-key']) {
            sh '''
                ssh ec2-user@<EC2_HOST> "
                    export IMAGE=<registry>/myapp:${COMMIT}
                    # --wait blocks until the healthcheck passes and exits
                    # non-zero if it doesn't, so this single line is the verify step.
                    # If it fails, ssh returns non-zero, the stage fails, and
                    # the post { failure } block below handles the rollback.
                    docker compose up -d --wait
                    # Reached only when the deploy is verified healthy:
                    echo ${COMMIT} > /home/ec2-user/last_good_tag
                "
            '''
        }
    }
    post {
        failure {
            sshagent(['ec2-ssh-key']) {
                sh '''
                    ssh ec2-user@<EC2_HOST> "
                        PREV=\\$(cat /home/ec2-user/last_good_tag 2>/dev/null)
                        if [ -n \\"\\$PREV\\" ]; then
                            export IMAGE=<registry>/myapp:\\$PREV
                            docker compose up -d --wait
                        else
                            echo 'No known-good tag recorded yet; cannot auto-roll back' >&2
                            exit 1
                        fi
                    "
                '''
            }
        }
    }
}
```

The mechanism is self-correcting: because the tag is written **only after** a deploy is verified healthy, `last_good_tag` always names a version that genuinely worked. A failed deploy never overwrites it, so the rollback always targets a real, last-known-good image. (If you'd rather not keep a file on the server, the same idea works by querying the currently running image with `docker inspect` before the swap, or by storing the tag as a Jenkins build artifact.)

For truly zero-downtime swaps, teams go further with strategies like **blue-green deployment** (run two identical environments and flip traffic from the old "blue" to the new "green," switching back instantly if needed) or **canary deployment** (route a small slice of traffic to the new version first and watch before going to 100%). Those are the next level up; for a single EC2 host, a fast health-check-plus-rollback already removes most of the risk, and `docker compose up -d`'s rolling replacement keeps the window of unavailability tiny.

### Step 3 — Keep secrets out of your code

Your app needs sensitive values: database passwords, API keys, the ECR registry address. The cardinal rule is **never commit a secret to your repository.** Anything in Git is permanent and visible to everyone with access — including in the history, long after you "delete" it.

Instead, separate secrets from code and inject them at runtime:

- **In Jenkins** — store credentials in the built-in credential store and pull them in with `withCredentials`, which masks them in the build log:

  ```groovy
  withCredentials([string(credentialsId: 'db-password', variable: 'DB_PASS')]) {
      sh 'deploy-using $DB_PASS'
  }
  ```

- **At the container level** — pass values in as environment variables via Compose, sourced from a `.env` file that lives on the server and is *git-ignored*, never committed:

  ```yaml
  services:
    web:
      image: ${IMAGE}
      env_file: /home/ec2-user/app.env
  ```

The same secret should never appear in two places. Jenkins holds the secrets it needs to *deploy*; the server holds the secrets the app needs to *run*. Mark secrets as protected and masked wherever the tool allows, so they don't leak into logs.

### The finished pipeline, end to end

Step back and look at what you've assembled across these eight lectures. The complete flow is:

1. You push code to **GitLab**.
2. A **webhook** triggers **Jenkins**.
3. Jenkins **checks out** the code, then **builds and tests** it — failing fast if anything is wrong.
4. On green tests, Jenkins **builds a Docker image** tagged with the commit SHA.
5. Jenkins authenticates to **AWS ECR** and **pushes** the image.
6. Jenkins **SSHes into EC2**, pulls the image, and swaps the container with **docker compose**.
7. A **health check** confirms success; if it fails, the pipeline **rolls back** to the previous image. Secrets stay out of the code and are injected safely.

### Making it yours

The example app was deliberately generic, but nothing about this pipeline is. To adapt it to your own project: replace the Dockerfile's base image and start command with your language's, swap in your real test command, point the ECR repository and EC2 host at your own infrastructure, and list your app's actual secrets in the credential store and `.env` file. The Dockerfile, the Jenkinsfile, and the deploy logic are the transferable skills — the rest is just configuration. You now have a repeatable blueprint for shipping any application from a `git push` to a live, verified, recoverable deployment.

## Key Takeaways
- A deploy isn't finished until a **health check** proves the new container is actually serving. Define a container `healthcheck` and run `docker compose up -d --wait`, which polls the probe for you and exits non-zero if the app never becomes healthy — never a fixed `sleep`, which races startup.
- **Rollback** works because every image is tagged with its commit SHA and kept in ECR — record the tag in a server-side file *only after* a verified deploy, then have a `post { failure { ... } }` block read that file and redeploy the last known-good tag.
- **Never commit secrets**; inject them at runtime via Jenkins credentials (`withCredentials`) for deploy-time secrets and a git-ignored `.env` for runtime secrets, keeping each secret in exactly one place.
- The finished pipeline carries any app from a `git push` through build, test, image push to ECR, and a verified, recoverable EC2 deploy — and the Dockerfile, Jenkinsfile, and deploy logic transfer directly to your own projects.
