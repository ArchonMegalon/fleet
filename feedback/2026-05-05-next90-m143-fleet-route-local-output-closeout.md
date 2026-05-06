# NEXT90 M143 Fleet route-local output closeout

Closed the Fleet-owned M143 gate by binding print/export/exchange and SR6 supplement/house-rule family rows to direct route-local output receipts, screenshot review, and current rule-environment proof surfaces.

Audit repairs included:
- `docs/chummer5a-oracle/veteran_workflow_packs.yaml` now carries `route_specific_compare_packs` for the print/export/exchange and SR6 supplement or house-rule families, so the oracle pack names exact route proofs and artifact markers instead of relying on broad family prose.
- canonical queue and registry closeout metadata now blocks reopened or stale package rows
- regenerated gate artifacts now match the current live parity, UI, and core output proof inputs and publish a route-by-route compare summary in the markdown proof packet
- unit coverage now proves the gate fails when the package is reopened without complete closeout metadata
