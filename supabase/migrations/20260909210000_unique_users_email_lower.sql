begin;

-- Login, signup, provisioning, and assignment already treat email as
-- case-insensitive. The existing unique index on `users.email` does not
-- stop `Ada@x.com` and `ada@x.com` from coexisting. This expression index
-- is expand-only: no clinical tables, no row rewrites.
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create unique index if not exists ix_users_email_lower
    on psychdeep_v12.users (lower(email));

reset role;
revoke psychdeep_backend from postgres granted by postgres;

commit;
