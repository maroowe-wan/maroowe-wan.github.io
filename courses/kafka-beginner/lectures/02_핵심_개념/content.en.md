---
lecture_no: 2
title: Core Concepts — Topic, Partition, Offset, Broker
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=kj9JH3ZdsBQ
  - https://www.youtube.com/watch?v=y9BStKvVzSs
  - https://www.youtube.com/watch?v=UHjSP7nxk7g
---

# Core Concepts — Topic, Partition, Offset, Broker

## Learning Objectives
- Understand that a Topic is the logical unit for classifying messages and that it is divided into Partitions
- Explain the meaning of Offset as the sequence number and position of a message within a Partition
- Identify the role of a Broker as the server that stores and serves data, and diagram the relationship among all four concepts

## Content

### Why This Topic Matters
In Lecture 1 we compared Kafka to a "post office that receives and forwards messages." Now it is time to look inside that post office. The four terms you will encounter most often when working with Kafka are **Topic, Partition, Offset, and Broker**. Once you can visualize how these four relate to one another, learning about Producers and Consumers becomes much easier.

### Topic — The Logical Unit for Classifying Messages
A **Topic** is a labeled container that groups events of the same kind. Just as a post office has separate windows for letters and large parcels, Kafka separates data by character into topics like `orders`, `payments`, and `trucks_gps`. Topics are distinguished by **name**, and how to divide them is a design decision developers make themselves — much like designing database tables.

Comparing a topic to a database table is a helpful starting point, but there is one important difference: unlike a table, a topic **cannot be queried by condition**. Data is only ever appended to the end and read sequentially from the front.

A more precise analogy is a **log** — a record where events accumulate line by line in the order they occur. The fact that a topic is a log gives it three properties:

- **Append-only:** New messages are always added to the very end. Nothing is inserted in the middle.
- **Immutable:** Once an event is written, consumers cannot modify or delete it. Like history, it cannot be undone. (Messages are cleaned up in bulk after their retention period expires, but individual messages are never selectively edited.)
- **Durable:** Stored as files on disk and retained for a configured retention period. The default is typically one week, but it can be set to a few seconds or virtually forever.

### Partition — Splitting a Topic for Scale
If all messages in a topic piled up in a single sequence, one server would have to handle everything as data volume grows — creating a bottleneck. To solve this, Kafka divides each topic into multiple chunks called **Partitions**.

Going back to the post office analogy: when the letter window gets too crowded, you hire several clerks and split the work by destination — Europe, the Americas, Asia. With multiple partitions, messages can be written and read in parallel, enabling **high throughput and horizontal scalability**. Partitions can reside on different servers, and that is how Kafka scales out.

For example, creating the `trucks_gps` topic with 12 partitions means that location data from a large fleet is split into 12 streams and processed simultaneously. The number of partitions is decided when the topic is designed.

### How Messages Are Assigned to Partitions — The Role of Keys
Now that we know *why* topics are partitioned, we need to understand *how* a message ends up in a specific partition. The answer lies in the **key** attached to a message. Each message a producer sends is typically a key-value pair, and the key controls partition assignment.

- **No key (null):** Kafka's default partitioner selects the partition automatically. A common assumption is that messages are distributed one by one across all partitions in strict round-robin fashion, but **that has not been the default behavior since Kafka 2.4**. The current default is the **Sticky Partitioner**, which accumulates messages into a **batch for the current partition, sends that batch, and then switches** to the next partition. Batching improves throughput. This means that over a short window you may see messages concentrated in one partition, but over time they spread evenly across all partitions. This approach is appropriate when it does not matter which partition a message lands in.
- **Key present:** The key is hashed (converted to a number by a deterministic formula) to determine the partition. As long as the same partitioner is used and the partition count stays the same, **messages with the same key always go to the same partition**.

This connects directly to the point made earlier: ordering is only guaranteed within a partition. For example, if GPS coordinates from a single truck (ID `T-7`) must be processed in the exact order they were sent, all messages from that truck must land in the same partition. By using the **truck ID as the key**, every message from `T-7` is routed to the same partition and read in order. Without a key, the Sticky Partitioner rotates partitions batch by batch, so coordinates from the same truck can scatter across partitions and arrive out of sequence.

> If messages within the same logical group must be processed in order, use a value that identifies that group (truck ID, order ID, customer ID, etc.) as the key. The key pins the group to a single partition and preserves order. (Exactly how key-based assignment works, along with the acks setting, is covered in detail in Lecture 4.)

### Offset — Sequence and Position Within a Partition
As messages accumulate inside a partition, each is assigned a number starting from 0 and incrementing by 1. This number is the **Offset**. It indicates **the position and order** of a message within that partition.

A few key points to remember about offsets:

- **Ordering is only guaranteed within a partition.** Messages within the same partition are read in offset order, but there is no ordering guarantee across different partitions.
- **Offsets are partition-scoped.** Offset 2 in Partition 0 and Offset 2 in Partition 1 are entirely different messages.
- **Offsets are never reused.** Even after older messages expire and are deleted, the numbering only ever increases.

Offsets also serve as a bookmark for consumers. A consumer records "I have read this partition up to offset 5," and even if it pauses and restarts, it can resume reading from exactly that point. (This bookmarking action is called an offset commit and is covered in detail in Lecture 5.)

### Broker — The Server That Stores and Serves Data
Topics and partitions as described above must be physically stored somewhere. The **Kafka server** responsible for this is called a **Broker**. A broker receives messages from producers, assigns offsets, writes them to disk, and serves that data in response to consumer requests. Think of it as a branch office of the post office.

Brokers typically run as a group — multiple brokers working together form a **cluster**. Cluster architecture and reliability guarantees (such as replication) are covered in Lecture 3. For now, the one thing to lock in is: **broker = the server that physically stores and serves data**.

### How the Four Concepts Relate
Putting the four concepts together: inside a **Broker (server)** there are multiple **Topics (logical categories)**, each topic is divided into multiple **Partitions (chunks for parallel processing)**, and every message inside a partition is identified by an **Offset (sequence/position number)**. Every message can therefore be addressed precisely by coordinates: "which broker → which topic → which partition → which offset."

The diagram below uses nested boxes to show the containment hierarchy: Broker contains Topics, Topics contain Partitions, and messages accumulate inside Partitions in offset order — with new messages always appended at the end.

```mermaid Containment hierarchy: Broker → Topic → Partition → offset messages
flowchart TD
    subgraph B["Broker — server that stores and serves data"]
        subgraph T1["Topic: orders"]
            subgraph P0["Partition 0 — messages pile up from offset 0"]
                M0["offset 0"]
                M1["offset 1"]
                M2["offset 2 (tail — new messages appended here)"]
            end
            subgraph P1["Partition 1 — messages pile up from offset 0"]
                N0["offset 0"]
                N1["offset 1"]
            end
        end
        subgraph T2["Topic: payments"]
            subgraph Q0["Partition 0 — messages pile up from offset 0"]
                R0["offset 0"]
                R1["offset 1"]
            end
        end
    end
```

## Key Takeaways
- A Topic is the labeled classification unit that groups events of the same kind; it is a log that only appends to the end and does not support modification or condition-based querying.
- A Partition is a slice of a Topic that enables parallel processing and horizontal scaling.
- Messages are assigned to partitions based on their key. Without a key, the default partitioner in Kafka 2.4+ (Sticky Partitioner) batches messages per partition and rotates across partitions over time, distributing load evenly in the long run. With a key, messages always go to the same partition (as long as the same partitioner and partition count are in use), preserving order for that group.
- An Offset is the number that indicates the sequence and position of a message within a partition; ordering guarantees and consumer bookmarks are meaningful only at the partition level.
- A Broker is the Kafka server that stores and serves data; multiple brokers together form a cluster.
