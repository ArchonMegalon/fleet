# Part 02 - Document rendering

## 1. Purpose

Document rendering is the safest first feature family for the repo because it proves the split without volatile image/video costs.

This part covers:

* dossier packets
* memos, invoices, manifests, bulletins
* news issues and recap sheets
* HTML, PDF, and image render derivatives
* thumbnails and share cards

## 2. Boundary

Upstream services prepare content.
Media-factory renders it.

That means this repo receives:

* finalized text sections
* finalized tables and metadata
* template/style references
* render targets and retention hints

It does **not** receive:

* raw transcripts to summarize
* "make this more dramatic" prompts
* unresolved factual ambiguity
* campaign approval decisions

## 3. Component model

### `RenderTemplateCatalog`

Resolves template pack references to immutable template versions.
It may eventually consume packs from `chummer6-hub-registry`, but the renderer itself only sees a versioned manifest.

### `HtmlTemplateRenderer`

Deterministically fills templates from normalized render models.
This component should be pure and testable.

### `PdfRendererAdapter`

Converts HTML and static assets to PDF.
It should be provider/engine swappable.

### `ImageRendererAdapter`

Produces page previews and image exports from HTML or PDF sources.

### `PacketRenderService`

Orchestrates the document pipeline for dossiers, forms, packets, and reports.

### `IssueRenderService`

Specialized wrapper for recap/news issue layouts where multiple article blocks, headlines, and bylines must be composed.

## 4. Contracts

Suggested media-side contracts:

* `DocumentRenderPlan`
* `DocumentRenderModel`
* `DocumentTemplateRef`
* `DocumentStyleRef`
* `DocumentRenderTarget`
* `DocumentArtifactManifest`
* `DocumentRenderResult`

Model rules:

* render models should already be localized or key-resolved upstream when required
* templates may reference style tokens only, not arbitrary code
* template versions must be immutable once released

## 5. Determinism

Document rendering must be the most deterministic part of the repo.

For the same:

* template version
* style version
* render model
* locale policy
* asset references

the repo should produce:

* byte-stable HTML
* stable manifest metadata
* stable page count when the underlying render engine is unchanged

PDF bytes may still vary if the engine embeds timestamps or metadata by default; the adapter should disable that where possible.

## 6. Styling model

Templates should consume versioned style packs rather than arbitrary CSS text from callers.
That gives you:

* reviewable template outputs
* predictable rendering
* easier sanitization
* eventual publication through `chummer6-hub-registry`

## 7. Security and sanitization

Treat templates and composition models as untrusted unless they originate from approved sources.

Required controls:

* HTML escaping by default
* no arbitrary script execution
* no remote asset fetch during render unless whitelisted and cached
* no template code with filesystem or network access
* strict font and asset allowlists in production

## 8. Output set

A typical packet render should emit:

* preview image
* PDF
* optional print image set
* thumbnail/share card
* one manifest grouping the set

The caller decides what to attach or publish later.

## 9. Tests

Document rendering tests must prove:

* missing template refs fail before worker execution
* required fields fail validation with actionable diagnostics
* stable input produces stable HTML
* PDFs and previews are linked to one manifest group
* thumbnail generation works for multi-page output
* the renderer refuses unsafe HTML or remote includes
