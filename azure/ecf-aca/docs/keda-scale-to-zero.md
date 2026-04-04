# ECF-ACA: KEDA Scale-to-Zero Design

**Date:** 2026-04-04  
**Status:** Draft  
**Context:** `azure/ecf-aca`

## Problem

The current deployment sets `minReplicas: 1` to ensure the OTel Collector
`kafkareceiver` is always running. Without at least one replica, nothing
triggers scale-up when messages arrive in Event Hub — there is no external
push mechanism to wake a scaled-to-zero container.

This means the collector incurs a constant compute cost even when Event Hubs
are idle (e.g. nights, weekends, low-traffic environments).

## Proposed Solution

Use KEDA's **`kafka` scaler** — built into every Azure Container Apps
Environment — to watch Event Hub consumer group lag and trigger scale-up from
zero when messages are present.

### Why the `kafka` scaler (not `azure-eventhub`)

Two KEDA scalers are relevant to Event Hubs:

| Scaler | How it measures lag | Compatible with `kafkareceiver`? |
|---|---|---|
| `azure-eventhub` | Reads checkpoint blobs from Azure Blob Storage | **No** — `kafkareceiver` does not write blob checkpoints |
| `kafka` | Queries consumer group offset lag via Kafka protocol | **Yes** — same Kafka endpoint the receiver already uses |

The `kafkareceiver` stores offsets in the Kafka consumer group protocol
(inside Event Hubs itself), so the `kafka` scaler can read lag directly
without any additional infrastructure.

### Authentication

The `kafka` scaler uses SASL/PLAIN credentials — exactly the same connection
string the receiver already uses. Managed identity is **not viable** for the
Kafka protocol path on Event Hubs; connection string is the only supported
option.

## Required Changes

### 1. `infra/main.bicep` — add scale rules

Replace the current `scale` block (minReplicas/maxReplicas only) with:

```bicep
scale: {
  minReplicas: minReplicas   // can now be 0
  maxReplicas: maxReplicas
  rules: [
    {
      name: 'kafka-logs-lag'
      custom: {
        type: 'kafka'
        metadata: {
          bootstrapServers: '${eventHubNamespace.name}.servicebus.windows.net:9093'
          consumerGroup: 'ecf'
          topic: 'logs'
          lagThreshold: '50'          // messages per replica before scaling up
          activationLagThreshold: '1' // min lag to wake from zero
          sasl: 'plaintext'
          tls: 'enable'
        }
        auth: [
          {
            secretRef: 'eventhub-sasl-username'
            triggerParameter: 'username'
          }
          {
            secretRef: 'eventhub-connection-string'
            triggerParameter: 'password'
          }
        ]
      }
    }
    {
      name: 'kafka-metrics-lag'
      custom: {
        type: 'kafka'
        metadata: {
          bootstrapServers: '${eventHubNamespace.name}.servicebus.windows.net:9093'
          consumerGroup: 'ecf'
          topic: 'metrics'
          lagThreshold: '50'
          activationLagThreshold: '1'
          sasl: 'plaintext'
          tls: 'enable'
        }
        auth: [
          {
            secretRef: 'eventhub-sasl-username'
            triggerParameter: 'username'
          }
          {
            secretRef: 'eventhub-connection-string'
            triggerParameter: 'password'
          }
        ]
      }
    }
  ]
}
```

Add a new secret for the SASL username (the literal string `$ConnectionString`):

```bicep
{
  name: 'eventhub-sasl-username'
  value: '$ConnectionString'
}
```

The existing `eventhub-connection-string` secret already holds the full
connection string — it doubles as the SASL password.

### 2. `infra/main.bicep` — update default `minReplicas`

```bicep
// Before
param minReplicas int = 1

// After
param minReplicas int = 0
```

Callers that need an always-on replica (e.g. production with strict latency
SLOs) can still pass `minReplicas: 1` at deploy time.

### 3. `config.yaml` — no changes needed

Both receivers already have `initial_offset: earliest`, which ensures the
collector catches up on any backlog accumulated during the cold-start window.
SASL credentials are already sourced from `EVENTHUB_CONNECTION_STRING`.

## Cold Start Behaviour

With `minReplicas: 0`, the expected timeline from first message to consumption:

| Phase | Duration |
|---|---|
| KEDA polling detects lag | 0–30 s (configurable, default 30 s) |
| Container start + collector init | 1–5 s (Go binary, small image) |
| Kafka consumer group rebalance | 1–5 s |
| **Total** | **~30–60 s** |

Messages are **not lost** — Event Hubs retains them (1 day default, up to 7
days on Standard). The collector resumes from the last committed offset on
restart.

To reduce detection latency, the polling interval can be tuned to 10–15 s
using API version `2025-01-01` or later (not yet configurable in the Bicep
template's current API version `2024-03-01`).

## Trade-offs

| | `minReplicas: 1` (current) | `minReplicas: 0` (proposed) |
|---|---|---|
| Cost | Constant (one replica always running) | Near-zero when idle |
| Latency | Zero (always consuming) | ~30–60 s cold start |
| Complexity | None | Adds KEDA scale rules + one extra secret |
| Message loss | None | None (Event Hubs retention) |

The `minReplicas: 0` default is appropriate for dev/test or environments with
bursty, non-continuous telemetry. For production with latency SLOs, deploy
with `minReplicas: 1`.

## Open Questions

- What `lagThreshold` makes sense? `50` is a placeholder — depends on expected
  message rate and desired replica count.
- Should both topics share one rule or have separate rules as shown? Separate
  rules allow independent scaling per pipeline.
- Is there a use case for scaling beyond 4 replicas (current partition count)?
  ACA's kafka scaler caps replicas at partition count by default.
