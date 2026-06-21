# Dispatch Pipeline

```text
WorldTickReceipt
-> PlayerSafeNewsProjection
-> DispatchFactPacket
-> DispatchDraft
-> DispatchGateReceipt
-> Dispatch approval
-> BlackLedgerDispatch
-> Public route
-> Email digest candidate
-> Delivery receipt
```

Failure behavior:

- if draft fails: suppress and keep stats without story
- if privacy fails: do not publish and do not email
- if email fails: keep public dispatch if already approved, record failed delivery receipt
