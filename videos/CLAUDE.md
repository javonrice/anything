# Video playbook

Short vertical videos (1080×1920, ~60s) selling automation systems to **med spa owners**.
The person talks in the bottom "camera zone"; the top shows what the system does.

## Locked decisions

- **Niche:** med spas only (owner-operators, often injectors).
- **Format: animated flowchart.** Every new video copies `medspa-01-flowchart/` as its template.
  Other styles (`medspa-01`, `-revenue`, `-split`, `-kinetic`, `-notify`) were tested and are archived.
- **Only pitch systems GoHighLevel can build natively**: workflows, calendars with deposits, Conversation AI,
  Voice AI, missed-call text-back, Instagram/FB DMs, reputation/review requests, smart lists, campaigns.
  Flag anything needing Zapier/Make or another tool. Never pitch review gating (sending only happy
  clients to Google); ask everyone for a review and alert the owner on low ratings.
- **Plain language on screen.** Show outcomes ("Booked on calendar"), never plumbing ("webhook → CRM").
- **Illustrative numbers** (names, prices, counts) are fine but must not be claimed as real client results.
- **CTA:** comment "SPA".

## Layout (do not change)

- Stage: top 0–1200px. Flowchart lives in `#world`, a large canvas the camera pans/zooms with GSAP.
- Camera zone: `#presenter`, 1200–1920px. Orb plus word-highlight captions as a placeholder until the user's
  own footage replaces the orb. Captions are built from `assets/words.json`.
- Flowchart grammar: red = pain path, rose glow = active step, green + check = done, amber = branch/edge case.
  Connectors draw on the spoken word; camera centers the active node; payoff zooms out to the whole map.

## Making the next video

1. Script: hook (pain, ~10s) → "here's what I build" → 1–3 systems → payoff → CTA. About 60s / ~180 words.
2. Voice: ElevenLabs `creative_generate_speech` (temp voice "Matt", `3iY0r3RaYmOh6WfIwMIH`, model `eleven_v4`)
   until the user records themselves. Download the take to `assets/voiceover.mp3`.
3. Timestamps: pin the take with `creative_add_flow_asset_node`, run `creative_transcribe_audio`
   (scribe), and save words as `[[text,start,end],…]` in `assets/words.json`. Local whisper cannot reach
   Hugging Face from this environment.
4. Copy `medspa-01-flowchart/` → `medspa-NN-<topic>/`. Edit `index.src`: the node map `N`, the lanes `LANES`,
   and the `timeline` section times (key everything to word start times). Update `meta.json` id.
5. `node build.mjs` (injects words.json into index.html) → `npx hyperframes check` (0 errors; structure /
   file-size / track-density warnings are accepted) → `npx hyperframes snapshot --at …` and look at the
   contact sheet → `npx hyperframes render -q standard -f 30 -o ../renders/<name>.mp4`.

## Gotchas

- GSAP and Inter are vendored in `assets/` (CDN is blocked in the render browser). No emoji font: use inline SVG.
- Keep only one root HTML file per project (`index.src` is the template, not `.html`).
- No `<br>`; no CSS `transform` on elements GSAP tweens (use `fromTo`); mark intentional overlaps with
  `data-layout-allow-overlap`.
- `renders/work-*` and `.hf-transaction*` are temp folders (gitignored).
