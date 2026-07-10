# Betslip Resolver Edge Case Results

Live tests run against The Odds API with the extracted JSON fixtures in `examples/`.

The chat images were not exposed as local files in the workspace, so these tests use manually encoded extracted JSON based on the visible screenshot text. The Gemini image command is wired and ready for local image files, but these specific chat attachments could not be passed to Gemini from this environment.

## Summary

| Fixture | Slip type | Result | Best sportsbook outcome |
|---|---|---|---|
| `examples/edge-hr-placed.json` | 4-leg MLB HR parlay | Partial | BetRivers matched 3/4 legs with outcome links |
| `examples/edge-batter-hits.json` | 6-leg MLB "record a hit" parlay | Partial | BetMGM, BetRivers, DraftKings, BetOnline each matched 4/6 legs |
| `examples/edge-game-lines.json` | 4-leg MLB moneyline + 1st inning totals parlay | Ready | FanDuel matched 4/4 and produced a parlay URL |
| `examples/edge-moneyline-total.json` | 5-leg MLB moneyline + full-game total parlay | Partial | Multiple books matched 4/5; full-game total leg did not complete |
| `examples/edge-alt-strikeouts.json` | 3-leg MLB alternate strikeouts parlay | Ready | FanDuel matched 3/3 and produced a parlay URL |
| `examples/edge-prizepicks-fantasy.json` | 6-leg MLB DFS fantasy/H+R+RBI slip | Ready | PrizePicks matched 6/6 with outcome links |
| `examples/edge-wnba-sgp.json` | WNBA SGP-style alternate points/rebounds slip | Ready | FanDuel matched 8/8 and produced a parlay URL; DraftKings matched 8/8 individual links |

## Notable findings

### FanDuel parlay construction works when links expose `marketId` and `selectionId`

The resolver successfully built FanDuel parlay URLs for:

- MLB moneyline + 1st inning totals.
- MLB alternate strikeouts.
- WNBA alternate points/rebounds.

This validates the adapter approach:

```text
outcome links -> parse marketId/selectionId -> indexed FanDuel addToBetslip URL
```

### DraftKings frequently returns outcome links but needs its own adapter

DraftKings returned complete individual outcome links for:

- MLB alternate strikeouts.
- WNBA alternate points/rebounds.

The resolver correctly classified these as `individual_links_only` because no tested DraftKings parlay builder exists yet.

### BetRivers returns template links

BetRivers often returned outcome-level links such as:

```text
https://{state}.betrivers.com/?page=sportsbook#event/...?...|{wagerAmount}
```

These are useful but require a BetRivers adapter that fills:

- `{state}`
- `{pickType}`
- `{wagerAmount}`

Until that format is verified, BetRivers should be treated as individual links only.

### Not every sportsbook supports every leg

Several slips returned partial matches. This confirms the product rule:

```text
Only show a sportsbook as a complete parlay option when it returns every requested leg.
```

Partial books should be shown separately or hidden behind "not fully available".

### DFS slips can resolve through `us_dfs`

The PrizePicks-style fixture resolved successfully with:

```text
--regions us_dfs
```

PrizePicks returned all 6 requested legs with outcome links.

### Non-player markets need different confidence scoring

Moneylines and totals do not have player names. The resolver was updated to score non-player markets using:

- market key
- side/outcome name
- point when applicable
- event/team context

This fixed game-line matching.

## Current limitations

1. Chat attachments are not locally available as image files, so end-to-end Gemini OCR could not be run on these exact screenshots in this environment.
2. FanDuel is the only implemented parlay URL adapter.
3. DraftKings, BetMGM, BetRivers, PrizePicks, and others currently return individual links unless/until a tested multi-selection adapter is added.
4. Same-game parlay acceptance is not guaranteed by URL construction; the sportsbook remains final authority.
5. The resolver does not yet model boost tokens, cashout state, settled/placed receipts, or sportsbook-specific account state.

## Recommended next adapter work

1. DraftKings parlay adapter.
2. BetRivers template-link adapter.
3. PrizePicks multi-selection link adapter, if supported.
4. BetMGM multi-selection adapter, if a stable format can be verified.

## Recommended next extraction work

1. Save uploaded chat/test images as local files and run:

   ```bash
   GEMINI_API_KEY="..." ODDS_API_KEY="..." npm run resolve:betslip:image -- --image path/to/slip.jpg
   ```

2. Compare `output/extracted-betslip.json` to the manually encoded fixtures.
3. Add correction rules for OCR mistakes.
4. Keep every new screenshot as a fixture with expected extracted JSON.
