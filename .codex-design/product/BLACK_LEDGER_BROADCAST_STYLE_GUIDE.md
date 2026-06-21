# Black Ledger Broadcast Style Guide

## Primary set

A premium cyberpunk newsroom, realistic and cinematic.

## Set features

```yaml
set:
  desk: dark matte broadcast desk with subtle transparent edge lighting
  background: curved city-pressure display wall
  windows: rain-glass city glow or abstract city silhouettes
  screens:
    - Black Ledger geoscape
    - faction heat rail
    - ticker
    - public-safe source card
  lighting:
    - soft key on face
    - cyan/amber rim
    - no blown-out neon
    - realistic skin exposure
```

## Camera language

```yaml
camera:
  primary_anchor:
    - medium desk shot
    - slow push-in for headline
    - over-shoulder map display
  breaking:
    - tighter crop
    - red/amber alert accent
    - subtle handheld feel only for field inserts
  field:
    - stabilized handheld
    - rain / street / facility exterior
```

## Lower thirds

Required:
- anchor name
- segment title
- source type
- public-safety label when needed

Examples:

```text
MARA VOSS | BLACK LEDGER NEWSROOM
MATRIX BREACH | PUBLIC-SAFE RECONSTRUCTION
TURN 1 UPDATE | RECEIPT-BACKED SUMMARY
```

## Ticker

Ticker must be short, readable, and not spammy.

Example:

```text
DEBT HEAT +2 · GHOSTLINE TRACE CONFIDENCE RISING · FREE WARDENS OPEN SAFEHOUSE WINDOW
```

## B-roll prompt grammar

Every B-roll prompt must include:

```yaml
location:
subject:
action:
camera:
lighting:
background_motion:
public_safety_note:
forbidden_elements:
```

Preferred scene families:
- facility breach
- matrix trace room
- magic heat
- rust market
- safehouse
- dockyard
- geoscape insert

## Visual fail states

Fail if:
- anchor looks like a cartoon by accident;
- tusks or ears look fake or costume-like;
- host is frozen;
- mouth does not move;
- body does not move;
- background is a flat SVG;
- no B-roll;
- no lower third;
- no caption track;
- no source provenance.
