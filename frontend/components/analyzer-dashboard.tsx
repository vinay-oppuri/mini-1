"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

import type { AnalyzeResponse, LogEntry } from "@/types/analyzer";

type InputMode = "json" | "lines";

type HealthState = {
  status: "loading" | "ready" | "error";
  detail: string;
};

const SAMPLE_JSON_LOGS = JSON.stringify(
  [
    {
      timestamp: "2026-03-25T10:00:00Z",
      level: "ERROR",
      service: "auth-service",
      message: "Login failed for user admin from IP 203.0.113.17",
    },
    {
      timestamp: "2026-03-25T10:00:02Z",
      level: "WARN",
      service: "api-gateway",
      message: "Too many requests from 203.0.113.17 status=503 rps=1320",
    },
    {
      timestamp: "2026-03-25T10:00:05Z",
      level: "ERROR",
      service: "ml-trainer",
      message: "Suspicious outbound transfer 1.2GB from pod to 203.0.113.17",
    },
  ],
  null,
  2
);

const SAMPLE_LINE_LOGS = [
  "2026-03-25T10:00:00Z | ERROR | auth-service | Login failed for user admin from IP 203.0.113.17",
  "2026-03-25T10:00:02Z | WARN | api-gateway | Too many requests from 203.0.113.17 status=503 rps=1320",
  "2026-03-25T10:00:05Z | ERROR | ml-trainer | Suspicious outbound transfer 1.2GB from pod to 203.0.113.17",
].join("\n");

function scoreLabel(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "n/a";
  }
  return value.toFixed(4);
}

function percentLabel(value: number | undefined): string {
  if (typeof value !== "number") {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function parseLogs(mode: InputMode, input: string): LogEntry[] {
  if (mode === "json") {
    let parsed: unknown;
    try {
      parsed = JSON.parse(input);
    } catch {
      throw new Error("JSON mode expects valid JSON.");
    }

    if (!Array.isArray(parsed) || parsed.length === 0) {
      throw new Error("JSON mode expects a non-empty array of log entries.");
    }

    return parsed as LogEntry[];
  }

  const lines = input
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    throw new Error("Line mode expects at least one non-empty log line.");
  }

  return lines;
}

export function AnalyzerDashboard() {
  const [inputMode, setInputMode] = useState<InputMode>("json");
  const [payload, setPayload] = useState<string>(SAMPLE_JSON_LOGS);
  const [source, setSource] = useState<string>("frontend-ui");
  const [threshold, setThreshold] = useState<string>("0.30");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [health, setHealth] = useState<HealthState>({
    status: "loading",
    detail: "Checking backend connectivity...",
  });

  const thresholdValue = useMemo(() => {
    const parsed = Number.parseFloat(threshold);
    return Number.isFinite(parsed) ? parsed : 0.3;
  }, [threshold]);

  async function refreshHealth() {
    setHealth({
      status: "loading",
      detail: "Checking backend connectivity...",
    });

    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      const data = (await response.json()) as Record<string, unknown>;

      if (!response.ok) {
        throw new Error(
          typeof data.error === "string"
            ? data.error
            : "Health check failed. Backend may be offline."
        );
      }

      const mode = typeof data.model_mode === "string" ? data.model_mode : "unknown";
      setHealth({
        status: "ready",
        detail: `Backend online (${mode})`,
      });
    } catch (err) {
      setHealth({
        status: "error",
        detail: err instanceof Error ? err.message : "Health check failed.",
      });
    }
  }

  useEffect(() => {
    void refreshHealth();
  }, []);

  function changeMode(nextMode: InputMode) {
    setInputMode(nextMode);
    setPayload(nextMode === "json" ? SAMPLE_JSON_LOGS : SAMPLE_LINE_LOGS);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      if (thresholdValue < 0 || thresholdValue > 1) {
        throw new Error("Threshold must be between 0 and 1.");
      }

      const logs = parseLogs(inputMode, payload);
      setIsSubmitting(true);

      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          logs,
          source: source.trim() || "frontend-ui",
          unknown_ratio_threshold: thresholdValue,
        }),
      });

      const data = (await response.json()) as Record<string, unknown>;
      if (!response.ok) {
        throw new Error(
          typeof data.error === "string"
            ? data.error
            : `Analyze request failed with status ${response.status}.`
        );
      }

      setResult(data as AnalyzeResponse);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Unexpected request error.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const anomalyScore = result?.analysis?.anomaly_score;
  const isAnomaly = result?.analysis?.is_anomaly;
  const actionList = result?.response?.actions ?? [];
  const executedActions = result?.response?.executed_actions ?? [];
  const compatibility = result?.compatibility;
  const llm = result?.llm_explanation;
  const cloudMetrics = result?.cloud_metrics;
  const decision = result?.decision;

  return (
    <section className="flex flex-1 flex-col gap-5 pb-6">
      <header className="glass-panel rounded-3xl p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
              Cloud Sentinel
            </p>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Log Anomaly Console
            </h1>
            <p className="text-sm text-muted">
              Submit logs, run backend analysis, and inspect response recommendations.
            </p>
          </div>
          <div className="rounded-full border border-border bg-surface px-4 py-2 text-sm text-foreground">
            <span
              className={`mr-2 inline-block status-dot ${
                health.status === "ready"
                  ? "bg-emerald-500"
                  : health.status === "error"
                    ? "bg-danger"
                    : "bg-amber-500"
              }`}
            />
            {health.detail}
          </div>
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-5 lg:grid-cols-[1.1fr_1fr]">
        <article className="glass-panel rounded-3xl p-6">
          <h2 className="text-lg font-semibold">Input</h2>
          <p className="mt-1 text-sm text-muted">
            Choose input format, adjust threshold, and send logs to the backend analyzer.
          </p>

          <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-medium text-foreground">Source label</span>
                <input
                  className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent-soft"
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                  placeholder="frontend-ui"
                  autoComplete="off"
                />
              </label>

              <label className="space-y-2">
                <span className="text-sm font-medium text-foreground">
                  Unknown ratio threshold
                </span>
                <input
                  className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent-soft"
                  value={threshold}
                  onChange={(event) => setThreshold(event.target.value)}
                  inputMode="decimal"
                  placeholder="0.30"
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className={`rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] transition ${
                  inputMode === "json"
                    ? "border-accent bg-accent text-white"
                    : "border-border bg-surface text-muted hover:border-accent"
                }`}
                onClick={() => changeMode("json")}
              >
                JSON Mode
              </button>
              <button
                type="button"
                className={`rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] transition ${
                  inputMode === "lines"
                    ? "border-accent bg-accent text-white"
                    : "border-border bg-surface text-muted hover:border-accent"
                }`}
                onClick={() => changeMode("lines")}
              >
                Line Mode
              </button>
            </div>

            <label className="space-y-2">
              <span className="text-sm font-medium text-foreground">
                {inputMode === "json" ? "JSON payload" : "Log lines"}
              </span>
              <textarea
                className="h-72 w-full resize-y rounded-2xl border border-border bg-surface px-3 py-3 font-mono text-xs leading-5 text-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent-soft"
                value={payload}
                onChange={(event) => setPayload(event.target.value)}
                spellCheck={false}
              />
            </label>

            {error ? (
              <div className="rounded-xl border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSubmitting ? "Running analysis..." : "Run Analysis"}
              </button>
              <button
                type="button"
                className="rounded-xl border border-border bg-surface px-4 py-2 text-sm font-semibold text-foreground transition hover:border-accent"
                onClick={() => void refreshHealth()}
              >
                Recheck Backend
              </button>
            </div>
          </form>
        </article>

        <article className="glass-panel rounded-3xl p-6">
          <h2 className="text-lg font-semibold">Results</h2>
          <p className="mt-1 text-sm text-muted">
            Decision summary, model confidence, policy output, and recommended actions.
          </p>

          {!result ? (
            <div className="mt-6 rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
              No analysis yet. Submit logs to view model and policy output.
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-border bg-surface p-3">
                  <p className="text-xs uppercase tracking-wide text-muted">Status</p>
                  <p className="mt-1 text-base font-semibold text-foreground">
                    {decision?.status ?? "n/a"}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-surface p-3">
                  <p className="text-xs uppercase tracking-wide text-muted">Anomaly score</p>
                  <p className="mt-1 text-base font-semibold text-foreground">
                    {scoreLabel(anomalyScore)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-surface p-3">
                  <p className="text-xs uppercase tracking-wide text-muted">Severity</p>
                  <p className="mt-1 text-base font-semibold text-foreground">
                    {decision?.severity ?? result.policy?.severity ?? "n/a"}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-surface p-3">
                  <p className="text-xs uppercase tracking-wide text-muted">Supported profile</p>
                  <p className="mt-1 text-base font-semibold text-foreground">
                    {compatibility?.is_supported ? "yes" : "no"}
                  </p>
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs uppercase tracking-wide text-muted">LLM explanation</p>
                <p className="mt-2 text-sm text-foreground">
                  <strong>Attack:</strong> {llm?.attack_type ?? "n/a"}
                </p>
                <p className="mt-1 text-sm text-foreground">
                  <strong>Reason:</strong> {llm?.reason ?? "n/a"}
                </p>
                <p className="mt-1 text-sm text-foreground">
                  <strong>Recommended action:</strong>{" "}
                  {llm?.recommended_action ?? "n/a"}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Source: {llm?.source ?? "n/a"}
                </p>
              </div>

              <div className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs uppercase tracking-wide text-muted">Actions</p>
                <ul className="mt-2 space-y-1 text-sm text-foreground">
                  {actionList.length === 0 ? (
                    <li>No response actions returned.</li>
                  ) : (
                    actionList.map((action, index) => <li key={`${action}-${index}`}>- {action}</li>)
                  )}
                </ul>
                {executedActions.length > 0 ? (
                  <p className="mt-2 text-xs text-muted">
                    Executed IDs: {executedActions.join(", ")}
                  </p>
                ) : null}
              </div>

              <div className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs uppercase tracking-wide text-muted">Telemetry</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  <p>
                    <strong>Total logs:</strong> {cloudMetrics?.total_logs ?? "n/a"}
                  </p>
                  <p>
                    <strong>Failed logs:</strong> {cloudMetrics?.failed_logs ?? "n/a"}
                  </p>
                  <p>
                    <strong>Error rate:</strong> {percentLabel(cloudMetrics?.error_rate)}
                  </p>
                  <p>
                    <strong>Anomaly flag:</strong>{" "}
                    {typeof isAnomaly === "boolean" ? String(isAnomaly) : "n/a"}
                  </p>
                  <p>
                    <strong>Unknown ratio:</strong>{" "}
                    {percentLabel(compatibility?.unknown_event_ratio)}
                  </p>
                  <p>
                    <strong>Top service:</strong> {cloudMetrics?.top_service ?? "n/a"}
                  </p>
                </div>
              </div>

              <details className="rounded-2xl border border-border bg-surface p-4">
                <summary className="cursor-pointer text-sm font-semibold text-foreground">
                  Raw result JSON
                </summary>
                <pre className="mt-3 max-h-72 overflow-auto rounded-xl bg-surface-strong p-3 font-mono text-xs text-foreground">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
