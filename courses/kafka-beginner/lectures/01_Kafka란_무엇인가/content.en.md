---
lecture_no: 1
title: What Is Kafka — Why Messaging and Event Streaming Matter
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=QkdkLdMBuL0
  - https://www.youtube.com/watch?v=aj9CDZm0Glc
  - https://www.youtube.com/watch?v=Ydts27Qa8H0
---

# What Is Kafka — Why Messaging and Event Streaming Matter

## Learning Objectives
- Understand the limitations of direct point-to-point integration and the need for asynchronous messaging
- Explain the difference between message queues and event streaming, and describe the background that led to Kafka's creation
- Identify what problems Kafka solves through real-world use cases

## Content

### Why This Topic Matters
Nearly every service we use today operates in "real time." Place an order and a notification arrives instantly. A delivery driver's location moves continuously on a map. The moment a card transaction occurs, fraudulent activity is detected. Behind these experiences lies a structure in which **countless systems are constantly exchanging data with one another**. Kafka is a tool built specifically for "moving data safely and quickly." Understanding why Kafka was created makes every concept you learn afterward fall naturally into place.

### The Limits of Direct Integration (Point-to-Point)
Consider an online shop as an example. When a customer places an order, a chain of events must follow: inventory is decremented, a confirmation email is sent, a receipt is issued, and a sales dashboard is updated.

The simplest approach is to have **the order service call each downstream service directly** — "Hey inventory, decrement stock," "Hey email, send a confirmation," and so on. This works fine at small scale. But as traffic surges or the number of services grows, problems emerge.

- **Tight coupling:** One service calls another directly, so they become deeply intertwined. Adding a new feature means drawing yet another connection line.
- **Synchronous domino effect:** The caller waits for a response. If the payment service slows down, the entire order flow stalls and users are left watching a loading spinner.
- **Single point of failure:** If the inventory service goes down for ten minutes, every order that arrives during that window piles up and cascades into a larger outage.
- **Data loss:** If an analytics service crashes briefly, the important data produced during that window simply disappears.

> Direct integration is clean only when you have few services. As services multiply, connection lines explode into a tangled web and a failure in one place spreads across the entire system.

As shown below, direct integration (left) becomes a tangled web as services grow, while placing Kafka as a central hub (right) means each service only needs to connect to Kafka.

```mermaid Comparison: direct point-to-point integration (left) vs. Kafka hub architecture (right)
flowchart LR
    subgraph P2P["Direct Integration (point-to-point)"]
        O1["Order Service"]
        I1["Inventory Service"]
        E1["Email Service"]
        R1["Receipt Service"]
        D1["Dashboard Service"]
        O1 --> I1
        O1 --> E1
        O1 --> R1
        O1 --> D1
        I1 --> E1
        I1 --> D1
        E1 --> R1
    end
    subgraph HUB["Kafka Hub (pub/sub)"]
        O2["Order Service"]
        K(("Kafka"))
        I2["Inventory Service"]
        E2["Email Service"]
        R2["Receipt Service"]
        D2["Dashboard Service"]
        O2 -->|publish| K
        K -->|subscribe| I2
        K -->|subscribe| E2
        K -->|subscribe| R2
        K -->|subscribe| D2
    end
```

### Asynchronous Messaging: Placing a "Post Office" in the Middle
The core idea behind solving this problem is to place a **middleman tool** between services. A post office is a good analogy. When we send a package, we don't fly directly to the recipient's door — we drop it off at the post office and go about our day, trusting the post office to handle delivery.

Kafka plays exactly this post-office role. The order service wraps the fact that "an order occurred" into a small bundle called an **event** and drops it into Kafka, then immediately continues with its own work — no waiting for a response. This style of communication, where the sender and receiver do not wait on each other, is called **asynchronous messaging**. The side that creates and sends events is called the **Producer**, and the side that receives and processes those events is called the **Consumer**.

Placing a post office in the middle loosens the coupling between services (this is known as **decoupling**, or dependency separation). The order service doesn't need to know who receives its events, and receiving services pull what they need when they need it. Adding a new service requires no changes to the existing ones.

### Message Queue vs. Event Streaming
Middleware that acts as a bridge between services is not a new idea. A classic example is a **traditional message queue** like RabbitMQ. So what makes Kafka different?

The biggest difference is **what happens to a message after it has been consumed**.

- **Traditional message queue:** Once a consumer fetches a message and processes it, the message is gone from the queue. It is essentially single-use.
- **Kafka (event streaming):** Reading an event does **not delete it** — it stays on disk for the configured retention period. Other services can read the same data later, or the same service can read it multiple times.

A simple analogy: a traditional queue is like live TV — you have to watch at the scheduled time or miss it. Kafka is like Netflix — you can watch on demand, at your own pace, and start over from the beginning. This approach of **storing continuously flowing data while simultaneously streaming it in real time** is called event streaming.

> A Kafka message is not "mail that disappears once read" — it is "a record that remains for the retention period." This is the decisive difference that sets Kafka apart from a simple message queue.

### The Background Behind Kafka
Kafka was created around 2010 at **LinkedIn**. As its user base exploded, enormous amounts of activity data were generated every second, and existing tools could no longer handle the scale. LinkedIn engineers designed a new **distributed streaming platform** that splits data across multiple servers for storage and processing, and released it as open source in 2011. Today, Kafka has become the de facto standard for large-scale, real-time data.

### Real-World Use Cases
Seeing what problems Kafka solves makes its value concrete.

- **Decoupling between services:** Instead of directly wiring payment, shipping, inventory, and notification services together, each service publishes and subscribes to events so they can be developed and operated independently.
- **Real-time location tracking:** In ride-hailing services, a driver's location is sent as an event every second to update the user's map and calculate surge pricing based on supply and demand.
- **Real-time analytics:** User activity — songs played, products clicked — is collected to instantly update recommendation engines or sales dashboards.
- **Fraud detection:** Card transaction events are streamed in real time so fraudulent transactions can be caught the moment they occur.

Processing individual events one at a time is the basic role of a consumer. More advanced processing — aggregating and analyzing a continuous stream of data — is also possible, but those advanced capabilities are covered in the **Kafka Intermediate** track and are beyond the scope of this course.

## Key Takeaways
- Point-to-point direct integration breaks down at scale due to tight coupling, synchronous blocking, and single points of failure.
- Kafka acts as a "post office" in the middle, accepting and forwarding messages to enable asynchronous, loosely coupled communication.
- Traditional message queues delete a message once it is read, but Kafka retains events for the retention period so multiple consumers can read the same data repeatedly (event streaming).
- Kafka is a distributed streaming platform created by LinkedIn to handle massive real-time data at scale, and is used for decoupling, location tracking, real-time analytics, fraud detection, and more.
