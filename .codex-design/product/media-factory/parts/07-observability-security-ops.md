# Part 07 - Observability, security, and operations

## 1. Purpose

Media systems fail differently from text APIs.
They consume more storage, take longer, cost more per request, and can leave ugly debris if poorly operated.

This part defines the boring but mandatory production posture.

## 2. Metrics

Required service metrics:

* jobs accepted by kind
* queue latency
* execution latency
* completion rate
* failure rate by normalized failure code
* retries by kind/provider
* storage footprint by asset kind
* hot-cache hit rate
* preview generation success rate
* provider spend/credit consumption where available

## 3. Logging

Structured logs must include:

* `CorrelationId`
* `JobId`
* `AssetId`
* `ProviderRunId`
* `JobKind`
* `State`
* `FailureCode`
* `DurationMs`

Never log raw secrets, signed URLs, or full unredacted prompts when those may contain sensitive content.

## 4. Tracing

Trace spans should cover:

* intake
* validation
* queue wait
* provider execution
* binary write
* preview generation
* callback or status publish

## 5. Security

Required controls:

* secret storage in infrastructure, not config files committed to repo
* provider credentials scoped per adapter
* virus/malware scanning for uploaded anchors and reference files
* strict MIME/content-type checks
* storage bucket least-privilege policy
* short-lived signed asset access
* redactable logs for provider-returned diagnostics

## 6. Disaster recovery

You must be able to restore:

* metadata DB
* binary store
* linkage between them

DR drills should demonstrate:

* manifest-only rebuild of status
* binary integrity verification via checksum
* recovery from partial provider outage
* cleanup of orphaned binaries or orphaned manifests

## 7. Safe degradation

Under pressure, the service should degrade in this order:

1. reject new expensive video jobs
2. accept only previews/documents/portraits
3. slow or pause low-priority jobs
4. preserve status reads and existing asset access
5. never corrupt manifest history

## 8. SLOs

Suggested initial SLOs:

* document render p95 under agreed internal threshold
* portrait preview p95 under agreed internal threshold
* asset status lookup p95 under agreed internal threshold
* queue wait within internal limit during nominal load
* signed asset availability within internal service SLO

The exact numbers can be added once provider selection is stable.

## 9. Release gate

This repo should not reach release without:

* dashboards
* alerts
* janitor jobs
* restore procedure
* quota/cost guardrails
* provider outage playbook
* on-call runbook for stuck jobs and orphaned assets
