# Chummer.run Flagship Redesign Package

Date: 2026-05-06

Scope basis:
- Fleet canon in `/docker/fleet/.codex-design/product`
- Fleet operating docs in `/docker/fleet`
- EA LTD inventory in `/docker/EA/LTDs.md`
- Live route audit on 2026-05-06 against `https://chummer.run`
- Current implementation audit in `/docker/chummercomplete/chummer.run-services`, `/docker/chummercomplete/chummer-hub-registry`, and `/docker/chummercomplete/chummer6-ui`

## 1. EXECUTIVE DIAGNOSIS

- The live front door is still visually light, safe, and polite when the product brief calls for dark, premium, and launch-grade.
- The homepage hero explains rules truth, but it still undersells the bigger promise that Chummer is becoming the Shadowrun campaign operating system.
- The page rhythm is flat. Hero, proof, works-now, trust pulse, and account CTA all use similar weight, so nothing feels decisive.
- The homepage repeats the same trust argument three times with different wrappers instead of building conviction once and moving forward.
- The current hero art is better than generic SaaS filler, but the composition still feels like an illustration plus floating copy, not a premium acquisition surface.
- The proof panel is valuable, but it is buried inside a page that still reads like a careful explainer instead of a product launch.
- The install path is honest, but it is not emotionally compelling. “Create account to install” still reads like a gate instead of an advantage.
- Account value is described in text, not demonstrated as continuity, device recovery, support history, and campaign return.
- `/downloads` is competent, but it still feels like a release management page with product copy added on top.
- `/what-is-chummer` explains categories instead of telling a high-confidence product story for a skeptical player, GM, or migrating Chummer5a veteran.
- `/now` and `/status` both carry truth, but the family still leaks internal operational posture into customer-facing routes more than a flagship front door should.
- `/artifacts` matters, but it competes with acquisition instead of serving as supporting proof behind the recommended install path.
- `/participate` leads with ProductLift boundary explanation. That is correct policy, but it is the wrong emotional lead for a premium product surface.
- `/feedback` is still effectively a fallback alias to the broader participate surface, which proves the public signal loop is not product-real yet.
- `/changelog` currently collapses into the same “what works today” posture, so shipped closeout is not distinct enough from status.
- Help, FAQ, privacy, terms, and contact all inherit too much of the same structure, so the route family feels templated rather than authored.
- The trust pulse is useful, but repeating it across nearly every route dilutes it. A flagship system uses proof surgically.
- The public header advertises too many destinations with near-equal weight, which weakens the action hierarchy for first-time visitors.
- The mobile stack is functional but not sharp. Long vertical sections, repeated explanatory text, and multiple mid-page CTA pockets add friction.
- The signed-in shell already contains strong continuity truth, but `/home` and `/account` feel like dense work surfaces, not a premium cockpit plus a calmer account rail.
- The product still looks more like a very careful preview shell than something worth paying for.
- The current surface does not visually separate customer routes, proof routes, signal routes, and operator routes strongly enough.
- Route-family drift remains visible. The routes share chrome, but they do not yet feel like one deliberate front door system with distinct jobs.
- LTD leverage is still mostly backstage. ProductLift, Emailit, MetaSurvey, Documentation.AI, and Mootion are not yet user-visible operating loops.

## 2. NORTH STAR POSITIONING

Positioning statement:
Chummer is the Shadowrun campaign operating system: deterministic character truth, explainable rulings, and account-linked campaign continuity in one serious product.

Brand paragraph:
Chummer should feel like the place where Shadowrun prep, rules confidence, and campaign return finally stop fragmenting across files, vague tools, and memory. The product voice is disciplined, technical without sounding internal, and premium without pretending the preview is already complete.

Hero concept:
A converted street-clinic fitting bay where a runner is getting a cyberarm installed under pressure, with diegetic diagnostic overlays, dossier props, and a compact inset of real product proof. The scene sells consequence, trust, and craft in one frame.

Three product pillars:
- Rules truth you can inspect
- Campaign continuity that survives devices and downtime
- Account-linked installs, support, and recovery that feel useful immediately

Front-door conversion goal:
Move a first-time visitor to one of two clean actions within ten seconds: start the recommended account-aware install handoff or inspect the live proof shelf without confusion.

## 3. FLAGSHIP REDESIGN PRINCIPLES

- Dark-first authority. The public route family should look like a premium campaign instrument, not a light marketing microsite.
- One page, one dominant job. Each route gets one obvious primary action and one clear reason to exist.
- The install shelf is the authority. Proof supports the install decision; it does not compete with it.
- Proof outranks exposition. Show one concrete result, one current release path, and one honest status line before asking the user to read.
- Account value must read as continuity, not bureaucracy.
- Support stays calm and first-party. Participation, public signal, and support must not blur together.
- Screenshots appear only where they prove product reality. They are not decorative filler.
- Raster art must show pressure, gear, people, and consequence. No poster cliches, empty alleys, or abstract neon fog.
- Mobile is not a shrunk desktop. It gets its own CTA rail, tighter proof stack, and shorter decision path.
- The signed-in shell must answer “what changed for me?” before it answers “what settings exist?”
- ProductLift may project signal, roadmap, and closeout, but it may never sound like roadmap truth or support truth.
- Downloads, account, install claim, relink, and recovery must remain one coherent story across public and signed-in surfaces.
- Trust pulse appears where it changes a decision, not as ritual repeated chrome.
- Public copy must never lead with repo, provider, LTD, or control-plane language again.
- No route should ever look like a generic theme pass on the same template again.

## 4. FLAGSHIP PAGE ARCHITECTURE

### Section 1: Hero command deck
- Purpose: Answer what Chummer is, why it matters, and what to do next in one premium frame.
- Content: Positioning headline, short subheadline, recommended install shelf, one secondary proof CTA, three proof chips, current build and channel line, compact product proof inset.
- Current content removed: The separate soft hero proof paragraph and the extra “public preview” line that repeats the same trust posture.
- Moves deeper: Extended explanation of lanes, roadmap, and artifact context.
- Primary CTA: `Create account and install`
- Secondary CTA: `See what works today`
- Proof strategy: Show current platform, channel, build label, and one visible product result in the hero itself.
- Image treatment: Full-bleed raster hero with inset proof panel anchored inside the right column.
- Mobile behavior: Copy first, sticky CTA rail second, proof shelf third, image crop last with safe center on hands, face, and cyberarm seam.

### Section 2: Live proof shelf
- Purpose: Prove that the product is real today without forcing a long scroll.
- Content: One recommended platform card, one explanation-trail proof card, one campaign continuity proof card, one support/recovery proof card.
- Current content removed: Repeated “current preview” prose and small proof notes spread across multiple sections.
- Moves deeper: Full artifact gallery and detailed route proof.
- Primary CTA: `Open downloads`
- Secondary CTA: `Inspect proof gallery`
- Proof strategy: Each card needs one live route, one receipt type, and one honest current limitation.
- Image treatment: Dense raster-plus-screenshot composite; screenshots only inside proof cards.
- Mobile behavior: Horizontal snap cards become stacked cards with one highlighted default card first.

### Section 3: Why it matters at the table
- Purpose: Translate product capability into table pain removed.
- Content: Three short tension cards for build opacity, rules disputes, and continuity loss across devices or sessions.
- Current content removed: Generic “start here” workflow grid copy that reads like taxonomy instead of urgency.
- Moves deeper: Full feature cards under `/what-is-chummer`.
- Primary CTA: `Read the product story`
- Secondary CTA: `Open what works today`
- Proof strategy: Each pain card pairs a product promise with one visible proof route.
- Image treatment: No full illustrations; use tight proof fragments and one cinematic divider still.
- Mobile behavior: Collapse to swipeable stacked cards with no more than three lines of copy each.

### Section 4: Player, GM, creator fit band
- Purpose: Let the visitor self-sort fast without fragmenting the primary pitch.
- Content: Three lane cards with one-sentence role value, one concrete output, one route.
- Current content removed: Overly similar “choose your lane” cards that feel secondary rather than decisive.
- Moves deeper: Role-specific nuance under `/what-is-chummer`, `/artifacts`, and later guide pages.
- Primary CTA: `See your lane`
- Secondary CTA: `Compare all lanes`
- Proof strategy: Every lane card points to one real route and one current proof artifact.
- Image treatment: Small raster crops with clear role semantics, not mini posters.
- Mobile behavior: Single-column stack with lane tags and oversized tap targets.

### Section 5: Account continuity band
- Purpose: Make account creation feel valuable in product terms.
- Content: Install linking summary, devices and access summary, support history summary, roaming continuity summary.
- Current content removed: Late-page generic “create the account that keeps your place” copy.
- Moves deeper: Full detail in `/signup`, `/home`, and `/account`.
- Primary CTA: `Create account`
- Secondary CTA: `Sign in`
- Proof strategy: Show “same download, better handoff” and “first launch still supports guest or link” as explicit microproof.
- Image treatment: Compact raster product composite with device handoff cues and one grounded UI crop.
- Mobile behavior: Turn into a four-row proof list with a sticky bottom CTA.

### Section 6: What ships now
- Purpose: Keep preview honesty visible after desire is created.
- Content: Available today, preview lanes, next caution, supportability note.
- Current content removed: Split available/preview/coming-next fragments that currently repeat across the page.
- Moves deeper: `/now`, `/status`, `/horizons`.
- Primary CTA: `Open what works today`
- Secondary CTA: `Read current caution`
- Proof strategy: Show one current recommendation, one caution, one next-most-likely lane.
- Image treatment: No new art; use disciplined status cards.
- Mobile behavior: Two cards plus one expandable caution drawer.

### Section 7: Futures preview
- Purpose: Signal product ambition without overclaiming.
- Content: Three horizon cards only: campaign continuity, explain moat, publication/distribution.
- Current content removed: Large public roadmap complexity on the homepage.
- Moves deeper: `/horizons` and `/roadmap`.
- Primary CTA: `Open roadmap`
- Secondary CTA: `Follow product direction`
- Proof strategy: Each card states current seam, not a fantasy promise.
- Image treatment: One shared atmospheric future still and compact lane badges.
- Mobile behavior: Stack as accordion cards with one sentence and one CTA each.

### Section 8: Artifact and publication shelf
- Purpose: Show that Chummer can produce output worth sharing.
- Content: Dossier packet, recap artifact, publication-ready output, release bundle proof.
- Current content removed: Artifact content that currently competes too high above acquisition.
- Moves deeper: `/artifacts`.
- Primary CTA: `Open proof gallery`
- Secondary CTA: `Open public publications`
- Proof strategy: Show provenance, audience, and route labels, not just pretty thumbnails.
- Image treatment: Shelf-style raster composites with product screenshots embedded in cards.
- Mobile behavior: Carousel becomes stacked shelf with one lead artifact and two secondary cards.

### Section 9: Public signal and follow-up band
- Purpose: Make the public loop real without letting it hijack the pitch.
- Content: Feedback, roadmap follow, changelog closeout, private-support redirect.
- Current content removed: Participation-first framing and long ProductLift boundary explanations above the fold.
- Moves deeper: `/participate`, `/feedback`, `/roadmap`, `/changelog`.
- Primary CTA: `Open feedback`
- Secondary CTA: `Need private help instead?`
- Proof strategy: Show one triage line, one closeout line, one privacy boundary line.
- Image treatment: Minimal; use one subdued raster shelf cue rather than a major illustration.
- Mobile behavior: Condense to four tap rows with a support escape hatch pinned last.

### Section 10: Final CTA band
- Purpose: Close the page with account value and a direct next step.
- Content: Account value summary, recommended install path, sign-in return path.
- Current content removed: Repetition of generic artifact and product-story links in the closing CTA.
- Moves deeper: Footer navigation.
- Primary CTA: `Create account and install`
- Secondary CTA: `Already have an account? Sign in`
- Proof strategy: Repeat only the continuity value, not the full trust story.
- Image treatment: Dark gradient band, no extra illustration.
- Mobile behavior: Sticky rail hands off into this band and then disappears near footer.

## 5. DESKTOP WIREFRAME

1. Sticky header, 80 to 88 px tall, transparent-to-solid transition.
2. Header grid: brand left, five-item primary nav center, account/install actions right.
3. Hero container: 12-column grid inside a 1280 px max shell with 72 px top breathing room.
4. Hero left column uses 5 columns for eyebrow, headline, subheadline, CTA row, proof chips, and install shelf.
5. Hero right column uses 7 columns for the raster hero with a floating proof inset anchored bottom-right.
6. Install shelf sits directly under hero CTA row, not on a later page band. It contains recommended platform, current channel, one sentence of install posture, and one support fallback link.
7. Live proof shelf sits immediately below hero in a 4-card row. Card one is acquisition proof, card two is explain proof, card three is continuity proof, card four is support/recovery proof.
8. Table-pain section uses a two-column rhythm: copy lead left, three stacked compact pain cards right.
9. Role-fit band uses three equal cards in one row with small art crops aligned to a shared baseline.
10. Account continuity band uses a split layout: left copy and CTA, right a stacked device/account proof panel.
11. What-ships-now section uses a 2+1 card arrangement: large current recommendation card, medium caution card, small preview/future card.
12. Futures preview uses three medium cards in one row with one background still spanning the section.
13. Artifact shelf uses one large lead artifact card and three smaller supporting cards in a staggered grid.
14. Public signal band uses a low-contrast row of four functional cards. It should feel like a utility rail, not a second homepage.
15. Final CTA band spans full width with one headline, one sentence, two actions, and no card clutter.
16. Spacing rhythm: 24 px micro, 40 px local section padding, 64 px between major content blocks, 96 px between hero and the rest of the page.
17. Card logic: no more than three surface tiers on the page at once. Lead cards get image plus proof tags. Secondary cards get no more than one proof line.
18. Screenshot placement: screenshots appear only inside proof cards, downloads shelf, and signed-in continuity panel. Never as wallpaper.
19. CTA placement: every major section gets one clear action, but only hero, proof shelf, and final band use button-weight CTAs.
20. Hierarchy note: the eye should move hero -> install shelf -> proof shelf -> role fit -> account value -> futures, with no route-taxonomy interruption.

## 6. MOBILE WIREFRAME

1. Header collapses to brand, menu, and one visible `Create account` action.
2. Hero stacks as headline, subheadline, primary CTA, secondary CTA, install shelf, proof chips, then art crop.
3. Sticky bottom CTA appears after the first viewport and contains `Create account and install` plus a compact secondary proof link.
4. The install shelf becomes a single highlighted card with platform, channel, account value, and one support fallback row.
5. The live proof shelf stacks vertically in priority order: install proof, explain proof, continuity proof, support proof.
6. The table-pain section collapses to three compact cards with 44 px minimum tap targets.
7. Role-fit cards become a swipeable or stacked three-card set. Only title, one sentence, and one CTA stay visible by default.
8. Account continuity band becomes four dense rows with small icons and one sentence each.
9. What-ships-now becomes one current card, one caution drawer, one preview/future drawer.
10. Futures preview becomes three accordions. Only one opens at a time.
11. Artifact shelf becomes a lead artifact card plus two text-first supporting rows. Extra artifacts move to `/artifacts`.
12. Public signal band becomes four list rows and one persistent `Need private help instead?` row.
13. Footer keeps only essential links exposed by default. Legal and deep secondary navigation collapse.
14. What collapses: milestone density, artifact clutter, expanded lane explanations, repeated trust pulse details.
15. What disappears: decorative proof flourishes, secondary image frames, long inline proof trails, large aside copy blocks.
16. Image crop rule: keep faces, hands, device seams, and proof props inside the center 60 percent safe zone.
17. Account/install CTA behavior on mobile: primary CTA always resolves to the best safe next step for the device, but the copy stays consistent.
18. Download/install/support mobile posture: acquisition first, support visible but secondary, recovery path always reachable within one additional tap.

## 7. VISUAL SYSTEM

Palette:
- `Obsidian 950` `#060b12`
- `Ink 900` `#0b1320`
- `Graphite 800` `#121d2d`
- `Steel 700` `#213147`
- `Mist 300` `#94a7bd`
- `Cloud 100` `#d7e0ea`
- `Signal Cyan` `#39c6ff`
- `Electric Blue` `#2e7bff`
- `Warm Amber` `#ffb15c`
- `Warning Red` `#ff5d5d`
- `Success Mint` `#53d6a5`

Typography:
- Display: `Space Grotesk`
- Body: `Instrument Sans`
- Mono and proof labels: `IBM Plex Mono`
- Headline treatment: tight tracking, strong weight, short lines
- Body treatment: calm, slightly compressed paragraphs, no wide marketing leading

Spacing scale:
- 4, 8, 12, 16, 24, 32, 48, 64, 96, 128

Radius:
- Hero and lead cards: 28
- Standard cards: 18
- Inputs and chips: 12
- Pill CTAs: 999

Borders:
- Default border: `1px solid rgba(148, 167, 189, 0.14)`
- Strong border: `1px solid rgba(57, 198, 255, 0.28)`
- Section dividers: soft top hairline, never thick framing

Card surfaces:
- Base surface: deep graphite with slight blue bias
- Elevated surface: slightly lighter graphite plus inner highlight
- Proof surface: darker, denser, more instrument-like
- Legal/help surface: flatter, calmer, lower glow

Elevation and shadow rules:
- Use broad soft shadows, not glass bubbles
- One hero shadow class, one standard card shadow class, one inset proof shadow class
- Never stack more than two shadow layers per component

Glow rules:
- Cyan glow is for active CTA, focus, and proof emphasis only
- Warm amber is only for caution or “recommended shelf” emphasis
- No full-card neon halos

Motion rules:
- 180 ms to 240 ms for hover and pressed state
- 320 ms to 420 ms for section reveal or image fade
- One staggered reveal on first load, then stop
- No bouncing, float loops, or constant pulsing

Hover, focus, pressed states:
- Hover: slight lift and brighter border
- Focus: thick visible cyan focus ring with dark inset contrast
- Pressed: reduce lift, deepen surface, preserve border

Accessibility rules:
- Minimum 4.5:1 contrast on all body text
- 3:1 for large display text only when font size and weight qualify
- No critical text embedded only in images
- No hover-only proof
- All CTA rows must be keyboard and screen-reader coherent

Dark mode handling:
- The flagship public family is dark-default in wave 1
- No public light-toggle is shipped on the flagship routes in the first implementation slice
- Token system still supports light variants for account admin, print, or legacy surfaces behind the same semantic tokens

Anti-patterns to ban:
- Light marketing gradients as the default public shell
- Glassmorphism panels over every surface
- Giant neon outlines
- Empty dashboard counters
- SVG illustration packs
- Card walls with duplicate proof copy
- Purple bias
- Fake terminal gimmicks
- Low-contrast muted-on-muted copy

## 8. IMAGE / ART DIRECTION

Exact hero-image concept:
A metahuman streetdoc fitting a replacement cyberarm in a bright improvised clinic bay while a teammate watches the calibration. The scene contains clamps, implant trays, dossier papers, taped cables, visible grime, and sparse diegetic AR aligned to the arm seam and tool positions.

Supporting still families:
- Proof stills: dense desk, rule receipt, mission prep, continuity handoff
- Install confidence stills: packaging bench, device handoff, update/recovery workstation
- Futures stills: branching district lanes, dossier wall, campaign command room
- Artifact stills: shelf, packet stack, publication card table
- Support stills: practical help desk, known-issue triage, repair bench

Where screenshots belong:
- Hero proof inset
- Live proof shelf
- Downloads shelf
- Signed-in continuity band
- `/home` and `/account` cockpit demonstrations

Where atmospheric campaign stills belong:
- Hero
- Table-pain section divider
- Futures preview
- Artifact shelf

Where dense proof visuals belong:
- Downloads
- `/now`
- `/artifacts`
- Signed-in continuity and devices rails

Where raster product composites belong:
- Hero inset
- Downloads install confidence section
- Account continuity band

Repeated visual motifs:
- Diagnostic seam traces
- Dossier paper stacks
- Evidence clips and seals
- Device-to-device handoff cues
- Layered rails and bracket overlays
- Premium print-like poster finish on grimy subject matter

What to avoid:
- Empty boulevards
- Lone hooded figures
- Generic dashboard screenshots as art
- Text baked into images
- Posterized neon linework
- Flat matte sludge

Twelve premium AI image prompts:

1. Flagship hero
`Premium painted cyberpunk-fantasy product art, Shadowrun-adjacent street clinic in a converted garage bay, metahuman streetdoc fitting a new cyberarm onto a scarred runner while one teammate watches with urgent concern, clamps, implant trays, med rig, dossier papers, six-sided dice, taped cables, wet concrete, warm clinic lamps plus electric cyan edge light, sparse diegetic diagnostic overlays anchored to the cyberarm seams and tools, readable faces and hands, polished poster finish, layered foreground midground background, gritty lived-in materials, no readable text, no logos, no generic alley mood, no empty space`

2. Proof section
`Premium raster product-proof scene, mission briefing desk covered in dossier packets, route overlays, integrity seals, commlink, dice, reagent pouch, compact embedded product screenshot frame showing modifier trail and build proof, dramatic but controlled top lighting, graphite and cyan palette with warm signal accents, high information density, no readable text, no logos, no SVG look`

3. Downloads and install confidence
`Dark premium install-confidence still, operator workstation with packaged desktop installer media, linked device card, update receipt, support note, one grounded screenshot crop, subtle AR rails showing account-linked handoff and recovery continuity, professional cyberpunk realism, clean polished finish over hard-used objects, no readable text, no logos, no poster cliche`

4. Roadmap and futures
`Wide premium future-lane panorama, multiple grounded cyberpunk districts and work lanes branching from one elevated observation point, metahuman traffic, body-worn cyberware cues, sparse ambient route overlays, Bug City and Barrens residue, campaign-operating-system mood rather than generic skyline, premium painted realism, no readable signage, no logos`

5. Artifacts and dossier shelf
`Close premium artifact shelf scene, dossiers, recap packets, evidence clips, sealed publication cards, stacked printed outputs, compact device showing artifact lineage, moody graphite lighting with cyan highlights and warm paper tones, tactile materials, high detail, no readable text, no logos`

6. Participation and signal lane
`Serious product-signal scene, public feedback board implied through pinned cards, recorded notes, moderated queue tokens, one operator reviewing safe public signals while private support folders stay separate, premium cyberpunk office realism, controlled cyan accents, no readable text, no logos, no generic dashboard wall`

7. Help and support
`Premium support and repair still, practical help desk with opened device, install media, recovery notes, calm operator posture, bounded issue triage props, trustworthy technical atmosphere, dark graphite background, cyan focus highlights, warm task lighting, no readable text, no logos, no corporate call center vibe`

8. Mobile continuity
`Premium mobile continuity scene, player using a tablet at a table while a secondary workstation sits nearby, visible reconnect and travel-cache cues through grounded props and subtle overlays, campaign notes, dice, coffee-ring wear, practical low-light cyberpunk realism, no readable text, no logos`

9. Campaign continuity
`Serious campaign OS still, GM command table with dossiers, faction markers, heat movement notes, mission packets, route overlays, metahuman team presence, premium painted realism, dense but organized composition, no readable text, no logos, no generic war room cliché`

10. Player, GM, creator fit
`Triptych-style premium scene composition without visible panel borders, player review moment, GM planning moment, creator publication moment, each with grounded props and product-specific cues, unified dark graphite palette with cyan and warm signal accents, polished realism, no readable text, no logos`

11. Signed-in access and device continuity
`Account continuity still, two claimed devices with different roles on the same desk environment, one support receipt, one install handoff proof, one recovery cue, subtle role overlays, premium professional cyberpunk aesthetic, trustworthy not flashy, no readable text, no logos`

12. Alternate hero family
`Alternative flagship hero, runner team in a cramped planning room reviewing one dossier and one explainable build result before a job, obvious cyberware, metahuman physiology, clipped AR markers anchored to gear and route maps, premium painted rulebook-cover realism, dark graphite and electric cyan with restrained amber highlights, no readable text, no logos`

## 9. COPY SKELETON

Global nav:
`Product` `Downloads` `What Works Today` `Roadmap` `Artifacts` `Participate`

Hero eyebrow:
`Campaign OS Preview`

Hero headline:
`The Shadowrun campaign OS that shows its work.`

Hero subheadline:
`Build runners, inspect rulings, and keep campaigns moving with deterministic rules truth, account-linked installs, and continuity that survives the next device or network wobble.`

Hero CTA pair:
`Create account and install`
`See what works today`

Proof section headline:
`Real product proof, not a themed shell.`

What’s-live-now strip:
`Available today, visible in proof, honest about caution.`

Downloads summary:
`One recommended build per platform, one calm install path, and the same file for everyone.`

Roadmap intro:
`Direction stays public. Promises stay attached to proof.`

Artifacts intro:
`Dossiers, recaps, and release proof belong on a shelf you can inspect, not in a vague gallery.`

Final CTA band:
`Create the account that keeps installs, devices, and support on one return path.`

Account-value microcopy:
`Accounts keep linked installs, support history, roadmap follow-up, and recovery on one calmer rail. The binary stays the same.`

Support/help microcopy:
`Need install help, account recovery, or a fix status you can trust? Start with first-party help, not the public signal board.`

Install-linking microcopy:
`Download the same build everyone gets. Link this copy on first launch when you want restore, recovery, and tracked follow-through.`

ProductLift feedback and voting microcopy:
`Public ideas, votes, and shipped follow-up live here. Crashes, installs, account issues, logs, and private campaign details do not.`

## 10. ROUTE FAMILY STRATEGY

### `/`
- Primary job: flagship acquisition and confidence.
- What it should stop doing: repeating trust copy and route taxonomy.
- What it should inherit: dark hero system, integrated install shelf, compact proof shelf, account-value band.
- Visual density: medium-high.
- Mobile simplifies: fewer proof cards, sticky install CTA, compact future preview.
- Exact CTA posture: `Create account and install` primary, `See what works today` secondary.
- Exact proof posture: one live build, one visible explanation trail, one continuity proof line.

### `/what-is-chummer`
- Primary job: explain the product and the migration value.
- What it should stop doing: reading like a parts catalog.
- What it should inherit: flagship hero language, role-fit cards, table-pain framing.
- Visual density: medium.
- Mobile simplifies: single narrative stack and three role cards.
- Exact CTA posture: `Open downloads` primary, `See what works today` secondary.
- Exact proof posture: one migration-proof band and three role-specific proof rows.

### `/downloads`
- Primary job: acquire the right build with confidence.
- What it should stop doing: feeling like a release-ops page with marketing wrapped around it.
- What it should inherit: dark acquisition shell, recommendation shelf, recovery rail, proof cards.
- Visual density: medium-high.
- Mobile simplifies: single recommended card, platform drawer, support drawer.
- Exact CTA posture: recommended install action primary, `Need install help?` secondary.
- Exact proof posture: package type, current channel, known caution, claim/recovery continuity, release evidence.

### `/now`
- Primary job: tell the truth about what is live, inspectable, preview, and cautionary.
- What it should stop doing: sharing the same emotional posture as the homepage.
- What it should inherit: proof-card language and status token system.
- Visual density: high.
- Mobile simplifies: one current card, one caution card, one future card.
- Exact CTA posture: `Open downloads` primary, `Inspect proof gallery` secondary.
- Exact proof posture: route-by-route proof rows with dates and limitations.

### `/horizons`
- Primary job: show future lanes without overclaiming.
- What it should stop doing: looking like a second status page.
- What it should inherit: future-lane card system and shared art family.
- Visual density: medium.
- Mobile simplifies: accordion lanes only.
- Exact CTA posture: `Follow roadmap` primary, `Open what works today` secondary.
- Exact proof posture: each horizon names current seam, not fake readiness.

### `/artifacts`
- Primary job: show inspectable outputs and provenance.
- What it should stop doing: competing with downloads as the first recommended route.
- What it should inherit: dark shelf grammar, artifact card system, lineage cues.
- Visual density: high.
- Mobile simplifies: lead artifact plus stacked shelves.
- Exact CTA posture: `Inspect proof gallery` primary, `Open downloads` secondary.
- Exact proof posture: audience, source, publication status, and live route linkage per card.

### `/participate`
- Primary job: route public signal and optional deeper contribution cleanly.
- What it should stop doing: leading with internal boundary explanations.
- What it should inherit: utility-band treatment, not flagship hero treatment.
- Visual density: medium.
- Mobile simplifies: four lane rows and one private-help escape hatch.
- Exact CTA posture: `Open feedback` primary, `Sign in for deeper participation` secondary.
- Exact proof posture: public signal boundaries, triage truth, shipped-closeout proof.

### `/help`
- Primary job: triage users to the safest help path.
- What it should stop doing: feeling like a generic trust page.
- What it should inherit: support rail, install help lane, recovery lane, known-issue lane.
- Visual density: medium.
- Mobile simplifies: top triage list and one support CTA.
- Exact CTA posture: `Open support intake` primary, `Open downloads` secondary.
- Exact proof posture: first-party help authority, route-specific next steps, known issue guidance.

### `/faq`
- Primary job: answer normal objections fast.
- What it should stop doing: repeating full support/trust prose.
- What it should inherit: concise answer cards and question grouping.
- Visual density: low-medium.
- Mobile simplifies: single-question drawers.
- Exact CTA posture: `See what works today` primary, `Open support intake` secondary.
- Exact proof posture: each answer points to one live route when evidence matters.

### `/privacy`
- Primary job: explain stored account truth, install-linking truth, and what stays out.
- What it should stop doing: feeling like legal copy with a decorative shell.
- What it should inherit: calm trust-doc template and install-linking visual proof.
- Visual density: medium.
- Mobile simplifies: summary strip plus expandable sections.
- Exact CTA posture: `Open account` primary, `Open support intake` secondary.
- Exact proof posture: same binary for everyone, no raw secrets in account record, clear telemetry boundary.

### `/terms`
- Primary job: explain preview rules in plain language.
- What it should stop doing: competing with the product story.
- What it should inherit: plain-language trust-doc template.
- Visual density: low-medium.
- Mobile simplifies: summary strip plus short sections.
- Exact CTA posture: `Open downloads` primary, `Read privacy` secondary.
- Exact proof posture: early access honesty, support-first route, installer and fallback clarity.

### `/contact`
- Primary job: start a support case cleanly.
- What it should stop doing: behaving like a general marketing contact page.
- What it should inherit: support-case type selector, guest vs tracked follow-up explanation.
- Visual density: medium.
- Mobile simplifies: case-type buttons first, form second.
- Exact CTA posture: `Open support intake` primary, `Create account for tracked support` secondary.
- Exact proof posture: case-type clarity, tracked follow-up promise, GitHub remains advanced/public only.

### `/signup`
- Primary job: convert a convinced visitor without friction.
- What it should stop doing: feeling like a bare auth wall.
- What it should inherit: premium auth shell, account-value strip, provider restraint.
- Visual density: low.
- Mobile simplifies: one value block, auth options, sign-in link.
- Exact CTA posture: `Continue with Google` primary when enabled, email path alongside, `Sign in` secondary.
- Exact proof posture: installs, devices, support, and recovery value in four short lines.

### `/login`
- Primary job: get returning users back to their path.
- What it should stop doing: looking identical to generic signup.
- What it should inherit: calm re-entry shell and next-target reminder.
- Visual density: low.
- Mobile simplifies: one short status strip plus auth actions.
- Exact CTA posture: `Continue with Google` primary, `Create account` secondary.
- Exact proof posture: next-target continuity and recovery language.

### `/home`
- Primary job: answer “what changed for me?” and hand the user to the next safe action.
- What it should stop doing: reading like a dense mixed-purpose dashboard.
- What it should inherit: signed-in cockpit shell, channel/role rail, continuity cards.
- Visual density: high, but disciplined.
- Mobile simplifies: continue card, what-changed packet, device-role rail, support notice.
- Exact CTA posture: context-sensitive `Continue` primary, `Open downloads` or `Open account access` secondary.
- Exact proof posture: claimed device, rule drift, support closure, recent campaign memory, role visibility.

### `/account`
- Primary job: hold devices and access, support history, settings, and deeper work safely.
- What it should stop doing: trying to feel like the first signed-in destination.
- What it should inherit: calmer account rail with subordinate navigation and stronger access/recovery grouping.
- Visual density: high.
- Mobile simplifies: segmented tabs, devices first, support second, settings third.
- Exact CTA posture: `Open devices and access` or `Open support` depending on context.
- Exact proof posture: linked installs, pending claims, active grants, recovery identities, support case state.

## 11. AUTH / INSTALL / DEVICE-LINKING PRESERVATION PLAN

Current truths that must remain:
- Hub owns the account, claim, device, identity, channel, and support truth.
- Public downloads remain guest-readable when the current policy says they are.
- Signed-in users may get `DownloadReceipt` and `InstallClaimTicket` handoff value without receiving a personalized binary.
- First launch must still support `Use as guest` and `Link this copy to my account`.
- Devices and access remain the calm relink, reclaim, and recovery path after the installer or app does the real work.

Routes that must remain stable:
- `/login`
- `/signup`
- `/auth/email/start`
- `/auth/email/callback`
- `/auth/google/start`
- `/auth/google/callback`
- `/home`
- `/account`
- `/participate`
- `/participate/codex`
- `/downloads/install/{artifact}`

How the redesign preserves `DownloadReceipt` and `InstallClaimTicket` posture:
- The public shell surfaces account-aware value at the CTA layer, not in the binary or artifact model.
- Downloads continue to resolve through the same registry-backed routes and signed-in dispatch behavior.
- The redesigned install shelf explicitly says the file stays the same for everyone and the account-aware piece is the handoff.

How first-run claim, link, and recovery remain intact:
- The redesign keeps first-run claim inside the app or guided installer path.
- Browser routes remain handoff and recovery helpers, not the primary claim ritual.
- Recovery messaging always points back to the linked device or account rail first.

How Devices and access stays useful and discoverable:
- `/account/access` becomes a first-class account rail destination with higher prominence in signed-in chrome.
- `/home` surfaces device role, linked-install state, and relink or reclaim cues so users know the route exists before they need it.

How the redesign avoids browser-only claim-code regressions:
- No manual claim-code ritual is promoted on the public front door.
- Any visible recovery code is explicitly secondary, temporary, and only shown when the install enters recovery mode.
- The recommended path remains guided installer or in-app linking.

How mobile users return safely to their install or account state:
- Signed-in mobile CTAs always prefer the last safe route for the current state.
- Support, devices, and downloads remain one-tap away from the signed-in shell.
- No mobile redesign moves the recovery path behind a hidden desktop-only drawer.

## 12. TIBOR MAC BUILD COMPATIBILITY PLAN

How to find the current Tibor-triggered Mac-build path:
- Audit `/downloads/release-upload` in `Chummer.Run.Api/Controllers/PublicLandingController.cs`.
- Audit `ReleaseUploadAccessPolicy.cs`, which currently defaults access to `tibor.girschele@gmail.com` and optionally honors `CHUMMER_RELEASE_UPLOAD_ALLOWED_EMAILS`.
- Audit `/downloads/release-upload/bootstrap.sh` and the digest-pinned bootstrap command builder in `PublicLandingController`.
- Audit `.github/workflows/desktop-downloads-matrix.yml` in `chummer6-ui`, which still supports manual `workflow_dispatch` and macOS matrix builds.

What must not break:
- Tibor can still sign in, open `/downloads/release-upload`, mint a short-lived handoff code, and copy one digest-pinned command.
- The bootstrap still exports `CHUMMER_RELEASE_UPLOAD_TICKET` or the configured token path without leaking secrets into shared logs.
- macOS builds still flow through the current `osx-arm64` desktop artifact lane and upload to `/api/internal/releases/bundles`.
- The manual `workflow_dispatch` path in `desktop-downloads-matrix.yml` remains callable.

What can be improved safely:
- The operator surface can be visually restyled and folded into a darker release-ops shell.
- The release-upload page can gain clearer preflight, cleanup, and receipt visualization.
- The workflow name can gain friendlier labels only if the existing workflow file and entry points stay backward-compatible.

How backward compatibility is preserved:
- Keep `/downloads/release-upload`, `/downloads/release-upload/bootstrap.sh`, and `/downloads/release-upload/bootstrap.command`.
- Keep `ReleaseUploadAccessPolicy` semantics and the default Tibor email fallback.
- Keep `CHUMMER_RELEASE_UPLOAD_TICKET` and `CHUMMER_RELEASE_UPLOAD_TOKEN`.
- Keep the current GitHub workflow filename or leave a compatibility alias if a future split becomes necessary.

What receipt, test, and evidence must prove it still works:
- `ReleaseUploadAccessPolicyTests`
- `PublicLandingMacBootstrapScriptTests`
- `VerificationEntryPointTests`
- One authenticated operator screenshot of the release-upload page after redesign
- One successful dry-run bootstrap digest verification
- One successful upload-session receipt against `/api/internal/releases/bundles`
- One updated release-channel proof row for the macOS tuple after a real run

## 13. LTD UTILIZATION MAP

### 1min.AI
- Current observed tier and truth: Tier 1, locally wired key rotation and active credit posture in `EA/LTDs.md`.
- Role in redesign: primary raster-generation lane for flagship hero art, supporting stills, and controlled variants.
- Live now, staged next, or future seam: live now.
- Exact productive implementation target: landing art family, proof still family, artifact shelf stills, and mobile-safe crops via `chummer-media-factory`.
- Dependencies: media recipe registry, prompt governance, asset review, output derivative pipeline.
- What must be verified: consistent prompt family, safe-crop compliance, master PNG plus AVIF and WebP derivatives.
- Files, routes, workflows touched: `PUBLIC_MEDIA_BRIEFS.yaml`, `PUBLIC_LANDING_ASSET_REGISTRY.yaml`, `chummer-media-factory` asset recipes, homepage and route shelf assets.
- Receipts and tests: generated asset manifest, crop check, reviewer signoff, route screenshots.

### BrowserAct
- Current observed tier and truth: Tier 1, live inventory and capture lane; direct connector was not exposed in this Codex session.
- Role in redesign: route capture, staged account verification, interface diffing, ProductLift/Emailit/Documentation.AI account-truth checks.
- Live now, staged next, or future seam: live now.
- Exact productive implementation target: prelaunch route audit packets and external-account verification playbooks.
- Dependencies: connector binding, capture templates, receipt archival.
- What must be verified: route screenshots, ProductLift account state, MetaSurvey board state, Documentation.AI account readiness.
- Files, routes, workflows touched: launch QA workflow, LTD verification runbooks, route audit packets.
- Receipts and tests: BrowserAct capture artifacts, dated route diffs, linked QA packet.

### Emailit
- Current observed tier and truth: Tier 1, verified `chummer.run` sender domain and live API key.
- Role in redesign: install handoff mail, support confirmation, ProductLift closeout mail, release-update follow-up, roadmap-follow notifications.
- Live now, staged next, or future seam: live now.
- Exact productive implementation target: Hub-owned outbound lifecycle templates for install, support, roadmap follow, and voter closeout.
- Dependencies: template registry, consent and suppression mirroring, source event mapping.
- What must be verified: sender domain auth, template versions, delivery receipts, unsubscribe behavior for non-transactional mail.
- Files, routes, workflows touched: `EMAILIT_OUTBOUND_DELIVERY_PROVIDER.md`, Hub notification adapter, `/signup`, `/downloads`, `/feedback`, `/roadmap`, `/account/support`.
- Receipts and tests: `EmailDeliveryReceipt`, webhook verification, template smoke tests, closeout proof.

### AI Magicx
- Current observed tier and truth: Tier 1, bounded overflow and short-form support lane.
- Role in redesign: copy variant exploration, support reply drafting, overflow public-content assistance under approval.
- Live now, staged next, or future seam: live now as a bounded helper.
- Exact productive implementation target: alternate hero copy, help/FAQ clarifiers, support-response helper pack.
- Dependencies: prompt and copy boundaries, human review, canon source packets.
- What must be verified: no unsupported claims, no provider leakage into public copy, human review before publish.
- Files, routes, workflows touched: copy review packets, help and support knowledge workflows.
- Receipts and tests: approved source packet, reviewed output diff, publication approval.

### Prompting Systems
- Current observed tier and truth: Tier 2, staged prompt and style helper with legacy hooks.
- Role in redesign: visual-director prompt governance, copy-voice discipline, image prompt refinement.
- Live now, staged next, or future seam: staged next.
- Exact productive implementation target: one reusable public-surface prompt pack for hero art, proof stills, and concise premium copy.
- Dependencies: prompt library, style review rules, media recipes.
- What must be verified: prompt family consistency and copy-voice adherence.
- Files, routes, workflows touched: media prompt packs, copy-review SOPs, asset-generation recipes.
- Receipts and tests: prompt packet versioning, review approval, asset-family consistency review.

### ApproveThis
- Current observed tier and truth: Tier 2, BrowserAct-readable approval queue support.
- Role in redesign: signoff lane for flagship art, launch copy, release go or no-go, and publish approvals.
- Live now, staged next, or future seam: staged next.
- Exact productive implementation target: approval packets for hero family, homepage publish, ProductLift status promotions, and public email templates.
- Dependencies: approval templates, external-review routing, mirrored decisions in Hub or Fleet.
- What must be verified: approval result mirrored to Chummer-owned receipt.
- Files, routes, workflows touched: launch runbooks, media approvals, ProductLift status transitions.
- Receipts and tests: approval receipt, mirrored decision packet, publish log.

### MetaSurvey
- Current observed tier and truth: Tier 2, activated with staged extraction support.
- Role in redesign: post-signup, post-install, post-support, and post-release usefulness measurement.
- Live now, staged next, or future seam: staged next.
- Exact productive implementation target: four bounded surveys tied to account creation, successful install, support closure, and shipped feature closeout.
- Dependencies: survey templates, Hub event triggers, consent posture, response ingestion.
- What must be verified: responses map to a `JourneyProofEventRef` and feed Fleet clustering.
- Files, routes, workflows touched: `/signup`, `/downloads`, `/account/support`, Emailit closeout flows, signal OODA loop.
- Receipts and tests: survey invite receipts, response ingestion receipts, dashboard proof.

### ProductLift.dev
- Current observed tier and truth: Tier 4, credentialed but not yet production-real in local runtime.
- Role in redesign: public feedback intake, voting, roadmap projection, changelog projection, and shipped-voter closeout.
- Live now, staged next, or future seam: staged next with immediate promotion target.
- Exact productive implementation target: `/feedback`, `/roadmap`, `/changelog` backed by mirrored read models and webhook ingestion.
- Dependencies: domain split, ProductLift API or webhook wiring, design-triage taxonomy, Hub mirroring, Emailit closeout.
- What must be verified: category mapping, public/private boundary copy, shipped status only after evidence.
- Files, routes, workflows touched: `PUBLIC_GROWTH_AND_VISIBILITY_STACK.md`, `FEEDBACK_AND_SIGNAL_OODA_LOOP.md`, public signal routes in `chummer.run-services`, Hub ingestion services, Fleet digest packets.
- Receipts and tests: webhook receipts, mirrored signal records, triage packet creation, shipped closeout proof, route screenshots.

### Documentation.AI
- Current observed tier and truth: Tier 4, credentialed and owned but not yet wired into productive docs publishing.
- Role in redesign: future-quality docs/help/public-guide projection layer.
- Live now, staged next, or future seam: staged next.
- Exact productive implementation target: help and guide publishing, cited assistant answers, docs freshness checks, `llms.txt`.
- Dependencies: site allocation, source sync, canon packet export, reviewer workflow.
- What must be verified: freshness, citation linkage, first-party fallback behavior.
- Files, routes, workflows touched: `/help`, `/faq`, public guide pages, docs export pipeline.
- Receipts and tests: docs sync receipt, freshness check, sample published guide, citation audit.

### Mootion
- Current observed tier and truth: Tier 2, scaffold-stage video generation lane.
- Role in redesign: teaser loops, social launch cuts, and micro-motion studies only after the still-image family is locked.
- Live now, staged next, or future seam: staged next.
- Exact productive implementation target: short social trailers for release, roadmap, and artifact promotion.
- Dependencies: approved still frames, script packets, sound or caption plan.
- What must be verified: brand consistency, no unsupported claims, export quality.
- Files, routes, workflows touched: public growth stack, media-factory teaser workflow, social closeout runbooks.
- Receipts and tests: motion storyboard, exported teaser, approval receipt.

### AvoMap
- Current observed tier and truth: Tier 2, staged integration with redeemed codes.
- Role in redesign: spatial route overlays and environmental storytelling where campaign navigation is genuinely useful.
- Live now, staged next, or future seam: staged next.
- Exact productive implementation target: future `/artifacts` location overlays, runsite route cards, campaign geography storytelling.
- Dependencies: place data, route packets, media-factory integration.
- What must be verified: location overlays stay useful and not gimmicky.
- Files, routes, workflows touched: future runsite or artifact routes, media briefs, map-backed artifact cards.
- Receipts and tests: route visualization mock, approved location proof, map render receipt.

### FineTuning.ai
- Current observed tier and truth: Tier 4, credentialed but not yet wired into a productive media lane.
- Role in redesign: sonic cue packs and teaser audio support for launch media.
- Live now, staged next, or future seam: future seam.
- Exact productive implementation target: bounded media-factory soundtrack and cue support for teaser loops and recap outputs.
- Dependencies: provider adapter, cue receipt model, media-factory smoke run.
- What must be verified: first cue render, approval loop, no fake live pipeline claims.
- Files, routes, workflows touched: media-factory audio workflow, teaser packages, recap artifact support.
- Receipts and tests: cue receipt stub, first smoke-run export, approval packet.

## 14. PRODUCTLIFT IMPLEMENTATION PACKAGE

Public entry points:
- `/feedback` for public ideas and safe public bugs
- `/roadmap` for public direction and planned-state projection
- `/changelog` for shipped closeout and voter follow-through
- Secondary entry points from homepage signal band, `/participate`, `/downloads`, `/now`, `/help`, and `/account`

Roadmap and changelog projection behavior:
- ProductLift may supply item status, reaction counts, and public discussion.
- Hub and Fleet remain the source of triage state, proof linkage, and public-safe boundary copy.
- A ProductLift item can only appear as `shipped` on `changelog` after release, guide, route, artifact, or closeout proof exists.

Feedback and voting surfaces:
- Public feedback accepts feature requests, UX friction, safe public bugs, and documentation gaps.
- Boundary copy rejects crashes, installs, account recovery, private campaign details, copyrighted source payloads, and logs.
- Votes inform demand, not roadmap authority.

Account-aware behavior:
- Guest posting stays possible on the public lane.
- Signed-in users may get prefilled display name and email, link-back to their Hub account, and Emailit follow-up eligibility.
- No ProductLift surface becomes the place to manage support history, installs, or account state.

Webhook and API ingestion:
- Preferred domain split: `signal.chummer.run` hosts the ProductLift service edge, while `chummer.run/feedback`, `/roadmap`, and `/changelog` remain first-party reverse-proxy or mirrored render surfaces.
- Required event families: idea created, idea updated, vote created, vote removed, status changed, comment created.
- Required mirror objects: `PublicSignalReceipt`, `PublicSignalCategoryRef`, `PublicSignalEvidenceLink`, `PublicSignalCloseoutReceipt`.
- Ingestion lands in Hub. Fleet consumes clustered packets, not raw vendor rows.

Design-triage mapping:
- Category `rules_explain` routes to Rules Navigator and Core
- Category `build_flow` routes to Build Lab and UI
- Category `campaign_continuity` routes to Campaign OS lanes
- Category `downloads_install` routes to downloads and install-linking triage, not ProductLift closure
- Category `help_copy` routes to docs/help and Documentation.AI
- Category `publication_artifacts` routes to artifact/publication lanes
- Category `public_route_quality` routes to front-door design triage

Canonical-boundary rules:
- ProductLift never owns roadmap truth, support truth, release truth, install truth, or canon truth.
- Every accepted public signal must map to a Chummer-owned packet before it influences milestones or customer claims.
- Every shipped closeout must cite first-party proof.

Rollout order:
1. Keep first-party fallback routes alive.
2. Build Hub mirroring and boundary copy.
3. Turn on ProductLift projection for `/feedback`.
4. Turn on mirrored roadmap projection for `/roadmap`.
5. Turn on shipped closeout bridge for `/changelog`.
6. Add Emailit voter and follower loops.
7. Add MetaSurvey usefulness follow-up.

What gets built now:
- Route redesign and boundary copy
- ProductLift mirror data model
- Webhook ingestion
- Triage taxonomy mapping
- Emailit closeout template family

What gets built next:
- Signed-in convenience features
- MetaSurvey follow-up loop
- Public analytics and JourneyProof linkage
- richer changelog proof cards

How this becomes a real operating loop:
- Public signal enters ProductLift
- Hub mirrors it immediately
- Fleet clusters it into one packet
- Product Governor decides route
- Accepted work attaches to milestone, horizon, or docs lane
- Shipped work emits proof
- Emailit closes the loop to voters and followers
- MetaSurvey measures whether the closeout helped

## 15. DEVELOPER HANDOFF

Priorities in order:
1. Replace the public token system and shell chrome with the dark flagship language.
2. Rebuild `/`, `/downloads`, `/what-is-chummer`, and `/now` as one coherent public system.
3. Rebuild `/signup`, `/login`, `/home`, and `/account` so account value and continuity feel premium and calm.
4. Make `/feedback`, `/roadmap`, and `/changelog` product-real through first-party shells and ProductLift mirroring.
5. Rebuild help, FAQ, privacy, terms, and contact on the calmer trust-doc template.

Reusable components:
- `FlagshipHero`
- `InstallShelf`
- `ProofCard`
- `RoleFitCard`
- `ContinuityBand`
- `StatusStrip`
- `ArtifactShelfCard`
- `SignalBoundaryRow`
- `SignedInCockpitCard`
- `DeviceRoleRail`

Page templates:
- flagship acquisition page
- acquisition and install page
- truth and readiness page
- horizon and roadmap page
- proof shelf page
- trust document page
- signed-in cockpit page
- account rail page

Token system changes:
- semantic dark surface tokens
- stronger display typography tokens
- proof-specific border and glow tokens
- signed-in rail tokens separate from public marketing emphasis

Responsive breakpoints:
- 360
- 480
- 768
- 1024
- 1280
- 1440

Image specs:
- Hero master: 2400x1350 PNG plus AVIF and WebP
- Secondary stills: 2000x1125 PNG plus derivatives
- Artifact cards: 1600x1000 PNG plus derivatives
- Mobile crops must preserve center-safe action zone

Screenshot specs:
- Product proof shots: 1600x1000 source capture
- Device continuity shots: desktop plus tablet crops
- Always pair screenshot with one sentence of proof context

Design QA checklist:
- one dominant CTA per route
- no repeated trust pulse block on every page
- no light-theme regressions on flagship public routes
- no route-level proof contradicts downloads or help
- account value is visible before auth choice
- participation never outranks support for customer help

Accessibility checklist:
- keyboard path through header, primary CTA, install shelf, and support routes
- visible focus on every CTA and card action
- contrast verified for dark surfaces and muted copy
- no proof only inside hover or image text
- mobile targets at least 44 by 44

Performance checklist:
- hero art under budget with AVIF and WebP
- no autoplay video on the front door
- limited font payload and preconnect discipline
- lazy-load lower-page imagery
- avoid stacking too many translucent layers

Rollout plan:
- Phase 0: land Fleet package, tokens, and asset brief
- Phase 1: rebuild `/`, `/downloads`, `/what-is-chummer`, `/now`
- Phase 2: rebuild `/signup`, `/login`, `/home`, `/account`
- Phase 3: rebuild `/participate`, `/feedback`, `/roadmap`, `/changelog`
- Phase 4: rebuild trust and help routes
- Phase 5: wire Emailit, ProductLift, MetaSurvey, Documentation.AI lanes
- Phase 6: produce launch stills, QA captures, and approval packets

## 16. IF CODING IS ENABLED IN THIS RUN

Best repos for the first implementation slice:
- Primary UI and route work: `/docker/chummercomplete/chummer.run-services`
- Canon and rollout authority: `/docker/fleet`
- Asset execution if needed: `/docker/fleet/repos/chummer-media-factory`
- Release metadata only if required by the new downloads shelf: `/docker/chummercomplete/chummer-hub-registry`

First patch set proposal:
- Patch A: replace public token layer and shared shell chrome in `Chummer.Run.Api/wwwroot/css/site.css` and shared layout partials.
- Patch B: rebuild `Landing.cshtml`, `Downloads.cshtml`, `ProductStory.cshtml`, and `Now.cshtml` around the new flagship acquisition, proof, and continuity grammar.
- Patch C: rebuild `Signup` and `Login` auth shells so account value is visible before provider choice.
- Patch D: simplify `Home.cshtml` and `Account.cshtml` into cockpit plus access-rail posture, without dropping current continuity data.
- Patch E: split ProductLift-facing first-party routes into differentiated `/feedback`, `/roadmap`, and `/changelog` shells with mirrored placeholders that honor current fallback truth.

Non-negotiable safeguards before code lands:
- Keep all current auth and install-linking routes stable.
- Preserve the same binary-for-everyone posture.
- Keep the first-run guest and link-this-copy choices.
- Keep Devices and access discoverable and useful.
- Keep `/downloads/release-upload` and the Tibor access contract untouched unless a compatibility wrapper ships with it.

Highest-leverage implementation start:
- Start in `chummer.run-services` with the public token layer and page-shell layout, because that changes every customer route at once without touching auth, install-linking, or release registry contracts.
- Treat `Landing`, `Downloads`, and `Home` as the first visible proof of the redesign.
- Leave deeper Hub, registry, and workflow changes behind feature-preserving seams until the surface language is stable.

Truth and maturity rule for the code slice:
- Do not promote any lane as flagship, live, or signed if the existing route truth does not already support it.
- Use real current proof, real current limitations, and real current fallback language only.
