#!/usr/bin/env bash
set -euo pipefail

export RELEASE_CHANNEL_PATH="${EXTERNAL_PROOF_RELEASE_CHANNEL_PATH:-/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json}"

cd /docker/chummercomplete/chummer6-ui

test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe
python3 -c 'import hashlib, pathlib, sys
p = pathlib.Path("/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe")
expected = "cb3493c1113c23b5e496dfe8a1e6de9afc43c802d7da865adc5255497341e5c4"
digest = hashlib.sha256(p.read_bytes()).hexdigest().lower()
if digest != expected:
    raise SystemExit("installer-contract-mismatch:%s:digest=%s:expected=%s" % (p, digest, expected))'

test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json
python3 -c 'import json, pathlib
p = pathlib.Path("/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json")
contract = {"head_id":"avalonia","host_class_contains":"windows","platform":"windows","ready_checkpoint":"pre_ui_event_loop","rid":"win-x64","status_any_of":["pass","passed","ready"]}
payload = json.loads(p.read_text(encoding="utf-8"))
if not isinstance(payload, dict):
    payload = {}
status = str(payload.get("status") or "").strip().lower()
expected_statuses = [str(token).strip().lower() for token in (contract.get("status_any_of") or []) if str(token).strip()]
head_id = str(payload.get("headId") or "").strip().lower()
platform = str(payload.get("platform") or "").strip().lower()
rid = str(payload.get("rid") or "").strip().lower()
ready_checkpoint = str(payload.get("readyCheckpoint") or "").strip().lower()
host_class = str(payload.get("hostClass") or "").strip().lower()
expected_head = str(contract.get("head_id") or "").strip().lower()
expected_platform = str(contract.get("platform") or "").strip().lower()
expected_rid = str(contract.get("rid") or "").strip().lower()
expected_ready = str(contract.get("ready_checkpoint") or "").strip().lower()
expected_host_contains = str(contract.get("host_class_contains") or "").strip().lower()
if not ((not expected_statuses or status in expected_statuses) and (not expected_head or head_id == expected_head) and (not expected_platform or platform == expected_platform) and (not expected_rid or rid == expected_rid) and (not expected_ready or ready_checkpoint == expected_ready) and (not expected_host_contains or expected_host_contains in host_class)):
    raise SystemExit(f"receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}")'
python3 -c 'import json, os, pathlib
p = pathlib.Path(os.environ["RELEASE_CHANNEL_PATH"])
payload = json.loads(p.read_text(encoding="utf-8"))
tuple_id = "avalonia:win-x64:windows"
expected_artifact = "avalonia-win-x64-installer"
expected_route = "/downloads/install/avalonia-win-x64-installer"
coverage = payload.get("desktopTupleCoverage") if isinstance(payload, dict) else {}
if not isinstance(coverage, dict):
    coverage = {}
rows = coverage.get("externalProofRequests") if isinstance(coverage, dict) else []
if not isinstance(rows, list):
    rows = []
row = next((item for item in rows if isinstance(item, dict) and str(item.get("tupleId") or item.get("tuple_id") or "").strip() == tuple_id), None)
if row is None:
    raise SystemExit(f"release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row")
artifact = str(row.get("expectedArtifactId") or row.get("expected_artifact_id") or "").strip()
route = str(row.get("expectedPublicInstallRoute") or row.get("expected_public_install_route") or "").strip()
if not ((not expected_artifact or artifact == expected_artifact) and (not expected_route or route == expected_route)):
    raise SystemExit(f"release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}")'
