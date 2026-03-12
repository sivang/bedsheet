# NATS Transport — Architecture Notes

> Research and design notes for replacing PubNub with NATS as the Sixth Sense transport layer.

## Why NATS Over PubNub

| Concern | PubNub | NATS |
|---------|--------|------|
| License | Proprietary SaaS | Apache 2.0 (CNCF project) |
| Corporate control | Yes — can change pricing, kill free tier | No — open source, community governed |
| Self-hosted | No | Yes — single binary, ~20MB |
| Cost | Free tier then paid | Free forever (you pay for infra) |
| Performance | Good (~100ms global) | Sub-millisecond (same region), low ms cross-region |
| Request/Reply | Must be built on top of pub/sub | **Native** — `nc.request(subject, msg)` |
| Python client | `pubnub` (heavy, thread-based EventEngine) | `nats-py` (async-native, lightweight) |
| Presence | Built-in | Heartbeat subjects + KV watch (build yourself) |

## Key Insight: NAT Traversal Is Not a Problem

PubNub solves NAT by being a centralized relay — clients connect **outbound** to PubNub's edge servers. NATS works exactly the same way:

```
Agent A → (outbound) → NATS server → (outbound from B) ← Agent B
```

Agents always initiate outbound connections. Only the NATS server needs a public address — which cloud deploy provides automatically (load balancer, Cloud Run URL, etc.).

## API Mapping

The `SenseTransport` protocol already abstracts the transport. NATS maps almost 1:1:

| PubNub | NATS | Notes |
|--------|------|-------|
| `publish(channel, msg)` | `nc.publish(subject, msg)` | Direct mapping |
| `subscribe(channel, callback)` | `nc.subscribe(subject, cb)` | Direct mapping |
| Request/response (custom) | `nc.request(subject, msg)` | NATS has this **native** — simpler code |
| Channel namespacing | Subject namespacing (dot-separated) | `bedsheet.agent-sentinel.alerts` works as-is |
| Presence | Heartbeat on dedicated subject + timeout tracking | Must implement ourselves |
| Signal (lightweight msg) | Regular publish (NATS messages are already lightweight) | No distinction needed |

## Deployment Strategy — bedsheet Deploys NATS Alongside Agents

This makes bedsheet the **first agent framework to bundle its own communication infrastructure**.

### Local Target (docker-compose)
```yaml
services:
  nats:
    image: nats:latest
    ports:
      - "4222:4222"  # Client connections
      - "8222:8222"  # Monitoring
  agent-worker:
    environment:
      - NATS_URL=nats://nats:4222
```

### GCP Target (Terraform)
- NATS deployed as Cloud Run service or GKE pod
- Agents connect via internal service URL
- For multi-region: NATS gateway routes between regional clusters

### AWS Target (CDK/Terraform)
- NATS on ECS Fargate or EKS
- Agents connect via service discovery (Cloud Map)
- Multi-region: NATS superclusters with gateway connections

## NATS Clustering (When Needed)

**Single region (most cases):** One NATS server, agents connect by service name. Trivial.

**Multi-region superclusters:**
- Each region runs a NATS cluster (3 nodes for HA)
- Gateway connections bridge clusters — explicitly configured with known endpoints
- Within a LAN, NATS auto-discovers peers via gossip protocol
- Across regions, Terraform/CDK wires the networking (VPC peering, load balancers, DNS)

## Implementation Plan

### Phase 1: NatsTransport (drop-in replacement)
- Implement `SenseTransport` protocol with NATS backend
- `nats-py` async client — fits bedsheet's async-first design
- Presence via heartbeat subject + timeout tracking
- Request/reply using NATS native `request()`

### Phase 2: Deploy Templates
- Add NATS container to local docker-compose template
- Add NATS to GCP Terraform templates
- Add NATS to AWS CDK/Terraform templates
- Auto-configure `NATS_URL` environment variable for agents

### Phase 3: Multi-Region (Future)
- NATS supercluster templates
- Gateway route configuration
- Cross-region latency optimization

## Alternatives Considered

| Option | Verdict |
|--------|---------|
| **NATS** | Best fit — Apache 2.0, CNCF, async Python, native request/reply |
| Mosquitto (MQTT) | Good for IoT, lacks native request/reply |
| Redis Pub/Sub | No persistence, no replay, no native presence |
| Centrifugo | WebSocket-focused, overkill for server-side agent comms |
| Matrix protocol | Too heavy for machine-to-machine messaging |
| Build our own | Reinventing NATS badly — no reason to |
| Synadia Cloud (managed NATS) | Corporation-controlled, defeats the purpose |

## Dependencies

- `nats-py` — official async NATS Python client
- `nats:latest` Docker image — official NATS server image (~20MB)
