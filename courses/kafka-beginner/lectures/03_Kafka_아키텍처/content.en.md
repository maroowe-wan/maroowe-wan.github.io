---
lecture_no: 3
title: Kafka Architecture — Cluster, Broker, ZooKeeper vs KRaft
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=IsgRatCefVc
  - https://www.youtube.com/watch?v=jY02MB-sz8I
  - https://www.youtube.com/watch?v=FKgi3n-FyNU
---

# Kafka Architecture — Cluster, Broker, ZooKeeper vs KRaft

## Learning Objectives
- Understand how multiple brokers form a cluster and how responsibilities are distributed
- Distinguish between the ZooKeeper approach and the KRaft approach for metadata management
- Draw the full flow of how Producers and Consumers communicate with the cluster

## Content

### Why This Topic Matters
In Lecture 2 we examined the individual building blocks — topic, partition, offset, and broker — one by one. Now it is time to see **how these components cooperate across multiple servers**, and how producers and consumers **communicate with that system**. Kafka can run on a single machine, but its real value lies in multiple servers working together to provide reliability and scalability.

### Cluster and Broker — Multiple Servers Working Together
A **Broker** is a single Kafka server. Multiple brokers working together as a unit form a **cluster**. A cluster can span many servers, or even multiple data centers.

Why run more than one? Two reasons:

- **Scalability:** Spreading a topic's partitions across multiple brokers removes the I/O ceiling of a single server. When throughput is insufficient, add more brokers and partitions.
- **High availability:** If one broker goes down, the others take over its work so the service keeps running without interruption.

### Replication — A Safety Net Against Data Loss (Conceptual Overview)
Replication is the key to high availability. The same partition is copied to multiple brokers. One copy becomes the **leader** — it handles all reads and writes. The remaining copies are **followers** that continuously replicate the leader's content.

By default, producers and consumers only communicate with the **leader partition**. If the broker holding the leader fails, one of the followers is automatically elected as the new leader, and reads and writes continue seamlessly — with no data loss.

> For this lecture, it is enough to understand replication as "copying data to multiple brokers so the system can survive the loss of one." Details such as the replication factor and ISR (In-Sync Replicas) are covered in the Kafka Intermediate track.

### Who Coordinates the Cluster — Controller and Metadata
For multiple brokers to work together, someone must manage the overall state: which brokers are alive, who is the leader of each partition, what are the topic configurations. This information is called **metadata**. The role of managing metadata and electing leaders is handled by a **controller**. At any given time, a cluster has exactly one active controller.

The question of "how to manage this controller and its metadata" gives rise to two approaches: the ZooKeeper approach and the KRaft approach.

### ZooKeeper Mode (Legacy Approach)
Early Kafka depended on an external tool called **ZooKeeper**. ZooKeeper is a separate distributed system that took on the work of electing the controller, managing broker membership, and storing topic configurations.

However, ZooKeeper is itself a distributed system, so in production environments it typically had to be operated as its own cluster of 3 or 5 nodes. This meant running Kafka required managing **two separate systems** — a Kafka cluster plus a ZooKeeper cluster — which added significant operational complexity.

### KRaft Mode (Modern Approach)
To eliminate this complexity, Kafka introduced **KRaft (Kafka Raft)** mode. KRaft removes the external ZooKeeper dependency and **embeds metadata management and controller election directly inside the Kafka brokers**. The "Raft" in the name refers to the Raft consensus algorithm, a standard algorithm used in distributed systems to agree on things like who the leader is.

KRaft mode has been production-ready since Kafka 3.3, and has since become the default direction. The benefits are clear:

- ZooKeeper, which had to be operated separately, is gone — the overall system is simpler.
- Metadata handling becomes more efficient and latency decreases.

> If you are starting fresh with Kafka and have no legacy systems that depend on ZooKeeper, starting with KRaft mode is recommended.

| | ZooKeeper Mode | KRaft Mode |
|---|---|---|
| Metadata management | Handled by external ZooKeeper | Handled internally within Kafka brokers |
| Operational overhead | Two systems: Kafka + ZooKeeper | Single system: Kafka only |
| Recommendation | When legacy compatibility is required | Recommended for new deployments |

As shown in the diagram below, ZooKeeper mode delegates metadata to an external cluster, while KRaft mode embeds the controller inside brokers so the whole thing operates as a single system.

```mermaid Comparison of metadata management: ZooKeeper mode vs. KRaft mode
flowchart LR
    subgraph ZK["ZooKeeper Mode (two systems)"]
        direction TB
        Z[("🗂️ ZooKeeper Cluster")]:::coord
        KZ["📦 Kafka Cluster (brokers)"]:::svc
        Z -.->|metadata management| KZ
    end
    subgraph KR["KRaft Mode (single system)"]
        direction TB
        BC["🧭 Broker + Controller (metadata embedded)"]:::ctrl
        B2["📦 Broker"]:::svc
        B3["📦 Broker"]:::svc
        BC --- B2
        BC --- B3
    end
    classDef coord fill:#fef3c7,stroke:#b45309,color:#78350f;
    classDef svc fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef ctrl fill:#e0e7ff,stroke:#4338ca,color:#312e81;
```

### The Communication Flow Between Producers/Consumers and the Cluster
Let's trace the entire flow from start to finish.

1. The **producer** starts by connecting to one broker in the cluster (the bootstrap server) and fetching metadata — specifically, which broker is the leader for the partition it wants to write to.
2. The producer sends the message **directly to the leader broker** for that partition. The leader assigns an offset, writes the message to disk, and the followers replicate the content.
3. The **consumer** works the same way — it connects to the leader broker for the partition it wants to read, and pulls messages in offset order. Reading does not delete the data.
4. If a broker fails, the controller elects a new leader and automatically reconnects producers and consumers to the new broker.

As shown in the sequence diagram below, producers and consumers first discover the leader's location via metadata, then communicate directly with that leader broker.

```mermaid Communication sequence between Producer/Consumer and the Kafka cluster
sequenceDiagram
    autonumber
    participant P as 👤 Producer
    participant B as 📦 Bootstrap Broker
    participant L as ⭐ Leader Broker
    participant F as 📦 Follower Broker
    participant C as 👤 Consumer
    P->>B: Request metadata (leader location)
    B-->>P: Partition leader = Leader Broker
    P->>L: Send message
    L->>L: Assign offset and write to disk
    L->>F: Replicate
    L-->>P: Acknowledge write (ack)
    C->>L: Request messages in offset order
    L-->>C: Deliver messages (data not deleted after read)
```

All of this coordination happens automatically — developers rarely need to think about it directly. How producers and consumers actually send and receive messages is covered hands-on in Lectures 4 and 5.

## Key Takeaways
- Multiple brokers form a cluster; partitions are spread across brokers to achieve scalability and high availability.
- Partitions are replicated with a leader and followers so that if one broker fails, a new leader is automatically elected and service continues.
- Metadata management was traditionally handled by an external ZooKeeper, but modern Kafka uses KRaft mode, which operates without ZooKeeper.
- Producers and consumers fetch metadata to locate the leader of their target partition, then communicate directly with that leader broker; on failure, the cluster handles reconnection automatically.
