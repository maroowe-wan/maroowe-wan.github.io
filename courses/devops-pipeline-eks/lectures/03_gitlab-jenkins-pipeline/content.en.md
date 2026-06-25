---
lecture_no: 3
title: "Building the GitLab + Jenkins Pipeline"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=361bfIvXMBI
  - https://www.youtube.com/watch?v=rcZoPygiI8o
---

# Building the GitLab + Jenkins Pipeline

## Learning Objectives
- Trigger a Jenkins pipeline automatically from a GitLab webhook.
- Write a `Jenkinsfile` with checkout, test, build, and image-push stages.
- End up with a CI skeleton where a push to GitLab automatically produces a container image in ECR.

## Body

You can already build an image and push it to ECR by hand. Doing that once is fine; doing it on every commit is misery. Here we automate it: a developer pushes to GitLab, Jenkins wakes up, tests, builds, and pushes the image to ECR — no human in the loop. The result is the **CI skeleton** (continuous integration). The deploy-to-EKS step comes later, in Lecture 6.

Two roles to keep straight: **GitLab** is the source host (it stores the repo and fires an event on push). **Jenkins** is the engine (it listens for that event and runs the work defined in a `Jenkinsfile`).

### Step 1 — Wire GitLab to Jenkins with a webhook

A **webhook** is an HTTP request GitLab sends to a URL whenever something happens (e.g. a push to `main`). Point that URL at Jenkins and a push triggers a build. There are two sides to configure.

**On Jenkins:** create a Pipeline job, install the GitLab plugin if needed, and enable the GitLab webhook trigger so the job accepts incoming calls. Jenkins receives webhook posts at a path like:

```
http://<jenkins-host>:8080/project/<job-name>
```

**On GitLab:** open *Settings → Webhooks*, paste the Jenkins URL, and select **Push events** and **Merge request events**. Save.

**Verify:** before trusting the webhook, click **Build Now** in Jenkins once to confirm the job runs at all. Then use GitLab's **Test** button to fire a sample event and confirm Jenkins responds.

> Get a manual build green *first*, then prove the trigger. Debugging "did the pipeline work?" and "did the webhook fire?" at the same time is twice the pain.

If Jenkins runs on a cloud VM, its security group must allow inbound traffic on the Jenkins port (8080 by default), or webhook delivery fails with a connection error.

### Step 2 — Define the pipeline as a Jenkinsfile

Rather than clicking through the Jenkins UI, write the build steps in a **`Jenkinsfile`** stored in your repo. This is "pipeline as code": the build is versioned, reviewable, and travels with the project. A declarative `Jenkinsfile` is organized into **stages**.

```groovy
pipeline {
    agent any

    environment {
        AWS_REGION = 'us-east-1'
        ACCOUNT_ID = '111122223333'
        ECR_REPO   = 'my-app'
        REGISTRY   = "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        IMAGE_TAG  = "${env.GIT_COMMIT.take(7)}"   // short commit SHA, not 'latest'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm   // pull the code GitLab just pushed
            }
        }

        stage('Test') {
            steps {
                sh 'npm install && npm test'   // fail fast if tests break
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build -t ${REGISTRY}/${ECR_REPO}:${IMAGE_TAG} ."
            }
        }

        stage('Push to ECR') {
            steps {
                sh """
                  aws ecr get-login-password --region ${AWS_REGION} \
                    | docker login --username AWS --password-stdin ${REGISTRY}
                  docker push ${REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
                """
            }
        }
    }
}
```

What each stage does:

- **Checkout** pulls the exact commit that triggered the build. Jenkins exposes its SHA as `GIT_COMMIT`, which we shorten and reuse as the image tag — never `latest`, so every artifact is traceable.
- **Test** runs the suite *before* the build, so a failing test stops the pipeline early instead of building an image you'd never deploy.
- **Build Image** runs `docker build`, tagging with the full ECR address and commit SHA.
- **Push to ECR** authenticates with `get-login-password` and pushes.

**Verify:** commit a trivial change (e.g. a `test.txt`) and watch Jenkins go from *pending* to *success*, then confirm the new commit-tagged image appears in your ECR repository.

### Step 3 — Supply AWS credentials safely

The push stage needs permission to talk to ECR. **Never** paste an access key into the `Jenkinsfile` — that leaks a secret into your repo. Instead:

- If Jenkins runs on EC2, attach an **IAM role** to the instance granting ECR push/pull. The AWS CLI picks it up automatically, with no static keys anywhere.
- Otherwise, store the keys in **Jenkins Credentials** and inject them into the job.

Keep the IAM permissions modest: get an authorization token plus push/pull, ideally scoped to just this repository. We reuse this "the machine has an IAM identity" idea in Lecture 5, when Jenkins authenticates to EKS itself.

### What you have built

Your CI skeleton is now complete: **push to GitLab → webhook → Jenkins checks out, tests, builds, and pushes a commit-tagged image to ECR — automatically.** Every commit leaves a deployable artifact in your registry.

Still missing is *delivery*: nothing yet tells EKS to run the new image. That needs manifests (Lecture 4) and a way for Jenkins to authenticate to the cluster (Lecture 5), after which we add a deploy stage in Lecture 6.

## Key Takeaways
- A GitLab webhook turns a `git push` into an automatic Jenkins build; configure the trigger on Jenkins, the webhook URL on GitLab, then test both.
- A `Jenkinsfile` defines the pipeline as versioned code: Checkout → Test → Build Image → Push to ECR.
- Reuse the commit SHA (`GIT_COMMIT`) as the image tag so every artifact is traceable; run tests before building to fail fast.
- Never hardcode AWS keys; use an IAM role on the Jenkins host or Jenkins-managed credentials.
- The result is a complete CI skeleton — deploy-to-EKS arrives in Lectures 5 and 6.
