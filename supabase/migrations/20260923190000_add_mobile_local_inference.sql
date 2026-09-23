begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.model_deployments drop constraint if exists ck_model_deployment_adapter;
alter table psychdeep_v12.model_deployments add constraint ck_model_deployment_adapter check (adapter in ('openai_compatible','managed_cloud','mobile_local'));

insert into psychdeep_v12.model_deployments
    (alias, adapter, model_id, capabilities, policy_version, timeout_seconds, data_handling_classification, base_url_ref, credential_ref, region, status)
values
    ('mobile-local', 'mobile_local', 'device-reported',
     '{"chat":true,"structured":true,"offline":true,"outbound_sync":true}'::jsonb,
     'support-policy-v1', 30, 'clinical_data_device_local', null, null, null, 'approved')
on conflict (alias) do update set adapter=excluded.adapter, capabilities=excluded.capabilities,
 policy_version=excluded.policy_version, timeout_seconds=excluded.timeout_seconds,
 data_handling_classification=excluded.data_handling_classification, updated_at=now();

create table if not exists psychdeep_v12.mobile_inference_events (
 id uuid primary key default gen_random_uuid(),
 event_id uuid not null unique,
 user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
 conversation_id uuid,
 model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
 deployment_alias varchar(96) not null default 'mobile-local',
 model_id varchar(192) not null,
 model_version varchar(192),
 prompt_version varchar(96),
 input_hash varchar(64) not null,
 output jsonb not null,
 output_schema varchar(96),
 client_platform varchar(32) not null default 'android',
 client_app_version varchar(64),
 inference_engine varchar(64),
 client_model_checksum varchar(128),
 client_timestamp timestamptz,
 latency_ms integer,
 idempotency_key varchar(128) not null,
 created_at timestamptz not null default now(),
 constraint ck_mobile_event_deployment check (deployment_alias='mobile-local'),
 constraint ck_mobile_event_latency check (latency_ms is null or latency_ms >= 0),
 constraint uq_mobile_event_user_idempotency unique (user_id,idempotency_key)
);
create index if not exists ix_mobile_inference_events_user_created on psychdeep_v12.mobile_inference_events(user_id,created_at desc);
create index if not exists ix_mobile_inference_events_model_run on psychdeep_v12.mobile_inference_events(model_run_id) where model_run_id is not null;
alter table psychdeep_v12.mobile_inference_events enable row level security;
alter table psychdeep_v12.mobile_inference_events force row level security;
drop policy if exists backend_full_access on psychdeep_v12.mobile_inference_events;
create policy backend_full_access on psychdeep_v12.mobile_inference_events for all to psychdeep_backend using (true) with check (true);
revoke all on table psychdeep_v12.mobile_inference_events from public, anon, authenticated, service_role;

reset role;
revoke psychdeep_backend from postgres granted by postgres;
commit;
