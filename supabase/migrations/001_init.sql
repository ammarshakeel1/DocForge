-- DocForge AI v0.1 schema
-- Storage bucket `invoices` must be PRIVATE. Files are served only via the API
-- (signed URL or streamed PDF). Never put SUPABASE_SERVICE_ROLE_KEY in the web app.

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  file_path text not null,
  original_filename text not null,
  status text not null default 'uploaded'
    check (status in ('uploaded', 'processing', 'needs_review', 'approved', 'exported')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists extracted_fields (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  field_name text not null,
  field_value text,
  confidence numeric,
  needs_review boolean not null default false,
  reviewed_value text,
  created_at timestamptz not null default now(),
  unique (document_id, field_name)
);

create index if not exists extracted_fields_document_id_idx
  on extracted_fields(document_id);

create table if not exists review_events (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  action text not null,
  payload jsonb,
  created_at timestamptz not null default now()
);

create index if not exists review_events_document_id_idx
  on review_events(document_id);
