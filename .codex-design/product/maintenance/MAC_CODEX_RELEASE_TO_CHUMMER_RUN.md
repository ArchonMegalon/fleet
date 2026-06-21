# Mac Codex Release To chummer.run

Purpose: let a Codex session running on a Mac build a public-ready desktop artifact, prove it, and promote it onto the live `chummer.run` downloads shelf through the authenticated HTTP upload endpoint instead of manual server file copies.

Use the signed-in path by opening `https://chummer.run/downloads/release-upload` in the browser first, copying the generated `Command` block, and pasting that exact command into the Mac shell. The signed-in handoff mints a short-lived upload code, embeds it in the generated bootstrap command, pins the hosted bootstrap digest, and keeps the published command synchronized with the current hosted bootstrap.

## One command

Open `https://chummer.run/downloads/release-upload`, copy the generated `Command` block, and paste that exact command into the Mac release shell.

Do not run `https://chummer.run/downloads/release-upload/bootstrap.sh` directly for live promotion; it can pass SHA-256 verification and still stop at upload time because a raw public script has no upload credential.
Do not paste `curl -fsSL https://chummer.run/downloads/release-upload/bootstrap.command | bash` unless you explicitly attach `?ticket=...` or `?apiToken=...`; terminal curl does not inherit the browser sign-in session.

Repo-local checkout fallback:

```bash
repo_root="$(git rev-parse --show-toplevel)"
bash "$repo_root/chummer6-hub/scripts/run-mac-release-bootstrap.sh"
```

Do not hardcode `/docker/chummercomplete/.../bootstrap.sh` on the Mac host. That path is for provisioned Linux control environments, not a normal Mac release workstation.

The bootstrap is the public deep link. It now:

1. clones or updates the required repos
2. builds the mac desktop head
3. packages a `.dmg`
4. codesigns, notarizes, staples, and validates it
5. runs startup smoke
6. generates both public release manifests
7. writes `release-evidence/public-promotion.json`
8. uploads the full bundle to `https://chummer.run/api/internal/releases/bundles`
9. verifies the promoted live shelf and prints the resulting `/downloads/install/{artifactId}` handoff URL
10. prints signed-in claim codes when it was launched from the signed-in release-upload handoff

By default the bootstrap checks out the latest pushed `main` branch for the GitHub-backed Chummer repos it builds from. Override the `CHUMMER_*_REF` variables only when you intentionally want a different branch.

## Minimum environment variables

```bash
export CHUMMER_APP_SIGN_IDENTITY="Developer ID Application: YOUR ORG (TEAMID)"
export CHUMMER_NOTARY_PROFILE="chummer-notary"
```

Optional overrides:

```bash
export CHUMMER_RELEASE_UPLOAD_URL="https://chummer.run/api/internal/releases/bundles"
export CHUMMER_PORTAL_DOWNLOADS_VERIFY_URL="https://chummer.run/downloads/RELEASE_CHANNEL.generated.json"
export CHUMMER_RELEASE_VERIFY_REQUIRE_COMPATIBILITY_PROJECTION="0"
export CHUMMER_RELEASE_CHANNEL="preview"
export CHUMMER_RELEASE_APP="avalonia"
export CHUMMER_RELEASE_RID="osx-arm64"
export CHUMMER_UI_REF="main"
export CHUMMER_CORE_REF="main"
export CHUMMER_HUB_REF="main"
export CHUMMER_UI_KIT_REF="main"
export CHUMMER_HUB_REGISTRY_REF="main"
export CHUMMER_LEGACY_REF="Docker"
export CHUMMER_MAC_RELEASE_MIN_FREE_GIB="20"
export CHUMMER_MAC_RELEASE_PACKAGING_MIN_FREE_GIB="8"
export CHUMMER_MAC_RELEASE_TMPDIR="/Volumes/FastScratch/chummer-release-tmp"
export CHUMMER_DESKTOP_INSTALLER_TMPDIR="/Volumes/FastScratch/chummer-release-tmp/desktop-installer"
```

Disk-space posture:

1. The bootstrap keeps a conservative pre-build free-space gate through `CHUMMER_MAC_RELEASE_MIN_FREE_GIB`.
2. The packaging/notarization phase uses `CHUMMER_MAC_RELEASE_PACKAGING_MIN_FREE_GIB` and will prune repo-local `bin/` and `obj/` directories once before failing.
3. If the Mac work root is tight, point `CHUMMER_MAC_RELEASE_TMPDIR` and `CHUMMER_DESKTOP_INSTALLER_TMPDIR` at a roomier volume so `hdiutil` and DMG repack work stop competing with the checkout root.

Preflight-capacity aborts:

1. If the run stops before clone/build/package because the work root or temporary packaging root is below the hard free-space floor, that is classified as `preflight_capacity_abort`.
2. The bootstrap writes `release-evidence/preflight-capacity-abort.json` inside the per-run work root.
3. That receipt is an audit artifact only. It does **not** count as clone, packaging, startup-smoke, manifest, or upload evidence, and it must not be used toward macOS promotion.
4. The hard minimum is still `20 GiB` by default, but the practical rerun target should be `25-30 GiB` free so DMG repack and notarization work have headroom instead of barely clearing preflight.

Cleanup after every run:

1. After a successful upload or a failed run, delete the local temporary release artifacts again so the Mac SSD does not fill up.
2. At minimum, clean the per-run work root under `$HOME/work/chummer-release/run-...` plus any custom `CHUMMER_MAC_RELEASE_TMPDIR` and `CHUMMER_DESKTOP_INSTALLER_TMPDIR` trees you pointed at another volume.
3. Keep those artifacts only when you are actively debugging a packaging, notarization, or upload failure.

## Promotion gate

The upload endpoint may merge platform slices independently, but it only makes an installer public when the bundle includes:

1. the artifact file under `files/`
2. `releases.json`
3. `RELEASE_CHANNEL.generated.json`
4. startup-smoke receipts matching the uploaded digest
5. `release-evidence/public-promotion.json`

For macOS that evidence must prove:

1. `promotionStatus=pass`
2. `startupSmokeStatus=pass`
3. `signingStatus=pass`
4. `notarizationStatus=pass`

If the run only produced `release-evidence/preflight-capacity-abort.json`, none of the promotion-gate evidence above exists yet. Treat that run as a capacity abort, not a packaging attempt.

For Windows promotion the same endpoint is valid, but the evidence must prove startup smoke and signing before the public shelf can expose the installer.

## Public result

Once the upload succeeds:

1. `https://chummer.run/downloads/RELEASE_CHANNEL.generated.json` contains the authoritative promoted artifact set
2. `https://chummer.run/downloads/releases.json` stays coherent as the installer-oriented compatibility view
3. the direct file URL resolves under `/downloads/files/...`
4. the signed-in claim-code handoff is live at `/downloads/install/{artifactId}`
5. the desktop app also ships `Samples/Legacy/Soma-Career.chum5`, bundled from the legacy Chummer5 test fixtures for a real completed-runner import check

The bootstrap now treats the canonical `RELEASE_CHANNEL.generated.json` projection as the success gate.
If the compatibility `releases.json` shelf lags briefly after publish, the run logs a warning instead of failing.
Set `CHUMMER_RELEASE_VERIFY_REQUIRE_COMPATIBILITY_PROJECTION=1` only when you explicitly want compatibility drift to fail the run.

## Final public-stable closeout

If macOS is the last missing required desktop tuple, do not hand-edit the published registry shelf.

From a Mac host that just minted a fresh passing `public_stable` startup-smoke receipt for
`chummer-avalonia-osx-arm64-installer.dmg`, run:

```bash
cd /docker/chummercomplete
chmod +x chummer6-hub-registry/scripts/release/refresh_public_desktop_truth_after_mac_smoke.sh
chummer6-hub-registry/scripts/release/refresh_public_desktop_truth_after_mac_smoke.sh
```

That wrapper will:

1. refuse to continue unless the mac startup-smoke receipt is passing, fresh, `public_stable`, and digest-bound to the current `.dmg`
2. rerun the canonical desktop truth refresh
3. keep pruning any installer bytes that do not make it into manifest truth
4. resync the public guide/docs after the shelf changes

The current Linux control session can only close Windows and Linux honestly.
macOS promotion still requires a real fresh `public_stable` receipt from a Mac host.
