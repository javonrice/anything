import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type ExtractedSlip = {
  betType?: "single" | "parlay" | "same_game_parlay" | "unknown";
  sportKey?: string;
  legs: ExtractedLeg[];
};

export type ExtractedLeg = {
  eventId?: string;
  sportKey?: string;
  player?: string;
  team?: string;
  opponent?: string;
  marketKey?: string;
  side?: string;
  point?: number | null;
  price?: number | null;
  commenceTimeHint?: string | null;
  rawText: string;
};

type OddsApiEvent = {
  id: string;
  sport_key: string;
  sport_title?: string;
  commence_time: string;
  home_team: string;
  away_team: string;
};

type OddsApiOutcome = {
  name?: string;
  description?: string;
  price?: number;
  point?: number | null;
  link?: string | null;
  sid?: string | null;
};

type OddsApiMarket = {
  key?: string;
  last_update?: string;
  link?: string | null;
  sid?: string | null;
  outcomes?: OddsApiOutcome[];
};

type OddsApiBookmaker = {
  key?: string;
  title?: string;
  last_update?: string;
  link?: string | null;
  sid?: string | null;
  markets?: OddsApiMarket[];
};

type OddsApiEventOdds = OddsApiEvent & {
  bookmakers?: OddsApiBookmaker[];
};

type NormalizedOutcome = {
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

type MatchedLeg = {
  legIndex: number;
  extractedLeg: ExtractedLeg;
  outcome: NormalizedOutcome;
  confidence: number;
  matchReasons: string[];
};

type SportsbookGroup = {
  sportsbookKey: string;
  sportsbookTitle: string;
  requestedLegCount: number;
  matchedLegCount: number;
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
  legs: MatchedLeg[];
};

type ResolutionResult = {
  status: "ready" | "partial" | "no_matches" | "failed";
  betType: string;
  requestedLegs: ExtractedLeg[];
  unmatchedLegs: Array<{ legIndex: number; leg: ExtractedLeg; reason: string }>;
  sportsbooks: SportsbookGroup[];
  fetchedEvents: Array<{
    eventId: string;
    homeTeam: string;
    awayTeam: string;
    commenceTime: string;
    markets: string[];
  }>;
  apiUsage: ApiUsage[];
  expiresAt: string;
};

type ApiUsage = {
  endpoint: "events" | "event_odds";
  sportKey: string;
  eventId?: string;
  requestsLast?: string | null;
  requestsUsed?: string | null;
  requestsRemaining?: string | null;
};

export type CliOptions = {
  inputPath?: string;
  outputPath: string;
  regions: string;
  bookmakers?: string;
  sampleLive: boolean;
  sampleLegs: number;
  maxSampleEvents: number;
};

type FanDuelSelection = {
  marketId: string;
  selectionId: string;
};

type SportsbookParlayAdapter = {
  sportsbookKey: string;
  createParlayLink(matches: MatchedLeg[]): string | null;
};

const ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4";
const REQUEST_TIMEOUT_MS = 15_000;
const DEFAULT_OUTPUT_PATH = path.join("output", "betslip-link-result.json");
const DEFAULT_SPORT_KEY = "baseball_mlb";
const DEFAULT_MARKET_KEY = "batter_home_runs";

const MLB_TEAM_ALIASES: Record<string, string[]> = {
  ARI: ["Arizona Diamondbacks", "Diamondbacks"],
  ATH: ["Athletics", "Oakland Athletics", "A's"],
  ATL: ["Atlanta Braves", "Braves"],
  BAL: ["Baltimore Orioles", "Orioles"],
  BOS: ["Boston Red Sox", "Red Sox"],
  CHC: ["Chicago Cubs", "Cubs"],
  CWS: ["Chicago White Sox", "White Sox"],
  CIN: ["Cincinnati Reds", "Reds"],
  CLE: ["Cleveland Guardians", "Guardians"],
  COL: ["Colorado Rockies", "Rockies"],
  DET: ["Detroit Tigers", "Tigers"],
  HOU: ["Houston Astros", "Astros"],
  KC: ["Kansas City Royals", "Royals"],
  LAA: ["Los Angeles Angels", "Angels"],
  LAD: ["Los Angeles Dodgers", "Dodgers"],
  MIA: ["Miami Marlins", "Marlins"],
  MIL: ["Milwaukee Brewers", "Brewers"],
  MIN: ["Minnesota Twins", "Twins"],
  NYM: ["New York Mets", "Mets"],
  NYY: ["New York Yankees", "Yankees"],
  OAK: ["Oakland Athletics", "Athletics", "A's"],
  PHI: ["Philadelphia Phillies", "Phillies"],
  PIT: ["Pittsburgh Pirates", "Pirates"],
  SD: ["San Diego Padres", "Padres"],
  SEA: ["Seattle Mariners", "Mariners"],
  SF: ["San Francisco Giants", "Giants"],
  STL: ["St. Louis Cardinals", "Saint Louis Cardinals", "Cardinals"],
  TB: ["Tampa Bay Rays", "Rays"],
  TEX: ["Texas Rangers", "Rangers"],
  TOR: ["Toronto Blue Jays", "Blue Jays"],
  WSH: ["Washington Nationals", "Nationals"],
};

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2));
  const apiKey = process.env.ODDS_API_KEY ?? process.env.THE_ODDS_API_KEY;

  if (!apiKey) {
    console.error("Missing ODDS_API_KEY. Set it in the environment and rerun the command.");
    process.exitCode = 1;
    return;
  }

  try {
    const slip = options.sampleLive
      ? await buildLiveSampleSlip(apiKey, options)
      : await readSlipInput(options.inputPath);

    const result = await resolveBetslipToLinks(slip, apiKey, options);

    await mkdir(path.dirname(options.outputPath), { recursive: true });
    await writeFile(options.outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

    printReport(result, options.outputPath);

    if (result.status === "failed") {
      process.exitCode = 1;
    }
  } catch (error) {
    if (isAbortError(error)) {
      console.error(`The Odds API request timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`);
    } else {
      console.error(`Failed to resolve betslip links: ${error instanceof Error ? error.message : String(error)}`);
    }
    process.exitCode = 1;
  }
}

function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = {
    outputPath: DEFAULT_OUTPUT_PATH,
    regions: "us",
    sampleLive: false,
    sampleLegs: 2,
    maxSampleEvents: 8,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    const next = args[index + 1];

    if (arg === "--input" && next) {
      options.inputPath = next;
      index += 1;
    } else if (arg.startsWith("--input=")) {
      options.inputPath = arg.slice("--input=".length);
    } else if (arg === "--output" && next) {
      options.outputPath = next;
      index += 1;
    } else if (arg.startsWith("--output=")) {
      options.outputPath = arg.slice("--output=".length);
    } else if (arg === "--regions" && next) {
      options.regions = next;
      index += 1;
    } else if (arg.startsWith("--regions=")) {
      options.regions = arg.slice("--regions=".length);
    } else if (arg === "--bookmakers" && next) {
      options.bookmakers = next;
      index += 1;
    } else if (arg.startsWith("--bookmakers=")) {
      options.bookmakers = arg.slice("--bookmakers=".length);
    } else if (arg === "--sample-live") {
      options.sampleLive = true;
    } else if (arg === "--sample-legs" && next) {
      options.sampleLegs = parsePositiveInt(next, "sample legs");
      index += 1;
    } else if (arg.startsWith("--sample-legs=")) {
      options.sampleLegs = parsePositiveInt(arg.slice("--sample-legs=".length), "sample legs");
    } else if (arg === "--max-sample-events" && next) {
      options.maxSampleEvents = parsePositiveInt(next, "max sample events");
      index += 1;
    } else if (arg.startsWith("--max-sample-events=")) {
      options.maxSampleEvents = parsePositiveInt(arg.slice("--max-sample-events=".length), "max sample events");
    } else if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    } else if (!arg.startsWith("-") && !options.inputPath) {
      options.inputPath = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!options.inputPath && !options.sampleLive) {
    options.inputPath = path.join("examples", "betslip-mlb-hr.json");
  }

  return options;
}

function printUsage(): void {
  console.log(`Usage:
  npm run resolve:betslip -- --input examples/betslip-mlb-hr.json
  npm run resolve:betslip -- --sample-live --sample-legs 2

Environment:
  ODDS_API_KEY or THE_ODDS_API_KEY must be set.

Options:
  --input <path>              Extracted betslip JSON input.
  --output <path>             Result JSON path. Default: ${DEFAULT_OUTPUT_PATH}
  --regions <regions>         The Odds API regions. Default: us
  --bookmakers <keys>         Optional comma-separated bookmaker keys instead of regions.
  --sample-live               Build a temporary slip from current MLB odds, then resolve it.
  --sample-legs <n>           Number of sample legs. Default: 2
  --max-sample-events <n>     Max events to scan for sample mode. Default: 8
`);
}

function parsePositiveInt(value: string, label: string): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`Invalid ${label}: ${value}`);
  }
  return parsed;
}

async function readSlipInput(inputPath: string | undefined): Promise<ExtractedSlip> {
  if (!inputPath) {
    throw new Error("Missing input path.");
  }

  const raw = await readFile(inputPath, "utf8");
  const parsed = JSON.parse(raw) as JsonValue;
  const slip = validateSlip(parsed);

  return slip;
}

export function validateSlip(value: JsonValue): ExtractedSlip {
  if (!isRecord(value) || !Array.isArray(value.legs)) {
    throw new Error("Input JSON must be an object with a legs array.");
  }

  const legs = value.legs.map((leg, index) => validateLeg(leg, index));
  if (legs.length === 0) {
    throw new Error("Input JSON must contain at least one leg.");
  }

  const betType = typeof value.betType === "string" ? value.betType : "unknown";
  return {
    betType: isKnownBetType(betType) ? betType : "unknown",
    sportKey: optionalKnownString(value.sportKey),
    legs,
  };
}

function validateLeg(value: JsonValue, index: number): ExtractedLeg {
  if (!isRecord(value)) {
    throw new Error(`Leg ${index} must be an object.`);
  }

  const rawText = typeof value.rawText === "string" ? value.rawText : "";
  const marketKey = typeof value.marketKey === "string" ? value.marketKey : inferMarketKey(rawText);
  const point = typeof value.point === "number" ? value.point : value.point === null ? null : inferPoint(rawText);
  const side = typeof value.side === "string" ? value.side : inferSide(rawText);

  return {
    sportKey: optionalKnownString(value.sportKey),
    eventId: typeof value.eventId === "string" ? value.eventId : undefined,
    player: typeof value.player === "string" ? value.player : undefined,
    team: typeof value.team === "string" ? value.team : undefined,
    opponent: typeof value.opponent === "string" ? value.opponent : undefined,
    marketKey: marketKey === "unknown" ? undefined : marketKey,
    side,
    point,
    price: typeof value.price === "number" ? value.price : null,
    commenceTimeHint: typeof value.commenceTimeHint === "string" ? value.commenceTimeHint : null,
    rawText,
  };
}

function optionalKnownString(value: JsonValue | undefined): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  return value.toLowerCase() === "unknown" ? undefined : value;
}

function isKnownBetType(value: string): value is NonNullable<ExtractedSlip["betType"]> {
  return ["single", "parlay", "same_game_parlay", "unknown"].includes(value);
}

function inferMarketKey(rawText: string): string | undefined {
  const normalized = normalizeText(rawText);
  if (/moneyline|\bml\b/.test(normalized)) {
    return "h2h";
  }
  if (/1st inning|first inning/.test(normalized) && /runs?|total/.test(normalized)) {
    return "totals_1st_1_innings";
  }
  if (/total runs?|game total/.test(normalized)) {
    return "totals";
  }
  if (/home runs?|homer|to hit a home run/.test(normalized)) {
    return "batter_home_runs";
  }
  if (/record a hit|to record a hit|1\+ hits?/.test(normalized)) {
    return "batter_hits";
  }
  if (/hits?\s*\+\s*runs?\s*\+\s*rbis?|hits runs rbis/.test(normalized)) {
    return "batter_hits_runs_rbis";
  }
  if (/hitter fs|batter fantasy|fantasy score|fantasy points/.test(normalized)) {
    return "batter_fantasy_score";
  }
  if (/total bases?/.test(normalized)) {
    return "batter_total_bases";
  }
  if (/\bhits?\b/.test(normalized)) {
    return "batter_hits";
  }
  if (/alt strikeouts?|alternate strikeouts?|strikeouts?\s*\d\+|\d\+\s*strikeouts?/.test(normalized)) {
    return "pitcher_strikeouts_alternate";
  }
  if (/strikeouts?|ks\b/.test(normalized)) {
    return "pitcher_strikeouts";
  }
  return undefined;
}

function inferSide(rawText: string): string | undefined {
  const normalized = normalizeText(rawText);
  if (/\bover\b|\bo\s*0/.test(normalized) || /to hit a home run/.test(normalized)) {
    return "Over";
  }
  if (/\d\+/.test(normalized) || /record a hit|to record a hit|hitter fs/.test(normalized)) {
    return "Over";
  }
  if (/\bunder\b|\bu\s*0/.test(normalized)) {
    return "Under";
  }
  if (/\byes\b/.test(normalized)) {
    return "Yes";
  }
  if (/\bno\b/.test(normalized)) {
    return "No";
  }
  return undefined;
}

function inferPoint(rawText: string): number | null | undefined {
  const pointMatch = rawText.match(/\b(?:over|under|o|u)\s*(\d+(?:\.\d+)?)/i);
  if (pointMatch?.[1]) {
    return Number(pointMatch[1]);
  }

  if (/to hit a home run|1\+\s*home runs?/i.test(rawText)) {
    return 0.5;
  }

  const milestoneMatch = rawText.match(/\b(\d+)\s*\+/);
  if (milestoneMatch?.[1]) {
    return Number(milestoneMatch[1]) - 0.5;
  }

  return undefined;
}

export async function resolveBetslipToLinks(
  slip: ExtractedSlip,
  apiKey: string,
  options: CliOptions,
): Promise<ResolutionResult> {
  const apiUsage: ApiUsage[] = [];
  const sportKey = slip.sportKey ?? firstDefined(slip.legs.map((leg) => leg.sportKey)) ?? DEFAULT_SPORT_KEY;
  const eventsResponse = await fetchOddsApi<OddsApiEvent[]>(`/sports/${sportKey}/events`, new URLSearchParams(), apiKey);
  apiUsage.push(usageFromHeaders("events", sportKey, eventsResponse.headers));

  const upcomingEvents = eventsResponse.data
    .filter((event) => Date.parse(event.commence_time) > Date.now())
    .sort((a, b) => Date.parse(a.commence_time) - Date.parse(b.commence_time));

  const candidatesByLeg = new Map<number, OddsApiEvent[]>();
  for (let index = 0; index < slip.legs.length; index += 1) {
    const leg = slip.legs[index]!;
    candidatesByLeg.set(index, findCandidateEvents(leg, upcomingEvents));
  }

  const eventMarketMap = new Map<string, { event: OddsApiEvent; markets: Set<string> }>();
  const unmatchedLegs: ResolutionResult["unmatchedLegs"] = [];

  for (let index = 0; index < slip.legs.length; index += 1) {
    const leg = slip.legs[index]!;
    const marketKey = leg.marketKey ?? inferMarketKey(leg.rawText);
    const candidates = candidatesByLeg.get(index) ?? [];

    if (!marketKey) {
      unmatchedLegs.push({ legIndex: index, leg, reason: "Could not infer market key." });
      continue;
    }

    if (candidates.length === 0) {
      unmatchedLegs.push({ legIndex: index, leg, reason: "No candidate event matched this leg." });
      continue;
    }

    for (const event of candidates) {
      const current = eventMarketMap.get(event.id) ?? { event, markets: new Set<string>() };
      current.markets.add(marketKey);
      eventMarketMap.set(event.id, current);
    }
  }

  const eventOddsResponses: OddsApiEventOdds[] = [];
  for (const { event, markets } of eventMarketMap.values()) {
    const params = new URLSearchParams({
      markets: [...markets].join(","),
      oddsFormat: "american",
      includeLinks: "true",
      includeSids: "true",
    });

    if (options.bookmakers) {
      params.set("bookmakers", options.bookmakers);
    } else {
      params.set("regions", options.regions);
    }

    const oddsResponse = await fetchOddsApi<OddsApiEventOdds>(
      `/sports/${sportKey}/events/${encodeURIComponent(event.id)}/odds`,
      params,
      apiKey,
    );
    apiUsage.push(usageFromHeaders("event_odds", sportKey, oddsResponse.headers, event.id));
    eventOddsResponses.push(oddsResponse.data);
  }

  const normalizedOutcomes = eventOddsResponses.flatMap(normalizeEventOdds);
  const matchesByBook = buildMatchesByBook(slip.legs, normalizedOutcomes, candidatesByLeg);
  const sportsbooks = buildSportsbookGroups(slip, matchesByBook);
  const fetchedEvents = [...eventMarketMap.values()].map(({ event, markets }) => ({
    eventId: event.id,
    homeTeam: event.home_team,
    awayTeam: event.away_team,
    commenceTime: event.commence_time,
    markets: [...markets],
  }));

  const anyFullBook = sportsbooks.some((book) => book.allLegsMatched);
  const anyMatch = sportsbooks.some((book) => book.matchedLegCount > 0);

  return {
    status: anyFullBook ? "ready" : anyMatch ? "partial" : "no_matches",
    betType: slip.betType ?? "unknown",
    requestedLegs: slip.legs,
    unmatchedLegs,
    sportsbooks,
    fetchedEvents,
    apiUsage,
    expiresAt: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
  };
}

async function buildLiveSampleSlip(apiKey: string, options: CliOptions): Promise<ExtractedSlip> {
  const sportKey = DEFAULT_SPORT_KEY;
  const eventsResponse = await fetchOddsApi<OddsApiEvent[]>(`/sports/${sportKey}/events`, new URLSearchParams(), apiKey);
  const upcomingEvents = eventsResponse.data
    .filter((event) => Date.parse(event.commence_time) > Date.now())
    .sort((a, b) => Date.parse(a.commence_time) - Date.parse(b.commence_time))
    .slice(0, options.maxSampleEvents);

  if (upcomingEvents.length === 0) {
    throw new Error("No upcoming MLB events were returned for live sample mode.");
  }

  for (const event of upcomingEvents) {
    const params = new URLSearchParams({
      markets: DEFAULT_MARKET_KEY,
      oddsFormat: "american",
      includeLinks: "true",
      includeSids: "true",
    });

    if (options.bookmakers) {
      params.set("bookmakers", options.bookmakers);
    } else {
      params.set("regions", options.regions);
    }

    const oddsResponse = await fetchOddsApi<OddsApiEventOdds>(
      `/sports/${sportKey}/events/${encodeURIComponent(event.id)}/odds`,
      params,
      apiKey,
    );

    const sampleOutcomes = normalizeEventOdds(oddsResponse.data)
      .filter((outcome) => outcome.marketKey === DEFAULT_MARKET_KEY)
      .filter((outcome) => isHomeRunOverOutcome(outcome.side, outcome.point))
      .filter((outcome) => outcome.player)
      .slice(0, options.sampleLegs);

    if (sampleOutcomes.length >= options.sampleLegs) {
      return {
        betType: options.sampleLegs > 1 ? "parlay" : "single",
        sportKey,
        legs: sampleOutcomes.map((outcome) => ({
          sportKey,
          eventId: outcome.eventId,
          player: outcome.player ?? undefined,
          team: undefined,
          opponent: undefined,
          marketKey: DEFAULT_MARKET_KEY,
          side: "Over",
          point: 0.5,
          price: outcome.price,
          rawText: `${outcome.player} To Hit A Home Run`,
        })),
      };
    }
  }

  throw new Error(
    `Could not find ${options.sampleLegs} current ${DEFAULT_MARKET_KEY} outcomes in the first ${upcomingEvents.length} MLB events.`,
  );
}

function findCandidateEvents(leg: ExtractedLeg, events: OddsApiEvent[]): OddsApiEvent[] {
  const legSportKey = leg.sportKey ?? DEFAULT_SPORT_KEY;
  const relevantEvents = events.filter((event) => event.sport_key === legSportKey);

  if (leg.eventId) {
    const exactEvent = relevantEvents.find((event) => event.id === leg.eventId);
    if (exactEvent) {
      return [exactEvent];
    }
  }

  if (leg.team || leg.opponent) {
    const matched = relevantEvents.filter((event) => eventContainsTeams(event, leg.team, leg.opponent));
    if (matched.length > 0) {
      return matched;
    }
  }

  if (leg.commenceTimeHint) {
    const hintMs = Date.parse(leg.commenceTimeHint);
    if (Number.isFinite(hintMs)) {
      const timeMatched = relevantEvents.filter(
        (event) => Math.abs(Date.parse(event.commence_time) - hintMs) <= 15 * 60 * 1000,
      );
      if (timeMatched.length > 0) {
        return timeMatched;
      }
    }
  }

  return relevantEvents.slice(0, 12);
}

function eventContainsTeams(event: OddsApiEvent, team?: string, opponent?: string): boolean {
  const teams = [event.home_team, event.away_team];
  const teamMatches = team ? teams.some((apiTeam) => teamMatchesAlias(team, apiTeam)) : true;
  const opponentMatches = opponent ? teams.some((apiTeam) => teamMatchesAlias(opponent, apiTeam)) : true;
  return teamMatches && opponentMatches;
}

function teamMatchesAlias(inputTeam: string, apiTeam: string): boolean {
  const normalizedInput = normalizeText(inputTeam);
  const normalizedApi = normalizeText(apiTeam);

  if (normalizedInput === normalizedApi || normalizedApi.includes(normalizedInput)) {
    return true;
  }

  const aliases = MLB_TEAM_ALIASES[inputTeam.toUpperCase()] ?? [];
  return aliases.some((alias) => normalizeText(alias) === normalizedApi);
}

function normalizeEventOdds(eventOdds: OddsApiEventOdds): NormalizedOutcome[] {
  const outcomes: NormalizedOutcome[] = [];

  for (const bookmaker of eventOdds.bookmakers ?? []) {
    for (const market of bookmaker.markets ?? []) {
      for (const outcome of market.outcomes ?? []) {
        if (!market.key || !bookmaker.key || typeof outcome.price !== "number") {
          continue;
        }

        const outcomeLink = outcome.link ?? null;
        const marketLink = market.link ?? null;
        const eventLink = bookmaker.link ?? null;
        const link = outcomeLink ?? marketLink ?? eventLink;
        const linkLevel = outcomeLink ? "outcome" : marketLink ? "market" : eventLink ? "event" : "none";

        outcomes.push({
          sportKey: eventOdds.sport_key,
          eventId: eventOdds.id,
          homeTeam: eventOdds.home_team,
          awayTeam: eventOdds.away_team,
          commenceTime: eventOdds.commence_time,
          bookmakerKey: bookmaker.key,
          bookmakerTitle: bookmaker.title ?? bookmaker.key,
          marketKey: market.key,
          player: outcome.description ?? null,
          side: outcome.name ?? "",
          point: outcome.point ?? null,
          price: outcome.price,
          link,
          sid: outcome.sid ?? market.sid ?? bookmaker.sid ?? null,
          linkLevel,
        });
      }
    }
  }

  return outcomes;
}

function buildMatchesByBook(
  legs: ExtractedLeg[],
  outcomes: NormalizedOutcome[],
  candidatesByLeg: Map<number, OddsApiEvent[]>,
): Map<string, MatchedLeg[]> {
  const matchesByBook = new Map<string, MatchedLeg[]>();

  for (let legIndex = 0; legIndex < legs.length; legIndex += 1) {
    const leg = legs[legIndex]!;
    const candidates = new Set((candidatesByLeg.get(legIndex) ?? []).map((event) => event.id));
    const legMatches = outcomes
      .filter((outcome) => candidates.size === 0 || candidates.has(outcome.eventId))
      .map((outcome) => scoreOutcomeMatch(legIndex, leg, outcome))
      .filter((match): match is MatchedLeg => match !== null && match.confidence >= 0.7)
      .sort((a, b) => b.confidence - a.confidence);

    const bestByBook = new Map<string, MatchedLeg>();
    for (const match of legMatches) {
      const existing = bestByBook.get(match.outcome.bookmakerKey);
      if (!existing || match.confidence > existing.confidence) {
        bestByBook.set(match.outcome.bookmakerKey, match);
      }
    }

    for (const match of bestByBook.values()) {
      const current = matchesByBook.get(match.outcome.bookmakerKey) ?? [];
      current.push(match);
      matchesByBook.set(match.outcome.bookmakerKey, current);
    }
  }

  return matchesByBook;
}

function scoreOutcomeMatch(legIndex: number, leg: ExtractedLeg, outcome: NormalizedOutcome): MatchedLeg | null {
  const reasons: string[] = [];
  let score = 0;

  const marketKey = leg.marketKey ?? inferMarketKey(leg.rawText);
  if (!marketKey || marketKey !== outcome.marketKey) {
    return null;
  }
  score += 0.2;
  reasons.push("market_key");

  const player = leg.player ?? extractPlayerFromRawText(leg.rawText, marketKey);
  if (player && outcome.player && namesMatch(player, outcome.player)) {
    score += 0.35;
    reasons.push("player_name");
  } else if (player) {
    return null;
  } else if (!isPlayerPropMarket(marketKey)) {
    score += 0.2;
    reasons.push("non_player_market");
  }

  const side = leg.side ?? inferSide(leg.rawText);
  if (side && sidesEquivalent(marketKey, side, outcome.side)) {
    score += 0.2;
    reasons.push("side");
  } else if (side) {
    return null;
  }

  const point = leg.point !== undefined ? leg.point : inferPoint(leg.rawText);
  if (pointsEquivalent(marketKey, point, outcome.point, outcome.side)) {
    score += 0.15;
    reasons.push("point");
  } else if (point !== undefined) {
    return null;
  }

  if (leg.team || leg.opponent) {
    const event: OddsApiEvent = {
      id: outcome.eventId,
      sport_key: outcome.sportKey,
      commence_time: outcome.commenceTime,
      home_team: outcome.homeTeam,
      away_team: outcome.awayTeam,
    };
    if (eventContainsTeams(event, leg.team, leg.opponent)) {
      score += 0.1;
      reasons.push("team_context");
    } else {
      return null;
    }
  }

  return {
    legIndex,
    extractedLeg: leg,
    outcome,
    confidence: Math.min(score, 1),
    matchReasons: reasons,
  };
}

function isPlayerPropMarket(marketKey: string): boolean {
  return (
    marketKey.startsWith("batter_") ||
    marketKey.startsWith("pitcher_") ||
    marketKey.startsWith("player_")
  );
}

function buildSportsbookGroups(slip: ExtractedSlip, matchesByBook: Map<string, MatchedLeg[]>): SportsbookGroup[] {
  const groups: SportsbookGroup[] = [];
  const requestedLegCount = slip.legs.length;

  for (const [sportsbookKey, matches] of matchesByBook.entries()) {
    const byLeg = new Map<number, MatchedLeg>();
    for (const match of matches) {
      const existing = byLeg.get(match.legIndex);
      if (!existing || match.confidence > existing.confidence) {
        byLeg.set(match.legIndex, match);
      }
    }

    const legs = [...byLeg.values()].sort((a, b) => a.legIndex - b.legIndex);
    const sportsbookTitle = legs[0]?.outcome.bookmakerTitle ?? sportsbookKey;
    const allLegsMatched = legs.length === requestedLegCount;
    const allLegsHaveOutcomeLinks = allLegsMatched && legs.every((match) => match.outcome.linkLevel === "outcome");
    const individualLinks = legs
      .map((match) => (match.outcome.linkLevel === "outcome" ? match.outcome.link : null))
      .filter((link): link is string => Boolean(link));

    const parlayUrl = buildSportsbookParlayLink(sportsbookKey, legs);
    const status = determineGroupStatus({
      requestedLegCount,
      allLegsMatched,
      allLegsHaveOutcomeLinks,
      parlayUrl,
      legs,
    });

    groups.push({
      sportsbookKey,
      sportsbookTitle,
      requestedLegCount,
      matchedLegCount: legs.length,
      allLegsMatched,
      allLegsHaveOutcomeLinks,
      canBuildParlay: Boolean(parlayUrl),
      parlayUrl,
      individualLinks,
      status,
      legs,
    });
  }

  return groups.sort((a, b) => {
    const priority = groupPriority(b) - groupPriority(a);
    if (priority !== 0) {
      return priority;
    }
    return a.sportsbookTitle.localeCompare(b.sportsbookTitle);
  });
}

function determineGroupStatus(input: {
  requestedLegCount: number;
  allLegsMatched: boolean;
  allLegsHaveOutcomeLinks: boolean;
  parlayUrl: string | null;
  legs: MatchedLeg[];
}): SportsbookGroup["status"] {
  if (!input.allLegsMatched) {
    return "partial_match";
  }

  if (input.parlayUrl) {
    return "ready_parlay";
  }

  if (input.allLegsHaveOutcomeLinks) {
    return input.requestedLegCount === 1 ? "ready_parlay" : "individual_links_only";
  }

  if (input.legs.some((leg) => leg.outcome.linkLevel === "market" || leg.outcome.linkLevel === "event")) {
    return "event_or_market_links_only";
  }

  return "unavailable";
}

function groupPriority(group: SportsbookGroup): number {
  switch (group.status) {
    case "ready_parlay":
      return 5;
    case "individual_links_only":
      return 4;
    case "event_or_market_links_only":
      return 3;
    case "partial_match":
      return 2;
    case "unavailable":
      return 1;
  }
}

const SPORTSBOOK_PARLAY_ADAPTERS: SportsbookParlayAdapter[] = [
  {
    sportsbookKey: "fanduel",
    createParlayLink: buildFanDuelParlayFromMatches,
  },
];

function buildSportsbookParlayLink(sportsbookKey: string, matches: MatchedLeg[]): string | null {
  const adapter = SPORTSBOOK_PARLAY_ADAPTERS.find((candidate) => candidate.sportsbookKey === sportsbookKey);
  if (!adapter) {
    return null;
  }

  const outcomeLinkedMatches = matches.filter((match) => match.outcome.linkLevel === "outcome");
  if (outcomeLinkedMatches.length < 2) {
    return null;
  }

  return adapter.createParlayLink(outcomeLinkedMatches);
}

function buildFanDuelParlayFromMatches(matches: MatchedLeg[]): string | null {
  const selections = matches.map((match) => {
    if (!match.outcome.link) {
      return null;
    }
    return parseFanDuelSelection(match.outcome.link);
  });

  if (selections.some((selection) => selection === null)) {
    return null;
  }

  return buildFanDuelParlayUrl(selections as FanDuelSelection[]);
}

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

function buildFanDuelParlayUrl(selections: FanDuelSelection[]): string {
  const url = new URL("https://account.sportsbook.fanduel.com/sportsbook/addToBetslip");

  selections.forEach((selection, index) => {
    url.searchParams.set(`marketId[${index}]`, selection.marketId);
    url.searchParams.set(`selectionId[${index}]`, selection.selectionId);
  });

  return url.toString();
}

function sidesEquivalent(marketKey: string, requestedSide: string, apiSide: string): boolean {
  const requested = normalizeText(requestedSide);
  const api = normalizeText(apiSide);

  if (requested === api) {
    return true;
  }

  if (marketKey === "batter_home_runs" && requested === "over") {
    return api === "over" || /1 home runs?|1\+ home runs?/.test(api);
  }

  return false;
}

function pointsEquivalent(
  marketKey: string,
  requestedPoint: number | null | undefined,
  apiPoint: number | null,
  apiOutcomeName: string,
): boolean {
  if (marketKey === "batter_home_runs") {
    if (requestedPoint === 0.5 && apiPoint === 0.5) {
      return true;
    }
    if (requestedPoint === 0.5 && /1\+|1 home run|home run/i.test(apiOutcomeName)) {
      return true;
    }
  }

  if (requestedPoint === undefined) {
    return true;
  }

  if (requestedPoint === null && apiPoint === null) {
    return true;
  }

  if (requestedPoint === null || apiPoint === null) {
    return false;
  }

  return Math.abs(requestedPoint - apiPoint) < 0.001;
}

function isHomeRunOverOutcome(side: string, point: number | null): boolean {
  return sidesEquivalent("batter_home_runs", "Over", side) && pointsEquivalent("batter_home_runs", 0.5, point, side);
}

function extractPlayerFromRawText(rawText: string, marketKey: string): string | undefined {
  if (marketKey === "batter_home_runs") {
    const cleaned = rawText
      .replace(/over\s*0\.5/gi, "")
      .replace(/to hit a home run/gi, "")
      .replace(/home runs?/gi, "")
      .replace(/\+?-?\d+$/g, "")
      .trim();
    return cleaned || undefined;
  }

  return undefined;
}

function namesMatch(left: string, right: string): boolean {
  const normalizedLeft = normalizeText(left);
  const normalizedRight = normalizeText(right);
  return normalizedLeft === normalizedRight;
}

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9+]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchOddsApi<T>(pathname: string, params: URLSearchParams, apiKey: string): Promise<{ data: T; headers: Headers }> {
  const url = new URL(`${ODDS_API_BASE_URL}${pathname}`);
  for (const [key, value] of params.entries()) {
    url.searchParams.set(key, value);
  }
  url.searchParams.set("apiKey", apiKey);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
    });
    const body = await response.text();
    const parsed = safeJson(body);

    if (!response.ok) {
      const message = isRecord(parsed)
        ? stringValue(parsed.message) ?? stringValue(parsed.error_code) ?? body
        : body;
      throw new Error(`The Odds API returned HTTP ${response.status}: ${message}`);
    }

    if (parsed === undefined) {
      throw new Error("The Odds API returned invalid JSON.");
    }

    return { data: parsed as T, headers: response.headers };
  } finally {
    clearTimeout(timeout);
  }
}

function safeJson(body: string): JsonValue | undefined {
  try {
    return JSON.parse(body) as JsonValue;
  } catch {
    return undefined;
  }
}

function usageFromHeaders(
  endpoint: ApiUsage["endpoint"],
  sportKey: string,
  headers: Headers,
  eventId?: string,
): ApiUsage {
  return {
    endpoint,
    sportKey,
    eventId,
    requestsLast: headers.get("x-requests-last"),
    requestsUsed: headers.get("x-requests-used"),
    requestsRemaining: headers.get("x-requests-remaining"),
  };
}

export function printReport(result: ResolutionResult, outputPath: string): void {
  console.log("Betslip sportsbook link resolution report");
  console.log("=========================================");
  console.log(`Status: ${result.status}`);
  console.log(`Bet type: ${result.betType}`);
  console.log(`Requested legs: ${result.requestedLegs.length}`);
  console.log(`Fetched events: ${result.fetchedEvents.length}`);
  console.log(`Sportsbook groups: ${result.sportsbooks.length}`);
  console.log(`Expires at: ${result.expiresAt}`);
  console.log(`Saved full result: ${outputPath}`);
  console.log("");

  console.log("API usage");
  console.log("---------");
  if (result.apiUsage.length === 0) {
    console.log("None");
  } else {
    for (const usage of result.apiUsage) {
      const label = usage.eventId ? `${usage.endpoint} ${usage.eventId}` : usage.endpoint;
      console.log(
        `${label}: last=${usage.requestsLast ?? "unknown"} used=${usage.requestsUsed ?? "unknown"} remaining=${usage.requestsRemaining ?? "unknown"}`,
      );
    }
  }
  console.log("");

  console.log("Fetched event/market pairs");
  console.log("--------------------------");
  if (result.fetchedEvents.length === 0) {
    console.log("None");
  } else {
    for (const event of result.fetchedEvents) {
      console.log(
        `${event.eventId}: ${event.awayTeam} @ ${event.homeTeam} ${event.commenceTime} markets=${event.markets.join(",")}`,
      );
    }
  }
  console.log("");

  console.log("Unmatched legs");
  console.log("--------------");
  if (result.unmatchedLegs.length === 0) {
    console.log("None");
  } else {
    for (const unmatched of result.unmatchedLegs) {
      console.log(`#${unmatched.legIndex + 1}: ${unmatched.leg.rawText} — ${unmatched.reason}`);
    }
  }
  console.log("");

  console.log("Sportsbook availability");
  console.log("-----------------------");
  if (result.sportsbooks.length === 0) {
    console.log("No sportsbooks returned matching legs.");
  } else {
    for (const group of result.sportsbooks) {
      console.log(
        `${group.sportsbookTitle} (${group.sportsbookKey}) — ${group.status} — ${group.matchedLegCount}/${group.requestedLegCount} legs`,
      );
      if (group.parlayUrl) {
        console.log(`  Parlay URL: ${group.parlayUrl}`);
      }
      for (const leg of group.legs) {
        console.log(
          `  #${leg.legIndex + 1} ${leg.outcome.player ?? "Unknown"} | ${leg.outcome.marketKey} | ${leg.outcome.side} ${leg.outcome.point ?? ""} | ${leg.outcome.price} | ${leg.outcome.linkLevel} | ${leg.outcome.link ?? ""}`,
        );
      }
    }
  }
}

function firstDefined<T>(values: Array<T | undefined>): T | undefined {
  return values.find((value): value is T => value !== undefined);
}

function isRecord(value: JsonValue | undefined): value is Record<string, JsonValue> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: JsonValue | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  void main();
}
