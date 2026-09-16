"""Capacity-only tests; sparse placeholders prove metadata limits, not Git validity."""
import json
from pathlib import Path

import pytest

from scripts import android_preview12_external_rebuilder as fleet
from test_android_preview12_offline_source_bundles import bundles, complete_bundle


def resize_metadata(case, row, size):
    # No huge payload allocation or hashing: _offline_manifest only admits
    # metadata. Actual snapshot/digest/Git checks remain separate mandatory gates.
    with Path(row['path']).open('r+b') as output:
        output.truncate(size)
    row['size_bytes'] = size
    case.manifest.write_text(json.dumps(case.rows))


@pytest.mark.parametrize('size', [1024**3 + 1, 5 * 1024**3])
def test_product_bundle_metadata_accepts_bounded_complete_history_size(bundles, size):
    row = bundles.rows['chummer6-hub']
    resize_metadata(bundles, row, size)
    parsed = fleet._offline_manifest(bundles.manifest, bundles.workspace)
    assert parsed['chummer6-hub'][1].st_size == size
    assert fleet.OFFLINE_BUNDLE_BYTES == 5 * 1024**3


def test_product_bundle_metadata_still_rejects_one_byte_over_limit(bundles):
    resize_metadata(bundles, bundles.rows['chummer6-hub'], fleet.OFFLINE_BUNDLE_BYTES + 1)
    with pytest.raises(fleet.RebuilderError, match='manifest row is not exact'):
        fleet._offline_manifest(bundles.manifest, bundles.workspace)


def test_product_total_accepts_exact_ceiling_and_rejects_next_byte(bundles):
    rows = list(bundles.rows.values())
    remainder = sum(row['size_bytes'] for row in rows[2:])
    resize_metadata(bundles, rows[0], fleet.OFFLINE_BUNDLE_BYTES)
    resize_metadata(bundles, rows[1], fleet.OFFLINE_TOTAL_BUNDLE_BYTES - fleet.OFFLINE_BUNDLE_BYTES - remainder)
    parsed = fleet._offline_manifest(bundles.manifest, bundles.workspace)
    assert sum(row[1].st_size for row in parsed.values()) == 6 * 1024**3
    resize_metadata(bundles, rows[1], rows[1]['size_bytes'] + 1)
    with pytest.raises(fleet.RebuilderError, match='inventory exceeds its byte limit'):
        fleet._offline_manifest(bundles.manifest, bundles.workspace)


def test_larger_transport_does_not_change_oracle_file_limit(tmp_path):
    root = tmp_path / 'oracle'
    root.mkdir(mode=0o700)
    target = root / 'object'
    with target.open('wb') as output:
        output.truncate(512 * 1024**2)
    target.chmod(0o600)
    assert fleet._oracle_inventory(root)['object'].st_size == 512 * 1024**2
    with target.open('r+b') as output:
        output.truncate(512 * 1024**2 + 1)
    with pytest.raises(fleet.RebuilderError, match='oracle bytes exceed transport limits'):
        fleet._oracle_inventory(root)
    assert fleet.OFFLINE_ORACLE_FILE_BYTES == 512 * 1024**2


def test_oracle_aggregate_accepts_exact_three_gib_and_rejects_next_byte(tmp_path):
    root = tmp_path / 'oracle'
    root.mkdir(mode=0o700)
    for index in range(6):
        with (root / str(index)).open('wb') as output:
            output.truncate(512 * 1024**2)
        (root / str(index)).chmod(0o600)
    inventory = fleet._oracle_inventory(root)
    assert len(inventory) == 6
    assert sum(info.st_size for info in inventory.values()) == 3 * 1024**3
    (root / 'one-byte-too-many').write_bytes(b'x')
    with pytest.raises(fleet.RebuilderError, match='oracle bytes exceed transport limits'):
        fleet._oracle_inventory(root)
    assert fleet.OFFLINE_ORACLE_TOTAL_BYTES == 3 * 1024**3
    assert fleet.TEST_ORACLE_FILE_COUNT == 250_000


def test_oracle_metadata_accepts_measured_full_history_size_without_payload_allocation(tmp_path):
    # Read-only measurement of the pinned fe4355 oracle on 2026-09-16.
    # These sparse placeholders model only its component byte totals: they are
    # deliberately not Git objects and cannot establish oracle admission.
    root = tmp_path / 'oracle'
    root.mkdir(mode=0o700)
    component_sizes = {
        'checkout': 1_240_994_870,
        'packs-index-rev': 1_345_350_073,
        'git-auxiliary': 3_005_080,
    }
    paths = []
    for component, size in component_sizes.items():
        directory = root / component
        directory.mkdir(mode=0o700)
        index = 0
        while size:
            chunk = min(size, 512 * 1024**2)
            path = directory / str(index)
            with path.open('wb') as output:
                output.truncate(chunk)
            path.chmod(0o600)
            paths.append(path)
            size -= chunk
            index += 1
    inventory = fleet._oracle_inventory(root)
    total = sum(inventory[path.relative_to(root).as_posix()].st_size for path in paths)
    assert total == sum(component_sizes.values()) == 2_589_350_023
    assert 2 * 1024**3 < total < fleet.OFFLINE_ORACLE_TOTAL_BYTES
    assert sum(path.stat().st_blocks * 512 for path in paths) < 1024**2


def test_streamed_snapshot_keeps_one_mib_reads_and_authenticates_bytes(tmp_path, monkeypatch):
    import hashlib
    import io
    import os

    # Exercise multiple full reads; a tiny Git fixture could not detect a
    # regression that requests the entire input in one oversized read.
    # This is a stream-helper test, not a valid Git-bundle admission claim.
    path = tmp_path / 'stream-input'
    path.write_bytes(b'x' * (3 * 1024**2 + 1))
    metadata = fleet._offline_input_identity(path, fleet.OFFLINE_BUNDLE_BYTES)
    original_read = os.read
    requested = []
    def observe_read(descriptor, count):
        requested.append(count)
        return original_read(descriptor, count)
    monkeypatch.setattr(os, 'read', observe_read)
    output = io.BytesIO()
    digest = fleet._copy_offline_input(path, metadata, output, fleet.OFFLINE_BUNDLE_BYTES)
    assert requested.count(1024**2) >= 3
    assert max(requested) <= 1024**2
    assert digest == hashlib.sha256(output.getvalue()).hexdigest()
    assert output.getvalue() == path.read_bytes()
