# Story Authority And Governance

Final authority stack:

- fact authority: `WorldTickReceipt`, `PlayerSafeNewsProjection`, `PackagePressureReceipt`, `CloseoutReceipt`
- narrative policy authority: `BLACK_LEDGER_DISPATCH_SPEC.md`, `BLACK_LEDGER_STORY_AUTHORITY_POLICY.md`, `BLACK_LEDGER_PUBLIC_COPY_POLICY.md`
- draft authority: `executive-assistant` plus optional adapters
- publication authority: `BlackLedgerDispatch`
- orchestration authority: fleet proof gates

Rules:

1. Dispatches cannot create facts not present in source receipts.
2. External tools can create `DispatchDraft` only.
3. Published dispatches must be stored in Chummer-owned runtime state.
4. Every public dispatch needs a linked source receipt.
5. Public-safe gating is mandatory.
6. Human review can override AI draft output.
