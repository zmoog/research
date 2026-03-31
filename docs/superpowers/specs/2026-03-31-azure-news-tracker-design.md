# Azure News Tracker — Design Spec

## Problem

Maintaining ~25 Azure integrations across Elastic Agent (integrations repo) and Beats requires staying on top of Azure announcements — deprecations, new services, SDK releases, breaking changes. Today this is manual (feed reader on the Azure SDK blog), which means things slip through, signal is lost in noise, and there's no systematic coverage of all relevant sources.

## Goal

A fully automated system that monitors Azure announcement sources, filters for relevance to our integrations, and delivers daily/weekly digests via email.

## Data Sources

Three feeds, polled daily:

| Source | URL | What it catches |
|--------|-----|-----------------|
| Azure Updates RSS | `https://www.microsoft.com/releasecommunications/api/v2/azure/rss` | GA, preview, retirement, action-required notices |
| Azure SDK Blog RSS | `https://devblogs.microsoft.com/azure-sdk/feed/` | Monthly SDK release summaries, breaking changes |
| Azure SDK Release CSVs (Go) | `https://raw.githubusercontent.com/Azure/azure-sdk/main/_data/releases/latest/go-packages.csv` | Per-package versions, EOL dates, replacements |

### RSS Feeds

Fetched daily. New entries detected by comparing published dates against last poll.

### SDK Release CSVs

Only Go packages tracked (Beats is written in Go). The script diffs against the previous day's snapshot (committed to the repo) to detect:

- New package versions (GA or preview)
- New EOL dates appearing
- Packages gaining a `Replace` value (deprecated in favor of something else)

## Relevance Filtering

### Stage 1: Keyword/Category Pre-filter

Cheap, no LLM. Keep items mentioning Azure service names covered by our integrations:

Event Hubs, Monitor, Storage, Blob Storage, Compute, VM, VM Scale Sets, Container Instances, Container Registry, AKS, Kubernetes, App Service, Functions, Frontdoor, Network Watcher, NSG, VNet, OpenAI, AI Foundry, Cosmos DB, Application Insights, Entra ID, Sentinel, Defender, Billing, Activity Log, Sign-in, Audit Log.

Discard obvious misses.

### Stage 2: LLM Relevance Scoring

Pass surviving items to Claude API with context about our integrations. Classify each as:

- **High** — deprecation, breaking change, or new service directly affecting an existing integration
- **Medium** — new feature, API change, or SDK update relevant to an integration
- **Low** — tangentially related, nice to know

### CSV Diffs

No LLM needed. If a Go package our integrations depend on has a version bump, EOL date, or replacement, it's automatically relevant.

## Notification Delivery

### Daily (Mon-Fri, 7am UTC)

- High + Medium items from the last 24h
- If nothing relevant, no email sent (no noise)
- Format: one-line summary per item, relevance tag, source link
- For SDK changes: old version -> new version, EOL date if applicable

### Weekly (Monday, 8am UTC)

- Rollup covering the past 7 days
- Includes Low items
- Grouped by category: deprecations, new features, SDK updates

### Channel

Email via Resend (simple API, free tier sufficient for this volume).

## Architecture

Git scraping pattern in a dedicated GitHub repo.

```
azure-news/                         (dedicated GitHub repo)
  data/
    rss/azure-updates.xml           <- raw snapshots
    rss/azure-sdk-blog.xml
    csv/go-packages.csv
  diffs/
    2026-03-31-csv-changes.json     <- detected diffs
  digests/
    2026-03-31-daily.md             <- generated summaries
    2026-W14-weekly.md
  scripts/
    fetch.py        <- download raw feeds/CSVs
    diff.py         <- compare against previous commit
    filter.py       <- keyword + LLM filtering
    notify.py       <- send email via Resend
  .github/workflows/
    daily.yml       <- cron: 7am UTC, Mon-Fri
    weekly.yml      <- cron: Monday 8am UTC (runs after daily)
```

### Flow

1. **fetch.py** — downloads RSS feeds and Go CSV, saves to `data/`
2. Git diff against previous commit reveals what changed (git scraping)
3. **diff.py** — parses the changes into structured items (new RSS entries, CSV field changes)
4. **filter.py** — applies keyword pre-filter, then Claude API for relevance scoring
5. **notify.py** — sends email + commits the digest to `digests/`
6. Git commit the updated `data/` snapshots

### Dependencies

- Python 3.12+
- `feedparser` — RSS parsing
- `anthropic` — Claude API for relevance filtering
- `resend` — email delivery

### Secrets (GitHub Actions)

- `ANTHROPIC_API_KEY`
- `RESEND_API_KEY`

## Integrations Covered

The system tracks announcements relevant to these Elastic integrations:

**Azure integrations (integrations repo):** azure, azure_ai_foundry, azure_app_service, azure_application_insights, azure_billing, azure_blob_storage, azure_frontdoor, azure_functions, azure_logs, azure_metrics, azure_network_watcher_nsg, azure_network_watcher_vnet, azure_openai

**Microsoft integrations:** entityanalytics_entra_id, microsoft_sentinel, microsoft_defender_cloud, microsoft_defender_endpoint, m365_defender, o365, o365_metrics, microsoft_exchange_online_message_trace

**Beats modules:** azure (filebeat: activitylogs, auditlogs, platformlogs, signinlogs; metricbeat: app_insights, app_state, billing, compute_vm, compute_vm_scaleset, container_instance, container_registry, container_service, database_account, monitor, storage)

## Non-Goals

- Real-time alerting (daily cadence is sufficient)
- Azure Resource Health API integration (requires auth, can add later)
- Tracking SDK packages beyond Go
- Multi-user support (single consumer for now)
