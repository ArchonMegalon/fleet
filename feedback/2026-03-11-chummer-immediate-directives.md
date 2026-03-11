# Chummer Immediate Directives

**Effective:** March 11, 2026

Ja. Aber die Gruppe sollte jetzt **keine einzelnen Wow-Features bauen**, sondern die **gemeinsamen Plattform-Fundamente**, auf denen `Karma Forge`, `NEXUS-PAN`, `ALICE` und `JACKPOINT` spaeter sauber aufsetzen.

Die unmittelbare Prioritaet bleibt:
- contract canon
- repo purification
- die naechste saubere split-welle

Zukunftsfaehige Dokumente duerfen existieren, aber sie muessen:

```yaml
status: horizon
queue_eligible: false
dispatchable: false
```

Fleet darf daraus keine `QUEUE.generated.yaml` und keine coding slices ableiten.

## Die neun Direktiven

1. Future-Visionen aus der aktiven Queue einfrieren
- kein Karma Forge
- kein NEXUS-PAN
- kein ALICE
- kein JACKPOINT
- kein Marketplace/Voting als aktive dispatchable Arbeit

2. `chummer6-design` boringly authoritative machen
- front door
- milestone truth
- review templates
- sync manifest
- split ADRs
- repo graph auf Fleet lockstep truth ziehen

3. `chummer-6` als human-only guide repo anfuehren
- downstream only
- signoff_only lifecycle
- keine queue ownership
- keine contract ownership
- keine canonical design ownership

4. Contract reset vor allem anderen abschliessen
- `Chummer.Engine.Contracts` vs `Chummer.Contracts` bereinigen
- nur eine kanonische engine contract familie
- nur eine kanonische play contract familie
- keine copied contracts
- keine cross-repo project refs

5. `chummer6-mobile` als naechste echte Produktgrenze fertigstellen
- placeholder browser clients ersetzen
- local-first event log / runtime cache / offline queue / sync bauen
- player vs GM capability gating haerten
- installable PWA fertigstellen

6. Nur drei future-proof seam seeds einfuehren
- Runtime Stack + Fingerprint DTO
- Session Authority + Event Envelope
- Explain / Provenance Receipt

7. Repo purification per deletion erzwingen
- split ist nicht fertig, solange der alte owner die surface noch advertisiert
- split ist nicht fertig, solange der alte owner die surface noch shippt
- split ist nicht fertig, solange die alte ownership noch im repo lebt
- `stale_preview` bleibt debt, nicht completion

8. Boundary-Repos schmal und package-real machen
- `chummer6-ui-kit`: package first, duplicate deletion in consumers
- `chummer6-hub-registry`: consumer migration, old registry ownership loeschen
- `chummer6-media-factory`: render-only halten, keine feature inflation

9. Fleet truthfulness rules anziehen
- horizon docs sind non-dispatchable
- purification scoreboard je repo
- `stale_preview` immer als debt zeigen
- shared lockstep blockers als runtime data zeigen

## Der eine Satz fuer das Team

**Right now, do not build the future features; build the truth layer that will make future features cheap.**

Das heisst:
- design kanonisch machen
- human guide repo anfuehren
- contract reset abschliessen
- play split fertigstellen
- runtime/session/explain seams seeden
- UI-kit/registry/media package-real machen
- purification per deletion erzwingen
