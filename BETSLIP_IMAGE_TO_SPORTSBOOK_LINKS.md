# Betslip Image to Sportsbook Links

## Goal

Convert a betslip screenshot into sportsbook-specific links that open the user's sportsbook app or website with the matching bet selections loaded when supported.

The feature should:

1. Accept a betslip image.
2. Extract the bet legs from the image.
3. Resolve those legs against live sportsbook odds.
4. Use only sportsbook links and IDs returned by the odds provider.
5. Group matched legs by sportsbook.
6. Produce a parlay link when every leg for a sportsbook can be combined.
7. Fall back to individual leg links when a parlay link cannot be safely built.
8. Never guess unavailable sportsbook links.

Headshots and player media are out of scope for this version.

---

## Non-goals

This version should not:

- Fetch player headshots.
- Build unsupported sportsbook URLs by guessing.
- Guarantee that a sportsbook will accept a parlay.
- Place bets automatically.
- Use stale links without click-time validation.
- Show books that did not return usable links for the requested bet.

The sportsbook remains the final source of truth. The user must review and place the bet inside the sportsbook.

---

## Recommended provider strategy

For this specific feature, The Odds API can be the primary provider.

### The Odds API responsibilities

- List current events.
- Return event-level player prop odds.
- Return bookmaker-level links when available.
- Return market-level links when available.
- Return outcome-level betslip links when available.
- Return source IDs / SIDs when available.

### Optional PropLine responsibilities

PropLine is not required for the first version of sportsbook link generation if The Odds API has the needed player prop coverage.

PropLine may still be useful later for:

- Cheaper broad discovery.
- Prop grading.
- Player history.
- Trends.
- Line movement.
- EV analysis.
- Game context.

For the MVP, avoid introducing a second odds provider unless The Odds API coverage is insufficient.

---

## High-level flow

```text
Betslip screenshot
        ↓
OCR / vision extraction
        ↓
Normalize extracted legs
        ↓
Find matching events in The Odds API
        ↓
Fetch event odds for only needed events and markets
        ↓
Match requested legs to returned outcomes
        ↓
Collect outcome-level links/SIDs by sportsbook
        ↓
Build sportsbook groups
        ↓
If supported, build parlay URL
        ↓
Return sportsbook link options to user
```

---

## Example input

A screenshot may contain:

```text
4-leg parlay

Ben Rice To Hit A Home Run +320
Seiya Suzuki To Hit A Home Run +340
Munetaka Murakami To Hit A Home Run +300
Kazuma Okamoto To Hit A Home Run +300
```

Normalize this to:

```json
{
  "betType": "parlay",
  "legs": [
    {
      "sportKey": "baseball_mlb",
      "player": "Ben Rice",
      "marketKey": "batter_home_runs",
      "side": "Over",
      "point": 0.5,
      "rawText": "Ben Rice To Hit A Home Run"
    },
    {
      "sportKey": "baseball_mlb",
      "player": "Seiya Suzuki",
      "marketKey": "batter_home_runs",
      "side": "Over",
      "point": 0.5,
      "rawText": "Seiya Suzuki To Hit A Home Run"
    }
  ]
}
```

---

## Core data models

### Extracted slip

```ts
type ExtractedSlip = {
  betType: "single" | "parlay" | "same_game_parlay" | "unknown";
  sportKey?: string;
  legs: ExtractedLeg[];
};
```

### Extracted leg

```ts
type ExtractedLeg = {
  sportKey?: string;
  eventId?: string;
  player?: string;
  team?: string;
  opponent?: string;
  marketKey?: string;
  side?: "Over" | "Under" | "Yes" | "No" | string;
  point?: number | null;
  price?: number | null;
  commenceTimeHint?: string | null;
  rawText: string;
};
```

### Normalized event

```ts
type NormalizedEvent = {
  provider: "the_odds_api";
  sportKey: string;
  eventId: string;
  homeTeam: string;
  awayTeam: string;
  commenceTime: string;
};
```

### Normalized outcome

```ts
type NormalizedOutcome = {
  provider: "the_odds_api";
  sportKey: string;
  eventId: string;
  homeTeam: string;
  awayTeam: string;
  commenceTime: string;
  bookmakerKey: string;
  bookmakerTitle: string;
  marketKey: string;
  player: string | null;
  side: string;
  point: number | null;
  price: number;
  link: string | null;
  sid: string | null;
  linkLevel: "outcome" | "market" | "event" | "none";
};
```

### Sportsbook group

```ts
type SportsbookGroup = {
  sportsbookKey: string;
  sportsbookTitle: string;
  requestedLegCount: number;
  matchedLegs: MatchedLeg[];
  allLegsMatched: boolean;
  allLegsHaveOutcomeLinks: boolean;
  canBuildParlay: boolean;
  parlayUrl: string | null;
  individualLinks: string[];
  status:
    | "ready_parlay"
    | "individual_links_only"
    | "partial_match"
    | "event_or_market_links_only"
    | "unavailable";
};
```

### Matched leg

```ts
type MatchedLeg = {
  extractedLeg: ExtractedLeg;
  outcome: NormalizedOutcome;
  confidence: number;
  matchReasons: string[];
};
```

---

## The Odds API calls

### 1. List events

Use the events endpoint to discover upcoming events.

```text
GET /v4/sports/{sportKey}/events
```

For MLB:

```text
GET /v4/sports/baseball_mlb/events
```

Cache this response briefly because event lists do not need to be fetched for every leg.

Suggested cache:

```text
2-10 minutes
```

### 2. Fetch event odds with links and SIDs

Player props must be fetched one event at a time.

```text
GET /v4/sports/{sportKey}/events/{eventId}/odds
  ?regions=us
  &markets={marketKeys}
  &oddsFormat=american
  &includeLinks=true
  &includeSids=true
```

Example:

```text
GET /v4/sports/baseball_mlb/events/{eventId}/odds
  ?regions=us
  &markets=batter_home_runs
  &oddsFormat=american
  &includeLinks=true
  &includeSids=true
```

If specific bookmakers are desired, use `bookmakers=` instead of `regions=`.

However, for the first version, using `regions=us` is often better because the product should show whichever books actually return usable links.

---

## Credit usage model

The Odds API charges live odds requests roughly as:

```text
credits = number of markets * number of regions
```

For this feature:

```text
credits per slip ~= number of unique event/market pairs
```

Examples:

| Slip | Unique events | Unique markets per event | Approx credits |
|---|---:|---:|---:|
| 1 HR leg | 1 | 1 | 1 |
| 4 HR legs, same game | 1 | 1 | 1 |
| 4 HR legs, 4 games | 4 | 1 | 4 |
| 4 mixed props, 4 games | 4 | up to 4 | up to 16 |
| 8 HR legs, 8 games | 8 | 1 | 8 |

With 20,000 credits/month, a normal 4-leg HR slip across four games costs about 4 credits.

That supports roughly:

```text
20,000 / 4 = 5,000 similar slips per month
```

The product should minimize usage by:

- Caching event lists.
- Querying only needed events.
- Querying only needed markets.
- Combining markets in one request per event when needed.
- Avoiding blind all-book/all-market scans.

---

## Market normalization

The image text must be mapped to API market keys.

Examples:

| Screenshot text | Normalized market | Side | Point |
|---|---|---|---:|
| To Hit A Home Run | `batter_home_runs` | Over | 0.5 |
| Over 0.5 Home Runs | `batter_home_runs` | Over | 0.5 |
| 1+ Home Runs | `batter_home_runs` | Over | 0.5 |
| Batter Hits | `batter_hits` | Over/Under | from text |
| Total Bases | `batter_total_bases` | Over/Under | from text |
| Pitcher Strikeouts | `pitcher_strikeouts` | Over/Under | from text |

For home runs, treat these as equivalent:

```text
To Hit A Home Run
Over 0.5 Home Runs
1+ Home Runs
```

Some books/providers may return:

```json
{
  "name": "Over",
  "description": "Ben Rice",
  "point": 0.5
}
```

Others may return:

```json
{
  "name": "1+ Home Runs",
  "description": "Ben Rice",
  "point": null
}
```

The matcher should treat both as the same requested leg when the market is `batter_home_runs`.

---

## Team and event matching

Do not depend only on player names. Use as much context as available from the image.

Possible image clues:

- Player name.
- Team abbreviation.
- Opponent abbreviation.
- Game time.
- Market text.
- Price.

Recommended matching order:

1. Sport.
2. Team/opponent if visible.
3. Player name.
4. Market.
5. Side.
6. Point.
7. Approximate commence time.

### Team alias table

Maintain a local team alias table.

Example:

```ts
const MLB_TEAM_ALIASES = {
  NYY: ["New York Yankees", "Yankees"],
  WSH: ["Washington Nationals", "Nationals"],
  CHC: ["Chicago Cubs", "Cubs"],
  CIN: ["Cincinnati Reds", "Reds"],
  ATH: ["Athletics", "Oakland Athletics"],
  CWS: ["Chicago White Sox", "White Sox"],
  TOR: ["Toronto Blue Jays", "Blue Jays"],
  SD: ["San Diego Padres", "Padres"]
};
```

### Event matching function

```ts
function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function teamsMatch(
  extractedTeam: string | undefined,
  apiTeam: string,
  aliases: Record<string, string[]>,
): boolean {
  if (!extractedTeam) return false;

  const normalizedExtracted = normalizeText(extractedTeam);
  const normalizedApiTeam = normalizeText(apiTeam);

  if (normalizedExtracted === normalizedApiTeam) return true;

  const aliasValues = aliases[extractedTeam.toUpperCase()] ?? [];
  return aliasValues.some((alias) => normalizeText(alias) === normalizedApiTeam);
}
```

If the image provides both teams, match the API event where the same two teams appear, regardless of whether the screenshot lists the away/home order clearly.

---

## Outcome matching

Once event odds are fetched, normalize outcomes.

Player prop outcomes generally look like:

```json
{
  "name": "Over",
  "description": "Ben Rice",
  "price": 320,
  "point": 0.5,
  "link": "https://sportsbook.example.com/...",
  "sid": "..."
}
```

Match a requested leg to an outcome using:

```text
bookmaker: any returned bookmaker
market: exact normalized market key
player: normalized player name
side: normalized side
point: equal or equivalent
```

For point matching:

```ts
function pointsEquivalent(
  requestedMarket: string,
  requestedPoint: number | null | undefined,
  apiPoint: number | null,
  apiOutcomeName: string,
): boolean {
  if (requestedMarket === "batter_home_runs") {
    if (requestedPoint === 0.5 && apiPoint === 0.5) return true;
    if (requestedPoint === 0.5 && /1\+|home run/i.test(apiOutcomeName)) return true;
  }

  if (requestedPoint == null && apiPoint == null) return true;
  if (requestedPoint == null || apiPoint == null) return false;

  return Math.abs(requestedPoint - apiPoint) < 0.001;
}
```

---

## Link levels

The Odds API can return links at different levels.

### Outcome-level link

This is the best case.

```json
{
  "name": "Over",
  "description": "Ben Rice",
  "point": 0.5,
  "link": "https://sportsbook.../addToBetslip?...",
  "sid": "..."
}
```

This can be treated as an exact selection link.

### Market-level link

This may open a market page but not select the exact bet.

Do not call this an exact betslip link.

### Event-level link

This may open the event page only.

Do not call this an exact betslip link.

### No link

Do not show the book as placeable for this leg.

---

## Sportsbook grouping

After all legs are matched, group by bookmaker.

Example:

```json
{
  "fanduel": [
    "Ben Rice HR Over 0.5",
    "Seiya Suzuki HR Over 0.5",
    "Munetaka Murakami HR Over 0.5",
    "Kazuma Okamoto HR Over 0.5"
  ],
  "draftkings": [
    "Ben Rice HR Over 0.5",
    "Seiya Suzuki HR Over 0.5"
  ]
}
```

Rules:

1. If a sportsbook has all requested legs with outcome-level links, it is eligible for a parlay link if an adapter supports that book.
2. If a sportsbook has at least two matched legs with outcome-level links, it may receive a partial parlay link if an adapter supports that book.
3. If a sportsbook has all requested legs with outcome-level links but no tested parlay adapter, show individual links only.
4. If a sportsbook has only some legs, mark it as partial; include a partial parlay URL only when it is explicitly adapter-supported.
5. If a sportsbook has only market/event links, do not show it as an exact betslip option.
6. If a sportsbook has no usable links, do not show it.

---

## FanDuel adapter

FanDuel is the best first sportsbook adapter because outcome links commonly contain:

```text
marketId
selectionId
```

Example individual link:

```text
https://sportsbook.fanduel.com/addToBetslip?marketId=42.448600011&selectionId=29165
```

Parse safely:

```ts
type FanDuelSelection = {
  marketId: string;
  selectionId: string;
};

function parseFanDuelSelection(link: string): FanDuelSelection | null {
  try {
    const url = new URL(link);
    const marketId = url.searchParams.get("marketId");
    const selectionId = url.searchParams.get("selectionId");

    if (!marketId || !selectionId) {
      return null;
    }

    return { marketId, selectionId };
  } catch {
    return null;
  }
}
```

Build a multi-selection URL only when every leg has a parseable FanDuel selection.

```ts
function buildFanDuelParlayUrl(selections: FanDuelSelection[]): string {
  if (selections.length < 2) {
    throw new Error("A parlay requires at least two selections.");
  }

  const url = new URL(
    "https://account.sportsbook.fanduel.com/sportsbook/addToBetslip",
  );

  selections.forEach((selection, index) => {
    url.searchParams.set(`marketId[${index}]`, selection.marketId);
    url.searchParams.set(`selectionId[${index}]`, selection.selectionId);
  });

  return url.toString();
}
```

Important:

- This should live in a FanDuel-specific adapter.
- Do not use this URL pattern for other books.
- Keep this replaceable because sportsbook URL formats can change.

---

## Sportsbook adapter interface

```ts
interface SportsbookLinkBuilder {
  sportsbookKey: string;

  canBuildParlay(outcomes: NormalizedOutcome[]): boolean;

  createParlayLink(outcomes: NormalizedOutcome[]): string;
}
```

Suggested structure:

```text
sportsbook-link-builders/
  fanduel.ts
  draftkings.ts
  betmgm.ts
  fanatics.ts
```

Only add a sportsbook adapter after its URL format has been tested with real outcome links.

---

## Output shape

The API should return something like:

```json
{
  "status": "ready",
  "betType": "parlay",
  "requestedLegs": [
    {
      "player": "Ben Rice",
      "marketKey": "batter_home_runs",
      "side": "Over",
      "point": 0.5
    }
  ],
  "sportsbooks": [
    {
      "sportsbookKey": "fanduel",
      "sportsbookTitle": "FanDuel",
      "status": "ready_parlay",
      "matchedLegCount": 4,
      "requestedLegCount": 4,
      "parlayUrl": "https://account.sportsbook.fanduel.com/sportsbook/addToBetslip?...",
      "legs": [
        {
          "player": "Ben Rice",
          "marketKey": "batter_home_runs",
          "side": "Over",
          "point": 0.5,
          "price": 320,
          "linkLevel": "outcome",
          "link": "https://sportsbook.fanduel.com/addToBetslip?marketId=...&selectionId=...",
          "sid": "..."
        }
      ]
    },
    {
      "sportsbookKey": "draftkings",
      "sportsbookTitle": "DraftKings",
      "status": "individual_links_only",
      "matchedLegCount": 4,
      "requestedLegCount": 4,
      "parlayUrl": null,
      "individualLinks": [
        "https://sportsbook.draftkings.com/..."
      ]
    }
  ],
  "expiresAt": "2026-07-10T14:45:00Z"
}
```

---

## UI behavior

### Ready parlay

Show:

```text
Place 4-leg parlay on FanDuel
```

Only when:

- Every leg matched.
- Every leg has an outcome-level link.
- The sportsbook has a tested parlay adapter.
- The generated parlay URL was created successfully.

### Individual links only

Show:

```text
Open individual DraftKings legs
```

Only when:

- Every leg matched.
- Outcome-level links exist.
- No tested parlay builder exists for the book.

### Partial match

Show:

```text
DraftKings has 3 of 4 legs available
```

Do not show this as a complete parlay option. If a tested sportsbook adapter can build a link from the matched subset, label it clearly as a partial parlay, for example:

```text
Open 3-leg FanDuel parlay from matched legs
```

### Event or market links only

Show carefully:

```text
Open event on BetMGM
```

Do not say:

```text
Place bet on BetMGM
```

### Unavailable

Hide by default or show under an expandable unavailable section.

---

## Confidence scoring

Every matched leg should receive a confidence score.

Example:

```json
{
  "player": "Ben Rice",
  "confidence": 0.97,
  "matchReasons": [
    "exact_player_name",
    "market_alias_home_run",
    "team_match",
    "point_equivalent"
  ]
}
```

Suggested confidence tiers:

| Confidence | Meaning | Behavior |
|---:|---|---|
| 0.95-1.00 | Very strong | Auto-match |
| 0.85-0.94 | Strong | Auto-match with light warning |
| 0.70-0.84 | Ambiguous | Ask user to review |
| < 0.70 | Weak | Do not generate link |

Never generate a parlay link from weak matches.

---

## Expiration and freshness

Generated results should expire quickly.

Suggested expiration:

```text
2-5 minutes
```

Before opening or returning a final link, the backend should optionally refresh:

1. Re-fetch the event odds.
2. Confirm every outcome still exists.
3. Confirm every link/SID still exists.
4. Confirm player, market, side, and point still match.
5. Rebuild the sportsbook URL.

This avoids combining stale selections.

---

## Error cases

### No legs extracted

```json
{
  "status": "failed",
  "reason": "No bet legs could be extracted from the image."
}
```

### Unsupported sport

```json
{
  "status": "unsupported",
  "reason": "The extracted sport is not supported yet."
}
```

### Event not found

```json
{
  "status": "needs_review",
  "reason": "Could not confidently match one or more legs to an upcoming event."
}
```

### Outcome not found

```json
{
  "status": "partial",
  "reason": "One or more requested player props were not available in the odds response."
}
```

### No sportsbook links

```json
{
  "status": "no_links",
  "reason": "Matching odds were found, but no sportsbooks returned outcome-level links."
}
```

### Parlay not buildable

```json
{
  "status": "individual_links_only",
  "reason": "All legs have individual links, but this sportsbook does not have a tested parlay builder."
}
```

---

## Security rules

- Store API keys server-side only.
- Do not expose provider API keys to the browser.
- Do not log URLs that contain provider API keys.
- Redact any key-like fields in saved debug responses.
- Do not store generated sportsbook URLs longer than necessary.
- Do not auto-place bets.
- Make the user confirm inside the sportsbook.

---

## Testing plan

### Phase 1: Static extraction tests

Use saved screenshots and expected structured outputs.

For each image, assert:

- Number of legs.
- Player names.
- Market key.
- Side.
- Point.
- Team/opponent if visible.
- Bet type.

### Phase 2: Event matching tests

Use known event fixtures.

Assert:

- Extracted teams match the right API event.
- Time tolerance works.
- Team aliases work.
- Ambiguous matches are flagged.

### Phase 3: Outcome matching tests

Use saved The Odds API responses.

Assert:

- `To Hit A Home Run` matches `batter_home_runs`.
- `Over 0.5 Home Runs` matches `1+ Home Runs` where applicable.
- Player names match with normalization.
- Wrong players do not match.
- Wrong markets do not match.

### Phase 4: Link grouping tests

Use mocked odds responses.

Assert:

- Books with all legs are marked complete.
- Books with missing legs are partial.
- Outcome links outrank market links.
- Market/event links are not treated as exact betslip links.

### Phase 5: FanDuel URL tests

Use known FanDuel individual links.

Assert:

- `marketId` and `selectionId` parse correctly.
- Missing IDs fail safely.
- Multi-leg URL contains indexed params.
- Leg order is stable.

### Phase 6: Manual live validation

For each test slip:

1. Upload the image.
2. Review extracted legs.
3. Generate sportsbook options.
4. Open FanDuel link.
5. Confirm the sportsbook loads the expected selections.
6. Confirm the user still has to review and place manually.

Record:

- Image quality.
- Extracted legs.
- Matched events.
- Matched outcomes.
- Sportsbooks returned.
- Link levels.
- Whether the sportsbook accepted the parlay.

---

## MVP scope

Start narrow:

```text
Sport: MLB
Market: batter_home_runs
Bet type: parlay
Sportsbook adapter: FanDuel
Provider: The Odds API
```

MVP success criteria:

1. A clean MLB HR parlay screenshot extracts into structured legs.
2. Each leg is matched to the correct event and outcome.
3. FanDuel outcome links are found for every leg when available.
4. The FanDuel parlay URL is generated from returned `marketId` and `selectionId`.
5. The user can open the sportsbook and review the populated betslip.
6. Unsupported books are not shown as complete parlay options.

After this works, expand to:

1. DraftKings.
2. BetMGM.
3. Fanatics.
4. Other MLB markets.
5. NBA/NFL player props.
6. Same-game parlays.

---

## Final recommendation

Use The Odds API as the primary source for this feature.

The app should:

1. Extract legs from the betslip image.
2. Query only the events and markets needed.
3. Match outcomes by player, market, side, point, and event context.
4. Use only returned outcome-level sportsbook links/SIDs.
5. Group links by sportsbook.
6. Build a parlay URL only for books with a tested adapter.
7. Show individual links or partial availability when a full parlay is not safe.
8. Expire generated results quickly.

This gives the same practical user experience as QuickPick-style products while avoiding unsupported assumptions about sportsbook availability or URL formats.
