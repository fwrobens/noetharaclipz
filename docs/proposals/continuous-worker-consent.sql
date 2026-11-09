-- REVIEW PROPOSAL ONLY. Do not apply without separate database authorization.
-- Target: zxdnjnsghdnviflahvry; requires the already deployed v1 queue migrations.
-- No existing job is backfilled, released, claimed, cancelled or reset here.
-- Record as a NEW versioned migration after review; never rewrite old migrations.

create table private.continuous_owner_consents (
 owner_id uuid primary key references auth.users(id) on delete cascade,
 consent_id uuid not null unique, request_id uuid not null,
 terms_version text not null check(terms_version='local-video-v1'),
 requested_at timestamptz not null, approved_at timestamptz, expires_at timestamptz,
 revoked_at timestamptz, approval_reason text,
 check(approved_at is null or expires_at>approved_at)
);
create table private.continuous_owner_exclusions(owner_id uuid primary key,reason text not null);
insert into private.continuous_owner_exclusions values
 ('c7ade7f9-2003-4a38-ae19-393fffae8452','Preserved original QA trial'),
 ('3e593ddf-c6ce-4895-ae05-0eccb721d674','Preserved failed QA trial'),
 ('07ad237e-669b-475d-871d-9bdb6e80f062','Preserved completed reliability trial');
create table private.continuous_job_exclusions(job_id uuid primary key,reason text not null,excluded_at timestamptz not null default clock_timestamp());
insert into private.continuous_job_exclusions(job_id,reason) values
 ('9c5c8869-ec2e-4a3e-927d-697615bb58a3','User protected upload; never release');
create table private.continuous_job_bindings (
 job_id uuid primary key references public.processing_jobs(id) on delete cascade,
 owner_id uuid not null, consent_id uuid not null, identity jsonb not null,
 bound_at timestamptz not null default clock_timestamp()
);
create table private.continuous_job_leases (
 job_id uuid primary key references public.processing_jobs(id) on delete cascade,
 owner_id uuid not null, consent_id uuid not null, token uuid not null,
 claimed_at timestamptz not null default clock_timestamp()
);
create table private.continuous_audit (
 id bigint generated always as identity primary key, at timestamptz not null default clock_timestamp(),
 actor uuid, actor_role text, owner_id uuid, consent_id uuid, job_id uuid,
 event text not null, reason text not null default '' check(length(reason)<=300)
);
do $$ declare t text; begin
 foreach t in array array['continuous_owner_consents','continuous_owner_exclusions','continuous_job_exclusions','continuous_job_bindings','continuous_job_leases','continuous_audit'] loop
  execute format('alter table private.%I enable row level security',t);
  execute format('revoke all on private.%I from public,anon,authenticated,service_role',t);
 end loop;
end $$;

create function private.continuous_log(ev text,uid uuid,cid uuid default null,jid uuid default null,why text default '') returns void
language sql security definer set search_path='' as $$
 insert into private.continuous_audit(actor,actor_role,owner_id,consent_id,job_id,event,reason)
 values(auth.uid(),auth.jwt()->>'role',uid,cid,jid,ev,left(why,300));
$$;
create function private.continuous_audit_immutable() returns trigger language plpgsql security definer set search_path='' as $$
begin raise exception 'Continuous audit is append-only' using errcode='42501'; end $$;
create trigger continuous_audit_immutable before update or delete on private.continuous_audit
 for each row execute function private.continuous_audit_immutable();

create function private.continuous_active(uid uuid,cid uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from private.continuous_owner_consents c where c.owner_id=uid and c.consent_id=cid
  and c.approved_at is not null and c.revoked_at is null and c.expires_at>clock_timestamp()
  and not exists(select 1 from private.continuous_owner_exclusions x where x.owner_id=uid));
$$;
create function private.continuous_owner(uid uuid,cid uuid) returns void language plpgsql security definer set search_path='' as $$
begin
 perform private.require_worker();
 perform 1 from private.continuous_owner_consents where owner_id=uid and consent_id=cid for share;
 if not private.continuous_active(uid,cid) then raise exception 'Processing consent inactive' using errcode='42501'; end if;
end $$;

create function private.continuous_request(rid uuid,terms text) returns jsonb language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); c private.continuous_owner_consents;
begin
 if uid is null or auth.jwt()->>'role' is distinct from 'authenticated' or rid is null or terms is distinct from 'local-video-v1' then
  raise exception 'Authenticated owner consent and current terms required' using errcode='42501'; end if;
 if exists(select 1 from private.continuous_owner_exclusions where owner_id=uid) then raise exception 'Archived QA owner cannot opt in' using errcode='42501'; end if;
 perform pg_advisory_xact_lock(hashtextextended(uid::text,809605));
 select * into c from private.continuous_owner_consents where owner_id=uid for update;
 if c.request_id=rid then return to_jsonb(c); end if;
 if c.approved_at is not null and c.revoked_at is null and c.expires_at>clock_timestamp() then raise exception 'Revoke the existing consent before requesting another generation'; end if;
 insert into private.continuous_owner_consents(owner_id,consent_id,request_id,terms_version,requested_at)
 values(uid,gen_random_uuid(),rid,terms,clock_timestamp()) on conflict(owner_id) do update set
 consent_id=excluded.consent_id,request_id=excluded.request_id,terms_version=excluded.terms_version,
 requested_at=excluded.requested_at,approved_at=null,expires_at=null,revoked_at=null,approval_reason=null returning * into c;
 perform private.continuous_log('requested',uid,c.consent_id);
 return to_jsonb(c);
end $$;
create function public.request_processing_consent(request_id uuid,terms_version text) returns jsonb language sql security invoker set search_path='' as $$
 select private.continuous_request(request_id,terms_version);
$$;
create function private.continuous_approve(uid uuid,cid uuid,expiry timestamptz,why text) returns jsonb language plpgsql security definer set search_path='' as $$
declare c private.continuous_owner_consents;
begin
 perform private.require_worker();
 if expiry is null or expiry<=clock_timestamp() or expiry>clock_timestamp()+interval '7 days' or length(trim(coalesce(why,''))) not between 1 and 300 then raise exception 'Bounded approval and audit reason required'; end if;
 select * into c from private.continuous_owner_consents where owner_id=uid and consent_id=cid for update;
 if c.owner_id is null or c.approved_at is not null or c.revoked_at is not null or exists(select 1 from private.continuous_owner_exclusions where owner_id=uid) then
  raise exception 'A fresh owner request is required; approval cannot be reset' using errcode='42501'; end if;
 update private.continuous_owner_consents set approved_at=clock_timestamp(),expires_at=expiry,approval_reason=why where owner_id=uid returning * into c;
 perform private.continuous_log('approved',uid,cid,null,why);
 return to_jsonb(c);
end $$;
create function public.approve_processing_consent(owner uuid,consent uuid,expires_at timestamptz,reason text) returns jsonb language sql security invoker set search_path='' as $$
 select private.continuous_approve(owner,consent,expires_at,reason);
$$;
create function private.continuous_revoke(uid uuid,cid uuid,why text,operator boolean) returns boolean language plpgsql security definer set search_path='' as $$
begin
 if operator then perform private.require_worker();
 elsif auth.uid() is distinct from uid or auth.jwt()->>'role' is distinct from 'authenticated' then raise exception 'Own consent required' using errcode='42501'; end if;
 perform 1 from private.continuous_owner_consents where owner_id=uid and consent_id=cid for update;
 if not found then raise exception 'Consent generation not found' using errcode='42501'; end if;
 update private.continuous_owner_consents set revoked_at=coalesce(revoked_at,clock_timestamp()) where owner_id=uid;
 update private.scoped_worker_health set ai_ready=false,detail='Processing authorization revoked' where owner_id=uid;
 perform private.continuous_log('revoked',uid,cid,null,why);
 return true;
end $$;
create function public.revoke_processing_consent(consent uuid) returns boolean language sql security invoker set search_path='' as $$
 select private.continuous_revoke(auth.uid(),consent,'Owner revoked consent',false);
$$;
create function public.revoke_owner_processing(owner uuid,consent uuid,reason text) returns boolean language sql security invoker set search_path='' as $$
 select private.continuous_revoke(owner,consent,reason,true);
$$;
create function private.continuous_status(uid uuid,cid uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare c private.continuous_owner_consents;
begin
 perform private.require_worker();
 select * into c from private.continuous_owner_consents where owner_id=uid and consent_id=cid;
 return jsonb_build_object('authorized',private.continuous_active(uid,cid),'owner_id',uid,'consent_id',cid,'approved_at',c.approved_at,'expires_at',c.expires_at,'future_jobs_only',true);
end $$;
create function public.worker_consent_status(owner uuid,consent uuid) returns jsonb language sql security invoker set search_path='' as $$ select private.continuous_status(owner,consent); $$;
create function private.continuous_read() returns jsonb language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'Sign in required' using errcode='42501'; end if;
 return (select to_jsonb(c) from private.continuous_owner_consents c where owner_id=auth.uid());
end $$;
create function public.processing_consent() returns jsonb language sql security invoker set search_path='' as $$ select private.continuous_read(); $$;

-- Capture immutable input identity only at INSERT. No UPDATE/backfill/re-consent
-- path can grant eligibility to an existing job or an old upload/project.
create function private.continuous_identity(jid uuid) returns jsonb language sql volatile security definer set search_path='' as $$
 select jsonb_build_object('owner_id',p.owner_id,'project_id',p.id,'id',v.id,'source_path',v.source_path,
 'byte_size',v.byte_size,'mime_type',v.mime_type,'instructions',p.instructions,
 'edit',case when j.kind='render' then j.payload->'edit' else null end,
 'revision',case when j.kind='render' then j.payload->'revision' else null end)
 from public.processing_jobs j join public.projects p on p.id=j.project_id join public.videos v on v.project_id=p.id where j.id=jid;
$$;
create function private.continuous_bind() returns trigger language plpgsql security definer set search_path='' as $$
declare c private.continuous_owner_consents; p public.projects;
begin
 select * into p from public.projects where id=new.project_id;
 select * into c from private.continuous_owner_consents where owner_id=p.owner_id for share;
 if c.owner_id is not null and private.continuous_active(c.owner_id,c.consent_id)
  and new.created_at>=c.approved_at and p.created_at>=c.approved_at and new.kind in ('analysis','render')
  and not exists(select 1 from private.continuous_job_exclusions where job_id=new.id) then
  insert into private.continuous_job_bindings(job_id,owner_id,consent_id,identity) values(new.id,p.owner_id,c.consent_id,private.continuous_identity(new.id));
  perform private.continuous_log('job_bound',p.owner_id,c.consent_id,new.id);
 end if;
 return new;
end $$;
create trigger continuous_bind after insert on public.processing_jobs for each row execute function private.continuous_bind();

create function private.continuous_job(uid uuid,cid uuid,jid uuid,tok uuid) returns void language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; b private.continuous_job_bindings;
begin
 perform private.continuous_owner(uid,cid);
 select * into b from private.continuous_job_bindings where job_id=jid;
 select * into j from public.processing_jobs where id=jid for update;
 if b.owner_id is distinct from uid or b.consent_id is distinct from cid or tok is null
  or j.lease_token is distinct from tok or j.lease_until is null or j.lease_until<=clock_timestamp()
  or j.status in ('completed','failed','cancelled') or b.identity is distinct from private.continuous_identity(jid)
  or exists(select 1 from private.continuous_job_exclusions where job_id=jid)
  or not exists(select 1 from private.continuous_job_leases where job_id=jid and token=tok and owner_id=uid and consent_id=cid)
 then raise exception 'Consent-bound lease unavailable' using errcode='42501'; end if;
end $$;
create function public.worker_authorize_optin(owner uuid,consent uuid,jid uuid,token uuid) returns boolean language plpgsql security definer set search_path='' as $$
begin perform private.continuous_job(owner,consent,jid,token); return true; end $$;

-- Trigger also rejects legacy claim/tick/finish attempts on a consented owner.
-- Revocation takes the owner row FOR UPDATE; writes hold FOR SHARE until commit.
create function private.continuous_guard_job() returns trigger language plpgsql security definer set search_path='' as $$
declare uid uuid; b private.continuous_job_bindings;
begin
 select owner_id into uid from public.projects where id=new.project_id;
 if new.lease_token is null then
  if ((new.status is distinct from old.status and new.status in ('preparing','analyzing','generating_highlights','rendering','completed'))
      or new.attempts>old.attempts or (new.lease_until is not null and new.lease_until is distinct from old.lease_until))
   and (exists(select 1 from private.continuous_owner_consents where owner_id=uid)
     or exists(select 1 from private.continuous_owner_exclusions where owner_id=uid)
     or exists(select 1 from private.continuous_job_exclusions where job_id=new.id)) then
   raise exception 'Processing transition requires a consent-bound lease' using errcode='42501'; end if;
  return new;
 end if;
 if new.id='9c5c8869-ec2e-4a3e-927d-697615bb58a3' or exists(select 1 from private.continuous_job_exclusions where job_id=new.id) then
  if new.lease_token is distinct from old.lease_token or new.lease_until is distinct from old.lease_until or new.attempts<>old.attempts or new.status<>old.status then
   raise exception 'Job explicitly excluded from processing' using errcode='42501'; end if;
 end if;
 if exists(select 1 from private.continuous_owner_exclusions where owner_id=uid) and
  (new.lease_token is distinct from old.lease_token or new.lease_until is distinct from old.lease_until or new.status<>old.status) then
  raise exception 'Archived QA owner cannot resume processing' using errcode='42501'; end if;
 if not exists(select 1 from private.continuous_owner_consents where owner_id=uid) then return new; end if;
 if new.lease_token is distinct from old.lease_token or new.lease_until is distinct from old.lease_until or new.status<>old.status or new.progress<>old.progress or new.payload is distinct from old.payload then
  select * into b from private.continuous_job_bindings where job_id=new.id;
  if b.owner_id is distinct from uid or b.identity is distinct from private.continuous_identity(new.id)
   or not exists(select 1 from private.continuous_job_leases where job_id=new.id and token=new.lease_token and owner_id=uid and consent_id=b.consent_id) then
   raise exception 'Legacy or unbound job cannot obtain a continuous lease' using errcode='42501'; end if;
  perform private.continuous_owner(uid,b.consent_id);
 end if;
 return new;
end $$;
create trigger continuous_guard_job before update on public.processing_jobs for each row execute function private.continuous_guard_job();

create function private.continuous_claim(uid uuid,cid uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare j public.processing_jobs; tok uuid; ident jsonb;
begin
 perform private.continuous_owner(uid,cid);
 perform pg_advisory_xact_lock(809604);
 if exists(select 1 from public.processing_jobs where lease_until>clock_timestamp() and status not in ('completed','failed','cancelled')) then return null; end if;
 select jobs.* into j from public.processing_jobs jobs
 join private.continuous_job_bindings b on b.job_id=jobs.id and b.owner_id=uid and b.consent_id=cid
 join public.projects p on p.id=jobs.project_id and p.owner_id=uid and p.deleted_at is null
 join pgmq.q_noetharaclipz q on q.msg_id=jobs.message_id and (q.message->>'job_id')::uuid=jobs.id
 where jobs.kind in ('analysis','render') and jobs.status not in ('completed','failed','cancelled')
 and (jobs.lease_until is null or jobs.lease_until<clock_timestamp()) and q.vt<=clock_timestamp()
 and not exists(select 1 from private.continuous_job_exclusions x where x.job_id=jobs.id)
 and b.identity=private.continuous_identity(jobs.id)
 order by jobs.created_at for update of jobs skip locked limit 1;
 if j.id is null then return null; end if;
 if j.cancel_requested or j.attempts>=3 then
  update public.processing_jobs set status=case when j.cancel_requested then 'cancelled' else 'failed' end,
   stage=case when j.cancel_requested then 'Cancelled' else 'Retry budget exhausted' end,
   lease_token=null,lease_until=null,updated_at=clock_timestamp() where id=j.id;
  perform pgmq.archive('noetharaclipz',j.message_id);
  perform private.continuous_log('job_held_or_cancelled',uid,cid,j.id,'Cancellation or retry limit');
  return null;
 end if;
 tok:=gen_random_uuid();
 insert into private.continuous_job_leases(job_id,owner_id,consent_id,token) values(j.id,uid,cid,tok)
 on conflict(job_id) do update set owner_id=excluded.owner_id,consent_id=excluded.consent_id,token=excluded.token,claimed_at=clock_timestamp();
 perform pgmq.set_vt('noetharaclipz',j.message_id,120);
 update public.processing_jobs set lease_token=tok,lease_until=clock_timestamp()+interval '120 seconds',attempts=attempts+1,updated_at=clock_timestamp() where id=j.id returning * into j;
 ident:=private.continuous_identity(j.id);
 perform private.continuous_log('claimed',uid,cid,j.id);
 return to_jsonb(j)||jsonb_build_object('owner_id',uid,'consent_id',cid,'source_identity',ident);
end $$;
create function public.worker_claim_optin(owner uuid,consent uuid) returns jsonb language sql security invoker set search_path='' as $$ select private.continuous_claim(owner,consent); $$;
create function public.worker_tick_optin(owner uuid,consent uuid,jid uuid,token uuid,state text,pct integer,detail text,error_message text default null) returns boolean language plpgsql security definer set search_path='' as $$
begin
 perform private.continuous_job(owner,consent,jid,token);
 return private.worker_tick(jid,token,state,pct,detail,error_message);
end $$;
create function private.continuous_metadata(uid uuid,jid uuid,m jsonb) returns void language plpgsql security definer set search_path='' as $$
declare prefix text;
begin
 select uid::text||'/'||project_id::text||'/' into prefix from public.processing_jobs where id=jid;
 if m is null or m->>'playback_path' is distinct from prefix||'playback.mp4'
  or m->>'thumbnail_path' is distinct from prefix||'thumbnail.jpg'
  or coalesce(m->>'source_hash','') !~ '^[0-9a-f]{64}$' then raise exception 'Source checkpoint paths/hash outside authorized project'; end if;
end $$;
create function public.worker_finish_analysis_optin(owner uuid,consent uuid,jid uuid,token uuid,metadata jsonb,artifacts jsonb,highlights jsonb) returns void language plpgsql security definer set search_path='' as $$
begin
 perform private.continuous_job(owner,consent,jid,token);
 perform private.continuous_metadata(owner,jid,metadata);
 if artifacts->>'provider' is distinct from 'local-smolvlm2' then raise exception 'Local provider required'; end if;
 perform private.worker_finish_analysis(jid,token,metadata,artifacts,highlights);
end $$;
create function public.worker_finish_render_optin(owner uuid,consent uuid,jid uuid,token uuid,path text,bytes bigint) returns void language plpgsql security definer set search_path='' as $$
begin perform private.continuous_job(owner,consent,jid,token); perform private.worker_finish_render(jid,token,path,bytes); end $$;
create function public.worker_checkpoint_optin(owner uuid,consent uuid,jid uuid,token uuid,metadata jsonb,artifacts jsonb) returns boolean language plpgsql security definer set search_path='' as $$
declare pid uuid;
begin
 perform private.continuous_job(owner,consent,jid,token);
 select project_id into pid from public.processing_jobs where id=jid and kind='analysis' and not cancel_requested;
 if pid is null then return private.worker_tick(jid,token,'preparing',0,'Cancellation acknowledged'); end if;
 if metadata is not null then
  perform private.continuous_metadata(owner,jid,metadata);
  update public.videos set duration=(metadata->>'duration')::double precision,width=(metadata->>'width')::int,height=(metadata->>'height')::int,
   fps=(metadata->>'fps')::double precision,has_audio=(metadata->>'has_audio')::boolean,source_hash=metadata->>'source_hash',
   playback_path=metadata->>'playback_path',thumbnail_path=metadata->>'thumbnail_path' where project_id=pid;
 end if;
 if artifacts is not null then
  if artifacts->>'provider' is distinct from 'local-smolvlm2' or artifacts->>'model' is distinct from 'HuggingFaceTB/SmolVLM2-500M-Video-Instruct@7b375e1b73b11138ff12fe22c8f2822d8fe03467' then raise exception 'Local model provenance required'; end if;
  insert into public.analysis_artifacts(project_id,transcript,scenes,audio_events,waveform,frame_paths,provider,model,summary,warnings)
  values(pid,artifacts->'transcript',artifacts->'scenes',artifacts->'audio_events',artifacts->'waveform',artifacts->'frame_paths',artifacts->>'provider',artifacts->>'model',artifacts->>'summary',coalesce(artifacts->'warnings','[]'))
  on conflict(project_id) do update set transcript=excluded.transcript,scenes=excluded.scenes,audio_events=excluded.audio_events,waveform=excluded.waveform,frame_paths=excluded.frame_paths,provider=excluded.provider,model=excluded.model,summary=excluded.summary,warnings=excluded.warnings,updated_at=clock_timestamp();
 end if;
 return true;
end $$;

-- Visible worker result writes are also guarded if an old worker calls its v1
-- finish RPC. Normal user editing/clearing stale outputs and cancellation remain.
create function private.continuous_guard_result() returns trigger language plpgsql security definer set search_path='' as $$
declare pid uuid; uid uuid; l private.continuous_job_leases; j public.processing_jobs;
begin
 pid:=new.project_id;
 if tg_table_name='videos' then
  if (new.source_path,new.byte_size,new.id,new.project_id,new.mime_type) is distinct from (old.source_path,old.byte_size,old.id,old.project_id,old.mime_type)
    and exists(select 1 from private.continuous_owner_consents c join public.projects p on p.owner_id=c.owner_id where p.id=pid) then
   raise exception 'Consented source identity is immutable' using errcode='42501'; end if;
  if (new.duration,new.playback_path,new.thumbnail_path,new.source_hash,new.width,new.height,new.fps,new.has_audio) is not distinct from (old.duration,old.playback_path,old.thumbnail_path,old.source_hash,old.width,old.height,old.fps,old.has_audio) then return new; end if;
 elsif tg_table_name='clips' then
  if new.output_path is null or (new.output_path,new.output_bytes,new.rendered_revision) is not distinct from (old.output_path,old.output_bytes,old.rendered_revision) then return new; end if;
 elsif tg_table_name='conversation_messages' then
  if new.role<>'assistant' then return new; end if;
 end if;
 select owner_id into uid from public.projects where id=pid;
 if not exists(select 1 from private.continuous_owner_consents where owner_id=uid) then return new; end if;
 select leases.* into l from private.continuous_job_leases leases join public.processing_jobs jobs on jobs.id=leases.job_id
 where jobs.project_id=pid and jobs.status not in ('completed','failed','cancelled') and jobs.lease_token=leases.token
 and jobs.lease_until>clock_timestamp() and not jobs.cancel_requested order by leases.claimed_at desc limit 1;
 perform private.continuous_job(uid,l.consent_id,l.job_id,l.token);
 select * into j from public.processing_jobs where id=l.job_id;
 if tg_table_name='clips' then
  if j.kind<>'render' or new.id is distinct from j.clip_id then raise exception 'Render publication requires its exact clip lease'; end if;
 elsif j.kind<>'analysis' then raise exception 'Analysis publication requires an analysis lease'; end if;
 if tg_table_name='provider_usage' then
  if new.job_id is distinct from j.id or new.provider is distinct from 'local-smolvlm2' or new.estimated_cost<>0 then raise exception 'Local provenance required'; end if;
 end if;
 return new;
end $$;
create trigger continuous_guard_video before update on public.videos for each row execute function private.continuous_guard_result();
create trigger continuous_guard_artifact before insert or update on public.analysis_artifacts for each row execute function private.continuous_guard_result();
create trigger continuous_guard_highlight before insert or update on public.highlights for each row execute function private.continuous_guard_result();
create trigger continuous_guard_usage before insert or update on public.provider_usage for each row execute function private.continuous_guard_result();
create trigger continuous_guard_clip before update on public.clips for each row execute function private.continuous_guard_result();
create trigger continuous_guard_message before insert on public.conversation_messages for each row execute function private.continuous_guard_result();

create function private.continuous_exclude(jid uuid,why text) returns void language plpgsql security definer set search_path='' as $$
declare uid uuid; cid uuid;
begin
 perform private.require_worker();
 if length(trim(coalesce(why,''))) not between 1 and 300 then raise exception 'Exclusion audit reason required'; end if;
 select owner_id into uid from public.projects p join public.processing_jobs j on j.project_id=p.id where j.id=jid;
 select consent_id into cid from private.continuous_owner_consents where owner_id=uid for update;
 insert into private.continuous_job_exclusions(job_id,reason) values(jid,why) on conflict(job_id) do nothing;
 perform private.continuous_log('excluded',uid,cid,jid,why);
end $$;
create function public.exclude_processing_job(jid uuid,reason text) returns void language sql security invoker set search_path='' as $$ select private.continuous_exclude(jid,reason); $$;
-- Intentionally no release or backfill RPC. Re-consent never rebinds old jobs.

create function public.worker_heartbeat_optin(owner uuid,consent uuid,ai_ready boolean,detail text) returns boolean language plpgsql security definer set search_path='' as $$
declare allowed boolean;
begin
 perform private.require_worker();
 perform 1 from private.continuous_owner_consents where owner_id=owner and consent_id=consent for share;
 allowed:=private.continuous_active(owner,consent);
 perform private.worker_heartbeat_scoped(owner,ai_ready and allowed,case when allowed then detail else 'Processing authorization inactive' end);
 return allowed;
end $$;
create or replace function private.pipeline_health() returns jsonb language plpgsql security definer set search_path='' as $$
declare h record; c private.continuous_owner_consents; allowed boolean:=true;
begin
 if auth.uid() is null then raise exception 'Sign in required'; end if;
 select * into c from private.continuous_owner_consents where owner_id=auth.uid();
 if found then
  allowed:=private.continuous_active(c.owner_id,c.consent_id);
  select heartbeat_at,ai_ready,detail into h from private.scoped_worker_health where owner_id=auth.uid();
 else
  select heartbeat_at,ai_ready,detail into h from private.scoped_worker_health where owner_id=auth.uid() and heartbeat_at>clock_timestamp()-interval '90 seconds';
  if not found then select heartbeat_at,ai_ready,detail into h from private.worker_health where id=true; end if;
 end if;
 return jsonb_build_object('online',allowed and coalesce(h.heartbeat_at>clock_timestamp()-interval '90 seconds',false),
 'ai_ready',allowed and coalesce(h.ai_ready and h.heartbeat_at>clock_timestamp()-interval '90 seconds',false),
 'detail',case when not allowed then 'Processing authorization inactive' else h.detail end,'max_bytes',45000000,'max_seconds',300);
end $$;
create function public.worker_continuous_protocol() returns jsonb language plpgsql security definer set search_path='' as $$
begin
 perform private.require_worker();
 return '{"version":2,"contract":"future-jobs-only-v1","future_jobs_only":true,"revocable":true,"job_exclusions":true,"audit":true,"global_claim":false,"provider":"local-smolvlm2"}'::jsonb;
end $$;

-- No global consumer, including an accidentally configured legacy service worker.
revoke execute on function public.worker_claim(),private.worker_claim() from service_role;
do $$ declare f record; begin
 for f in select p.oid::regprocedure as signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where (n.nspname='private' and p.proname in ('continuous_log','continuous_audit_immutable','continuous_active','continuous_owner','continuous_request','continuous_approve','continuous_revoke','continuous_status','continuous_read','continuous_identity','continuous_bind','continuous_job','continuous_guard_job','continuous_claim','continuous_metadata','continuous_guard_result','continuous_exclude')) or
 (n.nspname='public' and p.proname in ('request_processing_consent','approve_processing_consent','revoke_processing_consent','revoke_owner_processing','worker_consent_status','processing_consent','worker_authorize_optin','worker_claim_optin','worker_tick_optin','worker_finish_analysis_optin','worker_finish_render_optin','worker_checkpoint_optin','exclude_processing_job','worker_heartbeat_optin','worker_continuous_protocol')) loop
  execute format('revoke all on function %s from public,anon,authenticated,service_role',f.signature);
 end loop;
 for f in select p.oid::regprocedure as signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where (n.nspname='private' and p.proname in ('continuous_request','continuous_read','continuous_revoke')) or
 (n.nspname='public' and p.proname in ('request_processing_consent','processing_consent','revoke_processing_consent')) loop
  execute format('grant execute on function %s to authenticated',f.signature);
 end loop;
 for f in select p.oid::regprocedure as signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where (n.nspname='private' and p.proname in ('continuous_approve','continuous_revoke','continuous_status','continuous_claim','continuous_exclude')) or
 (n.nspname='public' and p.proname in ('approve_processing_consent','revoke_owner_processing','worker_consent_status','worker_authorize_optin','worker_claim_optin','worker_tick_optin','worker_finish_analysis_optin','worker_finish_render_optin','worker_checkpoint_optin','exclude_processing_job','worker_heartbeat_optin','worker_continuous_protocol')) loop
  execute format('grant execute on function %s to service_role',f.signature);
 end loop;
end $$;
