import { NextRequest, NextResponse } from "next/server";

import { BackendRequestError, callBackend } from "@/lib/backend-api";
import type { AnalyzeRequestPayload, LogEntry } from "@/types/analyzer";

export const dynamic = "force-dynamic";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isLogEntry(value: unknown): value is LogEntry {
  return typeof value === "string" || isRecord(value);
}

function parsePayload(body: unknown): AnalyzeRequestPayload {
  if (!isRecord(body)) {
    throw new Error("Request body must be a JSON object.");
  }

  if (!Array.isArray(body.logs) || body.logs.length === 0) {
    throw new Error("`logs` must be a non-empty array.");
  }

  const hasInvalidEntries = body.logs.some((item) => !isLogEntry(item));
  if (hasInvalidEntries) {
    throw new Error("Every log entry must be either a string or an object.");
  }

  const source =
    typeof body.source === "string" && body.source.trim()
      ? body.source.trim()
      : "frontend-ui";

  const thresholdValue =
    typeof body.unknown_ratio_threshold === "number"
      ? body.unknown_ratio_threshold
      : 0.3;

  if (Number.isNaN(thresholdValue) || thresholdValue < 0 || thresholdValue > 1) {
    throw new Error("`unknown_ratio_threshold` must be between 0 and 1.");
  }

  return {
    logs: body.logs,
    source,
    unknown_ratio_threshold: thresholdValue,
  };
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const payload = parsePayload(body);

    const result = await callBackend("/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    return NextResponse.json(result, { status: 200 });
  } catch (error) {
    if (error instanceof BackendRequestError) {
      return NextResponse.json(
        {
          error: error.message,
          detail: error.detail,
        },
        { status: error.status }
      );
    }

    if (error instanceof SyntaxError) {
      return NextResponse.json({ error: "Invalid JSON request body." }, { status: 400 });
    }

    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unexpected request failure.",
      },
      { status: 400 }
    );
  }
}
