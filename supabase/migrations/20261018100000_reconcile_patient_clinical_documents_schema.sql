-- Reconcile the earlier patient_clinical_documents schema with the current backend model.
-- This migration is additive/in-place: it preserves stored files, hashes, metadata, and legacy statuses.
begin;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

do $$
begin
    if to_regclass('psychdeep_v12.patient_clinical_documents') is null then
        raise exception 'psychdeep_v12.patient_clinical_documents must exist before reconciliation';
    end if;

    if exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'sha256'
    ) and not exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'file_sha256'
    ) then
        alter table psychdeep_v12.patient_clinical_documents rename column sha256 to file_sha256;
    end if;

    if exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'raw_content'
    ) and not exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'file_content'
    ) then
        alter table psychdeep_v12.patient_clinical_documents rename column raw_content to file_content;
    end if;

    if not exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'file_sha256'
    ) then
        raise exception 'Cannot reconcile patient_clinical_documents: hash column is missing';
    end if;
    if not exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'file_content'
    ) then
        raise exception 'Cannot reconcile patient_clinical_documents: binary content column is missing';
    end if;
end
$$;

alter table psychdeep_v12.patient_clinical_documents
    add column if not exists text_truncated boolean;
alter table psychdeep_v12.patient_clinical_documents
    add column if not exists patient_model_version_id uuid;
alter table psychdeep_v12.patient_clinical_documents
    add column if not exists uploaded_at timestamptz;

-- Preserve historical upload timestamps where the older schema called the field created_at.
do $$
begin
    if exists (
        select 1 from information_schema.columns
         where table_schema = 'psychdeep_v12'
           and table_name = 'patient_clinical_documents'
           and column_name = 'created_at'
    ) then
        execute 'update psychdeep_v12.patient_clinical_documents
                    set uploaded_at = created_at
                  where uploaded_at is null';
    end if;
end
$$;

update psychdeep_v12.patient_clinical_documents
   set uploaded_at = now()
 where uploaded_at is null;
update psychdeep_v12.patient_clinical_documents
   set extracted_text = ''
 where extracted_text is null;
update psychdeep_v12.patient_clinical_documents
   set text_truncated = false
 where text_truncated is null;

do $$
begin
    if exists (
        select 1 from psychdeep_v12.patient_clinical_documents
         where uploaded_by is null
            or original_filename is null
            or char_length(original_filename) not between 1 and 240
            or file_content is null
            or file_sha256 is null
            or char_length(file_sha256) <> 64
            or file_size_bytes < 1
            or file_size_bytes > 8388608
    ) then
        raise exception 'Existing clinical document rows violate the current document contract; no data was removed';
    end if;

    if not exists (
        select 1 from pg_constraint
         where conrelid = 'psychdeep_v12.patient_clinical_documents'::regclass
           and conname = 'patient_clinical_documents_patient_model_version_id_fkey'
    ) then
        alter table psychdeep_v12.patient_clinical_documents
            add constraint patient_clinical_documents_patient_model_version_id_fkey
            foreign key (patient_model_version_id)
            references psychdeep_v12.patient_model_versions(id)
            on delete set null;
    end if;

    if not exists (
        select 1 from pg_constraint
         where conrelid = 'psychdeep_v12.patient_clinical_documents'::regclass
           and conname = 'uq_patient_clinical_document_hash'
    ) then
        if exists (
            select 1
              from psychdeep_v12.patient_clinical_documents
             group by user_id, file_sha256
            having count(*) > 1
        ) then
            raise exception 'Duplicate patient/file hashes prevent adding the deduplication constraint';
        end if;
        alter table psychdeep_v12.patient_clinical_documents
            add constraint uq_patient_clinical_document_hash unique (user_id, file_sha256);
    end if;
end
$$;

alter table psychdeep_v12.patient_clinical_documents
    alter column uploaded_by set not null,
    alter column extracted_text set default '',
    alter column extracted_text set not null,
    alter column text_truncated set default false,
    alter column text_truncated set not null,
    alter column uploaded_at set default now(),
    alter column uploaded_at set not null,
    alter column file_sha256 set not null,
    alter column file_content set not null;

-- Match ORM deletion semantics: uploader audit attribution must not be silently nulled.
alter table psychdeep_v12.patient_clinical_documents
    drop constraint if exists patient_clinical_documents_uploaded_by_fkey;
alter table psychdeep_v12.patient_clinical_documents
    add constraint patient_clinical_documents_uploaded_by_fkey
    foreign key (uploaded_by)
    references psychdeep_v12.users(id)
    on delete restrict;

-- Keep legacy statuses accepted while allowing the new backend states.
alter table psychdeep_v12.patient_clinical_documents
    drop constraint if exists ck_patient_clinical_document_extraction;
alter table psychdeep_v12.patient_clinical_documents
    add constraint ck_patient_clinical_document_extraction
    check (extraction_status in ('text_extracted', 'needs_ocr', 'failed'));

alter table psychdeep_v12.patient_clinical_documents
    drop constraint if exists ck_patient_clinical_document_analysis;
alter table psychdeep_v12.patient_clinical_documents
    add constraint ck_patient_clinical_document_analysis
    check (analysis_status in ('queued', 'analysing', 'analysed', 'blocked', 'failed', 'consent_revoked'));

alter table psychdeep_v12.patient_clinical_documents
    drop constraint if exists ck_patient_clinical_document_size;
alter table psychdeep_v12.patient_clinical_documents
    drop constraint if exists ck_patient_clinical_document_file_size;
alter table psychdeep_v12.patient_clinical_documents
    add constraint ck_patient_clinical_document_file_size
    check (file_size_bytes between 1 and 8388608);

do $$
begin
    if not exists (
        select 1 from pg_constraint
         where conrelid = 'psychdeep_v12.patient_clinical_documents'::regclass
           and conname = 'ck_patient_clinical_document_filename'
    ) then
        alter table psychdeep_v12.patient_clinical_documents
            add constraint ck_patient_clinical_document_filename
            check (char_length(original_filename) between 1 and 240);
    end if;
end
$$;


drop index if exists psychdeep_v12.ix_patient_clinical_documents_user_uploaded;
create index ix_patient_clinical_documents_user_uploaded
    on psychdeep_v12.patient_clinical_documents(user_id, uploaded_at desc);

drop index if exists psychdeep_v12.ix_patient_clinical_documents_analysis_queue;
create index ix_patient_clinical_documents_analysis_queue
    on psychdeep_v12.patient_clinical_documents(user_id, analysis_status, uploaded_at);


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
    missing_columns text[];
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

    select array_agg(required.column_name)
      into missing_columns
      from (values ('file_content'), ('file_sha256'), ('extracted_text'),
                   ('text_truncated'), ('patient_model_version_id'), ('uploaded_at')) required(column_name)
     where not exists (
         select 1 from information_schema.columns column_row
          where column_row.table_schema = 'psychdeep_v12'
            and column_row.table_name = 'patient_clinical_documents'
            and column_row.column_name = required.column_name
     );

    if owner_name is distinct from 'psychdeep_backend'
       or not coalesce(rls_enabled, false)
       or not coalesce(rls_forced, false)
       or not policy_exists
       or missing_columns is not null then
        raise exception 'patient_clinical_documents schema or RLS verification failed; owner=%, rls=%, forced=%, policy=%, missing=%',
            owner_name, rls_enabled, rls_forced, policy_exists, missing_columns;
    end if;
end
$$;

commit;
