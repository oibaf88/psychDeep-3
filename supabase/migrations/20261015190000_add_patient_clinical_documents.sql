-- Private clinical-report ingestion for the longitudinal memory pipeline.
-- Expand-only: existing chat, diary, profile and clinical memory tables remain untouched.
begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create table if not exists psychdeep_v12.patient_clinical_documents (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    uploaded_by uuid references psychdeep_v12.users(id) on delete set null,
    original_filename varchar(255) not null,
    media_type varchar(96) not null,
    sha256 varchar(64) not null,
    file_size_bytes integer not null,
    document_type varchar(48) not null default 'clinical_report',
    document_date timestamptz,
    raw_content bytea not null,
    extracted_text text,
    extraction_status varchar(24) not null default 'text_extracted',
    analysis_status varchar(24) not null default 'queued',
    error_category varchar(64),
    created_at timestamptz not null default now(),
    analyzed_at timestamptz,
    constraint ck_patient_clinical_document_size check (file_size_bytes between 1 and 15728640),
    constraint ck_patient_clinical_document_extraction check (extraction_status in ('text_extracted', 'needs_ocr', 'failed')),
    constraint ck_patient_clinical_document_analysis check (analysis_status in ('queued', 'analysing', 'analysed', 'blocked', 'failed')),
    constraint ck_patient_clinical_document_type check (document_type in ('clinical_report', 'discharge_summary', 'psychological_report', 'psychiatric_report', 'medication_report', 'other')),
    constraint uq_patient_clinical_document_user_sha unique (user_id, sha256)
);

create index if not exists ix_patient_clinical_documents_user_created on psychdeep_v12.patient_clinical_documents(user_id, created_at desc);
alter table psychdeep_v12.patient_clinical_documents enable row level security;
alter table psychdeep_v12.patient_clinical_documents force row level security;
drop policy if exists backend_full_access on psychdeep_v12.patient_clinical_documents;
create policy backend_full_access on psychdeep_v12.patient_clinical_documents for all to psychdeep_backend using (true) with check (true);
revoke all on table psychdeep_v12.patient_clinical_documents from public, anon, authenticated, service_role;
reset role;
revoke psychdeep_backend from postgres granted by postgres;
do $$
declare hardened boolean; policy_exists boolean;
begin
    select owner_role.rolname = 'psychdeep_backend' and relation.relrowsecurity and relation.relforcerowsecurity
      into hardened from pg_class relation join pg_namespace namespace on namespace.oid = relation.relnamespace
      join pg_roles owner_role on owner_role.oid = relation.relowner
      where namespace.nspname = 'psychdeep_v12' and relation.relname = 'patient_clinical_documents';
    select exists (select 1 from pg_policies where schemaname = 'psychdeep_v12' and tablename = 'patient_clinical_documents' and policyname = 'backend_full_access' and 'psychdeep_backend' = any(roles)) into policy_exists;
    if not coalesce(hardened, false) then raise exception 'patient_clinical_documents owner/RLS hardening is incomplete'; end if;
    if not policy_exists then raise exception 'patient_clinical_documents backend RLS policy is missing'; end if;
end
$$;
commit;
