# Current Working Betslip Link Version

## Decision

Keep the current working implementation.

Do not add another odds/deep-link provider yet.

The current version is good enough for MVP testing and edge-case validation.

---

## Current stack

```text
Betslip image
  -> Gemini OCR / vision extraction
  -> Extracted betslip JSON
  -> The Odds API event odds
  -> Outcome link / SID matching
  -> Sportsbook grouping
  -> FanDuel parlay adapter when possible
  -> Individual or partial links for other books
```

### Providers

| Responsibility | Provider |
|---|---|
| Image extraction | Gemini |
| Events, odds, links, SIDs | The Odds API |
| FanDuel parlay URL construction | Our adapter |
| Other sportsbook links | Use returned links only |

---

## What works now

### 1. Extracted JSON to sportsbook links

Command:

```bash
ODDS_API_KEY="your-key" npm run resolve:betslip -- --input examples/betslip-mlb-hr.json
```

This:

1. Reads extracted betslip JSON.
2. Finds matching events.
3. Fetches only needed event/market pairs from The Odds API.
4. Matches outcomes by player/team/market/side/point.
5. Groups matches by sportsbook.
6. Returns full, partial, or individual-link availability.

### 2. Image to sportsbook links

Command:

```bash
GEMINI_API_KEY="your-gemini-key" ODDS_API_KEY="your-odds-api-key" npm run resolve:betslip:image -- --image path/to/betslip.jpg
```

This:

1. Sends the image to Gemini.
2. Extracts structured betslip JSON.
3. Saves the extraction to:

   ```text
   output/extracted-betslip.json
   ```

4. Runs the sportsbook-link resolver.
5. Saves the final result to:

   ```text
   output/betslip-image-link-result.json
   ```

### 3. Live sample test

Command:

```bash
ODDS_API_KEY="your-key" npm run resolve:betslip:sample
```

This creates a small live MLB home-run sample from current Odds API data and runs it through the resolver.

---

## Current sportsbook behavior

### FanDuel

FanDuel is the only verified parlay adapter right now.

When The Odds API returns FanDuel outcome links like:

```text
https://sportsbook.fanduel.com/addToBetslip?marketId=...&selectionId=...
```

the resolver parses:

```text
marketId
selectionId
```

and builds:

```text
https://account.sportsbook.fanduel.com/sportsbook/addToBetslip
  ?marketId[0]=...
  &selectionId[0]=...
  &marketId[1]=...
  &selectionId[1]=...
```

### DraftKings

DraftKings often returns outcome-level links.

Current behavior:

```text
individual_links_only
```

No DraftKings parlay adapter is implemented yet.

### BetRivers

BetRivers often returns template links like:

```text
https://{state}.betrivers.com/?page=sportsbook#event/...?...|{wagerAmount}
```

Current behavior:

```text
individual_links_only
```

No BetRivers template adapter is implemented yet.

### BetMGM

BetMGM sometimes returns outcome-level links.

Current behavior:

```text
individual_links_only
```

No BetMGM parlay adapter is implemented yet.

### PrizePicks / DFS

PrizePicks can be resolved through:

```bash
--regions us_dfs
```

Current behavior:

```text
individual_links_only
```

No PrizePicks multi-pick adapter is implemented yet.

---

## Full vs partial behavior

The resolver separates complete availability from partial availability.

### Full parlay

Returned when:

1. A sportsbook matches every requested leg.
2. Every matched leg has an outcome-level link.
3. A verified adapter exists for that sportsbook.

Example:

```text
FanDuel matched 4/4 legs
status: ready_parlay
parlayUrl: present
```

### Partial parlay

Returned when:

1. A sportsbook matches at least two legs.
2. Those matched legs have outcome-level links.
3. A verified adapter exists for that sportsbook.
4. Not every requested leg was available.

Example:

```text
FanDuel matched 4/5 legs
status: partial_match
parlayUrl: present for the 4 matched legs
```

This should be labeled in the UI as a partial parlay, not the full original slip.

### Individual links only

Returned when:

1. A sportsbook has matched legs.
2. Outcome-level links exist.
3. No verified parlay adapter exists for that sportsbook.

Example:

```text
DraftKings matched 3/3 legs
status: individual_links_only
parlayUrl: null
individualLinks: present
```

### Event or market links only

Returned when the API only gives event-level or market-level links.

These should not be shown as exact betslip links.

### Unavailable

Returned when a book does not provide usable exact links.

---

## Edge-case results so far

Live tests were run from manually encoded extracted JSON fixtures.

| Fixture | Result |
|---|---|
| MLB HR parlay | BetRivers matched 4/4 or 3/4 depending slip |
| MLB batter hits | Multiple books matched partial slips |
| MLB moneyline + 1st inning totals | FanDuel produced full parlay URL |
| MLB moneyline + full-game total | FanDuel produced partial parlay URL |
| MLB alternate strikeouts | FanDuel produced full parlay URL; DraftKings returned individual links |
| PrizePicks fantasy/H+R+RBI | PrizePicks matched 6/6 with links |
| WNBA alternate points/rebounds | FanDuel produced full parlay URL; DraftKings returned individual links |

See:

```text
BETSLIP_EDGE_CASE_RESULTS.md
```

for full details.

---

## Why we are staying with this version

The current version is:

- cheap
- working
- testable
- provider-light
- easy to extend book by book

The alternatives researched were either:

- much more expensive,
- sales-gated,
- not clearly better for parlay links,
- or still required custom adapters.

So the current MVP path is:

```text
The Odds API + Gemini + our sportsbook adapters
```

not:

```text
SharpSports / betFINDER / SportsGameOdds / OpticOdds yet
```

---

## Current limitations

1. Chat-uploaded images were not exposed as local files in this test environment, so exact chat attachments could not be passed to Gemini directly.
2. FanDuel is the only verified parlay adapter.
3. Other books are individual-link only until adapters are verified.
4. Some books only return partial coverage.
5. The sportsbook may still reject a generated parlay because of eligibility, state, line movement, suspension, or account restrictions.
6. The app should never claim the bet is placed automatically.

---

## Recommended next steps later

Only after keeping this version stable:

1. Add local uploaded image fixtures and run Gemini extraction end to end.
2. Compare Gemini extraction output against expected JSON.
3. Add DraftKings adapter investigation.
4. Add BetRivers adapter investigation.
5. Add PrizePicks multi-pick adapter investigation.
6. Add UI labels for:

   ```text
   full parlay
   partial parlay
   individual links only
   event link only
   unavailable
   ```

7. Add automated fixture tests around `examples/*.json`.

---

## Final current-version summary

Use this implementation:

```text
Gemini OCR
  + The Odds API
  + FanDuel parlay adapter
  + individual/partial links for all other returned books
```

Do not add new providers yet.
