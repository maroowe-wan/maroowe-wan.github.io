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
- Get Jenkins running and create a pipeline job.
- Understand Pipeline as Code (the Jenkinsfile) and its `stage`/`step` structure.
- Write a `checkout` stage that pulls your source from GitLab.

## Body

### From trigger to action

In the last lecture you made GitLab *notify* Jenkins on every push. But right now Jenkins receives that notification and does nothing useful. This lecture gives Jenkins its instructions — and we'll write those instructions as code, in a file that lives right alongside your application.

### Getting Jenkins running

The fastest way to a working Jenkins, and the one that fits this container-centric course, is to run Jenkins itself as a Docker container:

```bash
docker run -d --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

A few notes on what this does. `-p 8080:8080` exposes the **web UI** on `localhost:8080` — this is the port you open in a browser. `-p 50000:50000` exposes the **agent (JNLP) port**, which inbound build agents use to connect back to the Jenkins controller; map it now so you don't have to recreate the container later when you add agents. Note the two mappings are different ports — don't point the agent port at `8080`, or your agents and your browser would collide on the same port. The volume mount `-v jenkins_home:/var/jenkins_home` persists Jenkins' configuration and jobs so they survive a container restart — without it, you'd lose everything when the container stops. On first launch, Jenkins prints an initial admin password to its logs (`docker logs jenkins`); use it to unlock the UI, install the suggested plugins, and create your admin account.

> Running Jenkins in a container keeps your host clean and makes the setup reproducible — the same philosophy we applied to the app itself. Just remember the persistent volume, or your carefully configured jobs vanish on restart.

### Freestyle jobs vs. pipelines — and why pipelines win

Jenkins offers several job types. A **Freestyle** job is configured entirely by clicking through web forms — fine for a one-off task, but the configuration lives only inside the Jenkins server. A **Pipeline** job, by contrast, is defined in code.

Why does that matter? Because **Pipeline as Code** gives you three things a freestyle job can't:

- **Version control** — your build process lives in the repo, so every change is tracked, reviewable, and revertible just like application code.
- **Survivability** — if your Jenkins server is wiped, your pipelines aren't, because they're stored in Git.
- **Power** — pipelines support conditionals, loops, and parallel execution.

That code lives in a file called a **Jenkinsfile**, committed to the root of your repository.

### Anatomy of a Jenkinsfile

Jenkins supports two pipeline syntaxes: **scripted** (older, more flexible) and **declarative** (newer, easier to read). We'll use declarative throughout this course. Its structure is a simple nesting:

- **`pipeline`** — the outermost block that wraps everything.
- **`agent`** — *where* the pipeline runs. `agent any` means "any available Jenkins worker."
- **`stages`** — a container holding the ordered list of stages.
- **`stage`** — a named, logical phase of the build (e.g. "Checkout", "Build", "Test"). The stage names become the columns you see in the Jenkins stage view.
- **`steps`** — the individual commands that run inside a stage.

The flow is strictly top to bottom: `pipeline` contains `stages`, `stages` contains each `stage`, and each `stage` contains `steps`. Here is the smallest pipeline that does something real:

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

Create a new **Pipeline** job in Jenkins (**New Item → Pipeline**), paste this into the inline script box, and click **Build Now**. You'll see a green "Hello" box in the stage view. If it fails, the **Console Output** link tells you exactly which line broke — get comfortable reading it, because it's where you'll diagnose every future problem.

### Pulling the Jenkinsfile from GitLab instead of pasting it

Pasting a script inline defeats the purpose of Pipeline as Code. The real setup is **"Pipeline script from SCM."** In the job configuration, under **Pipeline**, choose **Pipeline script from SCM**, select **Git**, enter your GitLab repository URL and credentials, set the branch, and set **Script Path** to `Jenkinsfile`. Now Jenkins reads the pipeline definition straight from your repo on every run — which means editing your build process is just another commit.

### Writing the checkout stage

The very first thing a real pipeline must do is get the latest code. That's the **checkout** stage. When the Jenkinsfile is loaded "from SCM," Jenkins can grab the source with a single built-in step — you don't even need to specify the URL again, because Jenkins already knows where it loaded the Jenkinsfile from:

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

`checkout scm` clones the exact commit that triggered this build. If you ever need to check out a different repo explicitly, you can spell it out:

```groovy
git branch: 'main',
    url: 'https://gitlab.com/<namespace>/<project>.git',
    credentialsId: 'gitlab-creds'
```

Commit this Jenkinsfile, push it, and watch the webhook from the previous lecture trigger a build that now actually fetches your code. You've closed the loop: a push triggers Jenkins, and Jenkins pulls the code as the opening move of a pipeline defined entirely in your repository. Everything from here is just adding more stages.

## Key Takeaways
- Running Jenkins as a Docker container with a persistent volume gives you a clean, reproducible setup; map `8080:8080` for the web UI and `50000:50000` for the agent (JNLP) port.
- Prefer **Pipeline as Code (Jenkinsfile)** over freestyle jobs because it's version-controlled, survives a server wipe, and supports real logic.
- A declarative pipeline nests `pipeline → agent → stages → stage → steps`, and stage names appear in the Jenkins stage view.
- Use **"Pipeline script from SCM"** so Jenkins reads the Jenkinsfile from your repo, and make `checkout scm` your first stage to fetch the triggering commit.
