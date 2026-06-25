---
lecture_no: 4
title: Installing Jenkins and Your First Pipeline (Jenkinsfile)
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=ACG_jYCpYXg
  - https://www.youtube.com/watch?v=IhGtoHY5Wws
  - https://www.youtube.com/watch?v=wBvoerbHWEU
---

# Installing Jenkins and Your First Pipeline (Jenkinsfile)

## Learning Objectives
- Get Jenkins running and create a Pipeline job.
- Understand the Jenkinsfile and its `stage`/`step` structure.
- Write a `checkout` stage that pulls source from GitLab.

## Body

In the previous lecture, GitLab started notifying Jenkins on every push — but Jenkins still does nothing with that notification. Now we give it instructions, written as code in a **Jenkinsfile** that lives in your repo.

### 1. Run Jenkins

**What & why:** Run Jenkins itself as a Docker container so the setup stays clean and reproducible.

```bash
docker run -d --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

- `8080` → web UI (open in browser); `50000` → agent (JNLP) port for build agents. Keep them on different ports.
- The `jenkins_home` volume persists jobs and config across restarts — skip it and you lose everything.

**Verify:** Grab the initial admin password from the logs, then unlock the UI at `http://<host>:8080`.

```bash
docker logs jenkins   # copy the printed unlock password
```

Install the suggested plugins and create your admin account.

> Always keep the `jenkins_home` volume. Without it, every job you configure vanishes when the container restarts.

### 2. Create a Pipeline job (not Freestyle)

**What & why:** Jenkins has Freestyle jobs (configured by clicking web forms, stored only on the server) and Pipeline jobs (defined in code). Use **Pipeline** — it's version-controlled, survives a server wipe, and supports conditionals, loops, and parallel stages.

In Jenkins: **New Item → enter a name → Pipeline → OK**.

### 3. The smallest working pipeline

**What & why:** A declarative pipeline nests `pipeline → agent → stages → stage → steps`. `agent any` runs on any available worker; each `stage` becomes a column in the stage view.

```groovy
pipeline {
    agent any
    stages {
        stage('Hello') {
            steps {
                echo 'Pipeline is alive!'
            }
        }
    }
}
```

**Verify:** Paste this into the inline Pipeline script box, click **Build Now**, and look for a green "Hello" stage. If it fails, **Console Output** shows the exact line that broke.

### 4. Load the Jenkinsfile from GitLab

**What & why:** Pasting a script inline defeats Pipeline as Code. Instead, have Jenkins read the Jenkinsfile straight from your repo — then editing the build process is just another commit.

In the job config, under **Pipeline**:
- Definition: **Pipeline script from SCM**
- SCM: **Git**
- Repository URL + credentials: your GitLab repo
- Branch: e.g. `main`
- Script Path: `Jenkinsfile`

### 5. Write the checkout stage

**What & why:** A real pipeline's first job is to fetch the latest code — the **checkout** stage. When loaded from SCM, Jenkins already knows the source location, so one built-in step clones the exact triggering commit. Commit this file as `Jenkinsfile` in your repo root.

```groovy
pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
    }
}
```

To check out a different repo explicitly:

```groovy
git branch: 'main',
    url: 'https://gitlab.com/<namespace>/<project>.git',
    credentialsId: 'gitlab-creds'
```

**Verify:** Push the Jenkinsfile. The webhook from the previous lecture triggers a build that now actually clones your code — green Checkout stage in the stage view. The loop is closed: push → trigger → checkout. Every later stage just builds on this.

## Key Takeaways
- Run Jenkins as a Docker container with a persistent `jenkins_home` volume; map `8080` (UI) and `50000` (agent).
- Choose **Pipeline** over Freestyle so your build is code: version-controlled and server-independent.
- Declarative syntax nests `pipeline → agent → stages → stage → steps`.
- Use **Pipeline script from SCM** and make `checkout scm` your first stage to fetch the triggering commit.

## Sources
- https://www.youtube.com/watch?v=ACG_jYCpYXg
- https://www.youtube.com/watch?v=IhGtoHY5Wws
- https://www.youtube.com/watch?v=wBvoerbHWEU
