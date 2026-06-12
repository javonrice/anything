# MLB Stats Database — State of the Art

## Context
We're building our own internal SportRadar — a production-grade MLB stats database populated entirely from free sources. This becomes the source of truth for our capper system: every pick, every post, every edge we find gets backed by data we own and can query freely. **Scope: 2015–present** (last ~10 seasons). That's exactly where Statcast data begins, so we get the full modern analytics picture without wasted storage on pre-analytics-era stats.

---

## Data Sources (Free, Stable, Legal)

| Source | Data | Depth Used | Access |
|---|---|---|---|
| **MLB Stats API** | Live games, rosters, schedules, box scores, standings | 2015–live | REST, no auth, no official limits |
| **Baseball Savant (Statcast)** | Pitch-level: exit velo, spin rate, xBA, barrels, launch angle | 2015–live | REST via pybaseball, 25K rows/call |
| **Chadwick Bureau** | Player ID registry — maps IDs across all sources | 2015–present | CSV download, Open Data license |

> Lahman and Retrosheet are intentionally excluded — they cover pre-2015 data we don't need, and they add ETL complexity. MLB Stats API + Statcast gives us everything for the modern era.

**Primary libraries:** `pybaseball`, `mlb-statsapi` (Python wrappers)

---

## Database: Supabase (PostgreSQL)

**Why Supabase:**
- Already connected via MCP — can provision and migrate right now
- PostgreSQL = full SQL, window functions, CTEs — essential for baseball analytics
- Free tier handles our data volume comfortably
- Auto-REST API via PostgREST for downstream use
- Row-level security built in

---

## Schema Design

### Core Tables

```sql
-- Player registry (Chadwick as master ID, all source IDs cross-mapped)
players (
  player_id        TEXT PRIMARY KEY,  -- Chadwick person_key
  mlb_id           INTEGER,           -- MLB Stats API ID
  bbref_id         TEXT,              -- Baseball Reference slug
  fangraphs_id     TEXT,
  retrosheet_id    TEXT,
  first_name       TEXT,
  last_name        TEXT,
  birth_date       DATE,
  bats             CHAR(1),
  throws           CHAR(1),
  position         TEXT,
  debut_date       DATE
)

-- Teams (historical-aware — franchises move)
teams (
  team_id          TEXT PRIMARY KEY,
  mlb_id           INTEGER,
  name             TEXT,
  abbreviation     TEXT,
  city             TEXT,
  league           TEXT,
  division         TEXT,
  active_from      INTEGER,
  active_to        INTEGER
)

-- Games
games (
  game_pk          BIGINT PRIMARY KEY,  -- MLB Stats API game_pk
  game_date        DATE,
  season           INTEGER,
  home_team_id     TEXT REFERENCES teams,
  away_team_id     TEXT REFERENCES teams,
  venue            TEXT,
  home_score       INTEGER,
  away_score       INTEGER,
  innings          INTEGER,
  status           TEXT,               -- Final / Postponed / Suspended
  game_type        TEXT                -- R / P / D / L / W / F (regular/postseason etc)
)

-- Season batting stats (from Lahman + MLB Stats API)
batting_season (
  id               BIGSERIAL PRIMARY KEY,
  player_id        TEXT REFERENCES players,
  team_id          TEXT REFERENCES teams,
  season           INTEGER,
  games            INTEGER,
  pa               INTEGER,
  ab               INTEGER,
  h INTEGER, h2b INTEGER, h3b INTEGER, hr INTEGER,
  rbi INTEGER, r INTEGER, bb INTEGER, so INTEGER, hbp INTEGER, sf INTEGER,
  sb INTEGER, cs INTEGER,
  avg NUMERIC(5,3), obp NUMERIC(5,3), slg NUMERIC(5,3), ops NUMERIC(5,3),
  woba NUMERIC(5,3),
  UNIQUE(player_id, team_id, season)
)

-- Season pitching stats
pitching_season (
  id               BIGSERIAL PRIMARY KEY,
  player_id        TEXT REFERENCES players,
  team_id          TEXT REFERENCES teams,
  season           INTEGER,
  games            INTEGER,
  gs               INTEGER,
  ip               NUMERIC(6,1),
  h INTEGER, r INTEGER, er INTEGER, bb INTEGER, so INTEGER, hr INTEGER, hbp INTEGER,
  era NUMERIC(5,2), whip NUMERIC(5,3), k9 NUMERIC(5,2), bb9 NUMERIC(5,2),
  fip NUMERIC(5,2), xfip NUMERIC(5,2),
  UNIQUE(player_id, team_id, season)
)

-- Game-level batting lines (for recent form, streaks, matchup history)
batting_game (
  id               BIGSERIAL PRIMARY KEY,
  game_pk          BIGINT REFERENCES games,
  player_id        TEXT REFERENCES players,
  team_id          TEXT REFERENCES teams,
  game_date        DATE,
  ab INTEGER, h INTEGER, h2b INTEGER, h3b INTEGER, hr INTEGER,
  rbi INTEGER, r INTEGER, bb INTEGER, so INTEGER, hbp INTEGER, sb INTEGER,
  avg NUMERIC(5,3), obp NUMERIC(5,3), slg NUMERIC(5,3)
)

-- Game-level pitching lines
pitching_game (
  id               BIGSERIAL PRIMARY KEY,
  game_pk          BIGINT REFERENCES games,
  player_id        TEXT REFERENCES players,
  team_id          TEXT REFERENCES teams,
  game_date        DATE,
  ip NUMERIC(5,1),
  h INTEGER, r INTEGER, er INTEGER, bb INTEGER, so INTEGER, hr INTEGER,
  era_on_day NUMERIC(5,2),
  decision        CHAR(1)  -- W / L / S / H / BS / ND
)

-- Statcast pitch-level (2015+, ~3M rows/season — indexed heavily)
pitches (
  pitch_id         BIGSERIAL PRIMARY KEY,
  game_pk          BIGINT,
  game_date        DATE,
  batter_id        TEXT REFERENCES players,
  pitcher_id       TEXT REFERENCES players,
  inning           INTEGER,
  pitch_type       TEXT,
  release_speed    NUMERIC(5,1),
  spin_rate        INTEGER,
  pfx_x            NUMERIC(6,3),
  pfx_z            NUMERIC(6,3),
  plate_x          NUMERIC(6,3),
  plate_z          NUMERIC(6,3),
  launch_speed     NUMERIC(5,1),
  launch_angle     INTEGER,
  hit_distance     INTEGER,
  events           TEXT,    -- single, home_run, strikeout, etc.
  description      TEXT,    -- called_strike, ball, foul, hit_into_play
  zone             INTEGER,
  estimated_ba     NUMERIC(5,3),
  estimated_woba   NUMERIC(5,3),
  is_barrel        BOOLEAN
)

-- Aggregated Statcast metrics per player per season (query-friendly)
statcast_season (
  id               BIGSERIAL PRIMARY KEY,
  player_id        TEXT REFERENCES players,
  season           INTEGER,
  player_type      TEXT,  -- 'batter' or 'pitcher'
  avg_exit_velo    NUMERIC(5,1),
  max_exit_velo    NUMERIC(5,1),
  avg_launch_angle NUMERIC(5,1),
  barrel_rate      NUMERIC(5,3),
  hard_hit_rate    NUMERIC(5,3),
  xba              NUMERIC(5,3),
  xslg             NUMERIC(5,3),
  xwoba            NUMERIC(5,3),
  xera             NUMERIC(5,2),   -- pitchers
  whiff_rate       NUMERIC(5,3),   -- pitchers
  UNIQUE(player_id, season, player_type)
)

-- Situational splits (vs LHP/RHP, home/away, month, RISP, etc.)
splits (
  id               BIGSERIAL PRIMARY KEY,
  player_id        TEXT REFERENCES players,
  season           INTEGER,
  split_type       TEXT,   -- 'vs_lhp' | 'vs_rhp' | 'home' | 'away' | 'risp' | 'late_close'
  pa INTEGER, avg NUMERIC(5,3), obp NUMERIC(5,3), slg NUMERIC(5,3), ops NUMERIC(5,3),
  hr INTEGER, so INTEGER, bb INTEGER
)
```

### Key Indexes
```sql
CREATE INDEX idx_batting_game_player_date ON batting_game(player_id, game_date DESC);
CREATE INDEX idx_pitching_game_player_date ON pitching_game(player_id, game_date DESC);
CREATE INDEX idx_pitches_batter ON pitches(batter_id, game_date DESC);
CREATE INDEX idx_pitches_pitcher ON pitches(pitcher_id, game_date DESC);
CREATE INDEX idx_games_date ON games(game_date DESC);
CREATE INDEX idx_splits_player_season ON splits(player_id, season, split_type);
```

---

## Ingestion Pipeline (Python + GitHub Actions)

### Phase 1 — Historical Bootstrap (one-time, 2015–2024)
1. MLB Stats API → load all `players` active 2015–present, all `teams`, all `games` 2015–2024
2. MLB Stats API → load `batting_game` + `pitching_game` lines for every game 2015–2024
3. MLB Stats API → load `batting_season` + `pitching_season` aggregates per player per season
4. Baseball Savant via pybaseball → backfill `pitches` year by year 2015–2024 (25K rows/call, batched by month)
5. Aggregate `pitches` → populate `statcast_season` for all player/seasons
6. pybaseball splits endpoint → populate `splits` for 2015–2024
7. Chadwick register → cross-populate `mlb_id`, `bbref_id`, `fangraphs_id` on `players`

### Phase 2 — Daily Sync (GitHub Actions cron)
```
Schedule: 0 8 * * *  (8am UTC = ~4am ET, after last night's games finalize)
```
1. MLB Stats API → yesterday's `games`, `batting_game`, `pitching_game`
2. Baseball Savant → yesterday's `pitches` for completed games
3. Update rolling `statcast_season` aggregates

### Phase 3 — Weekly Refresh
- Pull updated season `batting_season` / `pitching_season` totals from MLB Stats API
- Refresh `splits` from pybaseball FanGraphs splits endpoint

### Scripts Structure
```
mlb_db/
  ingest/
    lahman_load.py        # one-time historical bootstrap
    statcast_backfill.py  # one-time 2015-2024 pitch data
    daily_games.py        # cron: last night's game lines
    daily_statcast.py     # cron: last night's pitches
    weekly_season.py      # cron: season stat totals + splits
  schema/
    001_core.sql          # players, teams, games
    002_stats.sql         # batting/pitching season + game
    003_statcast.sql      # pitches, statcast_season
    004_splits.sql        # splits
    005_indexes.sql
  config.py               # Supabase connection, API keys
```

---

## Example Power Queries

```sql
-- Last 10 games for a batter (recent form)
SELECT game_date, ab, h, hr, rbi, bb, so
FROM batting_game WHERE player_id = 'troutmi01'
ORDER BY game_date DESC LIMIT 10;

-- Batter vs pitcher career matchup history
SELECT COUNT(*) pa, AVG(estimated_ba) xba, SUM(CASE WHEN events='home_run' THEN 1 ELSE 0 END) hr
FROM pitches
WHERE batter_id = 'X' AND pitcher_id = 'Y';

-- Top barrel rate hitters this season
SELECT p.first_name, p.last_name, s.barrel_rate, s.xwoba
FROM statcast_season s JOIN players p USING(player_id)
WHERE s.season = 2025 AND s.player_type = 'batter'
ORDER BY s.barrel_rate DESC LIMIT 20;

-- Pitcher splits (vs LHB vs RHB this season)
SELECT split_type, pa, avg, ops, hr
FROM splits WHERE player_id = 'X' AND season = 2025;
```

---

## Implementation Order

1. **Provision Supabase project** (via MCP)
2. **Apply schema migrations** (SQL files via Supabase MCP `apply_migration`)
3. **Bootstrap players + teams + games** from MLB Stats API (2015–2024)
4. **Bootstrap game-level batting + pitching lines** (2015–2024)
5. **Statcast backfill 2015–2024** — year by year, batched by month
6. **Aggregate statcast_season + splits** from pitch data
7. **Chadwick ID cross-map** — link all source IDs on players table
8. **Daily GitHub Actions cron** — automated from here on

---

## Verification
- Query `players` count — expect ~1,500–2,000 active MLB players from 2015–present
- Query `batting_season` for a known player/season (e.g., Trout 2019) — validate stats match Baseball Savant
- Query `pitches` for a specific game — verify pitch count matches Baseball Savant game log
- Run the daily workflow manually — confirm yesterday's games populated correctly
- Test power queries: recent form, batter vs pitcher matchup history, barrel rate leaders
