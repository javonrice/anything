# Betting API experiments

Small TypeScript test utilities for validating sportsbook/player-prop workflows.

Current scripts:

- PropLine MLB link/SID probe.
- The Odds API betslip-to-sportsbook-link resolver.

## Setup

Requires Node.js 20+.

```bash
npm install
```

## Resolve a betslip to sportsbook links

The first working resolver accepts extracted betslip JSON. OCR/image extraction can feed this same shape later.

It reads The Odds API key from `ODDS_API_KEY` or `THE_ODDS_API_KEY`.

### Image to sportsbook links

This command sends a betslip screenshot to Gemini, saves the extracted JSON, then resolves sportsbook links through The Odds API.

macOS/Linux:

```bash
GEMINI_API_KEY="your-gemini-key" ODDS_API_KEY="your-odds-api-key" npm run resolve:betslip:image -- --image path/to/betslip.jpg
```

PowerShell:

```powershell
$env:GEMINI_API_KEY="your-gemini-key"; $env:ODDS_API_KEY="your-odds-api-key"; npm run resolve:betslip:image -- --image path/to/betslip.jpg
```

Outputs:

```text
output/extracted-betslip.json
output/betslip-image-link-result.json
```

### Extracted JSON to sportsbook links

macOS/Linux:

```bash
ODDS_API_KEY="your-key" npm run resolve:betslip -- --input examples/betslip-mlb-hr.json
```

PowerShell:

```powershell
$env:ODDS_API_KEY="your-key"; npm run resolve:betslip -- --input examples/betslip-mlb-hr.json
```

The command writes the full grouped result to:

```text
output/betslip-link-result.json
```

### Live sample mode

To spend a small number of credits and prove the live resolver path works without preparing an input file:

```bash
ODDS_API_KEY="your-key" npm run resolve:betslip:sample
```

This scans a few upcoming MLB events for `batter_home_runs`, builds a temporary extracted slip from current outcomes, then resolves that slip through the normal sportsbook grouping logic.

## PropLine link/SID probe

This older script checks whether PropLine itself returns sportsbook links/SIDs.

macOS/Linux:

```bash
PROPLINE_API_KEY="your-key" npm run test:links
```

PowerShell:

```powershell
$env:PROPLINE_API_KEY="your-key"; npm run test:links
```

## Scripts

- `npm run resolve:betslip:image` - extracts a betslip image with Gemini, then resolves sportsbook links through The Odds API.
- `npm run resolve:betslip` - resolves extracted betslip JSON through The Odds API, groups matching outcome links by sportsbook, and builds a FanDuel parlay URL when possible.
- `npm run resolve:betslip:sample` - creates a small live MLB home-run sample from The Odds API and runs it through the resolver.
- `npm run test:links` - fetches the next upcoming MLB event, requests pitcher/batter prop odds with `includeLinks=true` and `includeSids=true`, writes a redacted response to `output/propline-mlb-link-test.json`, and prints a link/SID support report.
- `npm run typecheck` - runs TypeScript type checking without emitting files.
