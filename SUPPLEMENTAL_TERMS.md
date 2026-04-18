# Bedsheet Agents - Supplemental License Terms

**Effective Date:** December 2025

These Supplemental Terms apply to the Bedsheet Agents software ("Software") and supplement the [Elastic License 2.0](LICENSE.md) under which the Software is made available. In the event of any conflict between the Elastic License 2.0 and these Supplemental Terms, these Supplemental Terms shall prevail.

---

## 1. Additional Restrictions

### 1.1 Cloud-Agnostic Agent Platform Prohibition

You may not use the Software, directly or indirectly, to offer, enable, operate, or provide any **Cloud-Agnostic Agent Platform** to third parties, whether as a hosted service, managed service, platform-as-a-service, or otherwise.

### 1.2 Repackaging and Competing Services

You may not repackage, rebrand, or otherwise offer the Software's agent-building, multi-cloud deployment, or cloud-agnostic orchestration capabilities to third parties. This includes, without limitation:

- Offering a hosted service that allows users to build, deploy, or manage AI agents across multiple cloud providers
- Creating a competing "deploy anywhere" or "write once, run anywhere" agent platform
- Providing agent deployment services that leverage the Software's cloud abstraction capabilities
- Offering the Software's deployment targets (AWS, GCP, Local) as part of a commercial platform

### 1.3 Agent Sentinel™ Protected Technology

You may not extract, replicate, or offer as a standalone product or service the Software's **Agent Sentinel™** technology, including without limitation:

- Sentinel-based agent security monitoring systems that use tamper-proof action ledgers to detect and respond to agent compromise, drift, or rogue behavior
- Action Gateway architectures that enforce deterministic, non-LLM trust boundaries for agent tool execution, including rate limiting, keyword blocking, and quarantine enforcement
- Multi-tier sentinel coordination patterns where behavior sentinels, supply-chain sentinels, and sentinel commanders collaborate to detect, correlate, and respond to agent security threats
- Any system that combines the above capabilities to provide autonomous agent security monitoring, whether using the Software's code or independently reimplementing its architecture

### 1.4 Sixth Sense Protected Technology

You may not extract, replicate, or offer as a standalone product or service the Software's **Sixth Sense** distributed agent communication technology, including without limitation:

- Pluggable transport protocol architectures that enable agents running on different machines, processes, or containers to exchange typed signals over interchangeable communication backends (such as PubNub, NATS, Redis pub/sub, or similar)
- Signal-based agent coordination patterns including request/response across distributed agents, claim protocols for incident deduplication, and typed signal schemas for inter-agent communication
- Transport factory abstractions that auto-select communication backends from environment configuration, enabling agents to operate identically across local development (in-process mock transport) and production (networked transport) without code changes
- Any system that combines the above capabilities to provide a general-purpose, transport-agnostic, real-time communication bus for AI agent networks, whether using the Software's code or independently reimplementing its architecture

### 1.5 Permitted Uses

The restrictions in Sections 1.1 through 1.4 do not prohibit you from:

**(a) Internal Use:** Using the Software to build and deploy your own AI agents for your own products, services, or internal operations, including deploying to any cloud provider.

**(b) Professional Services:** Using the Software to deliver bespoke agent solutions to individual clients, provided that:
- Only your personnel operate the Software
- Clients receive only the resulting deployed agent, not access to the agent-building or deployment capabilities
- You do not provide a multi-tenant platform where clients can build or deploy their own agents

**(c) Embedded Agents:** Integrating agents built with the Software into your products or services, where end users interact with the agent but cannot access agent-creation, configuration, or deployment features.

---

## 2. Definitions

**"Agent"** means any autonomous or semi-autonomous software system powered by artificial intelligence, machine learning, or large language models (LLMs) that can perform tasks, make decisions, or interact with users or systems.

**"Agent Sentinel™"** means the Software's agent security monitoring technology, including but not limited to: sentinel-based monitoring architectures, Action Gateway trust boundaries, tamper-proof action ledgers, multi-tier sentinel coordination (behavior sentinels, supply-chain sentinels, sentinel commanders), and quarantine enforcement mechanisms for compromised agents.

**"Cloud-Agnostic Agent Platform"** means any product, service, or platform that enables third parties to build, configure, deploy, or manage AI agents across multiple cloud providers or deployment targets (such as AWS, GCP, Azure, or local environments) using a unified interface or abstraction layer.

**"Sixth Sense"** means the Software's distributed agent communication technology, including but not limited to: pluggable transport protocol architectures for inter-agent signaling, typed signal schemas, request/response and claim protocols for distributed agent coordination, transport factory abstractions, and mock/production transport interchangeability.

**"Vitakka Consulting"** means Vitakka Consulting (https://vitakka.co/), the licensor of this Software.

---

## 3. Redistribution

Any redistribution of the Software must include both:
- The [Elastic License 2.0](LICENSE.md)
- These Supplemental Terms

---

## 4. Contact

For licensing inquiries, commercial partnerships, or questions about permitted uses, contact:

**Vitakka Consulting**
Website: https://vitakka.co/
Email: info@vitakka.co

---

Copyright 2025-2026 Sivan Grünberg, [Vitakka Consulting](https://vitakka.co/)
