---
lecture_no: 1
title: What Is DevOps? Concepts and Culture (CALMS)
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=0yWAtQ6wYNM
  - https://www.youtube.com/watch?v=jiDwhKNS9A0
  - https://www.youtube.com/watch?v=VySUutlo91E
  - https://www.youtube.com/watch?v=LdMtHOWhchk
  - https://www.youtube.com/watch?v=5ACICDxWops
---

# What Is DevOps? Concepts and Culture (CALMS)

## Learning Objectives
- Understand the problems caused by separating development (Dev) and operations (Ops), and the core values DevOps pursues: fast delivery, stability, and collaboration.
- Recognize that DevOps is not a tool but a culture and a way of working.
- Explain DevOps principles using the CALMS framework (Culture, Automation, Lean, Measurement, Sharing).

## Body

### The Wall Between Dev and Ops

Every piece of software follows the same basic journey: someone has an idea, developers write and test the code, and then it has to reach real users on a real server. After launch, the work continues — you watch for bugs, add features, and ship updates again and again. DevOps is about making this endless cycle of delivery **fast** and **reliable** at the same time.

In a traditional setup, two separate teams own two halves of that journey. **Developers** write code; **operations** run it in production. The trouble is that these teams often have opposing incentives.

- Developers are rewarded for shipping new features quickly.
- Operations are rewarded for keeping the system stable — which means resisting change, because every change is a risk.

The result is a built-in conflict of interest. Developers throw finished code "over the wall," and operations struggle to deploy something they didn't build and don't fully understand. Hand-offs become slow, bureaucratic checklists. A release that should take hours can stretch into days or weeks. And when a new feature crashes production at 2 a.m., it's operations who get paged — so the people writing the code feel little pressure to think about how it will actually run.

The diagram below shows how this split — two teams pulling in opposite directions across a wall — produces friction as its inevitable result.

```mermaid The wall between Dev and Ops and the opposing incentives that create friction
flowchart LR
    subgraph DevTeam["Dev Team"]
        D["Developers"]
        DG["Goal: ship features fast"]
    end
    subgraph OpsTeam["Ops Team"]
        O["Operations"]
        OG["Goal: keep system stable"]
    end
    WALL["The Wall<br/>slow hand-offs and blame"]
    D --> DG
    O --> OG
    DG -->|"throw code over"| WALL
    OG -->|"resist change"| WALL
    WALL --> F["Result: friction<br/>slow releases, errors reach users"]
```

> The core symptom of the Dev/Ops split is always the same: friction that slows the release cycle and lets errors slip through to users.

### What DevOps Actually Is

It's tempting to think DevOps is a set of tools, or a job title. It isn't — at least not at its heart. The original idea defines DevOps as a **combination of cultural philosophies, practices, and tools** for delivering software quickly and with high quality.

Notice the order: **culture comes first.** You can buy every automation tool on the market and still fail at DevOps if developers and operations don't actually talk to each other and share responsibility. The central insight is simple: the two teams should work together, communicate often, and own the outcome together rather than guarding their own silo.

So the goal of DevOps is to remove whatever slows down the release cycle — poor communication, manual hand-offs, error-prone deployments — and replace it with streamlined, automated, collaborative processes. Companies that get this right can release safely many times a day instead of a few times a year. The well-known infinity-loop logo captures the idea: improvement never ends, so the delivery process should never stop flowing either.

> DevOps is a way of working, not a product you install. Tools support the culture; they don't replace it.

### The CALMS Framework

Because "cultural philosophies, practices, and tools" is broad, the industry uses a simple checklist to make DevOps concrete: **CALMS**. It's the best short answer to "what is DevOps about?"

| Letter | Principle | What it means in practice |
|--------|-----------|---------------------------|
| **C** | **Culture** | Break down silos and share responsibility between Dev and Ops. Build a psychologically safe environment where failure is a learning opportunity, not a reason to blame. Shift from a fear of failure to "fail fast, fail forward," and from tech obsession to customer focus. |
| **A** | **Automation** | Eliminate repetitive manual work — testing, building, deploying — so releases are fast and consistent. But automation is about *people and process first*, not just buying tools. Automate the right things; a tool on a broken process just breaks faster. |
| **L** | **Lean** | Keep the flow through the whole value stream simple. Work in small batches, limit work-in-progress, and ship small increments continuously. Lean, repeatable processes are the ones teams actually follow. |
| **M** | **Measurement** | Make decisions from data, not opinions. Track metrics like lead time, deployment frequency, change failure rate, and mean time to recovery — and also people metrics like team satisfaction. You can't improve what you don't measure. |
| **S** | **Sharing** | Spread knowledge, feedback, and wins openly across the organization. Transparency builds trust, tightens feedback loops, and turns a local fix into a benefit for the whole company. |

Notice that four of the five letters are about people and process; only one is about automation. That balance is the whole point — it shows that the automated build-and-deploy chain everyone pictures is just a small slice of DevOps. The rest is how an organization thinks, learns, and works together.

A handy way to remember it: **"Keep CALMS and do DevOps."**

## Key Takeaways
- Splitting Dev and Ops into separate teams creates a conflict of interest — speed versus stability — that slows releases and lets errors reach users.
- DevOps aims to remove that friction so software is delivered both **fast** and **reliably**, through better collaboration, not just tooling.
- DevOps is a **culture and way of working**, not a tool or a single role. Culture comes first; tools support it.
- **CALMS** summarizes the principles: **C**ulture, **A**utomation, **L**ean, **M**easurement, **S**haring.
- Four of the five CALMS pillars are about people and process — a reminder that automation is only one part of DevOps.

## Sources
- What is DevOps? REALLY understand it | DevOps vs SRE — https://www.youtube.com/watch?v=0yWAtQ6wYNM
- CALMS (Eficode) — https://www.youtube.com/watch?v=jiDwhKNS9A0
- DevOps Principles - The C.A.M.S. Model — https://www.youtube.com/watch?v=VySUutlo91E
- DevOps CALMS Framework — https://www.youtube.com/watch?v=LdMtHOWhchk
- [DevOps 전문가 블로그] DevOps 엔지니어가 되려면 어떻게 해야해요? — https://www.youtube.com/watch?v=5ACICDxWops
