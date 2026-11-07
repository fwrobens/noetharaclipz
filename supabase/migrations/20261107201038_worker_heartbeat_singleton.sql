-- NoetharaClipZ only. Preserve the signature, worker guard, security context
-- and existing grants; scope the singleton heartbeat update explicitly.
create or replace function private.worker_heartbeat(ai_ready boolean, detail text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform private.require_worker();
  update private.worker_health
  set heartbeat_at = now(),
      ai_ready = worker_heartbeat.ai_ready,
      detail = left(worker_heartbeat.detail, 300)
  where id = true;
end;
$$;
