create function private.worker_finish_analysis(jid uuid, token uuid, metadata jsonb, artifacts jsonb, highlights jsonb) returns void language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; h jsonb; ids uuid[]:='{}'; hid uuid; dur double precision:=(metadata->>'duration')::double precision;
begin
 perform private.require_worker(); select * into j from public.processing_jobs where id=jid for update;
 if j.kind<>'analysis' or j.lease_token is distinct from token or j.lease_until<now() or j.cancel_requested then raise exception 'Invalid or cancelled analysis lease'; end if;
 if dur is null or dur<=0 or dur>300 then raise exception 'Invalid source duration'; end if;
 if jsonb_array_length(highlights)>5 then raise exception 'Too many highlights'; end if;
 if exists(select 1 from public.highlights where project_id=j.project_id) then raise exception 'Analysis already committed'; end if;
 update public.videos set duration=dur,width=(metadata->>'width')::int,height=(metadata->>'height')::int,fps=(metadata->>'fps')::double precision,
 has_audio=(metadata->>'has_audio')::boolean,playback_path=metadata->>'playback_path',thumbnail_path=metadata->>'thumbnail_path',source_hash=metadata->>'source_hash',status='ready' where project_id=j.project_id;
 insert into public.analysis_artifacts(project_id,transcript,scenes,audio_events,waveform,frame_paths,provider,model,summary,warnings)
 values(j.project_id,artifacts->'transcript',artifacts->'scenes',artifacts->'audio_events',artifacts->'waveform',artifacts->'frame_paths','gemini',artifacts->>'model',artifacts->>'summary',coalesce(artifacts->'warnings','[]'))
 on conflict(project_id) do update set transcript=excluded.transcript,scenes=excluded.scenes,audio_events=excluded.audio_events,waveform=excluded.waveform,frame_paths=excluded.frame_paths,provider=excluded.provider,model=excluded.model,summary=excluded.summary,warnings=excluded.warnings,updated_at=now();
 for h in select * from jsonb_array_elements(highlights) loop
  if (h->>'start')::double precision<0 or (h->>'end')::double precision>dur or (h->>'end')::double precision-(h->>'start')::double precision>60 then raise exception 'Highlight outside media bounds'; end if;
  insert into public.highlights(project_id,start_time,end_time,title,category,score,explanation,evidence) values(j.project_id,(h->>'start')::double precision,(h->>'end')::double precision,h->>'title',h->>'category',(h->>'score')::int,h->>'explanation',jsonb_build_object('visual',h->>'visual_evidence')) returning id into hid;
  ids:=array_append(ids,hid);
 end loop;
 insert into public.conversation_messages(project_id,role,content,highlight_ids) values(j.project_id,'assistant',coalesce(artifacts->>'summary','Analysis completed.'),ids);
 perform private.worker_tick(jid,token,'completed',100,'Analysis completed');
end $$;
create function private.worker_finish_render(jid uuid, token uuid, path text, bytes bigint) returns void language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; uid uuid;
begin
 perform private.require_worker(); select * into j from public.processing_jobs where id=jid for update;
 select owner_id into uid from public.projects where id=j.project_id;
 if j.kind<>'render' or j.lease_token is distinct from token or j.lease_until<now() or j.cancel_requested then raise exception 'Invalid or cancelled render lease'; end if;
 if path<>uid::text||'/'||j.project_id::text||'/'||jid::text||'.mp4' or bytes<=0 or bytes>45000000 or not exists(select 1 from storage.objects where bucket_id='rendered-clips' and name=path and (metadata->>'size')::bigint=bytes) then raise exception 'Rendered object is missing or invalid'; end if;
 update public.processing_jobs set payload=payload||jsonb_build_object('output_path',path,'output_bytes',bytes) where id=jid;
 update public.clips set output_path=path,output_bytes=bytes,rendered_revision=(j.payload->>'revision')::int where id=j.clip_id and revision=(j.payload->>'revision')::int;
 perform private.worker_tick(jid,token,'completed',100,'MP4 ready to download');
end $$;
revoke all on function private.worker_finish_analysis from public,anon,authenticated;
revoke all on function private.worker_finish_render from public,anon,authenticated;
grant execute on function private.worker_finish_analysis to service_role;
grant execute on function private.worker_finish_render to service_role;
create function public.worker_finish_analysis(jid uuid, token uuid, metadata jsonb, artifacts jsonb, highlights jsonb) returns void language sql security invoker set search_path='' as $$ select private.worker_finish_analysis(jid,token,metadata,artifacts,highlights); $$;
create function public.worker_finish_render(jid uuid, token uuid, path text, bytes bigint) returns void language sql security invoker set search_path='' as $$ select private.worker_finish_render(jid,token,path,bytes); $$;
revoke all on function public.worker_finish_analysis from public,anon,authenticated;
revoke all on function public.worker_finish_render from public,anon,authenticated;
grant execute on function public.worker_finish_analysis to service_role;
grant execute on function public.worker_finish_render to service_role;
