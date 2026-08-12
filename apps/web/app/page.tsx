"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { extractDocument, uploadDocument } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function pickFile(next: File | null) {
    if (!next) {
      setFile(null);
      return;
    }
    if (!next.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      setFile(null);
      return;
    }
    setError(null);
    setFile(next);
  }

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
        <div>
          <p className="mb-2 text-sm font-medium">PDF invoice</p>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragOver(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              pickFile(e.dataTransfer.files?.[0] ?? null);
            }}
            className={`flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-10 text-center transition-colors ${
              dragOver
                ? "border-[var(--accent)] bg-[#e8f5f1]"
                : file
                  ? "border-[var(--accent)] bg-[#f3faf7]"
                  : "border-[var(--border)] bg-[var(--background)] hover:border-[var(--accent)] hover:bg-[#f3faf7]"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <span className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white">
              {file ? "Change PDF" : "Choose PDF"}
            </span>
            <span className="mt-3 text-sm text-[var(--muted)]">
              {file ? (
                <>
                  Selected: <span className="font-medium text-[var(--foreground)]">{file.name}</span>
                </>
              ) : (
                "Click here or drag and drop a .pdf file"
              )}
            </span>
          </button>
        </div>

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
        Sample PDFs live in <code className="font-mono">samples/invoices/</code>.
      </p>
    </div>
  );
}
