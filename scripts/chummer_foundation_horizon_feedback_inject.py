#!/usr/bin/env python3
from pathlib import Path
from textwrap import dedent


DESIGN_FEEDBACK_ROOT = Path("/docker/chummercomplete/chummer-design/feedback")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")
FLEET_FEEDBACK_ROOT = Path("/docker/fleet/feedback")
FILENAME = "2026-03-11-chummer-foundation-horizon-guidance.md"
CONTENT = dedent(
    """
    # Chummer Foundation Horizon Guidance

    **Effective:** March 11, 2026

    Ja. Aber die Gruppe sollte jetzt **keine einzelnen Wow-Features bauen**, sondern die **gemeinsamen Plattform-Fundamente**, auf denen `Karma Forge`, `NEXUS-PAN`, `ALICE` und `JACKPOINT` spaeter sauber aufsetzen.

    Das passt zur aktuellen kanonischen Richtung: `chummer6-design` sagt ausdruecklich, dass der unmittelbare Fokus auf **Contract Canon, Repo Purification und der naechsten sauberen Split-Welle** liegt; gleichzeitig sind P0-P6 noch offen und die oeffentlichen Flaechen bleiben `stale_preview`.

    Die Fernziele sind **kein neues Parallelprogramm**. Sie passen bereits auf bestehende offene Milestones:
    - P1: Session-shell readiness
    - P2: Explain / provenance
    - P3: Generated artifact alignment
    - P5: UI-kit split
    - P6: Registry / media seams

    ## Entscheidung

    **Jetzt tun**
    - Future-capability foundation definieren
    - Ownership, Begriffe, Artefakttypen und spaetere Seams kanonisieren
    - Fleet gegen versehentliche Dispatch aus Zukunftstexten absichern

    **Jetzt nicht tun**
    - keine aktive Produktverpflichtung fuer Marketplace/Bazaar
    - keine Voting- oder Gamification-Programme
    - keine Auto-Promotion nach Popularitaet
    - keine per-user Branch/App-Varianten
    - keine C#-Plugin-Execution als V1-Basis

    Leitregel:

    > Karma Forge wird jetzt als zukuenftige Capability kanonisiert, aber noch nicht als aktive Produktverpflichtung oder dispatchable Arbeitsqueue aktiviert.

    ## Die Fundamente, die jetzt gelegt werden sollen

    1. Contract- und Naming-Reset
    - `Chummer.Engine.Contracts` gegen `Chummer.Contracts` bereinigen
    - neue Familien nur als future seeds reservieren
    - keine zweite aktive Contract-Welt neben `session_events_vnext`, `runtime_dtos_vnext`, `explain_trace_vnext`, `asset_review_vnext`

    2. Kanonisches Runtime-Stack-Modell
    - base runtime bundle
    - geordnete overlay / RulePack-Liste
    - runtime fingerprint
    - compatibility range
    - signature / lineage
    - optionale session binding

    3. Session Authority + Session Events
    - Session authority gehoert in play + session API seam, nicht in core
    - formales `Session Authority Profile`
    - append-only Session Events
    - deterministische Replay-/Merge-Semantik

    4. Explain / Provenance / Evidence Receipts
    - explain receipt
    - provenance receipt
    - grounding coverage
    - evidence source list
    - confidence policy
    - human summary vs machine evidence

    5. Artefaktmodell vor Produktfeatures
    - `Overlay Pack`
    - `Runtime Stack Profile`
    - `Scenario Pack`
    - `Session Authority Profile`
    - `Style Pack`
    - `Dossier Template`

    6. Preview / Apply / Rollback / Migration
    - preview receipt
    - apply receipt
    - migration preview
    - rollback receipt
    - conflict report

    7. Kleiner deterministischer Lab-Harness fuer `ALICE`
    - scenario DSL / lab harness
    - reproduzierbare seeds
    - definierte Gegnerprofile
    - erklaerbare failure paths
    - replaybare results

    8. `JACKPOINT` grounded halten
    - grounded digest model
    - source classification
    - provenance labels
    - approval states
    - render receipt vs narrative draft

    9. Nur UI-Primitives reservieren
    - compatibility badge
    - provenance badge
    - conflict chip
    - risk banner
    - session authority banner
    - preview / rollback card

    ## Design-Repo-Vorgaben

    Im Design-Repo sollen jetzt verankert werden:
    - ein knapper Zusatz in `VISION.md` zu deterministic runtime stacks und overlay-based future capability
    - `products/chummer/capabilities/KARMA_FORGE_FOUNDATION.md`
    - `products/chummer/GLOSSARY.md`
    - ADRs fuer Runtime Stack, Session Authority, Explain/Provenance Receipts und deklarative Overlays statt Plugins
    - `FUTURE_CONTRACT_SEEDS.yaml`
    - projektbezogene Touchpoints unter `products/chummer/projects/`
    - Review-Guidance gegen branch-per-user, code-plugins, contract-copying und fehlende conflict/migration models

    Horizon-Capabilities muessen klar markiert sein:

    ```yaml
    status: horizon
    queue_eligible: false
    dispatchable: false
    ```

    ## Fleet-Vorgaben

    Fleet trennt Design Compile, Policy Compile und Execution Compile. Genau deshalb duerfen Zukunftsdokumente keine aktive Arbeitsqueue erzeugen.

    Pflicht:
    - Horizon-Artefakte respektieren
    - in Compile-Manifesten sichtbar machen, ob ein Artefakt nur informativ oder dispatchable ist
    - keine `QUEUE.generated.yaml` aus Horizon-Dokumenten ableiten
    - Truth-Drift zwischen `products/chummer/*`, Fleet-Groups und Repo-Mirrors haerter anzeigen

    ## Code-Repo-Vorgaben

    In Code-Repos jetzt nur drei kleine technische Seeds:
    - Runtime Stack Manifest + Fingerprint DTOs
    - Session Event Envelope + Authority Profile
    - Explain / Provenance Receipt

    Nicht mehr.

    ## Prioritaetsreihenfolge

    1. Contract- und naming reset
    2. Runtime stack truth
    3. Session authority + session events
    4. Explain / provenance receipts
    5. Artifact metadata model in registry language
    6. Preview / apply / rollback / migration
    7. Kleiner deterministischer lab harness fuer `ALICE`
    8. Grounded narrative/export seams fuer `JACKPOINT`
    9. Spaetere UI primitives

    ## Bottom line

    Das richtige Vorgehen ist:
    - **jetzt**: horizon-capability + begriffs-/ownership-/artefaktkanon + review-/audit-regeln
    - **spaeter**: minimale foundation-implementierung in `chummer6-hub`, `chummer6-mobile`, `chummer6-hub-registry`
    - **viel spaeter**: community layer, registry publishing, promotion pipeline
    - **noch spaeter**: marketplace, voting, gamification, breite produktaktivierung
    """
).strip() + "\n"


def write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main() -> None:
    write(DESIGN_FEEDBACK_ROOT / FILENAME, CONTENT)
    write(GROUP_FEEDBACK_ROOT / FILENAME, CONTENT)
    write(FLEET_FEEDBACK_ROOT / FILENAME, CONTENT)
    print("Injected Chummer foundation horizon guidance into design, group, and fleet feedback lanes.")


if __name__ == "__main__":
    main()
