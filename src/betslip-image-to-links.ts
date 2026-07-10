import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  type CliOptions,
  type ExtractedSlip,
  type JsonValue,
  printReport,
  resolveBetslipToLinks,
  validateSlip,
} from "./betslip-to-links.js";

type ImageCliOptions = {
  imagePath?: string;
  extractedOutputPath: string;
  resultOutputPath: string;
  regions: string;
  bookmakers?: string;
  model: string;
};

type GeminiResponse = {
  candidates?: Array<{
    content?: {
      parts?: Array<{
        text?: string;
      }>;
    };
  }>;
};

const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta";
const DEFAULT_MODEL = "gemini-2.5-flash";
const DEFAULT_EXTRACTED_OUTPUT_PATH = path.join("output", "extracted-betslip.json");
const DEFAULT_RESULT_OUTPUT_PATH = path.join("output", "betslip-image-link-result.json");
const REQUEST_TIMEOUT_MS = 30_000;

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2));
  const geminiApiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY;
  const oddsApiKey = process.env.ODDS_API_KEY ?? process.env.THE_ODDS_API_KEY;

  if (!geminiApiKey) {
    console.error("Missing GEMINI_API_KEY. Set it in the environment and rerun the command.");
    process.exitCode = 1;
    return;
  }

  if (!oddsApiKey) {
    console.error("Missing ODDS_API_KEY. Set it in the environment and rerun the command.");
    process.exitCode = 1;
    return;
  }

  if (!options.imagePath) {
    console.error("Missing --image path.");
    process.exitCode = 1;
    return;
  }

  try {
    const extractedSlip = await extractSlipFromImage(options.imagePath, geminiApiKey, options.model);

    await mkdir(path.dirname(options.extractedOutputPath), { recursive: true });
    await writeFile(options.extractedOutputPath, `${JSON.stringify(extractedSlip, null, 2)}\n`, "utf8");

    const resolverOptions: CliOptions = {
      inputPath: options.extractedOutputPath,
      outputPath: options.resultOutputPath,
      regions: options.regions,
      bookmakers: options.bookmakers,
      sampleLive: false,
      sampleLegs: 2,
      maxSampleEvents: 8,
    };

    const result = await resolveBetslipToLinks(extractedSlip, oddsApiKey, resolverOptions);

    await mkdir(path.dirname(options.resultOutputPath), { recursive: true });
    await writeFile(options.resultOutputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

    printExtractionReport(extractedSlip, options.extractedOutputPath);
    printReport(result, options.resultOutputPath);
  } catch (error) {
    if (isAbortError(error)) {
      console.error(`Request timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`);
    } else {
      console.error(`Failed to resolve image betslip: ${error instanceof Error ? error.message : String(error)}`);
    }
    process.exitCode = 1;
  }
}

function parseArgs(args: string[]): ImageCliOptions {
  const options: ImageCliOptions = {
    extractedOutputPath: DEFAULT_EXTRACTED_OUTPUT_PATH,
    resultOutputPath: DEFAULT_RESULT_OUTPUT_PATH,
    regions: "us",
    model: DEFAULT_MODEL,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    const next = args[index + 1];

    if (arg === "--image" && next) {
      options.imagePath = next;
      index += 1;
    } else if (arg.startsWith("--image=")) {
      options.imagePath = arg.slice("--image=".length);
    } else if (arg === "--extracted-output" && next) {
      options.extractedOutputPath = next;
      index += 1;
    } else if (arg.startsWith("--extracted-output=")) {
      options.extractedOutputPath = arg.slice("--extracted-output=".length);
    } else if (arg === "--output" && next) {
      options.resultOutputPath = next;
      index += 1;
    } else if (arg.startsWith("--output=")) {
      options.resultOutputPath = arg.slice("--output=".length);
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
    } else if (arg === "--model" && next) {
      options.model = next;
      index += 1;
    } else if (arg.startsWith("--model=")) {
      options.model = arg.slice("--model=".length);
    } else if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    } else if (!arg.startsWith("-") && !options.imagePath) {
      options.imagePath = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return options;
}

function printUsage(): void {
  console.log(`Usage:
  npm run resolve:betslip:image -- --image path/to/betslip.jpg

Environment:
  GEMINI_API_KEY must be set for image extraction.
  ODDS_API_KEY must be set for sportsbook link resolution.

Options:
  --image <path>              Betslip screenshot image.
  --extracted-output <path>   Extracted JSON output. Default: ${DEFAULT_EXTRACTED_OUTPUT_PATH}
  --output <path>             Result JSON output. Default: ${DEFAULT_RESULT_OUTPUT_PATH}
  --regions <regions>         The Odds API regions. Default: us
  --bookmakers <keys>         Optional comma-separated bookmaker keys instead of regions.
  --model <model>             Gemini model. Default: ${DEFAULT_MODEL}
`);
}

async function extractSlipFromImage(imagePath: string, apiKey: string, model: string): Promise<ExtractedSlip> {
  const image = await readFile(imagePath);
  const mimeType = mimeTypeForPath(imagePath);
  const response = await callGemini({
    apiKey,
    model,
    mimeType,
    base64Image: image.toString("base64"),
  });

  const text = response.candidates?.[0]?.content?.parts?.map((part) => part.text ?? "").join("\n").trim();
  if (!text) {
    throw new Error("Gemini returned no extraction text.");
  }

  const parsed = parseJsonFromModel(text);
  return validateSlip(parsed);
}

async function callGemini(input: {
  apiKey: string;
  model: string;
  mimeType: string;
  base64Image: string;
}): Promise<GeminiResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${GEMINI_BASE_URL}/models/${encodeURIComponent(input.model)}:generateContent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-goog-api-key": input.apiKey,
      },
      body: JSON.stringify({
        contents: [
          {
            role: "user",
            parts: [
              { text: extractionPrompt() },
              {
                inline_data: {
                  mime_type: input.mimeType,
                  data: input.base64Image,
                },
              },
            ],
          },
        ],
        generationConfig: {
          temperature: 0,
          responseMimeType: "application/json",
        },
      }),
      signal: controller.signal,
    });

    const body = await response.text();
    const parsed = parseJson(body);

    if (!response.ok) {
      throw new Error(`Gemini returned HTTP ${response.status}: ${geminiErrorMessage(parsed) ?? "request failed"}`);
    }

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Gemini returned invalid JSON.");
    }

    return parsed as GeminiResponse;
  } finally {
    clearTimeout(timeout);
  }
}

function extractionPrompt(): string {
  return `Extract the betslip in this image into strict JSON only.

Return this exact shape:
{
  "betType": "single" | "parlay" | "same_game_parlay" | "unknown",
  "sportKey": "baseball_mlb" | "basketball_nba" | "football_nfl" | "hockey_nhl" | "unknown",
  "legs": [
    {
      "sportKey": "baseball_mlb",
      "player": "Player Name",
      "team": "NYY",
      "opponent": "WSH",
      "marketKey": "batter_home_runs",
      "side": "Over",
      "point": 0.5,
      "price": 320,
      "rawText": "visible text for the leg"
    }
  ]
}

Rules:
- Return JSON only. No markdown.
- Extract all visible legs.
- If the slip says "To Hit A Home Run", normalize to marketKey "batter_home_runs", side "Over", point 0.5.
- If the slip says "Over 0.5 Home Runs", normalize to marketKey "batter_home_runs", side "Over", point 0.5.
- Use American odds as numbers, without plus signs.
- Use team abbreviations when visible, such as NYY, WSH, CHC, CIN, ATH, CWS, TOR, SD.
- If a field is not visible or not knowable, omit it except rawText.
- Do not invent legs that are not visible.`;
}

function parseJsonFromModel(text: string): JsonValue {
  const direct = parseJson(text);
  if (direct !== undefined) {
    return direct;
  }

  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
  if (fenced?.[1]) {
    const parsed = parseJson(fenced[1]);
    if (parsed !== undefined) {
      return parsed;
    }
  }

  const objectStart = text.indexOf("{");
  const objectEnd = text.lastIndexOf("}");
  if (objectStart >= 0 && objectEnd > objectStart) {
    const parsed = parseJson(text.slice(objectStart, objectEnd + 1));
    if (parsed !== undefined) {
      return parsed;
    }
  }

  throw new Error("Could not parse Gemini extraction as JSON.");
}

function parseJson(text: string): JsonValue | undefined {
  try {
    return JSON.parse(text) as JsonValue;
  } catch {
    return undefined;
  }
}

function geminiErrorMessage(value: JsonValue | undefined): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }

  const error = value.error;
  if (!error || typeof error !== "object" || Array.isArray(error)) {
    return undefined;
  }

  return typeof error.message === "string" ? error.message : undefined;
}

function mimeTypeForPath(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".png") return "image/png";
  if (extension === ".webp") return "image/webp";
  if (extension === ".jpg" || extension === ".jpeg") return "image/jpeg";
  throw new Error(`Unsupported image extension: ${extension || "(none)"}`);
}

function printExtractionReport(slip: ExtractedSlip, extractedOutputPath: string): void {
  console.log("Gemini betslip extraction report");
  console.log("================================");
  console.log(`Bet type: ${slip.betType ?? "unknown"}`);
  console.log(`Sport: ${slip.sportKey ?? "unknown"}`);
  console.log(`Legs extracted: ${slip.legs.length}`);
  console.log(`Saved extracted slip: ${extractedOutputPath}`);
  for (const [index, leg] of slip.legs.entries()) {
    console.log(
      `#${index + 1}: ${leg.player ?? "Unknown"} | ${leg.marketKey ?? "unknown_market"} | ${leg.side ?? "unknown_side"} ${leg.point ?? ""} | ${leg.team ?? "?"} vs ${leg.opponent ?? "?"} | ${leg.price ?? ""}`,
    );
  }
  console.log("");
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

void main();
