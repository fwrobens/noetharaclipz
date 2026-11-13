-- Read-only preflight and postflight for the authorized NoetharaClipZ repair.
-- Execute through the Supabase SQL integration for zxdnjnsghdnviflahvry only.
select p.oid::regprocedure::text as signature,
       pg_get_userbyid(p.proowner) as owner,
       l.lanname as language,
       p.prosecdef as security_definer,
       p.proconfig as settings,
       p.proacl as permissions,
       pg_get_functiondef(p.oid) as definition
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
join pg_language l on l.oid = p.prolang
where (n.nspname = 'private' and p.proname in ('worker_heartbeat', 'require_worker'))
   or (n.nspname = 'public' and p.proname = 'worker_heartbeat')
order by n.nspname, p.proname;

select version, name
from supabase_migrations.schema_migrations
order by version;

select c.relrowsecurity as health_rls_enabled,
       pg_get_userbyid(c.relowner) as health_owner,
       c.relacl as health_permissions
from pg_class c
where c.oid = 'private.worker_health'::regclass;
