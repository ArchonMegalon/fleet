## External audit: Windows proof runtime and flagship familiarity blocker

Recorded: 2026-04-12T21:24:17Z

This is a blocking product audit result, not a cosmetic note.

Observed from live `chummer.run` Windows proof routes:

- `/downloads/install/avalonia-win-x64-installer`
- `/downloads/install/blazor-desktop-win-x64-installer`
- `/downloads/proof/windows/chummer-avalonia-win-x64-installer.exe`
- `/downloads/proof/windows/chummer-blazor-desktop-win-x64-installer.exe`

Findings:

- both Windows binaries are still `proof-only`
- both Windows binaries are unsigned (`Get-AuthenticodeSignature -> NotSigned`)
- the Avalonia Windows installer route has already regressed once on payload integrity and remains unfit to represent release readiness
- external runtime check says Avalonia launcher exits promptly with code `1`
- external runtime check says Blazor installer launches into a black window
- user feedback says Avalonia still looks nowhere near Chummer5a

Required interpretation:

- this is not `flagship_ready`
- this is not `veteran_ready`
- this is not `primary_route_ready`
- this is not `dense_workbench_ready`

Required action:

1. Treat both Windows proof installers as blocking evidence against flagship readiness until Windows startup-smoke plus real human runtime validation are green.
2. Do not let proof-route availability count as desktop closeout.
3. Route the Blazor black-window defect as a real runtime bug, not a proof-only footnote.
4. Route the Avalonia familiarity complaint as a flagship UI failure against the Chummer5a familiarity bridge and dense-workbench budget, not as additive polish.
5. Make the product-governor dashboard surface this exact state even when structural milestones are otherwise green.

Acceptance to clear this packet:

- Windows installer starts successfully for both heads
- no black-window launch on Blazor Desktop
- Avalonia shell passes a real Chummer5a familiarity review
- Windows route is signed/promoted if it is presented as install-ready
- proof-only binaries stop being treated as release-adjacent success
