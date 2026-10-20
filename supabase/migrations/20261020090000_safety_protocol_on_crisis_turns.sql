-- G3 safety protocol versioning: the stored LEVEL3/LEVEL4 chat turn and the
-- notices sent for a LEVEL3/LEVEL4 alert now name the server-owned safety
-- pack (SAFETY_PROTOCOL_VERSION, e.g. 'safety-protocol-v1') whose fixed copy
-- and crisis resources they carried. The RiskAssessment and ProfessionalAlert
-- already record it in their JSON traces; these two tables had no place for it.
--
-- Additive only: one new nullable column on each table. No rows are changed,
-- no defaults are set, nothing is dropped or renamed. Rows written before this
-- migration stay NULL and are not relabelled. The column holds a version label
-- only, never patient or model text.
begin;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.chat_messages
    add column if not exists safety_protocol_version varchar(64);
alter table psychdeep_v12.notifications
    add column if not exists safety_protocol_version varchar(64);

reset role;
do $$
begin
    revoke psychdeep_backend from postgres granted by postgres;
exception
    when others then
        null;
end $$;

commit;
