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
- See the finished pipeline end to end.

## Body

Our pipeline pulls the new image, swaps the container, and assumes it worked. If the new version crashes on startup, we've replaced a working app with a broken one. This lecture adds the safety net: verify with a health check, roll back on failure, and stop putting secrets in code.

### Task 1 — Add a health check

A **health check** is a small probe that asks the new container "are you actually serving?" Don't use a fixed `sleep` (it races startup); instead let Docker Compose poll for you. Define a `healthcheck` on the service:

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

Then deploy with `--wait`. It blocks until every service is **healthy** and exits `0`, or exits **non-zero** if any service never becomes healthy. That one command is your verify step:

```bash
docker compose up -d --wait
```

> `--wait` only does its job if the service has a `healthcheck` defined — without one, Compose waits for the container to *start*, not to become *healthy*. The exit code of `docker compose up -d --wait` is your pass/fail decision.

### Task 2 — Roll back on failure

When the health check fails, redeploy the **previous** working image. This works because back in lecture 6 we tagged every image with its commit SHA, so every past version still sits in ECR under its own tag.

The pipeline must remember the last known-good tag. The rule: **write the tag to a file on the server only after a verified deploy; on failure, read it back and redeploy it.** Because the file is updated only after success, it always names a version that genuinely worked.

```groovy
stage('Deploy & Verify') {
    environment { COMMIT = "${env.GIT_COMMIT}" }   // the new image tag
    steps {
        sshagent(['ec2-ssh-key']) {
            sh '''
                ssh ec2-user@<EC2_HOST> "
                    export IMAGE=<registry>/myapp:${COMMIT}
                    # --wait deploys AND verifies; non-zero exit => stage fails
                    docker compose up -d --wait
                    # Reached only when verified healthy:
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
                            echo 'No known-good tag recorded; cannot auto-roll back' >&2
                            exit 1
                        fi
                    "
                '''
            }
        }
    }
}
```

For zero-downtime swaps, teams go further with **blue-green** (run two environments and flip traffic) or **canary** (route a small slice of traffic first). For a single EC2 host, health-check-plus-rollback already removes most of the risk.

### Task 3 — Keep secrets out of your code

**Never commit a secret to your repository** — anything in Git is permanent and stays in history. Separate secrets from code and inject them at runtime in two places:

**Deploy-time secrets (in Jenkins)** — store them in the credential store and pull them in with `withCredentials`, which masks them in the log:

```groovy
withCredentials([string(credentialsId: 'db-password', variable: 'DB_PASS')]) {
    sh 'deploy-using $DB_PASS'
}
```

**Runtime secrets (on the server)** — pass them to the container via a git-ignored `.env` file that lives on the server:

```yaml
services:
  web:
    image: ${IMAGE}
    env_file: /home/ec2-user/app.env
```

Keep each secret in exactly one place: Jenkins holds what it needs to *deploy*, the server holds what the app needs to *run*. Mark secrets as protected and masked wherever the tool allows.

### The finished pipeline

1. Push code to **GitLab**.
2. A **webhook** triggers **Jenkins**.
3. Jenkins **checks out**, **builds and tests** — failing fast on any error.
4. On green tests, Jenkins **builds a Docker image** tagged with the commit SHA.
5. Jenkins authenticates to **ECR** and **pushes** the image.
6. Jenkins **SSHes into EC2** and swaps the container with **docker compose**.
7. A **health check** confirms success; if it fails, the pipeline **rolls back**. Secrets stay out of the code.

To adapt it to your app: swap the Dockerfile base image and start command, your real test command, your ECR repo and EC2 host, and your own secrets. The Dockerfile, Jenkinsfile, and deploy logic transfer directly.

## Key Takeaways
- A deploy isn't done until a **health check** proves the container is serving. Define a `healthcheck` and run `docker compose up -d --wait` — never a fixed `sleep`.
- **Rollback** works because every image is SHA-tagged in ECR: record the tag to a server file *only after* a verified deploy, then have `post { failure { ... } }` redeploy that last known-good tag.
- **Never commit secrets**; inject at runtime via Jenkins `withCredentials` (deploy-time) and a git-ignored `.env` (runtime), keeping each secret in one place.
- The finished pipeline carries any app from `git push` through build, test, push to ECR, and a verified, recoverable EC2 deploy.

## Sources
- https://www.youtube.com/watch?v=z7nLsJvEyMY
- https://www.youtube.com/watch?v=oWrwi1NiViw
- https://www.youtube.com/watch?v=J9JbzsufemE
