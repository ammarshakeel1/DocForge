const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "needs_review"
  | "approved"
  | "exported";

export type Document = {
  id: string;
  file_path: string;
  original_filename: string;
  status: DocumentStatus;
  created_at?: string | null;
};

export type ExtractedField = {
  id: string;
  document_id: string;
  field_name: string;
  field_value: string | null;
  confidence: number | null;
  needs_review: boolean;
  reviewed_value: string | null;
  created_at?: string | null;
};

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail && typeof data.detail === "object") {
      const message = data.detail.message;
      const errors = data.detail.validation_errors;
      if (typeof message === "string" && Array.isArray(errors) && errors.length) {
        return `${message} ${errors.join("; ")}`;
      }
      if (typeof message === "string") return message;
    }
    return JSON.stringify(data?.detail ?? data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/documents`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function extractDocument(id: string): Promise<{
  document: Document;
  fields: ExtractedField[];
  validation_errors: string[];
  extraction_method: string;
  error?: string | null;
}> {
  const res = await fetch(`${API_URL}/documents/${id}/extract`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getDocument(id: string): Promise<Document> {
  const res = await fetch(`${API_URL}/documents/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getFields(id: string): Promise<ExtractedField[]> {
  const res = await fetch(`${API_URL}/documents/${id}/fields`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function reviewDocument(
  id: string,
  body: {
    fields: { field_name: string; reviewed_value: string }[];
    approve: boolean;
  },
): Promise<{ document: Document; fields: ExtractedField[]; message: string }> {
  const res = await fetch(`${API_URL}/documents/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export function pdfUrl(id: string): string {
  return `${API_URL}/documents/${id}/file.pdf`;
}

export function exportCsvUrl(id: string): string {
  return `${API_URL}/documents/${id}/export.csv`;
}

export function exportJsonUrl(id: string): string {
  return `${API_URL}/documents/${id}/export.json`;
}

export { API_URL };
