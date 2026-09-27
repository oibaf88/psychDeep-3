begin;

alter table psychdeep_v12.llm_user_preferences
    drop constraint if exists ck_llm_user_provider;

alter table psychdeep_v12.llm_user_preferences
    add constraint ck_llm_user_provider
    check (provider in ('anthropic','openai','openai_compatible'));

commit;
