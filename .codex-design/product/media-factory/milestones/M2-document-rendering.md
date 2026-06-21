# M2 - Deterministic document rendering

## Goal

Deliver the first end-to-end value path through the new repo using the most controllable media family: documents.

The milestone proves:

* the package split is usable
* the kernel can power real workloads
* the repo can render deterministic artifacts from prepared input

## Included

* document render plans and models
* template catalog
* HTML rendering
* PDF rendering
* preview and thumbnail generation
* packet/dossier/document service
* issue/news render service
* versioned template/style references

## Excluded

* LLM drafting inside this repo
* portrait generation
* video rendering
* public template marketplace/registry concerns

## Detailed design

### 1. Input normalization

Upstream composition DTOs should be normalized into render models before the job reaches the renderer.
That normalization should freeze:

* sections
* tables
* assets
* locale-specific text or keys
* template ref
* style ref

The renderer should not make semantic decisions after that point.

### 2. Template versioning

Every render result must record:

* template pack id
* template version
* style pack id
* style version

That metadata is load-bearing because it explains how a PDF or bulletin was produced.

### 3. Deterministic rendering discipline

The HTML rendering component must be pure and isolated from:

* time-of-day defaults
* network fetches
* random layout choices
* implicit template upgrades

### 4. Output grouping

A document render should produce an artifact group, not a single anonymous file.
Typical group:

* preview
* PDF
* thumbnail
* optional print/export image set

Grouping belongs in manifests and lineage.

### 5. Security

Templates must be sanitized and capability-limited.
No arbitrary remote font fetches, no script execution, and no environment access during rendering.

## Exit tests

* finalized document models render to stable HTML and usable PDF
* missing template/style refs fail early
* previews and thumbnails attach to the same manifest group
* render metadata records template/style versions
* document output can be re-rendered from the same model and manifest lineage
