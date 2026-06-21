# M6 - Hardening and release readiness

## Goal

Turn the repo from "feature complete" into "safe to operate."

## Included

* dashboards and alerts
* structured logging and traces
* storage quota enforcement
* janitor and restore jobs
* provider health checks
* DR procedure
* cost guard verification
* signed asset access review
* load and soak testing
* on-call playbook and runbook

## Excluded

* net-new product surface unless required to close a safety gap

## Detailed design

### 1. Observability package

Expose metrics by job kind and provider.
Dashboards must answer:

* what is queued?
* what is slow?
* what is failing?
* what is consuming storage?
* what is expensive?

### 2. Safe degradation

Implement progressive shedding:

* reject new long video jobs first
* continue status reads and asset delivery
* keep cleanup and restore paths available
* avoid total outage from provider failure

### 3. Restore drill

Demonstrate restore from:

* metadata backup
* binary backup
* partial provider outage condition

### 4. Security review

Review:

* secret handling
* signed URL duration
* bucket policies
* MIME/content checks
* uploaded reference scanning
* sensitive log redaction

### 5. Release checklist

The repo does not release until:

* all milestone exit tests pass
* no legacy render execution remains in `run-services` for released domains
* rollback instructions are written
* restore drill is documented
* storage growth policy is defined
* provider outage runbook exists

## Exit tests

* dashboards and alerts are live
* janitor removes orphaned or expired assets safely
* restore drill succeeds
* provider outage does not cascade into upstream corruption
* signed asset access expires correctly
* SLOs and escalation targets are documented
