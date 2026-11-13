-- Run after the heartbeat migration, only in NoetharaClipZ or an isolated test
-- database. Exercise the actual functions and roll the health mutation back.
begin;

do $$
begin
  if not exists (select 1 from private.worker_health where id = true) then
    raise exception 'Expected singleton worker-health row is missing';
  end if;
  if not (select prosecdef from pg_proc
          where oid = 'private.worker_heartbeat(boolean,text)'::regprocedure) then
    raise exception 'Heartbeat lost SECURITY DEFINER';
  end if;
  if has_function_privilege('anon', 'public.worker_heartbeat(boolean,text)', 'EXECUTE')
     or has_function_privilege('authenticated', 'public.worker_heartbeat(boolean,text)', 'EXECUTE')
     or has_function_privilege('anon', 'private.worker_heartbeat(boolean,text)', 'EXECUTE')
     or has_function_privilege('authenticated', 'private.worker_heartbeat(boolean,text)', 'EXECUTE') then
    raise exception 'Heartbeat is executable by an unauthorized role';
  end if;
end;
$$;

select set_config('request.jwt.claims', '{"role":"service_role"}', true);
set local role service_role;
select public.worker_heartbeat(false, repeat('heartbeat regression ', 30));
reset role;

do $$
declare health private.worker_health;
begin
  select * into strict health from private.worker_health where id = true;
  if health.heartbeat_at is null or health.heartbeat_at < transaction_timestamp()
     or health.ai_ready is distinct from false or length(health.detail) <> 300 then
    raise exception 'Worker heartbeat did not persist the expected bounded values';
  end if;
end;
$$;

-- ACLs must reject both browser roles before entering the definer function.
set local role anon;
do $$
begin
  begin
    perform public.worker_heartbeat(false, 'unauthorized');
    raise exception 'Anonymous caller unexpectedly updated worker health';
  exception when insufficient_privilege then null;
  end;
end;
$$;
reset role;

set local role authenticated;
do $$
begin
  begin
    perform public.worker_heartbeat(false, 'unauthorized');
    raise exception 'Authenticated browser caller unexpectedly updated worker health';
  exception when insufficient_privilege then null;
  end;
end;
$$;
reset role;

rollback;
select 'Heartbeat update, worker authorization and browser denial assertions passed' as result;
