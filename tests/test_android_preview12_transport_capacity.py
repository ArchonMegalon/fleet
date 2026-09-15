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


def test_larger_transport_does_not_change_oracle_aggregate_limit(tmp_path):
    root = tmp_path / 'oracle'
    root.mkdir(mode=0o700)
    for index in range(4):
        with (root / str(index)).open('wb') as output:
            output.truncate(512 * 1024**2)
        (root / str(index)).chmod(0o600)
    assert len(fleet._oracle_inventory(root)) == 4
    (root / 'one-byte-too-many').write_bytes(b'x')
    with pytest.raises(fleet.RebuilderError, match='oracle bytes exceed transport limits'):
        fleet._oracle_inventory(root)
    assert fleet.OFFLINE_ORACLE_TOTAL_BYTES == 2 * 1024**3


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
