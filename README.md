# PropLine MLB link/SID test

Small TypeScript script for checking whether the PropLine MLB event odds API returns sportsbook deep links or sportsbook-native IDs for player props.

## Setup

Requires Node.js 20+.

```bash
npm install
```

## Run

macOS/Linux:

```bash
PROPLINE_API_KEY="your-key" npm run test:links
```

PowerShell:

```powershell
$env:PROPLINE_API_KEY="your-key"; npm run test:links
```

## Scripts

- `npm run test:links` - fetches the next upcoming MLB event, requests pitcher/batter prop odds with `includeLinks=true` and `includeSids=true`, writes a redacted response to `output/propline-mlb-link-test.json`, and prints a link/SID support report.
- `npm run typecheck` - runs TypeScript type checking without emitting files.
