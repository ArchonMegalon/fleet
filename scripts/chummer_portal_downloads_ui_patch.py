#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


METHOD = r'''    public static string BuildDownloadsHtml(string fallbackDownloadsUrl, bool hasFallbackSource)
    {
        string escapedFallbackUrl = HtmlEncode(fallbackDownloadsUrl);
        string escapedScriptFallbackUrl = JavaScriptStringEncode(fallbackDownloadsUrl);
        string fallbackLinkHiddenAttribute = hasFallbackSource ? string.Empty : " hidden";
        string endpointFailureText = hasFallbackSource
            ? "Release manifest request failed; use the configured fallback source while the portal downloads endpoint is unavailable."
            : "Release manifest request failed and no fallback source is configured.";
        return $$"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Chummer Downloads</title>
    <style>
      :root { --ink: #f0f3f7; --muted: #b5c2d0; --edge: #32495f; --bg: #071420; --card: #132230; --accent: #f58b2a; }
      * { box-sizing: border-box; }
      body { margin: 0; min-height: 100vh; padding: 24px; color: var(--ink); background: linear-gradient(160deg, #081824, #162736); font-family: "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif; }
      main { width: min(920px, 100%); margin: 0 auto; background: color-mix(in oklab, var(--card) 88%, #000 12%); border: 1px solid var(--edge); border-radius: 14px; box-shadow: 0 18px 40px rgba(0,0,0,0.35); overflow: hidden; }
      header { padding: 18px 20px 10px; border-bottom: 1px solid var(--edge); }
      h1 { margin: 0; font-size: clamp(1.3rem, 2.6vw, 1.9rem); }
      p { margin: 10px 0 0; color: var(--muted); }
      .content { padding: 14px 20px 18px; display: grid; gap: 12px; }
      .meta { font-size: 0.92rem; color: var(--muted); }
      .filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
      .filter { display: grid; gap: 6px; }
      .filter label { font-size: 0.88rem; color: var(--muted); }
      .filter select { width: 100%; border-radius: 10px; border: 1px solid var(--edge); background: rgba(255,255,255,0.04); color: var(--ink); padding: 10px 12px; font: inherit; color-scheme: dark; }
      .filter select option { color: var(--ink); background: #132230; }
      ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
      li { border: 1px solid var(--edge); background: rgba(255,255,255,0.02); border-radius: 10px; padding: 12px; display: grid; gap: 8px; }
      .artifact-top { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; flex-wrap: wrap; }
      .artifact-title { font-size: 1rem; font-weight: 700; }
      .artifact-tags { display: flex; gap: 8px; flex-wrap: wrap; }
      .tag { border: 1px solid var(--edge); border-radius: 999px; padding: 4px 9px; color: var(--muted); font-size: 0.82rem; }
      .artifact-meta { display: flex; gap: 10px; flex-wrap: wrap; color: var(--muted); font-size: 0.88rem; }
      a { color: #091016; background: var(--accent); text-decoration: none; font-weight: 700; border-radius: 999px; padding: 7px 11px; justify-self: start; }
      code { font-size: 0.8rem; color: #ffe0c2; overflow-wrap: anywhere; }
      .ghost { color: var(--muted); border: 1px solid var(--edge); border-radius: 10px; padding: 12px; }
    </style>
  </head>
  <body>
    <main>
      <header>
        <h1>Desktop Downloads</h1>
        <p>Manifest-backed platform matrix from <code>/downloads/releases.json</code>.</p>
      </header>
      <section class="content">
        <div id="meta" class="meta">Loading release manifest...</div>
        <div class="filters" id="filters" hidden>
          <div class="filter">
            <label for="download-platform">Platform</label>
            <select id="download-platform">
              <option value="all">All platforms</option>
            </select>
          </div>
          <div class="filter">
            <label for="download-type">Type</label>
            <select id="download-type">
              <option value="all">All types</option>
            </select>
          </div>
        </div>
        <ul id="download-list"></ul>
        <div id="empty" class="ghost" hidden>No platform artifacts published yet.</div>
        <a href="{{escapedFallbackUrl}}" id="fallback-link"{{fallbackLinkHiddenAttribute}}>Open configured fallback source</a>
      </section>
    </main>
    <script>
      (async function () {
        const meta = document.getElementById('meta');
        const list = document.getElementById('download-list');
        const empty = document.getElementById('empty');
        const fallbackLink = document.getElementById('fallback-link');
        const filters = document.getElementById('filters');
        const platformSelect = document.getElementById('download-platform');
        const typeSelect = document.getElementById('download-type');
        fallbackLink.href = '{{escapedScriptFallbackUrl}}';

        const ridLabels = {
          'win-x64': 'Windows x64',
          'win-arm64': 'Windows ARM64',
          'linux-x64': 'Linux x64',
          'linux-arm64': 'Linux ARM64',
          'osx-arm64': 'macOS ARM64',
          'osx-x64': 'macOS x64'
        };

        const inferType = (item) => {
          const text = `${item.id || ''} ${item.platform || ''}`.toLowerCase();
          if (text.includes('avalonia')) return { value: 'avalonia', label: 'Avalonia' };
          if (text.includes('blazor')) return { value: 'blazor', label: 'Blazor' };
          return { value: 'desktop', label: 'Desktop' };
        };

        const inferPlatform = (item) => {
          const text = `${item.id || ''} ${item.platform || ''} ${item.url || ''}`.toLowerCase();
          for (const [rid, label] of Object.entries(ridLabels)) {
            if (text.includes(rid.toLowerCase())) {
              return { value: rid, label };
            }
          }
          return { value: 'unknown', label: 'Other' };
        };

        const formatSize = (sizeBytes) => {
          const size = Number(sizeBytes || 0);
          if (!Number.isFinite(size) || size <= 0) {
            return '';
          }
          const units = ['B', 'KB', 'MB', 'GB'];
          let value = size;
          let index = 0;
          while (value >= 1024 && index < units.length - 1) {
            value /= 1024;
            index += 1;
          }
          return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
        };

        const resetOptions = (select, label) => {
          select.innerHTML = '';
          const option = document.createElement('option');
          option.value = 'all';
          option.textContent = label;
          select.appendChild(option);
        };

        let enrichedDownloads = [];

        const renderDownloads = () => {
          list.innerHTML = '';
          empty.hidden = true;
          const selectedPlatform = platformSelect.value || 'all';
          const selectedType = typeSelect.value || 'all';
          const filtered = enrichedDownloads.filter((item) => {
            const platformOk = selectedPlatform === 'all' || item.platformInfo.value === selectedPlatform;
            const typeOk = selectedType === 'all' || item.typeInfo.value === selectedType;
            return platformOk && typeOk;
          });

          if (!filtered.length) {
            empty.textContent = 'No downloads match the current platform/type filter.';
            empty.hidden = false;
            return;
          }

          for (const item of filtered) {
            const row = document.createElement('li');

            const top = document.createElement('div');
            top.className = 'artifact-top';

            const title = document.createElement('div');
            title.className = 'artifact-title';
            title.textContent = item.platform || 'Artifact';
            top.appendChild(title);

            const tags = document.createElement('div');
            tags.className = 'artifact-tags';

            const typeTag = document.createElement('span');
            typeTag.className = 'tag';
            typeTag.textContent = item.typeInfo.label;
            tags.appendChild(typeTag);

            const platformTag = document.createElement('span');
            platformTag.className = 'tag';
            platformTag.textContent = item.platformInfo.label;
            tags.appendChild(platformTag);

            top.appendChild(tags);
            row.appendChild(top);

            const artifactMeta = document.createElement('div');
            artifactMeta.className = 'artifact-meta';
            if (item.id) {
              const idMeta = document.createElement('span');
              idMeta.textContent = item.id;
              artifactMeta.appendChild(idMeta);
            }
            const sizeLabel = formatSize(item.sizeBytes);
            if (sizeLabel) {
              const sizeMeta = document.createElement('span');
              sizeMeta.textContent = sizeLabel;
              artifactMeta.appendChild(sizeMeta);
            }
            row.appendChild(artifactMeta);

            if (item.sha256) {
              const hash = document.createElement('code');
              hash.textContent = `sha256: ${item.sha256}`;
              row.appendChild(hash);
            }

            if (item.url) {
              const anchor = document.createElement('a');
              anchor.href = item.url;
              anchor.textContent = `Download ${item.typeInfo.label}`;
              row.appendChild(anchor);
            }

            list.appendChild(row);
          }
        };

        try {
          const response = await fetch('/downloads/releases.json', { cache: 'no-store' });
          if (!response.ok) {
            throw new Error('manifest request failed: ' + response.status);
          }

          const manifest = await response.json();
          const version = typeof manifest.version === 'string' ? manifest.version : 'unknown';
          const channel = typeof manifest.channel === 'string' ? manifest.channel : 'unknown';
          const published = manifest.publishedAt ? new Date(manifest.publishedAt).toISOString() : 'unknown';
          const downloads = Array.isArray(manifest.downloads) ? manifest.downloads : [];
          const status = typeof manifest.status === 'string' ? manifest.status : 'published';
          const source = typeof manifest.source === 'string' ? manifest.source : 'manifest';
          const message = typeof manifest.message === 'string' ? manifest.message : '';
          const manifestHasFallbackSource = manifest.hasFallbackSource === true;

          if (downloads.length === 0) {
            switch (status) {
              case 'unpublished':
                meta.textContent = `No published desktop builds yet (${channel}).`;
                empty.textContent = message || 'No published desktop builds yet. Run desktop-downloads workflow and deploy the generated bundle.';
                break;
              case 'manifest-empty':
                meta.textContent = `Release manifest is present but empty (${channel}).`;
                empty.textContent = message || 'Release manifest is present but has no platform artifacts.';
                break;
              case 'manifest-missing':
                meta.textContent = 'Release manifest is missing from this portal.';
                empty.textContent = message || 'Self-hosted downloads are not mounted or published on this portal.';
                break;
              case 'manifest-error':
                meta.textContent = 'Release manifest is invalid on this portal.';
                empty.textContent = message || 'Release manifest exists but could not be parsed.';
                break;
              case 'fallback-source':
                meta.textContent = 'Portal is using a configured fallback downloads source.';
                empty.textContent = message || 'Open the configured fallback source while self-hosted downloads are unavailable.';
                break;
              default:
                meta.textContent = `Version ${version} (${channel}) has no downloadable artifacts.`;
                empty.textContent = message || 'Manifest has no platform artifacts.';
                break;
            }

            if (!manifestHasFallbackSource) {
              fallbackLink.hidden = true;
            }

            empty.hidden = false;
            return;
          }

          meta.textContent = source === 'local-files'
            ? `Version ${version} (${channel}) available from locally discovered portal artifacts (${published}).`
            : `Version ${version} (${channel}) published ${published}`;

          enrichedDownloads = downloads.map((item) => ({
            ...item,
            typeInfo: inferType(item),
            platformInfo: inferPlatform(item)
          }));

          resetOptions(platformSelect, 'All platforms');
          resetOptions(typeSelect, 'All types');

          const platforms = [...new Map(enrichedDownloads.map((item) => [item.platformInfo.value, item.platformInfo])).values()]
            .sort((left, right) => left.label.localeCompare(right.label));
          const types = [...new Map(enrichedDownloads.map((item) => [item.typeInfo.value, item.typeInfo])).values()]
            .sort((left, right) => left.label.localeCompare(right.label));

          for (const platform of platforms) {
            const option = document.createElement('option');
            option.value = platform.value;
            option.textContent = platform.label;
            platformSelect.appendChild(option);
          }
          for (const type of types) {
            const option = document.createElement('option');
            option.value = type.value;
            option.textContent = type.label;
            typeSelect.appendChild(option);
          }

          platformSelect.addEventListener('change', renderDownloads);
          typeSelect.addEventListener('change', renderDownloads);
          filters.hidden = false;
          renderDownloads();
        } catch (error) {
          meta.textContent = '{{endpointFailureText}}';
          empty.textContent = '{{endpointFailureText}}';
          empty.hidden = false;
        }
      })();
    </script>
  </body>
</html>
""";
    }
'''


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: chummer_portal_downloads_ui_patch.py <PortalPageBuilder.cs>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    content = path.read_text(encoding="utf-8")
    start = content.find("    public static string BuildDownloadsHtml(")
    if start < 0:
        raise SystemExit("BuildDownloadsHtml method not found")
    end = content.find("    public static string BuildAvaloniaPlaceholderHtml(", start)
    if end < 0:
        raise SystemExit("BuildAvaloniaPlaceholderHtml method boundary not found")

    updated = content[:start] + METHOD + "\n\n" + content[end:]
    path.write_text(updated, encoding="utf-8")
    print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
