---
lecture_no: 5
title: The CI Stages — Build, Test, and Create the Image
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=ESQC5tH5Aow
  - https://www.youtube.com/watch?v=WyH_ihsIaik
  - https://www.youtube.com/watch?v=wBvoerbHWEU
---

# The CI Stages — Build, Test, and Create the Image

## Learning Objectives
- Add `build` and `test` stages to your Jenkinsfile so the pipeline stops the moment something fails.
- Build a Docker image only after the tests have passed.
- Understand how CI acts as an automatic quality gate.

## Body

Your pipeline already triggers on a push and checks out the code. Now we add the stages that make CI valuable: **build**, **test**, and **build image**. The guiding rule is **fail fast** — each stage is a gate, and in a declarative Jenkinsfile any step that returns a non-zero exit code fails the stage and cancels everything downstream. Because stages run top to bottom, simply ordering them correctly guarantees no untested code ever becomes an image.

> A failing test that turns your pipeline red is not a problem — it's the pipeline doing its most important job.

### 1. Add the build stage

**What & why:** The build stage assembles your code and its dependencies. What "build" means depends on your language; the shape is always the same — run a command and let a non-zero exit fail the stage.

```groovy
stage('Build') {
    steps {
        sh 'npm ci'
        sh 'npm run build'
    }
}
```

The `sh` step runs a shell command on the agent (use `bat` on Windows agents). If either command fails, the pipeline stops here — there's no point testing code that didn't assemble.

**Verify:** Run the pipeline; the Build stage should turn green in the Jenkins stage view.

### 2. Add the test stage

**What & why:** This is the gate that catches bugs. Run your automated tests as a stage — if any test fails, the stage fails and everything after it is cancelled.

```groovy
stage('Test') {
    steps {
        sh 'npm test'
    }
}
```

These can be unit tests, integration tests, or lint/format checks. Collect reports even when the run fails by using a `post { always { ... } }` block, so you can always see what broke:

```groovy
stage('Test') {
    steps {
        sh 'npm test'
    }
    post {
        always {
            junit 'reports/**/*.xml'
        }
    }
}
```

**Verify:** Introduce a deliberate failure (e.g. change a value a test asserts) and confirm the pipeline goes red and stops before the image is built. Then revert it.

### 3. Build the image — only after tests pass

**What & why:** Because a failed stage halts the pipeline, placing the image build *after* the test stage guarantees it only runs on green tests. The artifact this produces is the Docker image we'll push and deploy in the next lectures.

```groovy
stage('Build Image') {
    steps {
        sh 'docker build -t myapp:${BUILD_NUMBER} .'
    }
}
```

Two habits to adopt: **never tag a pipeline image `latest`** — a floating tag makes it impossible to know which build is running where and breaks clean rollbacks. Use something unique and traceable like `${BUILD_NUMBER}` (a built-in Jenkins variable; we switch to the commit SHA next lecture). Also, the agent needs access to a Docker daemon — the common setup is to mount the host's Docker socket into the Jenkins container.

**Verify:** After a green run, `docker images` on the host shows `myapp` tagged with the build number.

### The full pipeline so far

```groovy
pipeline {
    agent any
    stages {
        stage('Checkout')    { steps { checkout scm } }
        stage('Build')       { steps { sh 'npm ci'; sh 'npm run build' } }
        stage('Test')        { steps { sh 'npm test' } }
        stage('Build Image') { steps { sh 'docker build -t myapp:${BUILD_NUMBER} .' } }
    }
}
```

Read top to bottom, this is CI in its essence: every push is checked out, built, tested, and — only if all of that passes — turned into a deployable image. That image is now ready for a registry, which is exactly where the next lecture goes.

## Key Takeaways
- Order stages Build → Test → Build Image; in a declarative pipeline a non-zero exit fails the stage by default, so this ordering guarantees images come only from green, tested code.
- **Fail fast** — a failed stage halts the pipeline and notifies the team.
- Run real automated tests and publish reports (e.g. with `junit`) so results are visible for every build.
- Tag images with a unique, traceable value like the build number or commit SHA — never a floating `latest`.

## Sources
- https://www.youtube.com/watch?v=ESQC5tH5Aow
- https://www.youtube.com/watch?v=WyH_ihsIaik
- https://www.youtube.com/watch?v=wBvoerbHWEU
