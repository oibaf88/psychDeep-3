#!/bin/bash
docker rm -f pg || true
docker run -d --name pg -e POSTGRES_USER=supabase_admin -e POSTGRES_PASSWORD=postgres -e POSTGRES_HOST_AUTH_METHOD=trust -p 5432:5432 postgres:16
for i in $(seq 1 30); do
  docker exec pg pg_isready -U supabase_admin && break
  sleep 2
done
docker exec pg psql -U supabase_admin -d postgres -v ON_ERROR_STOP=1 -c "
  create role anon nologin;
  create role authenticated nologin;
  create role service_role nologin;
  create role psychdeep_backend nologin;
  create role postgres login createdb createrole;
  grant psychdeep_backend to postgres with admin option, inherit false, set false;
  alter database postgres owner to postgres;"

for f in $(ls supabase/migrations/*.sql | sort); do
  echo "--- $(basename "$f")"
  docker exec -i pg psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q < "$f"
  if [ $? -ne 0 ]; then
      echo "Failed at $f"
      break
  fi
done
