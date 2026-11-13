-- Local metadata fixtures only; not video/model acceptance and never hosted.
create function public.nc_assert(ok boolean,msg text) returns void language plpgsql as $$
begin if ok is distinct from true then raise exception 'FAIL: %',msg; end if; end $$;
create function public.nc_source(uid uuid,pid uuid,jid uuid) returns void language plpgsql as $$
begin
 insert into public.projects(id,owner_id,request_id,title,instructions,created_at) values(pid,uid,gen_random_uuid(),'Local consent fixture','No real AI inference',clock_timestamp());
 insert into public.videos(project_id,source_path,filename,mime_type,byte_size) values(pid,uid::text||'/'||pid::text||'/source.mp4','fixture.mp4','video/mp4',123);
 insert into public.processing_jobs(id,project_id,kind,dedupe_key,created_at) values(jid,pid,'analysis',jid::text,clock_timestamp());
 update public.processing_jobs set message_id=(select * from pgmq.send('noetharaclipz',jsonb_build_object('job_id',jid))) where id=jid;
end $$;
insert into auth.users(id,email) values ('10000000-0000-0000-0000-000000000001','a@fixture.invalid'),('10000000-0000-0000-0000-000000000002','b@fixture.invalid');
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','9c5c8869-ec2e-4a3e-927d-697615bb58a3');
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000002','30000000-0000-0000-0000-000000000002');
create table public.nc_original as select to_jsonb(j) as row from public.processing_jobs j where id='9c5c8869-ec2e-4a3e-927d-697615bb58a3';
select public.nc_assert(not has_function_privilege('anon','public.worker_claim_optin(uuid,uuid)','execute'),'anonymous cannot claim');
select public.nc_assert(not has_function_privilege('authenticated','public.worker_claim_optin(uuid,uuid)','execute'),'browser cannot claim');
select public.nc_assert(not has_function_privilege('service_role','public.worker_claim()','execute'),'global claim disabled on server');
select public.nc_assert((select bool_and(relrowsecurity) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='private' and c.relkind='r' and c.relname like 'continuous_%'),'RLS on private consent tables');
set role authenticated;
select set_config('request.jwt.claims','{"role":"authenticated","sub":"10000000-0000-0000-0000-000000000001"}',false);
select public.request_processing_consent('40000000-0000-0000-0000-000000000001','local-video-v1');
select public.nc_assert((public.processing_consent()->>'approved_at') is null,'owner request alone is not operator approval');
reset role;
select set_config('request.jwt.claims','{"role":"service_role"}',false);
select public.approve_processing_consent('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'),clock_timestamp()+interval '1 hour','Local SQL regression only');
select public.nc_assert(public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001')) is null,'approval never releases old jobs');
do $$ begin
 begin perform public.worker_claim_scoped('10000000-0000-0000-0000-000000000001'); raise exception 'Legacy claim released a protected or unbound old job'; exception when insufficient_privilege then null; end;
end $$;
select public.nc_source('10000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000003','30000000-0000-0000-0000-000000000003');
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000004','30000000-0000-0000-0000-000000000004');
select public.nc_assert((select count(*)=1 from private.continuous_job_bindings),'only new approved-owner job is bound');
select public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'));
select public.nc_assert((select attempts=1 from public.processing_jobs where id='30000000-0000-0000-0000-000000000004'),'new job actually claimed');
select public.nc_assert(public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001')) is null,'one active lease');
select public.worker_tick_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'),'30000000-0000-0000-0000-000000000004',(select lease_token from public.processing_jobs where id='30000000-0000-0000-0000-000000000004'),'analyzing',50,'Local fixture');
-- Expire only the local fixture lease, allowing an actual PGMQ recovery claim.
alter table public.processing_jobs disable trigger continuous_guard_job;
update public.processing_jobs set lease_until=clock_timestamp()-interval '1 second' where id='30000000-0000-0000-0000-000000000004';
alter table public.processing_jobs enable trigger continuous_guard_job;
select pgmq.set_vt('noetharaclipz',(select message_id from public.processing_jobs where id='30000000-0000-0000-0000-000000000004'),0);
create table public.nc_old_token as select lease_token from public.processing_jobs where id='30000000-0000-0000-0000-000000000004';
select public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'));
select public.nc_assert((select attempts=2 from public.processing_jobs where id='30000000-0000-0000-0000-000000000004'),'recovery increments attempt');
do $$ begin
 begin perform public.worker_tick_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'),'30000000-0000-0000-0000-000000000004',(select lease_token from public.nc_old_token),'analyzing',1,'Stale fixture'); raise exception 'Stale token accepted';
 exception when insufficient_privilege then null; end;
end $$;
-- Revocation takes effect for claims, active ticks, visible checkpoints and health.
create table public.nc_old_consent as select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001';
grant select on public.nc_old_consent to authenticated;
set role authenticated;
select set_config('request.jwt.claims','{"role":"authenticated","sub":"10000000-0000-0000-0000-000000000001"}',false);
select public.revoke_processing_consent((public.processing_consent()->>'consent_id')::uuid);
select public.nc_assert((public.pipeline_health()->>'ai_ready')::boolean=false,'revoked owner cannot appear ready');
reset role;
select set_config('request.jwt.claims','{"role":"service_role"}',false);
do $$ declare cid uuid:=(select consent_id from public.nc_old_consent); tok uuid:=(select lease_token from public.processing_jobs where id='30000000-0000-0000-0000-000000000004'); begin
 begin perform public.worker_authorize_optin('10000000-0000-0000-0000-000000000001',cid,'30000000-0000-0000-0000-000000000004',tok); raise exception 'Revoked lease authorized'; exception when insufficient_privilege then null; end;
 begin perform public.worker_tick_optin('10000000-0000-0000-0000-000000000001',cid,'30000000-0000-0000-0000-000000000004',tok,'completed',100,'Must fail'); raise exception 'Revoked completion accepted'; exception when insufficient_privilege then null; end;
 begin perform public.worker_checkpoint_optin('10000000-0000-0000-0000-000000000001',cid,'30000000-0000-0000-0000-000000000004',tok,'{}',null); raise exception 'Revoked checkpoint accepted'; exception when insufficient_privilege then null; end;
 begin update public.videos set duration=4 where project_id='20000000-0000-0000-0000-000000000004'; raise exception 'Legacy raw write bypassed revocation'; exception when insufficient_privilege then null; end;
 begin update public.processing_jobs set lease_token=null,status='completed' where id='30000000-0000-0000-0000-000000000004'; raise exception 'Null-token publication bypassed consent'; exception when insufficient_privilege then null; end;
end $$;
set role authenticated;
select set_config('request.jwt.claims','{"role":"authenticated","sub":"10000000-0000-0000-0000-000000000002"}',false);
do $$ begin
 begin perform public.revoke_processing_consent((select consent_id from public.nc_old_consent)); raise exception 'Cross-owner revoke accepted'; exception when insufficient_privilege then null; end;
end $$;
select public.nc_assert(public.processing_consent() is null,'other owner cannot read consent');
reset role;
select set_config('request.jwt.claims','{"role":"authenticated","sub":"10000000-0000-0000-0000-000000000001"}',false);
set role authenticated;
select public.request_processing_consent('40000000-0000-0000-0000-000000000002','local-video-v1');
reset role;
select set_config('request.jwt.claims','{"role":"service_role"}',false);
select public.approve_processing_consent('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'),clock_timestamp()+interval '1 hour','Second local consent generation');
select public.nc_assert(not exists(select 1 from private.continuous_job_bindings b join private.continuous_owner_consents c using(owner_id,consent_id)),'re-consent cannot rebind old queued or active jobs');
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000005','30000000-0000-0000-0000-000000000005');
select public.exclude_processing_job('30000000-0000-0000-0000-000000000005','Local exclusion regression');
select public.nc_assert(exists(select 1 from private.continuous_job_exclusions where job_id='30000000-0000-0000-0000-000000000005'),'exclusion recorded');
-- Only local metadata fixtures: clear the revoked lease to avoid waiting 120 s.
update public.processing_jobs set lease_token=null,lease_until=null where id='30000000-0000-0000-0000-000000000004';
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000006','30000000-0000-0000-0000-000000000006');
update public.projects set instructions='Changed source revision' where id='20000000-0000-0000-0000-000000000006';
select public.nc_assert(public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001')) is null,'excluded or changed revisions cannot be claimed');
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000007','30000000-0000-0000-0000-000000000007');
select public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'));
select public.worker_finish_analysis_optin('10000000-0000-0000-0000-000000000001',
 (select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'),
 '30000000-0000-0000-0000-000000000007',(select lease_token from public.processing_jobs where id='30000000-0000-0000-0000-000000000007'),
 '{"duration":4,"width":160,"height":90,"fps":10,"has_audio":false,"source_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","playback_path":"10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000007/playback.mp4","thumbnail_path":"10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000007/thumbnail.jpg"}',
 '{"provider":"local-smolvlm2","model":"HuggingFaceTB/SmolVLM2-500M-Video-Instruct@7b375e1b73b11138ff12fe22c8f2822d8fe03467","transcript":[],"scenes":[],"audio_events":[],"waveform":[],"frame_paths":[],"summary":"Synthetic SQL fixture; not inference","local_usage":{"input_tokens":1,"output_tokens":1}}',
 '[{"start":1,"end":3,"title":"SQL fixture only","category":"Other","score":1,"explanation":"Not model inference","visual_evidence":"No actual footage"}]');
select public.nc_assert((select status='completed' from public.processing_jobs where id='30000000-0000-0000-0000-000000000007'),'authorized analysis finish succeeds');
insert into public.clips(id,project_id,highlight_id,edit) select '70000000-0000-0000-0000-000000000007',project_id,id,'{"start":1,"end":3}' from public.highlights where project_id='20000000-0000-0000-0000-000000000007';
select private.enqueue('20000000-0000-0000-0000-000000000007','render','fixture-render-v1','{"revision":1,"edit":{"start":1,"end":3}}','70000000-0000-0000-0000-000000000007');
select public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'));
insert into storage.objects(bucket_id,name,metadata) select 'rendered-clips','10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000007/'||id::text||'.mp4','{"size":4}' from public.processing_jobs where kind='render';
select public.worker_finish_render_optin('10000000-0000-0000-0000-000000000001',
 (select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'),
 j.id,j.lease_token,'10000000-0000-0000-0000-000000000001/20000000-0000-0000-0000-000000000007/'||j.id::text||'.mp4',4)
 from public.processing_jobs j where kind='render';
select public.nc_assert((select output_bytes=4 from public.clips where id='70000000-0000-0000-0000-000000000007'),'authorized render publication succeeds');
select public.nc_source('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000008','30000000-0000-0000-0000-000000000008');
update public.processing_jobs set cancel_requested=true where id='30000000-0000-0000-0000-000000000008';
select public.worker_claim_optin('10000000-0000-0000-0000-000000000001',(select consent_id from private.continuous_owner_consents where owner_id='10000000-0000-0000-0000-000000000001'));
select public.nc_assert((select status='cancelled' and attempts=0 from public.processing_jobs where id='30000000-0000-0000-0000-000000000008'),'queued cancellation acknowledged without processing');
do $$ begin
 begin update private.continuous_audit set reason='tamper'; raise exception 'Audit mutation accepted'; exception when insufficient_privilege then null; end;
end $$;
select public.nc_assert((select to_jsonb(j)=(select row from public.nc_original) from public.processing_jobs j where id='9c5c8869-ec2e-4a3e-927d-697615bb58a3'),'original whole row unchanged');
select public.nc_assert((select count(*)>=7 from private.continuous_audit),'consent/claim/exclusion audit retained');
select public.nc_assert((select bool_and(p.prosecdef and p.proconfig @> array['search_path=""']) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='private' and p.proname like 'continuous_%'),'private definer/search path preserved');
select 'PASS: consent, future-only binding, exclusions, revocation, stale lease, ownership, audit, global denial and whole-row preservation';
