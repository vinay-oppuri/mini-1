import { NextResponse } from "next/server";

import { BackendRequestError, callBackend } from "@/lib/backend-api";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await callBackend("/health", { method: "GET" });
    return NextResponse.json(result, { status: 200 });
  } catch (error) {
    if (error instanceof BackendRequestError) {
      return NextResponse.json(
        {
          status: "error",
          error: error.message,
          detail: error.detail,
        },
        { status: error.status }
      );
    }

    return NextResponse.json(
      {
        status: "error",
        error: "Unexpected health check failure.",
      },
      { status: 500 }
    );
  }
}
