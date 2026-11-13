create or replace function private.worker_claim() returns jsonb language plpgsql security definer set search_path='' as $$
declare m record; j public.processing_jobs; tok uuid;
begin
 perform private.require_worker();
 perform pg_advisory_xact_lock(809604);
 if exists(select 1 from public.processing_jobs where lease_until>now() and status not in ('completed','failed','cancelled')) then return null; end if;
 for m in select * from pgmq.read('noetharaclipz',120,1) loop
  select * into j from public.processing_jobs where id=(m.message->>'job_id')::uuid for update;
  if j.id is null or j.status in ('completed','failed','cancelled') then perform pgmq.delete('noetharaclipz',m.msg_id); return null; end if;
  if j.lease_until>now() then return null; end if;
  tok:=gen_random_uuid();
  update public.processing_jobs set lease_token=tok,lease_until=now()+interval '120 seconds',message_id=m.msg_id,attempts=attempts+1,updated_at=now() where id=j.id returning * into j;
  return to_jsonb(j);
 end loop;
 return null;
end $$;
create or replace function private.cancel_job(jid uuid) returns void language plpgsql security definer set search_path='' as $$
declare pid uuid; j public.processing_jobs;
begin
 select project_id into pid from public.processing_jobs where id=jid; perform private.require_owner(pid);
 select * into j from public.processing_jobs where id=jid for update;
 update public.processing_jobs set cancel_requested=true,updated_at=now() where id=jid and status not in ('completed','failed','cancelled');
 if j.status='queued' and (j.lease_until is null or j.lease_until<now()) then
  update public.processing_jobs set status='cancelled',stage='Cancelled before processing',updated_at=now() where id=jid;
  perform pgmq.delete('noetharaclipz',j.message_id);
  if j.kind='analysis' then update public.projects set status='cancelled',updated_at=now() where id=pid; end if;
 end if;
end $$;
create or replace function private.retry_job(jid uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; mid bigint;
begin
 select * into j from public.processing_jobs where id=jid for update; perform private.require_owner(j.project_id);
 if j.status not in ('failed','cancelled') or j.attempts>=3 then raise exception 'Job cannot be retried'; end if;
 if exists(select 1 from public.provider_usage where job_id=jid and status in ('reserved','unknown')) then raise exception 'Provider outcome is uncertain. Review usage before retrying.'; end if;
 if j.reserved_bytes>0 then perform private.check_capacity(auth.uid(),j.reserved_bytes); end if;
 select pgmq.send('noetharaclipz',jsonb_build_object('job_id',jid)) into mid;
 update public.processing_jobs set status='queued',error=null,cancel_requested=false,lease_token=null,lease_until=null,progress=0,stage='Waiting for worker',updated_at=now(),message_id=mid where id=jid;
 if j.kind='analysis' then update public.projects set status='queued',updated_at=now() where id=j.project_id; end if;
 return jid;
end $$;
