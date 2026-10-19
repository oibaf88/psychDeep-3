-- Private therapist-uploaded source documents for the consent-gated
-- whole-person longitudinal model. Existing clinical data is untouched.
begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create table if not exists psychdeep_v12.patient_clinical_documents (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    uploaded_by uuid not null references psychdeep_v12.users(id) on delete restrict,
    original_filename varchar(240) not null,
    media_type varchar(128) not null,
    file_size_bytes integer not null,
    file_sha256 varchar(64) not null,
    file_content bytea not null,
    extracted_text text not null default '',
    extraction_status varchar(24) not null default 'text_extracted',
    analysis_status varchar(24) not null default 'queued',
    error_category varchar(64),
    analyzed_at timestamptz,
    constraint uq_patient_clinical_document_hash unique (user_id, file_sha256),
    constraint ck_patient_clinical_document_file_size check (file_size_bytes between 1 and 8388608),
    constraint ck_patient_clinical_document_filename check (char_length(original_filename) between 1 and 240),
    constraint ck_patient_clinical_document_extraction check (extraction_status in ('text_extracted', 'failed')),
    constraint ck_patient_clinical_document_analysis check (
        analysis_status in ('queued', 'analysing', 'analysed', 'failed', 'consent_revoked')
    )
);

create index if not exists ix_patient_clinical_documents_user_uploaded
    on psychdeep_v12.patient_clinical_documents(user_id);
create index if not exists ix_patient_clinical_documents_analysis_queue
    on psychdeep_v12.patient_clinical_documents(user_id, analysis_status);

alter table psychdeep_v12.patient_clinical_documents enable row level security;
alter table psychdeep_v12.patient_clinical_documents force row level security;
drop policy if exists backend_full_access on psychdeep_v12.patient_clinical_documents;
create policy backend_full_access on psychdeep_v12.patient_clinical_documents
    for all to psychdeep_backend using (true) with check (true);
revoke all on table psychdeep_v12.patient_clinical_documents from public, anon, authenticated, service_role;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

do $$
declare
    owner_name text;
    rls_enabled boolean;
    rls_forced boolean;
    policy_exists boolean;
begin
    select owner_role.rolname, relation.relrowsecurity, relation.relforcerowsecurity
      into owner_name, rls_enabled, rls_forced
      from pg_class relation
      join pg_namespace namespace on namespace.oid = relation.relnamespace
      join pg_roles owner_role on owner_role.oid = relation.relowner
     where namespace.nspname = 'psychdeep_v12'
       and relation.relname = 'patient_clinical_documents';

    select exists (
        select 1 from pg_policies
         where schemaname = 'psychdeep_v12'
           and tablename = 'patient_clinical_documents'
           and policyname = 'backend_full_access'
           and 'psychdeep_backend' = any(roles)
    ) into policy_exists;

    if owner_name is distinct from 'psychdeep_backend'
       or not coalesce(rls_enabled, false)
       or not coalesce(rls_forced, false)
       or not policy_exists then
        raise exception 'patient_clinical_documents owner/RLS hardening is incomplete';
    end if;
end
$$;

commit;
