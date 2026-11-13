-- Proposed scoped local-worker support for zxdnjnsghdnviflahvry only.
-- Not applied. Existing heartbeat migration and global claim are unchanged.
create table private.scoped_worker_health (
 owner_id uuid primary key references auth.users(id) on delete cascade,
 heartbeat_at timestamptz not null, ai_ready boolean not null, detail text not null
);
alter table private.scoped_worker_health enable row level security;
revoke all on private.scoped_worker_health from public, anon, authenticated, service_role;

create function private.worker_claim_scoped(owner uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; tok uuid;
begin
 perform private.require_worker();
 if owner is null then raise exception 'Explicit owner scope required'; end if;
 perform pg_advisory_xact_lock(809604);
 if exists(select 1 from public.processing_jobs where lease_until>now() and status not in ('completed','failed','cancelled')) then return null; end if;
 select jobs.* into j from public.processing_jobs jobs
 join public.projects p on p.id=jobs.project_id
 join pgmq.q_noetharaclipz q on q.msg_id=jobs.message_id and (q.message->>'job_id')::uuid=jobs.id
 where p.owner_id=owner and p.deleted_at is null
 and jobs.status not in ('completed','failed','cancelled')
 and (jobs.lease_until is null or jobs.lease_until<now()) and q.vt<=clock_timestamp()
 order by jobs.created_at for update of jobs skip locked limit 1;
 if j.id is null then return null; end if;
 perform pgmq.set_vt('noetharaclipz',j.message_id,120);
 tok:=gen_random_uuid();
 update public.processing_jobs set lease_token=tok,lease_until=now()+interval '120 seconds',attempts=attempts+1,updated_at=now() where id=j.id returning * into j;
 return to_jsonb(j);
end $$;
create function public.worker_claim_scoped(owner uuid) returns jsonb language sql security invoker set search_path='' as $$ select private.worker_claim_scoped(owner); $$;
revoke all on function private.worker_claim_scoped(uuid) from public,anon,authenticated;
revoke all on function public.worker_claim_scoped(uuid) from public,anon,authenticated;
grant execute on function private.worker_claim_scoped(uuid),public.worker_claim_scoped(uuid) to service_role;

create function private.worker_heartbeat_scoped(owner uuid,ai_ready boolean,detail text) returns void language plpgsql security definer set search_path='' as $$
begin
 perform private.require_worker();
 if owner is null then raise exception 'Explicit owner scope required'; end if;
 insert into private.scoped_worker_health(owner_id,heartbeat_at,ai_ready,detail)
 values(owner,now(),ai_ready,left(detail,300)) on conflict(owner_id)
 do update set heartbeat_at=excluded.heartbeat_at,ai_ready=excluded.ai_ready,detail=excluded.detail;
end $$;
create function public.worker_heartbeat_scoped(owner uuid,ai_ready boolean,detail text) returns void language sql security invoker set search_path='' as $$ select private.worker_heartbeat_scoped(owner,ai_ready,detail); $$;
revoke all on function private.worker_heartbeat_scoped(uuid,boolean,text) from public,anon,authenticated;
revoke all on function public.worker_heartbeat_scoped(uuid,boolean,text) from public,anon,authenticated;
grant execute on function private.worker_heartbeat_scoped(uuid,boolean,text),public.worker_heartbeat_scoped(uuid,boolean,text) to service_role;

create or replace function private.pipeline_health() returns jsonb language plpgsql security definer set search_path='' as $$
declare h record;
begin
 if auth.uid() is null then raise exception 'Sign in required'; end if;
 select heartbeat_at,ai_ready,detail into h from private.scoped_worker_health
 where owner_id=auth.uid() and heartbeat_at>now()-interval '90 seconds';
 if not found then select heartbeat_at,ai_ready,detail into h from private.worker_health where id=true; end if;
 return jsonb_build_object('online',coalesce(h.heartbeat_at>now()-interval '90 seconds',false),'ai_ready',coalesce(h.ai_ready and h.heartbeat_at>now()-interval '90 seconds',false),'detail',h.detail,'max_bytes',45000000,'max_seconds',300);
end $$;

create or replace function private.worker_finish_analysis(jid uuid, token uuid, metadata jsonb, artifacts jsonb, highlights jsonb) returns void language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; h jsonb; ids uuid[]:='{}'; hid uuid; dur double precision:=(metadata->>'duration')::double precision; selected_provider text:=coalesce(artifacts->>'provider','gemini');
begin
 perform private.require_worker(); select * into j from public.processing_jobs where id=jid for update;
 if j.id is null or j.status in ('completed','failed','cancelled') or j.kind<>'analysis' or token is null or j.lease_token is null or j.lease_until is null or j.lease_token is distinct from token or j.lease_until<now() or j.cancel_requested then raise exception 'Invalid or cancelled analysis lease'; end if;
 if selected_provider not in ('gemini','local-smolvlm2') then raise exception 'Unsupported provider'; end if;
 if selected_provider='local-smolvlm2' and (artifacts->>'model' is distinct from 'HuggingFaceTB/SmolVLM2-500M-Video-Instruct@7b375e1b73b11138ff12fe22c8f2822d8fe03467' or (coalesce((artifacts->'local_usage'->>'input_tokens')::int,-1)<0 or coalesce((artifacts->'local_usage'->>'output_tokens')::int,-1)<0 or ((artifacts->'local_usage'->>'input_tokens')::int=0 and not (coalesce((artifacts->'local_metrics'->>'analysis_cache_hit')::boolean,false) or coalesce((artifacts->'local_metrics'->>'admission_rejected')::boolean,false))))) then raise exception 'Invalid local provenance'; end if;
 if dur is null or dur<=0 or dur>300 then raise exception 'Invalid source duration'; end if;
 if jsonb_array_length(highlights)>5 then raise exception 'Too many highlights'; end if;
 if exists(select 1 from public.highlights where project_id=j.project_id) then raise exception 'Analysis already committed'; end if;
 update public.videos set duration=dur,width=(metadata->>'width')::int,height=(metadata->>'height')::int,fps=(metadata->>'fps')::double precision,
 has_audio=(metadata->>'has_audio')::boolean,playback_path=metadata->>'playback_path',thumbnail_path=metadata->>'thumbnail_path',source_hash=metadata->>'source_hash',status='ready' where project_id=j.project_id;
 insert into public.analysis_artifacts(project_id,transcript,scenes,audio_events,waveform,frame_paths,provider,model,summary,warnings)
 values(j.project_id,artifacts->'transcript',artifacts->'scenes',artifacts->'audio_events',artifacts->'waveform',artifacts->'frame_paths',selected_provider,artifacts->>'model',artifacts->>'summary',coalesce(artifacts->'warnings','[]'))
 on conflict(project_id) do update set transcript=excluded.transcript,scenes=excluded.scenes,audio_events=excluded.audio_events,waveform=excluded.waveform,frame_paths=excluded.frame_paths,provider=excluded.provider,model=excluded.model,summary=excluded.summary,warnings=excluded.warnings,updated_at=now();
 for h in select * from jsonb_array_elements(highlights) loop
  if (h->>'start')::double precision<0 or (h->>'end')::double precision>dur or (h->>'end')::double precision-(h->>'start')::double precision>60 then raise exception 'Highlight outside media bounds'; end if;
  insert into public.highlights(project_id,start_time,end_time,title,category,score,explanation,evidence) values(j.project_id,(h->>'start')::double precision,(h->>'end')::double precision,h->>'title',h->>'category',(h->>'score')::int,h->>'explanation',jsonb_build_object('visual',h->>'visual_evidence')) returning id into hid;
  ids:=array_append(ids,hid);
 end loop;
 insert into public.conversation_messages(project_id,role,content,highlight_ids) values(j.project_id,'assistant',coalesce(artifacts->>'summary','Analysis completed.'),ids);
 if selected_provider='local-smolvlm2' then
 insert into public.provider_usage(job_id,project_id,request_key,provider,model,status,input_tokens,output_tokens)
 values(jid,j.project_id,'local:'||jid::text,selected_provider,artifacts->>'model','completed',(artifacts->'local_usage'->>'input_tokens')::int,coalesce((artifacts->'local_usage'->>'output_tokens')::int,0));
 end if;
 update public.processing_jobs set payload=payload||jsonb_build_object('provider',selected_provider,'model',artifacts->>'model','local_metrics',coalesce(artifacts->'local_metrics','{}'::jsonb)) where id=jid;
 perform private.worker_tick(jid,token,'completed',100,'Analysis completed');
end $$;

create function public.worker_protocol() returns jsonb language plpgsql security definer set search_path='' as $$
begin
 perform private.require_worker();
 return '{"version":1,"providers":["gemini","local-smolvlm2"],"scoped_claim":true,"scoped_health":true}'::jsonb;
end $$;
revoke all on function public.worker_protocol() from public,anon,authenticated;
grant execute on function public.worker_protocol() to service_role;
