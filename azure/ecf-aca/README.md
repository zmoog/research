# ECF-ACA: EDOT Cloud Forwarder on Azure Container Apps

A prototype exploring an alternative deployment model for EDOT Cloud Forwarder
(ECF) for Azure, running the OpenTelemetry Collector on **Azure Container Apps
(ACA)** instead of Azure Functions.

## Architecture Overview

```
Azure Resources
  ├─ Diagnostic Settings ──► Event Hub "logs"    ──┐
  └─ Diagnostic Settings ──► Event Hub "metrics" ──┘
                                                    │
                                           (Kafka protocol)
                                                    │
                                                    ▼
                              ┌──────────────────────────────────┐
                              │   Azure Container App (ACA)      │
                              │                                  │
                              │   OTel Collector                 │
                              │   ├─ kafkareceiver/logs          │
                              │   ├─ kafkareceiver/metrics       │
                              │   ├─ azureencodingextension      │
                              │   ├─ beatsencodingextension      │
                              │   ├─ transformprocessor          │
                              │   └─ otlpexporter/elastic        │
                              │                                  │
                              │   Auth: SASL/PLAIN over TLS      │
                              │   (Event Hub connection string)  │
                              └──────────────────────────────────┘
                                              │
                                              │ OTLP gRPC
                                              ▼
                                        Elasticsearch
```

### Why Kafka Receiver?

Azure Event Hubs exposes a Kafka-compatible endpoint. We use the OTel Collector
contrib `kafkareceiver` instead of the `azureeventhubreceiver` because:

1. **Encoding extension support**: The Kafka receiver supports pluggable encoding
   extensions. This lets us use `azureencodingextension` and `beatsencodingextension`
   to decode Event Hub messages — the same encodings used by the Azure Functions
   based ECF.
2. **The Event Hub receiver does not support encoding extensions**: It has a
   hardcoded `format` field (`azure`, `raw`) with no extension hook.
3. **Kafka consumer group protocol**: Partition assignment and offset tracking are
   handled by the Kafka protocol itself — no separate blob checkpoint store needed.

### Key Differences from ECF Azure Functions

| Aspect | ECF (Azure Functions) | ECF-ACA (Container Apps) |
|--------|----------------------|--------------------------|
| **Compute** | Azure Functions (Flex Consumption) | Azure Container Apps |
| **Scaling** | Event-driven (per-event) | Container-level (min/max replicas) |
| **Receiver** | Custom `azurefunctionsreceiver` (push via HTTP custom handler) | Upstream `kafkareceiver` (pull via Kafka protocol) |
| **Event Hub protocol** | AMQP (via Functions runtime) | Kafka (SASL/PLAIN over TLS on port 9093) |
| **Encoding** | `azureencodingextension`, `beatsencodingextension` | Same — `azureencodingextension`, `beatsencodingextension` |
| **Checkpointing** | Functions runtime handles offsets | Kafka consumer group protocol |
| **Cold start** | Yes (especially on Consumption plan) | No (always-on container) |
| **Custom code** | Custom receiver + encoding extensions | Zero custom code — all upstream components |
| **Event Hub SKU** | Any (Basic, Standard, Premium) | Standard or above (Kafka requires it) |

## Project Structure

```
ecf-aca/
├── README.md              # This file
├── Makefile               # Build and deploy commands
├── Dockerfile             # Container image build
├── config.yaml            # OTel Collector configuration
├── collector/
│   ├── main.go            # Collector entry point
│   ├── components.go      # Component registration
│   ├── go.mod             # Go module
│   └── go.sum             # Dependency lock file
└── infra/
    └── main.bicep         # ACA + Event Hubs infrastructure
```

## Components

| Component | Type | Source |
|-----------|------|--------|
| `kafkareceiver` | Receiver | otel-collector-contrib |
| `azureencodingextension` | Extension | otel-collector-contrib |
| `beatsencodingextension` | Extension | elastic/opentelemetry-collector-components |
| `transformprocessor` | Processor | otel-collector-contrib |
| `otlpexporter` | Exporter | otel-collector-core |
| `debugexporter` | Exporter | otel-collector-core |

## Quick Start

```bash
# Build the collector binary
make build

# Build the container image
make docker-build

# Deploy infrastructure (requires Azure CLI)
make deploy
```

## Configuration

The collector is configured via environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `EVENTHUB_NAMESPACE` | Event Hub namespace FQDN (e.g., `ns.servicebus.windows.net`) | Yes |
| `EVENTHUB_CONNECTION_STRING` | Event Hub namespace connection string (SASL password) | Yes |
| `EVENTHUB_LOGS_NAME` | Event Hub name for logs (default: `logs`) | No |
| `EVENTHUB_METRICS_NAME` | Event Hub name for metrics (default: `metrics`) | No |
| `EVENTHUB_CONSUMER_GROUP` | Kafka consumer group ID (default: `ecf`) | No |
| `LOGS_ENCODING` | Encoding for logs (default: `azure_encoding`) | No |
| `METRICS_ENCODING` | Encoding for metrics (default: `azure_encoding`) | No |
| `ELASTICSEARCH_OTLP_ENDPOINT` | Elasticsearch OTLP endpoint | Yes |
| `ELASTICSEARCH_API_KEY` | Elasticsearch API key | Yes |
| `PIPELINE_EXPORTER` | Override exporter (default: `otlp/elastic`, use `debug` for testing) | No |

### Encoding Options

The encoding can be switched per-pipeline via environment variables:

- **`azure_encoding`** (default): Decodes Azure resource logs/metrics format into
  OTel-native attributes using the contrib `azureencodingextension`.
- **`beats_encoding`**: Produces Beats-compatible output with `data_stream.dataset`,
  `input_type`, and tags like `forwarded` — matches the existing Elastic integration
  format.

## Infrastructure

The Bicep template (`infra/main.bicep`) deploys:

- **Event Hub Namespace** (Standard SKU with Kafka enabled) with `logs` and `metrics`
  hubs, each with an `ecf` consumer group
- **Shared Access Policy** (`ecf-listen`) with Listen rights — the connection string
  is used as the SASL/PLAIN password for the Kafka receiver
- **Container Apps Environment** with Log Analytics workspace
- **Container App** with the collector image and all env vars wired up

### Event Hub SKU Requirement

The Kafka protocol is only available on **Standard** tier and above. The Basic tier
does not support Kafka. The Bicep template enforces this with an `@allowed` constraint.
