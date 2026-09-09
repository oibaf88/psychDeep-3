begin;

-- These are account-level fields shared by every role. They are deliberately
-- kept on `users`, which is already on the PDF architecture's replication
-- allowlist; no clinical portrait or Supabase Auth table is exposed.
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.users
    add column if not exists first_name varchar(100),
    add column if not exists last_name varchar(150),
    add column if not exists phone varchar(40),
    add column if not exists auth_version integer not null default 1,
    add column if not exists updated_at timestamp without time zone not null default now();

alter table psychdeep_v12.users
    drop constraint if exists ck_users_auth_version;
alter table psychdeep_v12.users
    add constraint ck_users_auth_version check (auth_version >= 1);

reset role;
revoke psychdeep_backend from postgres granted by postgres;

commit;
