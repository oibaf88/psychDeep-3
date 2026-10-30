with open("supabase/migrations/20261018100000_reconcile_patient_clinical_documents_schema.sql", "r") as f:
    content = f.read()

content = content.replace(
"""    if owner_name is distinct from 'psychdeep_backend'
       or not coalesce(rls_enabled, false)
       or not coalesce(rls_forced, false)
       or not policy_exists
       or missing_columns is not null then
        raise exception 'patient_clinical_documents schema or RLS verification failed; owner=%, rls=%, forced=%, policy=%, missing=%',
            owner_name, rls_enabled, rls_forced, policy_exists, missing_columns;
    end if;""",
"""    if array_length(missing_columns, 1) = 0 then
        missing_columns := null;
    end if;

    if owner_name is distinct from 'psychdeep_backend'
       or not coalesce(rls_enabled, false)
       or not coalesce(rls_forced, false)
       or not policy_exists
       or missing_columns is not null then
        raise exception 'patient_clinical_documents schema or RLS verification failed; owner=%, rls=%, forced=%, policy=%, missing=%',
            owner_name, rls_enabled, rls_forced, policy_exists, missing_columns;
    end if;""")

with open("supabase/migrations/20261018100000_reconcile_patient_clinical_documents_schema.sql", "w") as f:
    f.write(content)
