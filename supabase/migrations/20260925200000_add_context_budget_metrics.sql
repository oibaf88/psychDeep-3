begin;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.llm_usage_events
    add column if not exists context_budget_tokens integer,
    add column if not exists estimated_input_tokens integer,
    add column if not exists context_truncated boolean not null default false,
    add column if not exists context_message_count integer;

alter table psychdeep_v12.llm_usage_events
    drop constraint if exists ck_llm_usage_context_budget_nonnegative;

alter table psychdeep_v12.llm_usage_events
    add constraint ck_llm_usage_context_budget_nonnegative check (
        (context_budget_tokens is null or context_budget_tokens >= 0)
        and (estimated_input_tokens is null or estimated_input_tokens >= 0)
        and (context_message_count is null or context_message_count >= 0)
    );

create index if not exists ix_llm_usage_context_truncated
    on psychdeep_v12.llm_usage_events(context_truncated, created_at desc);

reset role;
revoke psychdeep_backend from postgres granted by postgres;

commit;
