-- Query-aware lexical retrieval indexes for the longitudinal memory pipeline.
-- PostgreSQL built-in full-text search only; no new extension/provider is required.
-- Raw sources remain canonical. GIN stores lexemes, and every retrieval query is
-- constrained to the authenticated user's namespace by the backend service.

begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create index if not exists ix_memory_items_content_fts
    on psychdeep_v12.memory_items
    using gin (to_tsvector('simple', coalesce(content, '')))
    where status = 'active';

create index if not exists ix_memory_episodes_content_fts
    on psychdeep_v12.memory_episodes
    using gin (
        to_tsvector('simple',
            coalesce(title, '') || ' ' ||
            coalesce(l0, '') || ' ' ||
            coalesce(l1, '') || ' ' ||
            coalesce(themes::text, '') || ' ' ||
            coalesce(transitions::text, '')
        )
    )
    where status = 'active';

create index if not exists ix_memory_summaries_content_fts
    on psychdeep_v12.memory_summary_versions
    using gin (
        to_tsvector('simple',
            coalesce(scope_key, '') || ' ' ||
            coalesce(l0, '') || ' ' ||
            coalesce(l1, '')
        )
    )
    where status = 'active';

create index if not exists ix_discourse_facts_quote_fts
    on psychdeep_v12.discourse_facts
    using gin (to_tsvector('simple', coalesce(quote, '')));

create index if not exists ix_chat_messages_user_content_fts
    on psychdeep_v12.chat_messages
    using gin (to_tsvector('simple', coalesce(content, '')))
    where role = 'user';

create index if not exists ix_diary_entries_content_fts
    on psychdeep_v12.diary_entries
    using gin (to_tsvector('simple', coalesce(content, '')));

reset role;
revoke psychdeep_backend from postgres granted by postgres;
commit;
