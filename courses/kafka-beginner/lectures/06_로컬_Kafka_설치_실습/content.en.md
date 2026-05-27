---
lecture_no: 6
title: Installing Kafka Locally and End-to-End Practice — Produce/Consume via CLI
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=U4y2R3v9tlY
  - https://www.youtube.com/watch?v=GvdlpbQr6jo
  - https://www.youtube.com/watch?v=QkdkLdMBuL0
---

# Installing Kafka Locally and End-to-End Practice — Produce/Consume via CLI

## Learning Objectives
- Install and run Kafka locally using Docker or a binary distribution
- Create a Topic via CLI and publish messages using the console producer
- Consume messages with the console consumer and verify the complete produce→consume flow hands-on

## Content

### Why This Topic Matters
The previous five lectures introduced Kafka's concepts and commands. This time we **run Kafka directly on our own machine**, create a topic, send and receive messages, and complete the full end-to-end flow with our own hands. Doing it once makes all the concepts you drew in your head click into place at the fingertips.

The overall flow is: **Start Kafka → Create a topic → Publish with a producer → Consume with a consumer.** We'll follow this single pipeline from start to finish.

### Choosing an Installation Method
There are two main ways to run Kafka locally.

- **Docker (recommended):** Runs Kafka in a container, so your machine stays clean and you can start and tear down the environment in one step. (Docker is a tool that runs applications inside isolated boxes called containers.)
- **Binary:** Download the official Apache Kafka distribution and run it directly. Requires Java.

**Docker is the recommended approach here**, but binary instructions are provided as well. Both ultimately use the same CLI tools — `kafka-topics`, `kafka-console-producer`, `kafka-console-consumer` — and so on.

### Option A: Running Kafka with Docker
First, Docker Desktop must be installed (download it for free from the official Docker website). In your working directory, create a `docker-compose.yml` file as shown below. This example starts a single broker in **KRaft mode** (see Lecture 3: the modern approach that does not require ZooKeeper).

```
services:
  kafka:
    image: apache/kafka:latest
    container_name: kafka
    ports:
      - "9092:9092"
```

Open a terminal in the same directory and run the following to start Kafka in the background.

```
docker compose up -d
```

The `-d` flag means detached (background) mode. Verify the container is up.

```
docker ps
```

If the `kafka` container appears in the list, you are good to go. All subsequent CLI commands are run inside the container. To open a shell inside the container, run:

```
docker exec -it kafka /bin/bash
```

> `docker exec -it ... /bin/bash` opens a terminal session inside a running container. All the `kafka-topics.sh` commands that follow are run inside this container shell. In the official Apache image, the scripts are located at `/opt/kafka/bin`, and this path may not be in the PATH by default — so right after entering the shell, run `cd /opt/kafka/bin` to navigate there. The commands below will then work as written (if you see `command not found`, you have likely skipped this step).

### Option B: Running Kafka from the Binary Distribution (Alternative)
To run without Docker, download the Apache Kafka distribution and extract it. The latest Kafka starts in KRaft mode as follows (run from inside the distribution folder).

```
# 1) Generate a cluster ID
KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"

# 2) Format the storage
bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c config/kraft/server.properties

# 3) Start the broker
bin/kafka-server-start.sh config/kraft/server.properties
```

Once the broker is running on port 9092, open a new terminal and follow the CLI exercises below.

### Step 1: Create a Topic
Create a practice topic called `quickstart` with 1 partition.

```
kafka-topics.sh --create \
  --topic quickstart \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

Verify the topic was created by checking the topic list and details.

```
kafka-topics.sh --list --bootstrap-server localhost:9092

kafka-topics.sh --describe \
  --topic quickstart \
  --bootstrap-server localhost:9092
```

`--describe` shows detailed information about the topic — partition count, leader broker, and so on.

### Step 2: Publish Messages with the Producer
Start the console producer. When the prompt (`>`) appears, type one line at a time to publish messages.

```
kafka-console-producer.sh \
  --topic quickstart \
  --bootstrap-server localhost:9092
```

```
> hello kafka
> my first message
> end-to-end test
```

Leave this terminal running so you can continue sending messages.

### Step 3: Consume Messages with the Consumer
**Open a new terminal** (if using Docker, enter the container again with `docker exec -it kafka /bin/bash`). Then read all messages from the beginning.

```
kafka-console-consumer.sh \
  --topic quickstart \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

If the three lines you just published appear in the output, the **produce → consume** flow is working end to end.

```
hello kafka
my first message
end-to-end test
```

The sequence below traces the complete path, from creating the topic through publishing, storing, and consuming.

```mermaid End-to-end flow from topic creation through produce → broker → consume
sequenceDiagram
    participant CLI as User (CLI)
    participant Prod as console producer
    participant B as Kafka Broker
    participant Cons as console consumer
    CLI->>B: kafka-topics.sh --create (create quickstart topic)
    B-->>CLI: Topic created
    CLI->>Prod: Enter message (hello kafka)
    Prod->>B: Publish to quickstart topic
    B->>B: Assign offset and write to disk
    CLI->>Cons: kafka-console-consumer.sh --from-beginning
    Cons->>B: Subscribe to quickstart topic (request from offset 0)
    B-->>Cons: Deliver stored messages
    Cons-->>CLI: Print messages to screen
```

### Step 4: Verifying Real-Time Delivery
Now place the two terminals side by side. Leave the consumer running and type new messages in the producer terminal.

```
> live message 1
> live message 2
```

The moment you press Enter, the same message appears in the consumer terminal. This is the "real-time data streaming" mentioned in Lecture 1, happening right in front of you. One side sends, the other receives immediately.

### Step 5: Cleaning Up
When you are done, delete the topic and stop the container.

```
# Delete the topic
kafka-topics.sh --delete \
  --topic quickstart \
  --bootstrap-server localhost:9092
```

If you started Kafka with Docker, exit the container shell and then shut down the container.

```
exit
docker compose down
```

`docker compose down` stops and removes the containers, leaving your environment clean.

> If you get stuck during the practice, the cause is usually one of two things: (1) the broker has not finished starting — wait a moment and retry; (2) a typo in the `--bootstrap-server` address or port — confirm it is 9092. CLI script names may include `.sh` (`kafka-topics.sh`) or not, depending on the distribution.

## Key Takeaways
- Kafka can be run as a local single-broker instance using Docker (recommended) or a binary distribution; modern Kafka runs in KRaft mode without ZooKeeper.
- Use `kafka-topics.sh --create` to create a topic, and `--list` / `--describe` to verify it.
- Use `kafka-console-producer.sh` to publish messages and `kafka-console-consumer.sh --from-beginning` to consume them, confirming the end-to-end flow.
- Running the producer and consumer side by side in separate terminals lets you watch messages being delivered in real time.
