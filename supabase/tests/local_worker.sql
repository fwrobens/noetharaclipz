-- Transactional SQL fixtures, NOT AI/media acceptance. Run after local-worker support.
begin;
create temporary table nc_local(owner uuid,other_owner uuid,pid uuid,protected_pid uuid,jid uuid,protected_jid uuid,token uuid);
insert into nc_local(owner,other_owner) values(gen_random_uuid(),gen_random_uuid());
grant all on nc_local to authenticated,service_role;
insert into auth.users(id,email) select owner,'nc-local-sql-owner@example.com' from nc_local union all select other_owner,'nc-local-sql-other@example.com' from nc_local;
select set_config('request.jwt.claims',jsonb_build_object('sub',other_owner,'role','authenticated')::text,true) from nc_local;
set local role authenticated;
update nc_local set protected_pid=(public.prepare_upload(gen_random_uuid(),'protected.mp4','video/mp4',1000,'Protected queued SQL fixture')->>'project_id')::uuid;
reset role;
insert into storage.objects(bucket_id,name,metadata) select 'source-videos',v.source_path,'{"size":1000}'::jsonb from public.videos v where project_id=(select protected_pid from nc_local);
set local role authenticated;
update nc_local set protected_jid=public.finalize_upload(protected_pid);
select set_config('request.jwt.claims',jsonb_build_object('sub',owner,'role','authenticated')::text,true) from nc_local;
update nc_local set pid=(public.prepare_upload(gen_random_uuid(),'test.mp4','video/mp4',1000,'Owned SQL fixture')->>'project_id')::uuid;
reset role;
insert into storage.objects(bucket_id,name,metadata) select 'source-videos',v.source_path,'{"size":1000}'::jsonb from public.videos v where project_id=(select pid from nc_local);
set local role authenticated;
update nc_local set jid=public.finalize_upload(pid);
reset role;
create temporary table nc_protected_job as select to_jsonb(j) original from public.processing_jobs j where id=(select protected_jid from nc_local);
create temporary table nc_protected_message as select to_jsonb(q) original from pgmq.q_noetharaclipz q where (q.message->>'job_id')::uuid=(select protected_jid from nc_local);
select set_config('request.jwt.claims','{"role":"service_role"}',true);
set local role service_role;
do $$ declare j jsonb;
begin
 if public.worker_protocol()->>'version'<>'1' then raise exception 'Wrong protocol'; end if;
 begin
  perform public.worker_finish_analysis((select jid from nc_local),null,'{}','{}','[]');
  raise exception 'Unclaimed analysis accepted';
 exception when raise_exception then
  if sqlerrm<>'Invalid or cancelled analysis lease' then raise;end if;
 end;
 j:=public.worker_claim_scoped((select owner from nc_local));
 if j->>'id' is distinct from (select jid::text from nc_local) then raise exception 'Scope did not claim owned job'; end if;
 update nc_local set token=(j->>'lease_token')::uuid;
 if public.worker_claim_scoped((select owner from nc_local)) is not null then raise exception 'Concurrency guard weakened'; end if;
 perform public.worker_heartbeat_scoped((select owner from nc_local),true,'Local test model ready');
end $$;
reset role;
-- Only the owning account sees scoped readiness; no private-table browser access.
select set_config('request.jwt.claims',jsonb_build_object('sub',owner,'role','authenticated')::text,true) from nc_local;
set local role authenticated;
do $$ begin
 if (public.pipeline_health()->>'online')::boolean is distinct from true or (public.pipeline_health()->>'ai_ready')::boolean is distinct from true then raise exception 'Own scoped readiness missing'; end if;
 begin perform public.worker_claim_scoped((select owner from nc_local));raise exception 'Browser claim allowed';exception when insufficient_privilege then null;end;
 begin perform public.worker_heartbeat_scoped((select owner from nc_local),true,'forged');raise exception 'Browser heartbeat allowed';exception when insufficient_privilege then null;end;
end $$;
select set_config('request.jwt.claims',jsonb_build_object('sub',other_owner,'role','authenticated')::text,true) from nc_local;
do $$ begin if (public.pipeline_health()->>'ai_ready')::boolean then raise exception 'Scoped readiness leaked to other owner';end if;end $$;
reset role;
-- Simulate lease expiry only for the owned fixture, retaining a stale token.
update public.processing_jobs set lease_until=now()-interval '1 second' where id=(select jid from nc_local);
select pgmq.set_vt('noetharaclipz',message_id,0) from public.processing_jobs where id=(select jid from nc_local);
select set_config('request.jwt.claims','{"role":"service_role"}',true);
set local role service_role;
do $$ declare j jsonb;
begin
 j:=public.worker_claim_scoped((select owner from nc_local));
 if (j->>'attempts')::int<>2 then raise exception 'Scoped recovery failed';end if;
 begin perform public.worker_tick((select jid from nc_local),(select token from nc_local),'analyzing',10,'stale');raise exception 'Old token accepted';exception when raise_exception then if sqlerrm='Old token accepted' then raise;end if;end;
 update nc_local set token=(j->>'lease_token')::uuid;
 perform public.worker_tick((j->>'id')::uuid,(j->>'lease_token')::uuid,'analyzing',50,'SQL fixture only');
end $$;
reset role;
-- Cancellation/retry remains in the existing owner RPCs, never direct status writes.
select set_config('request.jwt.claims',jsonb_build_object('sub',owner,'role','authenticated')::text,true) from nc_local;
set local role authenticated;
select public.cancel_job(jid) from nc_local;
reset role;
select set_config('request.jwt.claims','{"role":"service_role"}',true);
set local role service_role;
select public.worker_tick(jid,token,'analyzing',50,'Cancellation acknowledgement') from nc_local;
reset role;
select set_config('request.jwt.claims',jsonb_build_object('sub',owner,'role','authenticated')::text,true) from nc_local;
set local role authenticated;
select public.retry_job(jid) from nc_local;
reset role;
select set_config('request.jwt.claims','{"role":"service_role"}',true);
set local role service_role;
update nc_local set token=(public.worker_claim_scoped(owner)->>'lease_token')::uuid;
-- Local metadata is accepted without Gemini records; invalid provenance rolls back.
do $$ declare meta jsonb; artifact jsonb;
begin
 meta:='{"duration":52,"width":854,"height":480,"fps":24,"has_audio":true,"source_hash":"sql-fixture"}';
 artifact:='{"provider":"local-smolvlm2","model":"wrong","transcript":[],"scenes":[],"audio_events":[],"waveform":[],"frame_paths":[],"summary":"SQL fixture, not inference","local_usage":{"input_tokens":12,"output_tokens":1}}';
 begin perform public.worker_finish_analysis((select jid from nc_local),(select token from nc_local),meta,artifact,'[]');raise exception 'Wrong model accepted';exception when raise_exception then if sqlerrm='Wrong model accepted' then raise;end if;end;
 artifact:=jsonb_set(artifact,'{model}','"HuggingFaceTB/SmolVLM2-500M-Video-Instruct@7b375e1b73b11138ff12fe22c8f2822d8fe03467"');
 perform public.worker_finish_analysis((select jid from nc_local),(select token from nc_local),meta,artifact,'[]');
 begin perform public.worker_finish_analysis((select jid from nc_local),(select token from nc_local),meta,artifact,'[]');raise exception 'Duplicate completion accepted';exception when raise_exception then if sqlerrm='Duplicate completion accepted' then raise;end if;end;
end $$;
reset role;
do $$ begin
 if not exists(select 1 from public.processing_jobs where id=(select jid from nc_local) and status='completed' and payload->>'provider'='local-smolvlm2') then raise exception 'Local completion not atomic';end if;
 if not exists(select 1 from public.provider_usage where job_id=(select jid from nc_local) and provider='local-smolvlm2' and input_tokens=12 and status='completed') or exists(select 1 from public.provider_usage where job_id=(select jid from nc_local) and provider='gemini') then raise exception 'Provider provenance or usage is wrong';end if;
 if (select original from nc_protected_job) is distinct from (select to_jsonb(j) from public.processing_jobs j where id=(select protected_jid from nc_local)) then raise exception 'Protected queued job changed';end if;
 if (select original from nc_protected_message) is distinct from (select to_jsonb(q) from pgmq.q_noetharaclipz q where (q.message->>'job_id')::uuid=(select protected_jid from nc_local)) then raise exception 'Protected queue visibility changed';end if;
end $$;

-- Zero executed tokens are accepted only for an actual cache reuse or empty-media admission.
do $$ declare mode text; reservation jsonb; job jsonb; new_jid uuid; artifact jsonb; meta jsonb;
begin
 foreach mode in array array['cache','admission'] loop
  perform set_config('request.jwt.claims',jsonb_build_object('sub',(select owner from nc_local),'role','authenticated')::text,true);
  reservation:=public.prepare_upload(gen_random_uuid(),mode||'.mp4','video/mp4',1000,'Zero-token SQL contract');
  insert into storage.objects(bucket_id,name,metadata) values('source-videos',reservation->>'path','{"size":1000}');
  new_jid:=public.finalize_upload((reservation->>'project_id')::uuid);
  perform set_config('request.jwt.claims','{"role":"service_role"}',true);
  job:=public.worker_claim_scoped((select owner from nc_local));
  if job->>'id' is distinct from new_jid::text then raise exception 'Scoped zero-token claim failed';end if;
  meta:='{"duration":10,"width":320,"height":180,"fps":24,"has_audio":false}';
  artifact:='{"provider":"local-smolvlm2","model":"HuggingFaceTB/SmolVLM2-500M-Video-Instruct@7b375e1b73b11138ff12fe22c8f2822d8fe03467","transcript":[],"scenes":[],"audio_events":[],"waveform":[],"frame_paths":[],"summary":"SQL fixture, no AI claim","local_usage":{"input_tokens":0,"output_tokens":0}}';
  begin perform public.worker_finish_analysis(new_jid,(job->>'lease_token')::uuid,meta,artifact,'[]');raise exception 'Unexplained zero usage accepted';exception when raise_exception then if sqlerrm='Unexplained zero usage accepted' then raise;end if;end;
  artifact:=artifact||jsonb_build_object('local_metrics',case mode when 'cache' then '{"analysis_cache_hit":true}'::jsonb else '{"admission_rejected":true}'::jsonb end);
  perform public.worker_finish_analysis(new_jid,(job->>'lease_token')::uuid,meta,artifact,'[]');
  if not exists(select 1 from public.provider_usage where job_id=new_jid and input_tokens=0 and output_tokens=0 and provider='local-smolvlm2') then raise exception 'Zero executed usage was misreported';end if;
 end loop;
 if (select original from nc_protected_job) is distinct from (select to_jsonb(j) from public.processing_jobs j where id=(select protected_jid from nc_local)) then raise exception 'Protected job changed during cache tests';end if;
 if (select original from nc_protected_message) is distinct from (select to_jsonb(q) from pgmq.q_noetharaclipz q where (q.message->>'job_id')::uuid=(select protected_jid from nc_local)) then raise exception 'Protected visibility changed during cache tests';end if;
end $$;
rollback;
select 'Local provider, scoped queue, readiness, cancellation/recovery, provenance and protected-job assertions passed' as result;
