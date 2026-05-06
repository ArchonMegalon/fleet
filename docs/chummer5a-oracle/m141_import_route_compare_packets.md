# M141 route-local compare packets

This EA-owned packet compiles the direct screenshot and compare evidence for translator, XML amendment, Hero Lab, and adjacent import-oracle parity without inventing a second proof plane.

- milestone: `141`
- package: `next90-m141-ea-compile-route-local-screenshot-packs-and-compare-packets-for-translator-x`
- work task: `141.4`
- generated_at: `2026-05-06T00:04:56Z`
- live desktop readiness: `warning`

## Route-local screenshot packs

### Translator route

- parity row: `source:translator_route`
- compare artifacts: `menu:translator`, `source:translator_route`
- screenshots: `38-translator-dialog-light.png`
- runtime tokens: `translator_xml_custom_data`, `ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture`
- core receipt tokens: `translatorDeterministicReceipt`
- parity verdict: visual `yes`, behavioral `yes`
- reason: Catalog, presenter, dialog-factory, and dual-head acceptance proofs directly cover the Translator route.

### XML amendment editor route

- parity row: `source:xml_amendment_editor_route`
- compare artifacts: `menu:xml_editor`, `source:xml_amendment_editor_route`
- screenshots: `39-xml-editor-dialog-light.png`
- runtime tokens: `translator_xml_custom_data`, `ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture`
- core receipt tokens: `customDataXmlBridgeDeterministicReceipt`
- parity verdict: visual `yes`, behavioral `yes`
- reason: Catalog, presenter, dialog-factory, and dual-head acceptance proofs directly cover the XML Amendment Editor route.

### Hero Lab importer route

- parity row: `source:hero_lab_importer_route`
- compare artifacts: `menu:hero_lab_importer`, `source:hero_lab_importer_route`
- screenshots: `40-hero-lab-importer-dialog-light.png`
- runtime tokens: `hero_lab_import_oracle`, `ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture`
- core receipt tokens: `importOracleDeterministicReceipt`
- parity verdict: visual `yes`, behavioral `yes`
- reason: Catalog, dialog-factory, and dialog-coordinator proofs directly cover the Hero Lab importer route.

## Family compare packets

### Custom data/XML and translator bridge family

- parity row: `family:custom_data_xml_and_translator_bridge`
- compare artifacts: `menu:translator`, `menu:xml_editor`
- screenshots: `38-translator-dialog-light.png`, `39-xml-editor-dialog-light.png`
- runtime tokens: `translator_xml_custom_data`, `ExecuteCommandAsync_translator_opens_dialog_with_master_index_lane_posture`, `ExecuteCommandAsync_xml_editor_opens_dialog_with_xml_bridge_posture`
- core receipt tokens: `customDataXmlBridgeDeterministicReceipt`, `translatorDeterministicReceipt`, `family:custom_data_xml_and_translator_bridge`
- parity verdict: visual `yes`, behavioral `yes`
- reason: All declared compare artifacts for this Chummer5A family are directly backed by current parity proof: ['menu:translator', 'menu:xml_editor'].

### Legacy and adjacent import-oracle family

- parity row: `family:legacy_and_adjacent_import_oracles`
- compare artifacts: `menu:hero_lab_importer`, `workflow:import_oracle`
- screenshots: `40-hero-lab-importer-dialog-light.png`
- runtime tokens: `hero_lab_import_oracle`, `ExecuteCommandAsync_hero_lab_importer_opens_dialog_with_import_oracle_lane_posture`
- core receipt tokens: `importOracleDeterministicReceipt`, `family:legacy_and_adjacent_import_oracles`
- parity verdict: visual `yes`, behavioral `yes`
- reason: All declared compare artifacts for this Chummer5A family are directly backed by current parity proof: ['menu:hero_lab_importer', 'workflow:import_oracle'].

## Live readiness note

- desktop_client status: `warning`
- summary: Desktop flagship proof is still incomplete.
- missing keys: `none`
