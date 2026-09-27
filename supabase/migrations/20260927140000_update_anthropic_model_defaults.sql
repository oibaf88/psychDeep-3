begin;

update psychdeep_v12.llm_user_preferences
set
    chat_model = 'claude-sonnet-4-6',
    analysis_model = 'claude-sonnet-4-6',
    copilot_model = 'claude-sonnet-4-6'
where provider = 'anthropic'
  and (
      chat_model like 'claude-3-5-sonnet%'
      or analysis_model like 'claude-3-5-sonnet%'
      or copilot_model like 'claude-3-5-sonnet%'
  );

commit;
