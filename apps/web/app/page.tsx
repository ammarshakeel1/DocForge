"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { extractDocument, uploadDocument } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose a PDF invoice first.");
      return;
    }

    setBusy(true);
    setError(null);
    setStatus("Uploading…");
    try {
      const doc = await uploadDocument(file);
      setStatus("Extracting fields with OpenAI…");
      // Soft OCR/text failures still land on the review page with status needs_review.
      await extractDocument(doc.id);
      router.push(`/documents/${doc.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">Upload invoice</h1>
      <p className="mt-2 text-[var(--muted)]">
        Upload a synthetic PDF invoice. DocForge stores it, extracts structured fields, then opens
        the review screen.
      </p>

      <form
        onSubmit={onSubmit}
        className="mt-6 space-y-4 rounded-lg border border-[var(--border)] bg-[var(--panel)] p-5"
      >
        <label className="block text-sm font-medium">
          PDF file
          <input
            type="file"
            accept="application/pdf,.pdf"
            className="mt-2 block w-full text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
        </label>

        <button
          type="submit"
          disabled={busy || !file}
          className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Working…" : "Upload & extract"}
        </button>

        {status && <p className="text-sm text-[var(--muted)]">{status}</p>}
        {error && (
          <p className="rounded-md bg-[var(--warn-bg)] px-3 py-2 text-sm text-[var(--warn)]">
            {error}
          </p>
        )}
      </form>

      <p className="mt-6 text-sm text-[var(--muted)]">
        Sample PDFs live in <code className="font-mono">samples/invoices/</code>. Configure{" "}
        <code className="font-mono">.env</code> with Supabase + OpenAI before running the API.
      </p>
    </div>
  );
}
