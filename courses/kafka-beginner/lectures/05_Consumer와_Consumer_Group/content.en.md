---
lecture_no: 5
title: Consumer and Consumer Group — Subscribe, Offset, Parallel Consumption
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=ovdSOIXSyzI
  - https://www.youtube.com/watch?v=lAdG16KaHLs
  - https://www.youtube.com/watch?v=XgmJWoXQVvY
---

# Consumer and Consumer Group — Subscribe, Offset, Parallel Consumption

## Learning Objectives
- Understand the flow of a Consumer subscribing to a Topic, reading messages, and committing offsets
- Grasp the principle by which multiple Consumers in a Consumer Group split Partitions for parallel consumption
- Understand the concept of rebalancing that occurs when Consumers are added or removed from a group

## Content

### Why This Topic Matters
In Lecture 4, the producer put messages into Kafka. Now it is the turn of the side that **reads those messages** — the **Consumer**. Kafka separates "storing data" from "processing data," and processing is almost always the job of consumer applications. Understanding how consumers subscribe, how they remember their progress, and how multiple consumers split the work completes the Kafka reading flow.

### Subscribing and Reading — Basic Consumer Behavior
A consumer starts by **subscribing** to the topics it wants to read. It can subscribe to more than one topic at a time. After subscribing, a consumer typically runs an **infinite loop** — continuously polling for new messages and processing any that arrive.

Here Kafka's important characteristic emerges: reading a message **does not delete it**. Like the Netflix analogy from Lecture 1, data stays in place for the retention period so other consumers can read the same data later. This makes it natural for the same topic to be read by zero, one, or many consumers, each at its own pace.

### Offset Commit — Remembering "How Far I've Read"
A consumer reads each partition in offset order (Lecture 2 recap: an offset is the position number within a partition). But if a consumer pauses and restarts, where should it resume reading? To answer this, the consumer records a bookmark — "I have processed this partition up to offset N" — and this action is called an **offset commit**.

Committed offsets are stored in a special internal Kafka topic (`__consumer_offsets`). When a consumer restarts, it looks up the last committed offset for each partition and resumes reading from the next message. If no committed offset exists (a brand-new consumer), the setting controls whether to start from the **very beginning of the topic (earliest)** or from the **latest point (new messages only)**.

> Thanks to offset commits, a consumer never loses its place even after a restart. The fact that "the consumer itself manages where it is" is a major difference from traditional queues that delete a message the moment it is read.

### Consumer Group — Multiple Consumers Sharing the Work
When data volume surges, a single consumer cannot keep up. The solution is to run multiple consumers doing the same job and **divide the work among them** — this is a **Consumer Group**.

The rule for grouping is simple: consumers that specify the same **group.id** when registering with Kafka belong to the same group. Multiple replicas of the same application share the same group.id, so they automatically form one group.

The key rule is: **one partition is assigned to exactly one consumer within a group at a time.** Kafka automatically distributes partitions among the consumers in a group, and each consumer processes its assigned partitions in parallel.

For example, say a Consumer Group is processing a topic with 3 partitions:

- 1 consumer: that one consumer reads all 3 partitions.
- 3 consumers: each consumer takes 1 partition, processing 3× faster.
- 4 consumers: 3 consumers each handle 1 partition; the 4th sits idle.

The important point here is that **the maximum parallelism within a group is capped at the number of partitions**. To parallelize further, you first need to increase the number of partitions.

The diagram below shows 3 consumers each taking 1 of 3 partitions, while a 4th consumer has no partition to be assigned and sits idle.

```mermaid Partition-to-consumer mapping when a Consumer Group of 4 splits 3 partitions
flowchart LR
    subgraph T["Topic: orders (3 partitions)"]
        P0["Partition 0"]
        P1["Partition 1"]
        P2["Partition 2"]
    end
    subgraph G["Consumer Group (order-processors)"]
        C1["Consumer 1"]
        C2["Consumer 2"]
        C3["Consumer 3"]
        C4["Consumer 4 (idle / no partition assigned)"]
    end
    P0 --> C1
    P1 --> C2
    P2 --> C3
```

> Multiple groups can subscribe to the same topic simultaneously. In this case, each group independently receives all messages. For example, if a "notifications group" and a "billing group" both subscribe to the `orders` topic, both groups receive every order event and process it for their own purpose.

### Rebalancing — Redistributing Work When Membership Changes
In production, the composition of a group can change: a consumer is added to handle increased load, a consumer dies due to a failure, or new partitions are added. When the group membership changes, Kafka **automatically redistributes partitions among the remaining members**. This process is called **rebalancing**.

Rebalancing is orchestrated by the **group coordinator** (a role on the broker side). For example, if a consumer dies, the partitions it owned are handed off to other live consumers so processing continues without interruption. Conversely, when a new consumer joins, some partitions are moved to it.

Rebalancing happens automatically — developers do not need to manually assign partitions. Note that processing may pause briefly during a rebalance; advanced strategies for minimizing this pause are covered in the Kafka Intermediate track.

### Hands-On — Consuming Messages with the Console Consumer
In Lecture 4 we published messages to the `orders` topic. Now let's read them back. (Kafka installation and setup is covered from scratch in Lecture 6.)

The simplest approach: read all messages from the beginning of the topic.

```
kafka-console-consumer.sh \
  --topic orders \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

- `--from-beginning`: reads from the first stored message (the oldest offset). Omitting this option means only messages that arrive after the command is run will be received.

To print both key and value together, add options:

```
kafka-console-consumer.sh \
  --topic orders \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --property "print.key=true" \
  --property "key.separator=:"
```

Specifying a consumer group causes offsets to be committed under that group name, so the next time the same group is started it resumes from where it left off.

```
kafka-console-consumer.sh \
  --topic orders \
  --bootstrap-server localhost:9092 \
  --group order-processors
```

Now open a second terminal and run the same command (the same `--group order-processors`). The two consumers form one group and each takes a share of the partitions. If you send more messages using the producer from Lecture 4, you can see the messages arriving split between the two consumers — parallel consumption in action.

## Key Takeaways
- A consumer subscribes to a topic and reads messages in offset order; reading does not delete messages.
- Offset commits record "how far I have read" so that when a consumer restarts, it resumes from exactly where it left off.
- Consumers sharing the same group.id form a group that splits partitions for parallel consumption; one partition is assigned to exactly one consumer within a group (maximum parallelism = number of partitions).
- When group membership changes, Kafka automatically redistributes partitions in a process called rebalancing.
