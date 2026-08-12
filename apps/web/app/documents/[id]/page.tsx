"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Document,
  ExtractedField,
  exportCsvUrl,
  exportJsonUrl,
  getDocument,
  getFields,
  pdfUrl,
  reviewDocument,
} from "@/lib/api";

function displayValue(field: ExtractedField, draft: string | undefined): string {
  if (draft !== undefined) return draft;
  if (field.reviewed_value != null && field.reviewed_value !== "") {
    return field.reviewed_value;
  }
  return field.field_value ?? "";
}

function statusLabel(status: Document["status"] | undefined): string {
  switch (status) {
    case "needs_review":
      return "Needs review";
    case "approved":
      return "Approved — ready to export";
    case "exported":
      return "Exported";
    case "processing":
      return "Processing";
    case "uploaded":
      return "Uploaded";
    case undefined:
      return "Unknown";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function statusTone(status: Document["status"] | undefined): string {
  switch (status) {
    case "approved":
    case "exported":
      return "bg-[#e8f5f1] text-[#0b5744] border-[#b7e0d2]";
    case "needs_review":
      return "bg-[var(--warn-bg)] text-[var(--warn)] border-orange-300";
    case "processing":
    case "uploaded":
    case undefined:
      return "bg-[var(--background)] text-[var(--muted)] border-[var(--border)]";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

export default function DocumentReviewPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [document, setDocument] = useState<Document | null>(null);
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [doc, extracted] = await Promise.all([getDocument(id), getFields(id)]);
        if (cancelled) return;
        setDocument(doc);
        setFields(extracted);
        const initial: Record<string, string> = {};
        for (const field of extracted) {
          initial[field.field_name] =
            field.reviewed_value != null && field.reviewed_value !== ""
              ? field.reviewed_value
              : (field.field_value ?? "");
        }
        setDrafts(initial);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load document");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const lowConfidenceCount = useMemo(
    () => fields.filter((f) => f.needs_review).length,
    [fields],
  );

  const canExport = document?.status === "approved" || document?.status === "exported";

  async function saveReview(approve: boolean) {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updates = fields
        .map((field) => {
          const next = drafts[field.field_name] ?? "";
          const current =
            field.reviewed_value != null && field.reviewed_value !== ""
              ? field.reviewed_value
              : (field.field_value ?? "");
          if (next === current && !approve) return null;
          return { field_name: field.field_name, reviewed_value: next };
        })
        .filter((item): item is { field_name: string; reviewed_value: string } => item !== null);

      const payloadFields = approve
        ? fields.map((field) => ({
            field_name: field.field_name,
            reviewed_value: drafts[field.field_name] ?? field.field_value ?? "",
          }))
        : updates;

      const result = await reviewDocument(id, {
        fields: payloadFields,
        approve,
      });
      setDocument(result.document);
      setFields(result.fields);
      setMessage(
        approve
          ? "Approved and saved to Supabase. Status is now approved — use Export CSV/JSON above to download the final data."
          : "Edits saved to Supabase (reviewed values stored). Status stays needs review until you Approve.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-[var(--muted)]">Loading document…</p>;
  }

  if (error && !document) {
    return (
      <p className="rounded-md bg-[var(--warn-bg)] px-3 py-2 text-sm text-[var(--warn)]">
        {error}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Review extraction</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">{document?.original_filename}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${statusTone(document?.status)}`}
            >
              {statusLabel(document?.status)}
            </span>
            {lowConfidenceCount > 0 && document?.status === "needs_review" && (
              <span className="text-xs text-[var(--muted)]">
                {lowConfidenceCount} field(s) flagged for review
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex flex-wrap gap-2">
            {canExport ? (
              <>
                <a
                  href={exportCsvUrl(id)}
                  className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
                >
                  Export CSV
                </a>
                <a
                  href={exportJsonUrl(id)}
                  className="rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm font-medium hover:bg-[var(--background)]"
                >
                  Export JSON
                </a>
              </>
            ) : (
              <>
                <button
                  type="button"
                  disabled
                  title="Approve the document before exporting"
                  className="cursor-not-allowed rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white opacity-40"
                >
                  Export CSV
                </button>
                <button
                  type="button"
                  disabled
                  title="Approve the document before exporting"
                  className="cursor-not-allowed rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm font-medium opacity-40"
                >
                  Export JSON
                </button>
              </>
            )}
          </div>
          {!canExport && (
            <p className="text-xs text-[var(--muted)]">Approve first to unlock export</p>
          )}
        </div>
      </div>

      <p className="rounded-md border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--muted)]">
        <span className="font-medium text-[var(--foreground)]">What the buttons do:</span>{" "}
        <strong>Save review</strong> writes your edits to Supabase and keeps the doc in review.{" "}
        <strong>Approve</strong> validates required fields, marks the doc approved in Supabase, then
        unlocks CSV/JSON export. Nothing navigates away — you stay on this page.
      </p>

      {error && (
        <p className="rounded-md bg-[var(--warn-bg)] px-3 py-2 text-sm text-[var(--warn)]">
          {error}
        </p>
      )}
      {message && (
        <p className="rounded-md border border-[#b7e0d2] bg-[#e8f5f1] px-3 py-2 text-sm text-[#0b5744]">
          {message}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="min-h-[70vh] overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--panel)]">
          <div className="border-b border-[var(--border)] px-3 py-2 text-sm font-medium">
            Original PDF
          </div>
          <iframe
            title="Invoice PDF"
            src={pdfUrl(id)}
            className="h-[70vh] w-full bg-white"
          />
        </section>

        <section className="rounded-lg border border-[var(--border)] bg-[var(--panel)]">
          <div className="border-b border-[var(--border)] px-3 py-2 text-sm font-medium">
            Extracted fields
          </div>
          <div className="space-y-3 p-3">
            {fields.map((field) => {
              const value = displayValue(field, drafts[field.field_name]);
              const isLow = field.needs_review;
              return (
                <label
                  key={field.id}
                  className={`block rounded-md border px-3 py-2 ${
                    isLow
                      ? "border-orange-300 bg-[var(--warn-bg)]"
                      : "border-[var(--border)] bg-white"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{field.field_name}</span>
                    <span className="font-mono text-xs text-[var(--muted)]">
                      conf{" "}
                      {field.confidence != null ? field.confidence.toFixed(2) : "—"}
                      {isLow ? " · needs review" : ""}
                    </span>
                  </div>
                  {field.field_name === "line_items" ? (
                    <>
                      <p className="mb-1 text-xs text-[var(--muted)]">
                        Stored as one JSON field for v0.1 (edit only if needed).
                      </p>
                      <textarea
                        className="w-full rounded border border-[var(--border)] bg-white px-2 py-1 font-mono text-sm"
                        rows={6}
                        value={value}
                        onChange={(e) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [field.field_name]: e.target.value,
                          }))
                        }
                      />
                    </>
                  ) : (
                    <input
                      className="w-full rounded border border-[var(--border)] bg-white px-2 py-1 text-sm"
                      value={value}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [field.field_name]: e.target.value,
                        }))
                      }
                    />
                  )}
                </label>
              );
            })}

            {fields.length === 0 && (
              <p className="text-sm text-[var(--muted)]">
                No fields extracted yet. If this PDF has no text layer, OCR/Tesseract may be
                missing — the document stays in needs_review instead of crashing. Re-upload a
                text PDF or install Tesseract, then extract again.
              </p>
            )}

            <div className="space-y-2 border-t border-[var(--border)] pt-3">
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void saveReview(false)}
                  className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--background)] disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save review"}
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void saveReview(true)}
                  className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Approve"}
                </button>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Both actions persist to Supabase. Approve is the gate before export.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
