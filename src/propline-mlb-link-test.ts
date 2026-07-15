import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
type JsonObject = { [key: string]: JsonValue };

type FetchResult =
  | {
      ok: true;
      status: number;
      headers: Headers;
      data: JsonValue;
    }
  | {
      ok: false;
      status: number;
      headers: Headers;
      data?: JsonValue;
      rawText?: string;
      errorKind: "http" | "invalid_json";
    };

type Discovery = {
  path: string;
  key: string;
  value: JsonValue;
  kind: "link" | "id";
  level: "event" | "bookmaker" | "market" | "outcome";
};

type BookmakerEntry = {
  path: string;
  bookmaker: JsonObject;
};

type MarketEntry = {
  bookmaker: JsonObject;
  market: JsonObject;
};

type OutcomeRow = {
  sportsbook: string;
  player: string;
  market: string;
  side: string;
  line: string;
  price: string;
  link: string;
  sid: string;
};

const BASE_URL = "https://api.prop-line.com/v1";
const SPORT = "baseball_mlb";
const MARKETS = [
  "pitcher_strikeouts",
  "batter_hits",
  "batter_total_bases",
  "batter_home_runs",
];
const BOOKMAKERS = ["fanduel", "draftkings", "betmgm"];
const REQUEST_TIMEOUT_MS = 15_000;
const OUTPUT_PATH = path.join("output", "propline-mlb-link-test.json");

const REDACTED_FIELD_NAMES = new Set([
  "apikey",
  "api_key",
  "token",
  "authorization",
]);

const LINK_FIELD_TERMS = ["deep_link", "deeplink", "link", "url"];
const ID_FIELD_TERMS = ["selection_id", "market_id", "event_id", "sid"];
const DISCOVERY_TERMS = [...LINK_FIELD_TERMS, ...ID_FIELD_TERMS];

async function main(): Promise<void> {
  const apiKey = process.env.PROPLINE_API_KEY;
  if (!apiKey) {
    console.error("Missing PROPLINE_API_KEY. Set it in the environment and rerun npm run test:links.");
    process.exitCode = 1;
    return;
  }

  try {
    const eventsResult = await fetchJson(
      `/sports/${SPORT}/events`,
      new URLSearchParams(),
      apiKey,
    );

    if (!eventsResult.ok) {
      printFetchFailureReport("events", eventsResult);
      process.exitCode = 1;
      return;
    }

    const events = extractArray(eventsResult.data, ["events", "data"]);
    if (events.length === 0) {
      console.log("No MLB events were returned by PropLine.");
      return;
    }

    const nextEvent = selectNextUpcomingEvent(events);
    if (!nextEvent) {
      console.log("PropLine returned MLB events, but none appear to be upcoming and unstarted.");
      return;
    }

    const eventId = requiredStringField(nextEvent, ["id", "event_id", "eventId"], "event ID");
    const awayTeam = firstStringField(nextEvent, ["away_team", "awayTeam", "away", "away_name"]) ?? "Unknown";
    const homeTeam = firstStringField(nextEvent, ["home_team", "homeTeam", "home", "home_name"]) ?? "Unknown";
    const startTime =
      firstStringField(nextEvent, ["commence_time", "start_time", "startTime", "commenceTime"]) ??
      "Unknown";

    const oddsParams = new URLSearchParams({
      markets: MARKETS.join(","),
      includeLinks: "true",
      includeSids: "true",
      bookmakers: BOOKMAKERS.join(","),
    });

    const oddsResult = await fetchJson(
      `/sports/${SPORT}/events/${encodeURIComponent(eventId)}/odds`,
      oddsParams,
      apiKey,
    );

    if (!oddsResult.ok) {
      await saveResponse(redactJsonValue(errorResponseForSave(oddsResult)));
      printFetchFailureReport("event odds", oddsResult, {
        eventId,
        awayTeam,
        homeTeam,
        startTime,
      });
      process.exitCode = 1;
      return;
    }

    const redactedResponse = redactJsonValue(oddsResult.data);
    await saveResponse(redactedResponse);

    const discoveries = discoverFields(redactedResponse);
    const bookmakerEntries = extractBookmakers(redactedResponse);
    const marketEntries = extractMarkets(bookmakerEntries);
    const rows = buildOutcomeRows(marketEntries);

    printReport({
      eventId,
      awayTeam,
      homeTeam,
      startTime,
      redactedResponse,
      discoveries,
      bookmakerEntries,
      marketEntries,
      rows,
    });
  } catch (error) {
    if (isAbortError(error)) {
      console.error(`PropLine request timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`);
    } else {
      console.error(`Unexpected failure: ${error instanceof Error ? error.message : String(error)}`);
    }
    process.exitCode = 1;
  }
}

async function fetchJson(pathname: string, params: URLSearchParams, apiKey: string): Promise<FetchResult> {
  const url = new URL(`${BASE_URL}${pathname}`);
  for (const [key, value] of params.entries()) {
    url.searchParams.set(key, value);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "X-API-Key": apiKey,
      },
      signal: controller.signal,
    });

    const rawText = await response.text();
    const parsed = parseJson(rawText);

    if (!parsed.ok) {
      return {
        ok: false,
        status: response.status,
        headers: response.headers,
        rawText,
        errorKind: "invalid_json",
      };
    }

    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        headers: response.headers,
        data: parsed.data,
        errorKind: "http",
      };
    }

    return {
      ok: true,
      status: response.status,
      headers: response.headers,
      data: parsed.data,
    };
  } finally {
    clearTimeout(timeout);
  }
}

function parseJson(rawText: string): { ok: true; data: JsonValue } | { ok: false } {
  try {
    return { ok: true, data: JSON.parse(rawText) as JsonValue };
  } catch {
    return { ok: false };
  }
}

function extractArray(value: JsonValue, wrapperKeys: string[]): JsonObject[] {
  if (Array.isArray(value)) {
    return value.filter(isJsonObject);
  }

  if (!isJsonObject(value)) {
    return [];
  }

  for (const key of wrapperKeys) {
    const nested = value[key];
    if (Array.isArray(nested)) {
      return nested.filter(isJsonObject);
    }
  }

  return [];
}

function selectNextUpcomingEvent(events: JsonObject[]): JsonObject | undefined {
  const now = Date.now();

  return events
    .map((event) => {
      const start = firstStringField(event, [
        "commence_time",
        "start_time",
        "startTime",
        "commenceTime",
      ]);
      const startMs = start ? Date.parse(start) : Number.NaN;
      return { event, startMs };
    })
    .filter(({ event, startMs }) => Number.isFinite(startMs) && startMs > now && !looksStarted(event))
    .sort((a, b) => a.startMs - b.startMs)[0]?.event;
}

function looksStarted(event: JsonObject): boolean {
  const completed = booleanField(event, ["completed", "is_completed", "isCompleted"]);
  if (completed === true) {
    return true;
  }

  const status = firstStringField(event, ["status", "event_status", "state"])?.toLowerCase();
  if (!status) {
    return false;
  }

  return ["live", "in_progress", "inprogress", "started", "complete", "completed", "final"].includes(status);
}

function requiredStringField(object: JsonObject, keys: string[], label: string): string {
  const value = firstStringField(object, keys);
  if (!value) {
    throw new Error(`Could not determine ${label} from selected event.`);
  }
  return value;
}

function firstStringField(object: JsonObject, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = object[key];
    if (typeof value === "string" && value.trim() !== "") {
      return value;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
  }
  return undefined;
}

function booleanField(object: JsonObject, keys: string[]): boolean | undefined {
  for (const key of keys) {
    const value = object[key];
    if (typeof value === "boolean") {
      return value;
    }
  }
  return undefined;
}

function redactJsonValue(value: JsonValue): JsonValue {
  if (Array.isArray(value)) {
    return value.map(redactJsonValue);
  }

  if (!isJsonObject(value)) {
    return value;
  }

  const redacted: JsonObject = {};
  for (const [key, nestedValue] of Object.entries(value)) {
    if (REDACTED_FIELD_NAMES.has(key.toLowerCase())) {
      redacted[key] = "[REDACTED]";
    } else {
      redacted[key] = redactJsonValue(nestedValue);
    }
  }
  return redacted;
}

async function saveResponse(response: JsonValue): Promise<void> {
  await mkdir(path.dirname(OUTPUT_PATH), { recursive: true });
  await writeFile(OUTPUT_PATH, `${JSON.stringify(response, null, 2)}\n`, "utf8");
}

function errorResponseForSave(result: Exclude<FetchResult, { ok: true }>): JsonValue {
  return {
    error: {
      status: result.status,
      kind: result.errorKind,
      body: result.data ?? result.rawText ?? null,
    },
  };
}

function discoverFields(value: JsonValue): Discovery[] {
  const discoveries: Discovery[] = [];

  function walk(current: JsonValue, currentPath: string): void {
    if (Array.isArray(current)) {
      current.forEach((item, index) => walk(item, `${currentPath}[${index}]`));
      return;
    }

    if (!isJsonObject(current)) {
      return;
    }

    for (const [key, nestedValue] of Object.entries(current)) {
      const nestedPath = appendPath(currentPath, key);
      const normalizedKey = key.toLowerCase();

      if (DISCOVERY_TERMS.some((term) => normalizedKey.includes(term))) {
        discoveries.push({
          path: nestedPath,
          key,
          value: nestedValue,
          kind: LINK_FIELD_TERMS.some((term) => normalizedKey.includes(term)) ? "link" : "id",
          level: classifyLevel(nestedPath),
        });
      }

      walk(nestedValue, nestedPath);
    }
  }

  walk(value, "$");
  return discoveries;
}

function classifyLevel(jsonPath: string): Discovery["level"] {
  if (/\.outcomes\[\d+\]/.test(jsonPath)) {
    return "outcome";
  }
  if (/\.markets\[\d+\]/.test(jsonPath)) {
    return "market";
  }
  if (/\.bookmakers\[\d+\]/.test(jsonPath)) {
    return "bookmaker";
  }
  return "event";
}

function appendPath(currentPath: string, key: string): string {
  if (/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)) {
    return `${currentPath}.${key}`;
  }
  return `${currentPath}[${JSON.stringify(key)}]`;
}

function extractBookmakers(value: JsonValue): BookmakerEntry[] {
  const entries: BookmakerEntry[] = [];

  function walk(current: JsonValue, currentPath: string): void {
    if (Array.isArray(current)) {
      current.forEach((item, index) => walk(item, `${currentPath}[${index}]`));
      return;
    }

    if (!isJsonObject(current)) {
      return;
    }

    const bookmakers = current.bookmakers;
    if (Array.isArray(bookmakers)) {
      bookmakers.forEach((bookmaker, index) => {
        if (isJsonObject(bookmaker)) {
          entries.push({ path: `${appendPath(currentPath, "bookmakers")}[${index}]`, bookmaker });
        }
      });
    }

    for (const [key, nestedValue] of Object.entries(current)) {
      walk(nestedValue, appendPath(currentPath, key));
    }
  }

  walk(value, "$");
  return dedupeBookmakers(entries);
}

function dedupeBookmakers(entries: BookmakerEntry[]): BookmakerEntry[] {
  const seen = new Set<JsonObject>();
  return entries.filter((entry) => {
    if (seen.has(entry.bookmaker)) {
      return false;
    }
    seen.add(entry.bookmaker);
    return true;
  });
}

function extractMarkets(bookmakerEntries: BookmakerEntry[]): MarketEntry[] {
  const markets: MarketEntry[] = [];
  for (const { bookmaker } of bookmakerEntries) {
    const bookmakerMarkets = bookmaker.markets;
    if (!Array.isArray(bookmakerMarkets)) {
      continue;
    }

    for (const market of bookmakerMarkets) {
      if (isJsonObject(market)) {
        markets.push({ bookmaker, market });
      }
    }
  }
  return markets;
}

function buildOutcomeRows(marketEntries: MarketEntry[]): OutcomeRow[] {
  const rows: OutcomeRow[] = [];

  for (const { bookmaker, market } of marketEntries) {
    const outcomes = market.outcomes;
    if (!Array.isArray(outcomes)) {
      continue;
    }

    for (const outcome of outcomes) {
      if (!isJsonObject(outcome)) {
        continue;
      }

      rows.push({
        sportsbook: bookmakerLabel(bookmaker),
        player: playerLabel(outcome),
        market: stringValue(market.key) ?? stringValue(market.market_key) ?? stringValue(market.title) ?? "Unknown",
        side: stringValue(outcome.name) ?? stringValue(outcome.side) ?? stringValue(outcome.label) ?? "Unknown",
        line: stringValue(outcome.point) ?? stringValue(outcome.line) ?? "",
        price: stringValue(outcome.price) ?? stringValue(outcome.odds) ?? "",
        link: firstDiscoveryValue(outcome, LINK_FIELD_TERMS) ?? "",
        sid: firstDiscoveryValue(outcome, ID_FIELD_TERMS) ?? "",
      });
    }
  }

  return rows;
}

function bookmakerLabel(bookmaker: JsonObject): string {
  const key = stringValue(bookmaker.key) ?? stringValue(bookmaker.id);
  const title = stringValue(bookmaker.title) ?? stringValue(bookmaker.name);

  if (key && title && key !== title) {
    return `${title} (${key})`;
  }
  return title ?? key ?? "Unknown";
}

function playerLabel(outcome: JsonObject): string {
  const player =
    stringValue(outcome.description) ??
    stringValue(outcome.player) ??
    stringValue(outcome.player_name) ??
    stringValue(outcome.participant);

  if (player) {
    return player;
  }

  const name = stringValue(outcome.name);
  if (name && !["over", "under", "yes", "no"].includes(name.toLowerCase())) {
    return name;
  }

  return "Unknown";
}

function firstDiscoveryValue(object: JsonObject, terms: string[]): string | undefined {
  for (const [key, value] of Object.entries(object)) {
    const normalizedKey = key.toLowerCase();
    if (terms.some((term) => normalizedKey.includes(term))) {
      return formatValue(value);
    }
  }
  return undefined;
}

function printReport(input: {
  eventId: string;
  awayTeam: string;
  homeTeam: string;
  startTime: string;
  redactedResponse: JsonValue;
  discoveries: Discovery[];
  bookmakerEntries: BookmakerEntry[];
  marketEntries: MarketEntry[];
  rows: OutcomeRow[];
}): void {
  const sportsbookLabels = unique(input.bookmakerEntries.map(({ bookmaker }) => bookmakerLabel(bookmaker)));
  const sportsbookKeys = unique(
    input.bookmakerEntries.map(
      ({ bookmaker }) => stringValue(bookmaker.key) ?? stringValue(bookmaker.id) ?? bookmakerLabel(bookmaker),
    ),
  ).map((sportsbook) => sportsbook.toLowerCase());
  const marketKeys = unique(
    input.marketEntries.map(({ market }) =>
      stringValue(market.key) ?? stringValue(market.market_key) ?? stringValue(market.title) ?? "Unknown",
    ),
  );
  const linkDiscoveries = input.discoveries.filter((discovery) => discovery.kind === "link");
  const idDiscoveries = input.discoveries.filter((discovery) => discovery.kind === "id");
  const outcomeLinkCount = linkDiscoveries.filter((discovery) => discovery.level === "outcome").length;
  const marketLinkCount = linkDiscoveries.filter((discovery) => discovery.level === "market").length;
  const bookmakerLinkCount = linkDiscoveries.filter((discovery) => discovery.level === "bookmaker").length;
  const strongestLinkingLevel = determineStrongestLinkingLevel(linkDiscoveries, idDiscoveries);
  const queryStatus = determineQueryStatus({
    sportsbookKeys,
    sportsbookLabels,
    marketKeys,
    linkDiscoveries,
    idDiscoveries,
  });

  console.log("PropLine MLB player-prop link/SID support report");
  console.log("==================================================");
  console.log(`Event ID: ${input.eventId}`);
  console.log(`Away team: ${input.awayTeam}`);
  console.log(`Home team: ${input.homeTeam}`);
  console.log(`Start time: ${input.startTime}`);
  console.log(`Sportsbooks returned: ${sportsbookLabels.length > 0 ? sportsbookLabels.join(", ") : "None"}`);
  console.log(`Markets returned: ${marketKeys.length > 0 ? marketKeys.join(", ") : "None"}`);
  console.log(`Number of bookmaker-level links: ${bookmakerLinkCount}`);
  console.log(`Number of market-level links: ${marketLinkCount}`);
  console.log(`Number of outcome-level links: ${outcomeLinkCount}`);
  console.log(`Number of sid or sportsbook-native ID fields: ${idDiscoveries.length}`);
  console.log(`Strongest supported linking level: ${strongestLinkingLevel}`);
  console.log(`Saved redacted full response: ${OUTPUT_PATH}`);
  console.log("");

  console.log("Requested query parameter support");
  console.log("---------------------------------");
  for (const line of queryStatus) {
    console.log(`- ${line}`);
  }
  console.log("");

  console.log("Discovered link or ID fields");
  console.log("----------------------------");
  if (input.discoveries.length === 0) {
    console.log("None");
  } else {
    for (const discovery of input.discoveries) {
      console.log(`${discovery.path} = ${formatValue(discovery.value)}`);
    }
  }
  console.log("");

  console.log("Player-prop outcomes");
  console.log("--------------------");
  if (input.rows.length === 0) {
    console.log("No player-prop outcomes were returned for the selected event/bookmaker/market filters.");
  } else {
    console.log("Sportsbook | Player | Market | Side | Line | Price | Link | SID");
    for (const row of input.rows) {
      console.log(
        [
          row.sportsbook,
          row.player,
          row.market,
          row.side,
          row.line,
          row.price,
          row.link,
          row.sid,
        ].join(" | "),
      );
    }
  }
  console.log("");

  console.log(`Conclusion: ${buildConclusion(input.bookmakerEntries, linkDiscoveries, idDiscoveries)}`);
}

function determineQueryStatus(input: {
  sportsbookKeys: string[];
  sportsbookLabels: string[];
  marketKeys: string[];
  linkDiscoveries: Discovery[];
  idDiscoveries: Discovery[];
}): string[] {
  const returnedRequestedBooks = BOOKMAKERS.filter((bookmaker) => input.sportsbookKeys.includes(bookmaker));
  const missingRequestedBooks = BOOKMAKERS.filter((bookmaker) => !input.sportsbookKeys.includes(bookmaker));
  const unrequestedBooks = input.sportsbookKeys.filter(
    (bookmaker) => !BOOKMAKERS.includes(bookmaker) && bookmaker !== "unknown",
  );
  const returnedRequestedMarkets = MARKETS.filter((market) => input.marketKeys.includes(market));

  return [
    `markets=${MARKETS.join(",")}: ${
      returnedRequestedMarkets.length > 0
        ? `supported (${returnedRequestedMarkets.join(", ")} returned)`
        : "accepted but no requested markets were returned; possibly no data or the filter was ignored"
    }`,
    `bookmakers=${BOOKMAKERS.join(",")}: ${bookmakerSupportText(
      returnedRequestedBooks,
      missingRequestedBooks,
      unrequestedBooks,
    )}`,
    `includeLinks=true: ${
      input.linkDiscoveries.length > 0
        ? "supported/populated (link-like fields returned)"
        : "accepted but no link-like fields were returned; possibly ignored or unavailable for this event"
    }`,
    `includeSids=true: ${
      input.idDiscoveries.length > 0
        ? "supported/populated (SID/native ID-like fields returned)"
        : "accepted but no SID/native ID-like fields were returned; possibly ignored or unavailable for this event"
    }`,
  ];
}

function bookmakerSupportText(
  returnedRequestedBooks: string[],
  missingRequestedBooks: string[],
  unrequestedBooks: string[],
): string {
  if (returnedRequestedBooks.length === BOOKMAKERS.length && unrequestedBooks.length === 0) {
    return `supported (${returnedRequestedBooks.join(", ")} returned)`;
  }

  if (returnedRequestedBooks.length === 0) {
    return "accepted but none of the requested bookmakers were returned";
  }

  const details = [`returned requested: ${returnedRequestedBooks.join(", ")}`];
  if (missingRequestedBooks.length > 0) {
    details.push(`missing requested: ${missingRequestedBooks.join(", ")}`);
  }
  if (unrequestedBooks.length > 0) {
    details.push(`also returned unrequested: ${unrequestedBooks.join(", ")}`);
  }

  return `accepted but appears partially supported or ignored (${details.join("; ")})`;
}

function determineStrongestLinkingLevel(
  linkDiscoveries: Discovery[],
  idDiscoveries: Discovery[],
):
  | "EXACT_SELECTION_LINK"
  | "MARKET_LINK"
  | "EVENT_OR_BOOK_LINK"
  | "SPORTSBOOK_IDS_ONLY"
  | "NO_LINK_SUPPORT" {
  if (linkDiscoveries.some((discovery) => discovery.level === "outcome")) {
    return "EXACT_SELECTION_LINK";
  }
  if (linkDiscoveries.some((discovery) => discovery.level === "market")) {
    return "MARKET_LINK";
  }
  if (linkDiscoveries.length > 0) {
    return "EVENT_OR_BOOK_LINK";
  }
  if (idDiscoveries.length > 0) {
    return "SPORTSBOOK_IDS_ONLY";
  }
  return "NO_LINK_SUPPORT";
}

function buildConclusion(
  bookmakerEntries: BookmakerEntry[],
  linkDiscoveries: Discovery[],
  idDiscoveries: Discovery[],
): string {
  const outcomeLinkBooks = booksWithOutcomeLinks(bookmakerEntries);
  if (outcomeLinkBooks.length > 0) {
    return `PropLine returned outcome-level sportsbook links for ${outcomeLinkBooks.join(", ")}.`;
  }

  if (linkDiscoveries.some((discovery) => discovery.level === "market")) {
    return "PropLine accepted the parameters and returned market-level sportsbook links, but no outcome-level links.";
  }

  if (linkDiscoveries.length > 0) {
    return "PropLine accepted the parameters and returned event/bookmaker-level links only; no exact outcome links were found.";
  }

  if (idDiscoveries.length > 0) {
    return "PropLine accepted the parameters and returned sportsbook-native ID fields, but no link fields were found.";
  }

  return "PropLine accepted the parameters but returned no link or SID fields, so exact sportsbook linking is not currently available through this response.";
}

function booksWithOutcomeLinks(bookmakerEntries: BookmakerEntry[]): string[] {
  const books: string[] = [];

  for (const { bookmaker } of bookmakerEntries) {
    const markets = bookmaker.markets;
    if (!Array.isArray(markets)) {
      continue;
    }

    const hasOutcomeLink = markets.some((market) => {
      if (!isJsonObject(market) || !Array.isArray(market.outcomes)) {
        return false;
      }

      return market.outcomes.some(
        (outcome) => isJsonObject(outcome) && firstDiscoveryValue(outcome, LINK_FIELD_TERMS),
      );
    });

    if (hasOutcomeLink) {
      books.push(bookmakerLabel(bookmaker));
    }
  }

  return unique(books);
}

function printFetchFailureReport(
  endpointLabel: string,
  result: Exclude<FetchResult, { ok: true }>,
  event?: { eventId: string; awayTeam: string; homeTeam: string; startTime: string },
): void {
  console.log("PropLine MLB player-prop link/SID support report");
  console.log("==================================================");
  if (event) {
    console.log(`Event ID: ${event.eventId}`);
    console.log(`Away team: ${event.awayTeam}`);
    console.log(`Home team: ${event.homeTeam}`);
    console.log(`Start time: ${event.startTime}`);
  }
  console.log(`Failed while calling the ${endpointLabel} endpoint.`);
  console.log(`HTTP status: ${result.status}`);

  if (result.status === 429) {
    console.log("Rate limit handling: PropLine returned HTTP 429.");
  }

  if (result.errorKind === "invalid_json") {
    console.log("Invalid JSON handling: PropLine returned a response body that could not be parsed as JSON.");
  } else {
    console.log("HTTP error handling: PropLine rejected or failed the request.");
    console.log(`Redacted error body: ${formatValue(redactJsonValue(result.data ?? null))}`);
  }

  console.log("");
  console.log("Requested query parameter support");
  console.log("---------------------------------");
  if (endpointLabel === "event odds" && [400, 404, 422].includes(result.status)) {
    console.log("- One or more requested odds query parameters appear rejected by the API.");
  } else if (endpointLabel === "event odds") {
    console.log("- Query parameter support could not be determined because the odds request failed.");
  } else {
    console.log("- Odds query parameter support was not tested because the events request failed first.");
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function isJsonObject(value: JsonValue): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: JsonValue | undefined): string | undefined {
  if (typeof value === "string" && value.trim() !== "") {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "boolean") {
    return String(value);
  }
  return undefined;
}

function formatValue(value: JsonValue): string {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter((value) => value.trim() !== ""))];
}

void main();
