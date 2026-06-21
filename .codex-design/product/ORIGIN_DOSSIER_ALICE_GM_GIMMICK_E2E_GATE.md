# Origin Dossier, ALICE Follow-Up, and GM Gimmick E2E Gate

**Product:** Chummer6 desktop
**Surface:** Native ALICE workbench
**Status:** Required flagship acceptance gate
**Type:** Deterministic desktop E2E

## Why this test exists

The origin dossier lane is only real if four things work together in one journey:

1. a player can generate an origin dossier from a blank or active runner state
2. origin canon can be generated from pure build context alone
3. origin canon can also be steered by a bounded GM gimmick without becoming mechanical truth
4. ALICE can use that approved canon later as bounded follow-up context

Source-shape tests are not enough here.
This needs one mouse-first journey that proves the workflow as a product.

## What this test must prove

The test passes only if all of the following are true:

* Origin Dossier can be opened directly from desktop ALICE
* a draft can be generated without crashing on blank-state or active-runner context
* a pure build-context origin draft works
* the visible origin draft passes the humanizer loop without changing approved facts
* a GM-steered origin draft works with both allowances and hard requirements
* canon approval creates a real bundle root
* dossier assets can be produced in sequence
* ALICE later references the approved origin canon during follow-up
* GM allowances, requirements, or gimmicks appear in ALICE context and output
* GM allowances and hard requirements do not auto-apply mechanics
* the whole flow works with mouse-only interaction

## Recommended scenario

Use one deterministic scenario and keep it fixed.

### Scenario ID

`sr4_origin_dossier_troll_decker_gm_gimmick`

### Starting posture

* ruleset: `SR4`
* build state: blank desktop or new-character state with no saved workspace requirement
* ALICE mode: `Build Help` first, then `Origin Dossier`
* runner concept: `troll decker`

### GM gimmick

Use one bounded gimmick that is flavorful but mechanically explicit:

> GM steer: one clinic contact quietly fronted restricted starter ware and one over-availability deck part. The runner must also have an illegal-drug addiction hook, must be magically active, and must keep Logic or Intuition at 2 or higher. ALICE must explain the consequences and keep the final build proposal non-applied until the player explicitly edits the sheet.

This is a good gimmick because it tests:

* extra ware
* extra availability
* required quality/story pressure
* required awakened posture
* minimum mental-attribute constraints
* advisory-only posture
* later ALICE explanation continuity

## Test flow

### Phase 1: Open ALICE from desktop

1. Launch desktop client.
2. Open `ALICE`.
3. Verify the ALICE window opens natively.
4. Verify mode shortcuts are visible:
   * `Build Help`
   * `Rules Coach`
   * `Origin Dossier`

### Phase 2: Establish blank-state build context

1. Stay in `Build Help`.
2. Verify the visible `Draft from scratch` affordance is present.
3. Click `Draft from scratch`, or ask a starter question with mouse-only input:
   * `Build me an SR4 troll decker from scratch.`
4. Verify ALICE does not respond with:
   * `open a workspace first`
   * `no preview-backed build candidate`
   * any equivalent dead-end error
5. Verify ALICE returns a complete from-scratch draft posture:
   * metatype
   * build method
   * attribute emphasis
   * skill emphasis
   * gear / ware posture

### Phase 3: Generate pure origin dossier canon

1. Switch to `Origin Dossier`.
2. Ask:
   * `Give this runner a grounded origin that explains the metatype and hacking focus.`
3. Verify a real origin draft appears.
4. Verify the humanizer pass completes before approval.
5. Verify the visible text keeps the same canon facts but removes obvious generated-text tells.
6. Click `Approve canon`.
7. Verify a bundle root is created.

### Phase 4: Follow-up from pure canon

1. Switch back to `Build Help`.
2. Ask:
   * `Using the approved origin, what should I add next and why?`
3. Verify ALICE follow-up references:
   * approved origin canon or origin summary
   * the runner’s troll/decker identity
4. Verify ALICE still keeps bounded truth posture:
   * explanation only
   * no hidden sheet mutation

### Phase 5: Generate GM-steered origin dossier canon

1. In the GM allowances and requirements box, enter the fixed gimmick text.
2. Verify ALICE context updates visibly.
3. Switch to `Origin Dossier`.
4. Ask:
   * `Regenerate this origin with the clinic favor, addiction hook, magical-active requirement, and Logic or Intuition minimum as real story influences, but keep mechanics advisory only.`
5. Verify the new origin draft visibly references:
   * the clinic contact or clinic favor
   * restricted ware / deck-part pressure as story context
   * the illegal-drug addiction hook
   * the required magical-active posture
   * the minimum Logic or Intuition requirement
6. Verify the humanizer pass completes and preserves every GM steer.
7. Verify the visible text does not expose provider, prompt, source-packet, or "generated by AI" phrasing.
8. Click `Approve canon`.
9. Verify the new approved canon remains a narrative bundle, not a mechanical auto-apply.

### Phase 6: Generate dossier assets

1. Click `Render dossier PDF`.
2. Click `Generate portraits`.
3. Click `Generate scenes`.
4. Click `Generate default voice packet`.
5. Click `Generate alternate voice packet`.
6. Click `Prepare media-factory request`.
7. Click `Generate dossier video`.

The test does not need real external provider success for every lane.
It does need deterministic local artifact creation and packet generation.

### Phase 7: Verify artifact outputs

Verify all of the following exist:

* canon markdown
* canon json
* dossier pdf
* portrait set json
* selected portrait path
* scene set json
* selected scene path
* default narration packet
* alternate narration packet
* media-factory narration request
* video storyboard
* vidBoard packet
* video poster

### Phase 8: Follow-up through ALICE after GM-steered canon

1. Switch back to `Build Help`.
2. Ask:
   * `Using the approved origin, what should I add next and why?`
3. Verify ALICE follow-up references:
   * approved origin canon or origin summary
   * the runner’s troll/decker identity
   * the GM clinic gimmick as advisory context
   * the illegal-drug addiction, magical-active, and mental-attribute requirements as advisory context
4. Verify ALICE still keeps bounded truth posture:
   * explanation only
   * no hidden sheet mutation

### Phase 9: Rules-coach continuity check

1. Switch to `Rules Coach`.
2. Ask:
   * `Rules-wise, what do the clinic favor, addiction hook, magical-active requirement, and Logic or Intuition minimum actually allow here, and what is still risky?`
3. Verify ALICE explains:
   * legality posture
   * availability posture
   * ware posture
   * quality or addiction posture
   * awakened or magical-active posture
   * minimum mental-attribute posture
   * what remains manual review

## Assertions

### Pass assertions

The test must assert all of these:

* ALICE window opened
* mode switch works
* `Draft from scratch` button is visible and usable from blank-state Build Help
* blank-state build help returns a full build draft
* no dead-end blank-state error text appears
* pure origin draft generated from non-GM-steered context
* humanizer loop completed for the pure origin draft
* humanizer loop preserved the pure origin fact set
* pure canon follow-up references approved origin
* GM allowances and hard requirements are visible in later context
* GM-steered origin draft generated
* humanizer loop completed for the GM-steered origin draft
* humanizer loop preserved clinic, addiction, magical-active, and mental-attribute steer facts
* both canon approvals succeed
* bundle directory created
* required bundle artifacts exist
* later ALICE answer references approved origin
* later ALICE answer references GM gimmick
* later ALICE answer references the illegal-drug addiction, magical-active, and mental-attribute requirements
* no auto-apply or sheet mutation language is shown

### Fail assertions

The test must fail if any of these happen:

* ALICE requires a workspace for the blank-state build draft
* pure origin draft cannot be generated from the test state
* GM-steered origin draft cannot be generated from the test state
* humanizer output drops or mutates any approved canon or GM steer fact
* visible origin text exposes provider, prompt, source-packet, or decorative "generated by AI" phrasing
* canon approval does not create bundle root
* any required artifact is missing
* pure follow-up ignores approved origin
* GM-steered follow-up ignores approved origin
* GM-steered follow-up ignores GM gimmick
* ALICE claims to have changed mechanics automatically
* the path requires keyboard-only affordances the mouse-first user cannot reach

## Harness shape

This should be implemented as a real Avalonia headless UI test using the same interaction style as
the existing flagship gate harness.

Recommended host:

* `Chummer.Tests/Presentation/AvaloniaFlagshipUiGateTests.cs`

Implemented runtime-backed gate:

* `Alice_supports_blank_state_build_help_and_gm_steered_origin_dossier_flow`

Follow-on gate still worth adding:

* `Alice_origin_dossier_bundle_supports_pure_and_gm_steered_canon_without_mutating_build_truth`

## Suggested control contract

The test should interact only through named controls, not text search where avoidable.

Expected controls:

* `ClassicToolStripAutoAliceButton` or equivalent shell ALICE entry
* `AliceConversationModeCombo`
* `AliceDraftFromScratchButton`
* `AliceQuestionTextBox`
* `AliceGmAllowanceTextBox`
* `AliceAskButton`
* `AliceOriginApproveCanonButton`
* `AliceOriginRenderDossierPdfButton`
* `AliceOriginGeneratePortraitSetButton`
* `AliceOriginGenerateSceneSetButton`
* `AliceOriginGenerateAudiobookPacketButton`
* `AliceOriginGenerateAlternateAudiobookPacketButton`
* `AliceOriginGenerateMediaFactoryNarrationRequestButton`
* `AliceOriginGenerateDossierVideoButton`

## Fixture recommendations

The best deterministic version uses a fake or fixture-backed client with:

* fixed SR4 ruleset id
* zero required remote services
* stable build path candidate or deliberate blank-state path
* temp bundle directory override
* stable timestamps where needed for file checks

If the current implementation uses temp paths and wall-clock timestamps, the test should capture the
newly created bundle root during execution instead of hardcoding a path.

## Screenshot proof

This test should emit screenshots for:

1. blank-state ALICE build help
2. `Draft from scratch` affordance visible
3. pure origin draft generated
4. pure canon follow-up in build help
5. GM-steered origin draft generated with hard requirements visible
6. approved bundle actions visible
7. rules-coach explanation using GM gimmick and hard requirements

These screenshots are part of the exit gate because this is both a behavior and presentation flow.

## Gold bar

This journey is required for Gold because it proves:

* ALICE is not just a shell
* origin dossier is not just hidden code
* origin can stand on its own from pure build context
* GM advisory input and hard requirements can steer origin canon without becoming rules truth
* follow-up continuity works in both variants
* narrative and mechanics boundaries stay intact
