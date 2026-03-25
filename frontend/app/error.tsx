"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col items-center justify-center px-6">
      <div className="glass-panel w-full rounded-3xl p-8 text-center">
        <p className="text-xs uppercase tracking-[0.18em] text-muted">Frontend Error</p>
        <h1 className="mt-3 text-2xl font-semibold">Something went wrong</h1>
        <p className="mt-3 text-sm text-muted">{error.message}</p>
        <button
          type="button"
          onClick={() => reset()}
          className="mt-5 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:brightness-95"
        >
          Retry
        </button>
      </div>
    </main>
  );
}
