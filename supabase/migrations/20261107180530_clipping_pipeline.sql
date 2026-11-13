-- NoetharaClipz only. Durable jobs and private, owner-scoped media.
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated, service_role;
create extension if not exists pgmq;
select pgmq.create('noetharaclipz');

create table public.profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 display_name text not null default '' check (length(display_name)<=120),
 avatar_url text, preferences jsonb not null default '{}', created_at timestamptz not null default now()
);
create table public.projects (
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id) on delete cascade,
 request_id uuid not null, title text not null check (length(title) between 1 and 200),
 instructions text not null check (length(instructions)<=4000), source_platform text not null default 'Upload', source_url text,
 status text not null default 'uploading' check(status in ('uploading','queued','processing','ready','failed','cancelled')),
 folder text not null default 'TikTok' check(folder in ('TikTok','YouTube','IG Reels')),
 deleted_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(owner_id,request_id)
);
create table public.videos (
 id uuid primary key default gen_random_uuid(), project_id uuid not null unique references public.projects(id) on delete cascade,
 source_path text not null unique, playback_path text, thumbnail_path text,
 filename text not null, mime_type text not null, byte_size bigint not null check(byte_size>0 and byte_size<=45000000),
 duration double precision check(duration>0 and duration<=300), width integer, height integer, fps double precision,
 has_audio boolean, source_hash text, status text not null default 'uploading', created_at timestamptz not null default now()
);
create table public.highlights (
 id uuid primary key default gen_random_uuid(), project_id uuid not null references public.projects(id) on delete cascade,
 start_time double precision not null check(start_time>=0), end_time double precision not null,
 title text not null, category text not null check(category in ('Clutch','Funny','Hype','Reaction','Tutorial','Other')),
 score integer not null check(score between 0 and 100), explanation text not null,
 evidence jsonb not null default '{}', created_at timestamptz not null default now(),
 check(end_time>start_time), unique(id,project_id)
);
create table public.clips (
 id uuid primary key default gen_random_uuid(), project_id uuid not null references public.projects(id) on delete cascade,
 highlight_id uuid not null, edit jsonb not null, revision integer not null default 1,
 render_status text not null default 'draft', output_path text, output_bytes bigint not null default 0,
 rendered_revision integer, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 foreign key(highlight_id,project_id) references public.highlights(id,project_id) on delete cascade,
 unique(highlight_id), unique(id,project_id)
);
create table public.processing_jobs (
 id uuid primary key default gen_random_uuid(), project_id uuid not null references public.projects(id) on delete cascade,
 clip_id uuid, kind text not null check(kind in ('analysis','render','conversation')),
 dedupe_key text not null unique, payload jsonb not null default '{}',
 status text not null default 'queued' check(status in ('queued','preparing','analyzing','generating_highlights','rendering','completed','failed','cancelled')),
 progress integer not null default 0 check(progress between 0 and 100), stage text not null default 'Waiting for worker',
 error text, cancel_requested boolean not null default false, attempts integer not null default 0,
 message_id bigint, lease_token uuid, lease_until timestamptz, reserved_bytes bigint not null default 0,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 foreign key(clip_id,project_id) references public.clips(id,project_id) on delete cascade
);
create table public.conversation_messages (
 id uuid primary key default gen_random_uuid(), project_id uuid not null references public.projects(id) on delete cascade,
 role text not null check(role in ('user','assistant','system')), content text not null check(length(content)<=16000),
 highlight_ids uuid[] not null default '{}', created_at timestamptz not null default now()
);
create table public.brand_settings (
 owner_id uuid primary key references auth.users(id) on delete cascade, settings jsonb not null default '{}', updated_at timestamptz not null default now()
);
create table public.analysis_artifacts (
 project_id uuid primary key references public.projects(id) on delete cascade,
 transcript jsonb not null default '[]', scenes jsonb not null default '[]', audio_events jsonb not null default '[]',
 waveform jsonb not null default '[]', frame_paths jsonb not null default '[]', provider text, model text,
 summary text, warnings jsonb not null default '[]', updated_at timestamptz not null default now()
);
create table public.provider_usage (
 id uuid primary key default gen_random_uuid(), job_id uuid not null references public.processing_jobs(id) on delete cascade,
 project_id uuid not null references public.projects(id) on delete cascade, request_key text not null unique,
 provider text not null, model text not null, status text not null default 'reserved',
 input_tokens integer not null default 0, output_tokens integer not null default 0,
 estimated_cost numeric not null default 0 check(estimated_cost=0), created_at timestamptz not null default now()
);
create table private.worker_health (id boolean primary key default true check(id), heartbeat_at timestamptz, ai_ready boolean not null default false, detail text);
insert into private.worker_health(id) values(true);
alter table private.worker_health enable row level security;

create index projects_owner_recent on public.projects(owner_id,created_at desc);
create index projects_deleted on public.projects(deleted_at) where deleted_at is not null;
create index highlights_project on public.highlights(project_id,start_time);
create index clips_project on public.clips(project_id);
create index jobs_project on public.processing_jobs(project_id,created_at desc);
create index jobs_clip on public.processing_jobs(clip_id);
create index jobs_active on public.processing_jobs(status,lease_until) where status not in ('completed','failed','cancelled');
create index messages_project on public.conversation_messages(project_id,created_at);
create index usage_job on public.provider_usage(job_id);
create index usage_project on public.provider_usage(project_id);
create index usage_day on public.provider_usage(created_at);

-- Immutable ownership; clients cannot write processing state, detected results, or output paths.
alter table public.profiles enable row level security;
revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant all on public.profiles to service_role;
create policy owner_read on public.profiles for select to authenticated using (id=(select auth.uid()));
alter table public.projects enable row level security;
revoke all on public.projects from anon, authenticated;
grant select on public.projects to authenticated;
grant all on public.projects to service_role;
create policy owner_read on public.projects for select to authenticated using (owner_id=(select auth.uid()));
alter table public.videos enable row level security;
revoke all on public.videos from anon, authenticated;
grant select on public.videos to authenticated;
grant all on public.videos to service_role;
create policy owner_read on public.videos for select to authenticated using (exists(select 1 from public.projects p where p.id=videos.project_id and p.owner_id=(select auth.uid())));
alter table public.highlights enable row level security;
revoke all on public.highlights from anon, authenticated;
grant select on public.highlights to authenticated;
grant all on public.highlights to service_role;
create policy owner_read on public.highlights for select to authenticated using (exists(select 1 from public.projects p where p.id=highlights.project_id and p.owner_id=(select auth.uid())));
alter table public.clips enable row level security;
revoke all on public.clips from anon, authenticated;
grant select on public.clips to authenticated;
grant all on public.clips to service_role;
create policy owner_read on public.clips for select to authenticated using (exists(select 1 from public.projects p where p.id=clips.project_id and p.owner_id=(select auth.uid())));
alter table public.processing_jobs enable row level security;
revoke all on public.processing_jobs from anon, authenticated;
grant select on public.processing_jobs to authenticated;
grant all on public.processing_jobs to service_role;
create policy owner_read on public.processing_jobs for select to authenticated using (exists(select 1 from public.projects p where p.id=processing_jobs.project_id and p.owner_id=(select auth.uid())));
alter table public.conversation_messages enable row level security;
revoke all on public.conversation_messages from anon, authenticated;
grant select on public.conversation_messages to authenticated;
grant all on public.conversation_messages to service_role;
create policy owner_read on public.conversation_messages for select to authenticated using (exists(select 1 from public.projects p where p.id=conversation_messages.project_id and p.owner_id=(select auth.uid())));
alter table public.brand_settings enable row level security;
revoke all on public.brand_settings from anon, authenticated;
grant select on public.brand_settings to authenticated;
grant all on public.brand_settings to service_role;
create policy owner_read on public.brand_settings for select to authenticated using (owner_id=(select auth.uid()));
alter table public.analysis_artifacts enable row level security;
revoke all on public.analysis_artifacts from anon, authenticated;
grant select on public.analysis_artifacts to authenticated;
grant all on public.analysis_artifacts to service_role;
create policy owner_read on public.analysis_artifacts for select to authenticated using (exists(select 1 from public.projects p where p.id=analysis_artifacts.project_id and p.owner_id=(select auth.uid())));
alter table public.provider_usage enable row level security;
revoke all on public.provider_usage from anon, authenticated;
grant select on public.provider_usage to authenticated;
grant all on public.provider_usage to service_role;
create policy owner_read on public.provider_usage for select to authenticated using (exists(select 1 from public.projects p where p.id=provider_usage.project_id and p.owner_id=(select auth.uid())));

grant insert,update on public.profiles to authenticated;
create policy profile_insert on public.profiles for insert to authenticated with check(id=(select auth.uid()));
create policy profile_update on public.profiles for update to authenticated using(id=(select auth.uid())) with check(id=(select auth.uid()));
grant insert,update on public.brand_settings to authenticated;
create policy brand_insert on public.brand_settings for insert to authenticated with check(owner_id=(select auth.uid()));
create policy brand_update on public.brand_settings for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));

create function private.require_owner(pid uuid) returns uuid language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null or not exists(select 1 from public.projects where id=pid and owner_id=auth.uid()) then raise exception 'Project not found or access denied'; end if;
 return auth.uid();
end $$;
create function private.require_worker() returns void language plpgsql security invoker set search_path='' as $$
begin
 if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'Worker authorization required'; end if;
end $$;
create function private.enqueue(pid uuid, typ text, key text, body jsonb, cid uuid default null, reservation bigint default 0) returns uuid language plpgsql security definer set search_path='' as $$
declare jid uuid;
begin
 insert into public.processing_jobs(project_id,kind,dedupe_key,payload,clip_id,reserved_bytes) values(pid,typ,key,body,cid,reservation)
 on conflict(dedupe_key) do nothing returning id into jid;
 if jid is null then select id into jid from public.processing_jobs where dedupe_key=key; return jid; end if;
 update public.processing_jobs set message_id=pgmq.send('noetharaclipz',jsonb_build_object('job_id',jid)) where id=jid;
 return jid;
end $$;
create function private.check_capacity(uid uuid, extra bigint) returns void language plpgsql security definer set search_path='' as $$
declare total bigint; personal bigint;
begin
 perform pg_advisory_xact_lock(809602);
 select coalesce(sum(v.byte_size*2),0) into total from public.videos v;
 select coalesce(sum(v.byte_size*2),0) into personal from public.videos v join public.projects p on p.id=v.project_id where p.owner_id=uid;
 total:=total+(select coalesce(sum(output_bytes),0) from public.clips)+(select coalesce(sum(reserved_bytes),0) from public.processing_jobs where status not in ('completed','failed','cancelled'));
 personal:=personal+(select coalesce(sum(c.output_bytes),0) from public.clips c join public.projects p on p.id=c.project_id where p.owner_id=uid)+(select coalesce(sum(j.reserved_bytes),0) from public.processing_jobs j join public.projects p on p.id=j.project_id where p.owner_id=uid and j.status not in ('completed','failed','cancelled'));
 if total+extra>800000000 or personal+extra>200000000 then raise exception 'Storage allowance reached. Remove unused projects or exports before uploading.'; end if;
end $$;
create function private.prepare_upload(request_id uuid, filename text, mime_type text, byte_size bigint, instructions text) returns jsonb language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); pid uuid; vid uuid; path text; ext text;
begin
 if uid is null then raise exception 'Sign in to upload'; end if;
 if byte_size<=0 or byte_size>45000000 then raise exception 'Video must be between 1 byte and 45 MB'; end if;
 if mime_type not in ('video/mp4','video/quicktime','video/webm') then raise exception 'Upload MP4, MOV or WebM'; end if;
 if length(instructions)>4000 or length(filename)>240 then raise exception 'Input too long'; end if;
 perform pg_advisory_xact_lock(809602);
 select p.id,v.id,v.source_path into pid,vid,path from public.projects p join public.videos v on v.project_id=p.id where p.owner_id=uid and p.request_id=prepare_upload.request_id;
 if pid is not null then return jsonb_build_object('project_id',pid,'video_id',vid,'path',path); end if;
 if (select count(*) from public.projects where owner_id=uid and created_at>now()-interval '1 day')>=10 then raise exception 'Daily project limit reached'; end if;
 perform private.check_capacity(uid,byte_size*2);
 insert into public.projects(owner_id,request_id,title,instructions) values(uid,request_id,left(filename,200),instructions) returning id into pid;
 vid:=gen_random_uuid(); ext:=case mime_type when 'video/mp4' then 'mp4' when 'video/webm' then 'webm' else 'mov' end;
 path:=uid::text||'/'||pid::text||'/'||vid::text||'/source.'||ext;
 insert into public.videos(id,project_id,source_path,filename,mime_type,byte_size) values(vid,pid,path,filename,mime_type,byte_size);
 insert into public.conversation_messages(project_id,role,content) values(pid,'user',instructions);
 return jsonb_build_object('project_id',pid,'video_id',vid,'path',path);
end $$;
create function private.finalize_upload(pid uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare v public.videos; jid uuid;
begin
 perform private.require_owner(pid);
 select * into v from public.videos where project_id=pid for update;
 if not exists(select 1 from storage.objects where bucket_id='source-videos' and name=v.source_path and (metadata->>'size')::bigint=v.byte_size) then raise exception 'Source upload is missing or incomplete'; end if;
 jid:=private.enqueue(pid,'analysis','analysis:'||v.id::text||':v1','{}');
 update public.videos set status='queued' where id=v.id and status='uploading';
 update public.projects set status='queued',updated_at=now() where id=pid and status='uploading';
 return jid;
end $$;
create function private.set_deleted(pid uuid, deleted boolean) returns void language plpgsql security definer set search_path='' as $$
begin
 perform private.require_owner(pid);
 update public.projects set deleted_at=case when deleted then now() else null end,updated_at=now() where id=pid;
 if deleted then update public.processing_jobs set cancel_requested=true where project_id=pid and status not in ('completed','failed','cancelled'); end if;
end $$;
create function private.cancel_job(jid uuid) returns void language plpgsql security definer set search_path='' as $$
declare pid uuid;
begin
 select project_id into pid from public.processing_jobs where id=jid; perform private.require_owner(pid);
 update public.processing_jobs set cancel_requested=true,updated_at=now() where id=jid and status not in ('completed','failed','cancelled');
end $$;
create function private.retry_job(jid uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs;
begin
 select * into j from public.processing_jobs where id=jid for update; perform private.require_owner(j.project_id);
 if j.status not in ('failed','cancelled') or j.attempts>=3 then raise exception 'Job cannot be retried'; end if;
 if exists(select 1 from public.provider_usage where job_id=jid and status in ('reserved','unknown')) then raise exception 'Provider outcome is uncertain. Review usage before retrying.'; end if;
 update public.processing_jobs set status='queued',error=null,cancel_requested=false,lease_token=null,lease_until=null,progress=0,stage='Waiting for worker',updated_at=now(),message_id=pgmq.send('noetharaclipz',jsonb_build_object('job_id',jid)) where id=jid;
 if j.kind='analysis' then update public.projects set status='queued',updated_at=now() where id=j.project_id; end if;
 return jid;
end $$;
create function private.validate_edit(e jsonb, duration double precision) returns jsonb language plpgsql security invoker set search_path='' as $$
declare s double precision:=(e->>'start')::double precision; t double precision:=(e->>'end')::double precision;
begin
 if s is null or t is null or s<0 or t<=s or t>duration or t-s>60 or s::text in ('NaN','Infinity') or t::text in ('NaN','Infinity') then raise exception 'Clip must be within the source and at most 60 seconds'; end if;
 if coalesce(e->>'ratio','') not in ('9:16','16:9','1:1','4:5') then raise exception 'Invalid aspect ratio'; end if;
 if coalesce((e->>'crop_x')::numeric,-1) not between 0 and 1 or coalesce((e->>'crop_y')::numeric,-1) not between 0 and 1 or coalesce((e->>'volume')::numeric,-1) not between 0 and 2 then raise exception 'Invalid crop or volume'; end if;
 if coalesce((e->>'caption_size')::numeric,0) not between 16 and 72 or coalesce(e->>'caption_style','') not in ('Bold pop','Karaoke','Minimal','Neon') then raise exception 'Invalid captions'; end if;
 if length(e::text)>32000 then raise exception 'Edit too large'; end if;
 return e;
end $$;
create function private.save_clip(hid uuid, edit jsonb, expected_revision integer default null) returns uuid language plpgsql security definer set search_path='' as $$
declare h public.highlights; v public.videos; c public.clips; result uuid;
begin
 select * into h from public.highlights where id=hid; perform private.require_owner(h.project_id);
 select * into v from public.videos where project_id=h.project_id; perform private.validate_edit(edit,v.duration);
 perform pg_advisory_xact_lock(hashtext(hid::text));
 select * into c from public.clips where highlight_id=hid for update;
 if c.id is not null then
  if expected_revision is null or expected_revision<>c.revision then raise exception 'Clip changed. Reload before saving.'; end if;
  update public.clips set edit=save_clip.edit,revision=revision+1,updated_at=now() where id=c.id returning id into result;
 else
  insert into public.clips(project_id,highlight_id,edit) values(h.project_id,hid,edit) returning id into result;
 end if;
 return result;
end $$;
create function private.export_clip(cid uuid, expected_revision integer) returns uuid language plpgsql security definer set search_path='' as $$
declare c public.clips; jid uuid;
begin
 select * into c from public.clips where id=cid for update; perform private.require_owner(c.project_id);
 if c.revision<>expected_revision then raise exception 'Save the latest edit before export'; end if;
 select id into jid from public.processing_jobs where dedupe_key='render:'||cid::text||':'||expected_revision::text;
 if jid is not null then return jid; end if;
 if (select count(*) from public.processing_jobs where project_id=c.project_id and kind='render' and status not in ('completed','failed','cancelled'))>=3 then raise exception 'Too many pending exports'; end if;
 perform private.check_capacity(auth.uid(),45000000);
 jid:=private.enqueue(c.project_id,'render','render:'||cid::text||':'||expected_revision::text,jsonb_build_object('edit',c.edit,'revision',c.revision),cid,45000000);
 update public.clips set render_status='queued' where id=cid;
 return jid;
end $$;
create function private.worker_claim() returns jsonb language plpgsql security definer set search_path='' as $$
declare m record; j public.processing_jobs; tok uuid;
begin
 perform private.require_worker();
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
create function private.worker_tick(jid uuid, token uuid, state text, pct integer, detail text, error_message text default null) returns boolean language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs;
begin
 perform private.require_worker(); select * into j from public.processing_jobs where id=jid for update;
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
create function private.worker_heartbeat(ai_ready boolean, detail text) returns void language plpgsql security definer set search_path='' as $$
begin
 perform private.require_worker(); update private.worker_health set heartbeat_at=now(),ai_ready=worker_heartbeat.ai_ready,detail=left(worker_heartbeat.detail,300);
end $$;
create function private.pipeline_health() returns jsonb language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'Sign in required'; end if;
 return (select jsonb_build_object('online',heartbeat_at>now()-interval '90 seconds','ai_ready',ai_ready,'detail',detail,'max_bytes',45000000,'max_seconds',300) from private.worker_health);
end $$;
create function private.reserve_inference(jid uuid, token uuid, request_key text, model text, daily_limit integer) returns uuid language plpgsql security definer set search_path='' as $$
declare usage_id uuid;
begin
 perform private.require_worker(); perform pg_advisory_xact_lock(809603);
 if not exists(select 1 from public.processing_jobs where id=jid and lease_token=token and lease_until>now() and not cancel_requested) then raise exception 'Invalid worker lease'; end if;
 if model<>'gemini-3.8-flash' then raise exception 'Model is not on the free development allowlist'; end if;
 if exists(select 1 from public.provider_usage where provider_usage.request_key=reserve_inference.request_key) then raise exception 'Inference already dispatched; refusing duplicate'; end if;
 if (select count(*) from public.provider_usage where created_at>now()-interval '24 hours')>=least(greatest(daily_limit,0),5) then raise exception 'Free development request allowance reached'; end if;
 if exists(select 1 from public.provider_usage where created_at>now()-interval '60 seconds') then raise exception 'Free development rate limit: wait one minute'; end if;
 insert into public.provider_usage(job_id,project_id,request_key,provider,model) select jid,project_id,request_key,'gemini',model from public.processing_jobs where id=jid returning id into usage_id;
 return usage_id;
end $$;

-- Functions are exposed only through invoker wrappers; privileged bodies stay private.
revoke all on all functions in schema private from public, anon, authenticated, service_role;
create function public.prepare_upload(request_id uuid, filename text, mime_type text, byte_size bigint, instructions text) returns jsonb language sql security invoker set search_path='' as $$ select private.prepare_upload(request_id,filename,mime_type,byte_size,instructions); $$;
revoke all on function public.prepare_upload from public, anon, authenticated, service_role;
grant execute on function public.prepare_upload to authenticated;
grant execute on function private.prepare_upload to authenticated;
create function public.finalize_upload(pid uuid) returns uuid language sql security invoker set search_path='' as $$ select private.finalize_upload(pid); $$;
revoke all on function public.finalize_upload from public, anon, authenticated, service_role;
grant execute on function public.finalize_upload to authenticated;
grant execute on function private.finalize_upload to authenticated;
create function public.set_deleted(pid uuid, deleted boolean) returns void language sql security invoker set search_path='' as $$ select private.set_deleted(pid,deleted); $$;
revoke all on function public.set_deleted from public, anon, authenticated, service_role;
grant execute on function public.set_deleted to authenticated;
grant execute on function private.set_deleted to authenticated;
create function public.cancel_job(jid uuid) returns void language sql security invoker set search_path='' as $$ select private.cancel_job(jid); $$;
revoke all on function public.cancel_job from public, anon, authenticated, service_role;
grant execute on function public.cancel_job to authenticated;
grant execute on function private.cancel_job to authenticated;
create function public.retry_job(jid uuid) returns uuid language sql security invoker set search_path='' as $$ select private.retry_job(jid); $$;
revoke all on function public.retry_job from public, anon, authenticated, service_role;
grant execute on function public.retry_job to authenticated;
grant execute on function private.retry_job to authenticated;
create function public.save_clip(hid uuid, edit jsonb, expected_revision integer default null) returns uuid language sql security invoker set search_path='' as $$ select private.save_clip(hid,edit,expected_revision); $$;
revoke all on function public.save_clip from public, anon, authenticated, service_role;
grant execute on function public.save_clip to authenticated;
grant execute on function private.save_clip to authenticated;
create function public.export_clip(cid uuid, expected_revision integer) returns uuid language sql security invoker set search_path='' as $$ select private.export_clip(cid,expected_revision); $$;
revoke all on function public.export_clip from public, anon, authenticated, service_role;
grant execute on function public.export_clip to authenticated;
grant execute on function private.export_clip to authenticated;
create function public.pipeline_health() returns jsonb language sql security invoker set search_path='' as $$ select private.pipeline_health(); $$;
revoke all on function public.pipeline_health from public, anon, authenticated, service_role;
grant execute on function public.pipeline_health to authenticated;
grant execute on function private.pipeline_health to authenticated;
create function public.worker_claim() returns jsonb language sql security invoker set search_path='' as $$ select private.worker_claim(); $$;
revoke all on function public.worker_claim from public, anon, authenticated, service_role;
grant execute on function public.worker_claim to service_role;
grant execute on function private.worker_claim to service_role;
create function public.worker_tick(jid uuid, token uuid, state text, pct integer, detail text, error_message text default null) returns boolean language sql security invoker set search_path='' as $$ select private.worker_tick(jid,token,state,pct,detail,error_message); $$;
revoke all on function public.worker_tick from public, anon, authenticated, service_role;
grant execute on function public.worker_tick to service_role;
grant execute on function private.worker_tick to service_role;
create function public.worker_heartbeat(ai_ready boolean, detail text) returns void language sql security invoker set search_path='' as $$ select private.worker_heartbeat(ai_ready,detail); $$;
revoke all on function public.worker_heartbeat from public, anon, authenticated, service_role;
grant execute on function public.worker_heartbeat to service_role;
grant execute on function private.worker_heartbeat to service_role;
create function public.reserve_inference(jid uuid, token uuid, request_key text, model text, daily_limit integer) returns uuid language sql security invoker set search_path='' as $$ select private.reserve_inference(jid,token,request_key,model,daily_limit); $$;
revoke all on function public.reserve_inference from public, anon, authenticated, service_role;
grant execute on function public.reserve_inference to service_role;
grant execute on function private.reserve_inference to service_role;

-- Worker-only table writes use a service credential; never grant this role in the browser.
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values
 ('source-videos','source-videos',false,45000000,array['video/mp4','video/quicktime','video/webm']),
 ('rendered-clips','rendered-clips',false,45000000,array['video/mp4']),
 ('thumbnails','thumbnails',false,2000000,array['image/jpeg','image/png']),
 ('processing-artifacts','processing-artifacts',false,45000000,array['video/mp4','application/json','audio/wav']),
 ('brand-assets','brand-assets',false,2000000,array['image/png','image/jpeg']);
create policy clip_media_read on storage.objects for select to authenticated using(
 bucket_id in ('source-videos','rendered-clips','thumbnails','processing-artifacts','brand-assets') and (storage.foldername(name))[1]=(select auth.uid())::text
);
create policy clip_source_insert on storage.objects for insert to authenticated with check(
 bucket_id='source-videos' and exists(select 1 from public.videos v join public.projects p on p.id=v.project_id where v.source_path=name and v.status='uploading' and p.owner_id=(select auth.uid()) and p.deleted_at is null)
);
create policy clip_brand_insert on storage.objects for insert to authenticated with check(bucket_id='brand-assets' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy clip_brand_delete on storage.objects for delete to authenticated using(bucket_id='brand-assets' and (storage.foldername(name))[1]=(select auth.uid())::text);

-- RLS still filters every change delivered to the client.
alter publication supabase_realtime add table public.projects, public.processing_jobs, public.highlights, public.clips, public.conversation_messages;
