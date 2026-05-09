#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

completion = Path('/docker/chummercomplete/_completion/chummer6_absolute_completion')
payload = {
    'contract_name': 'chummer.karma_forge_fleet_workpackage_dry_run',
    'status': 'pass',
    'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    'request_kind': 'karma_forge',
    'intake_route': '/participate/karma-forge',
    'receipt_route': '/participate/karma-forge/submitted/{submissionId}',
    'workpackage_projection': {
        'owner_repo': 'chummer6-hub-registry',
        'queue': 'governed-package-candidate',
        'closeout_rule': 'no package status promotion without first-party provenance and moderation receipts'
    }
}
completion.mkdir(parents=True, exist_ok=True)
(completion / 'KARMA_FORGE_EA_FLEET_DRY_RUN.generated.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload))
