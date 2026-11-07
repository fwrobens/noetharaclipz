create or replace function private.enqueue(pid uuid, typ text, key text, body jsonb, cid uuid default null, reservation bigint default 0) returns uuid language plpgsql security definer set search_path='' as $$
declare jid uuid; mid bigint;
begin
 insert into public.processing_jobs(project_id,kind,dedupe_key,payload,clip_id,reserved_bytes) values(pid,typ,key,body,cid,reservation)
 on conflict(dedupe_key) do nothing returning id into jid;
 if jid is null then select id into jid from public.processing_jobs where dedupe_key=key; return jid; end if;
 select pgmq.send('noetharaclipz',jsonb_build_object('job_id',jid)) into mid;
 update public.processing_jobs set message_id=mid where id=jid;
 return jid;
end $$;
create or replace function private.retry_job(jid uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; mid bigint;
begin
 select * into j from public.processing_jobs where id=jid for update; perform private.require_owner(j.project_id);
 if j.status not in ('failed','cancelled') or j.attempts>=3 then raise exception 'Job cannot be retried'; end if;
 if exists(select 1 from public.provider_usage where job_id=jid and status in ('reserved','unknown')) then raise exception 'Provider outcome is uncertain. Review usage before retrying.'; end if;
 select pgmq.send('noetharaclipz',jsonb_build_object('job_id',jid)) into mid;
 update public.processing_jobs set status='queued',error=null,cancel_requested=false,lease_token=null,lease_until=null,progress=0,stage='Waiting for worker',updated_at=now(),message_id=mid where id=jid;
 if j.kind='analysis' then update public.projects set status='queued',updated_at=now() where id=j.project_id; end if;
 return jid;
end $$;
create or replace function private.worker_tick(jid uuid, token uuid, state text, pct integer, detail text, error_message text default null) returns boolean language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs;
begin
 perform private.require_worker(); select * into j from public.processing_jobs where id=jid for update;
 if j.status in ('completed','failed','cancelled') then raise exception 'Job already finished'; end if;
 if j.lease_token is distinct from token or j.lease_until<now() then raise exception 'Worker lease expired'; end if;
 if j.cancel_requested then state:='cancelled'; detail:='Cancelled'; end if;
 update public.processing_jobs set status=state,progress=pct,stage=left(detail,300),error=left(error_message,2000),lease_until=now()+interval '120 seconds',updated_at=now() where id=jid;
 if state in ('completed','failed','cancelled') then
  perform pgmq.delete('noetharaclipz',j.message_id);
  if j.kind='analysis' then update public.projects set status=case state when 'completed' then 'ready' else state end,updated_at=now() where id=j.project_id; end if;
  if j.kind='render' then update public.clips set render_status=state where id=j.clip_id; end if;
 else
  perform pgmq.set_vt('noetharaclipz',j.message_id,120);
  if j.kind='analysis' then update public.projects set status='processing',updated_at=now() where id=j.project_id; end if;
 end if;
 return not j.cancel_requested;
end $$;
