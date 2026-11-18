-- Disposable-database regression for docs/model-runs-schema.sql.
-- Run with: node scripts/test_model_runs_sql.mjs (in-process PGlite; never contacts Supabase).
-- The fixture below is a minimal stand-in for the existing schema (roles, auth helpers,
-- private.require_worker, projects and processing_jobs columns the proposal uses).

-- >>> fixture
create role anon; create role authenticated; create role service_role bypassrls;
create schema auth; grant usage on schema auth to anon, authenticated, service_role;
create function auth.jwt() returns jsonb language sql stable as $$select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb$$;
create function auth.uid() returns uuid language sql stable as $$select nullif(auth.jwt()->>'sub','')::uuid$$;
create schema private;
create function private.require_worker() returns void language plpgsql security invoker set search_path='' as $$
begin
 if coalesce(auth.jwt()->>'role','') <> 'service_role' then raise exception 'Worker authorization required'; end if;
end $$;
grant usage on schema public to anon, authenticated, service_role;
create table public.projects(id uuid primary key, owner_id uuid not null);
alter table public.projects enable row level security;
create policy owner_read on public.projects for select to authenticated using (owner_id=(select auth.uid()));
grant select on public.projects to authenticated; grant all on public.projects to service_role;
create table public.processing_jobs(id uuid primary key, project_id uuid not null references public.projects(id) on delete cascade,
 kind text not null, status text not null default 'analyzing', lease_token uuid, lease_until timestamptz);
grant all on public.processing_jobs to service_role;
insert into public.projects values
 ('a0000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001'),
 ('b0000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000002');
insert into public.processing_jobs values
 ('a1000000-0000-0000-0000-000000000001','a0000000-0000-0000-0000-000000000001','analysis','analyzing','c0000000-0000-0000-0000-000000000001',now()+interval '5 minutes'),
 ('b1000000-0000-0000-0000-000000000002','b0000000-0000-0000-0000-000000000002','analysis','analyzing','c0000000-0000-0000-0000-000000000002',now()+interval '5 minutes'),
 ('a2000000-0000-0000-0000-000000000003','a0000000-0000-0000-0000-000000000001','analysis','completed','c0000000-0000-0000-0000-000000000003',now()+interval '5 minutes'),
 ('a3000000-0000-0000-0000-000000000004','a0000000-0000-0000-0000-000000000001','analysis','analyzing','c0000000-0000-0000-0000-000000000004',now()-interval '1 minute');
create function public.nc_assert(ok boolean, label text) returns void language plpgsql as $$
begin if ok is not true then raise exception 'FAIL: %', label; end if; raise notice 'PASS: %', label; end $$;
create function public.nc_rejects(statement text, label text) returns void language plpgsql as $$
begin
 begin execute statement; exception when others then raise notice 'PASS: %', label; return; end;
 raise exception 'FAIL: % (statement succeeded)', label;
end $$;
grant execute on function public.nc_assert(boolean,text), public.nc_rejects(text,text) to anon, authenticated, service_role;
-- <<< fixture

-- >>> proposal (inserted by the runner from docs/model-runs-schema.sql)
-- <<< proposal

-- >>> assertions
select public.nc_assert((select relrowsecurity from pg_class where oid='public.model_runs'::regclass),'RLS enabled on model_runs');
select public.nc_assert(not has_function_privilege('authenticated','public.worker_log_model_runs(uuid,uuid,jsonb)','execute'),'browser cannot call logging RPC');
select public.nc_assert(not has_function_privilege('anon','public.worker_log_model_runs(uuid,uuid,jsonb)','execute'),'anon cannot call logging RPC');
select public.nc_assert(not has_table_privilege('authenticated','public.model_runs','insert'),'authenticated has no INSERT');
select public.nc_assert(not has_table_privilege('authenticated','public.model_runs','update'),'authenticated has no UPDATE');
select public.nc_assert(not has_table_privilege('authenticated','public.model_runs','delete'),'authenticated has no DELETE');
select public.nc_assert(not has_table_privilege('anon','public.model_runs','select'),'anon has no SELECT');
select public.nc_assert(not has_table_privilege('service_role','public.model_runs','insert'),'service role has no direct INSERT grant');
select public.nc_assert(not has_table_privilege('service_role','public.model_runs','update'),'service role has no UPDATE grant');

set role service_role;
select set_config('request.jwt.claims','{"role":"service_role"}',false);
select public.nc_assert(public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001',
 '[{"task":"transcription","provider":"local","model_id":"whisper-small","role":"local","status":"success","attempt":1,"latency_ms":900,"input_tokens":null,"output_tokens":null,"error_class":null,"error_message":null},
   {"task":"visual_context","provider":"nvidia","model_id":"z-ai/glm-5.3-flash","role":"primary","status":"error","attempt":1,"latency_ms":30000,"input_tokens":null,"output_tokens":null,"error_class":"timeout","error_message":"Request timed out"},
   {"task":"highlight_reasoning","provider":"anymodel","model_id":"am/nemotron-3.5-lightning-30b-a3b","role":"fallback","status":"success","attempt":1,"latency_ms":1200,"input_tokens":120,"output_tokens":40,"error_class":null,"error_message":null}]'::jsonb)=3,'service role logs three runs');
select public.nc_assert(public.worker_log_model_runs('b1000000-0000-0000-0000-000000000002','c0000000-0000-0000-0000-000000000002',
 ('[{"task":"highlight_reasoning","provider":"nvidia","model_id":"deepseek-ai/deepseek-v4.1-flash","role":"primary","status":"success","attempt":1,"latency_ms":800,"error_message":"'||repeat('x',400)||'"}]')::jsonb)=1,'second owner run logged');
select public.nc_assert((select max(length(error_message)) from public.model_runs)<=160,'error messages truncated to 160 chars');
select public.nc_assert((select bool_and(project_id='a0000000-0000-0000-0000-000000000001') from public.model_runs where job_id='a1000000-0000-0000-0000-000000000001'),'project derived from job, not caller');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000002','[]')$q$,'wrong lease token rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001',null,'[]')$q$,'missing lease token rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a2000000-0000-0000-0000-000000000003','c0000000-0000-0000-0000-000000000003','[]')$q$,'completed job rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a3000000-0000-0000-0000-000000000004','c0000000-0000-0000-0000-000000000004','[]')$q$,'expired lease rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','{"task":"x"}')$q$,'non-array batch rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001',null)$q$,'null batch rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"visual_context","provider":"nvidia","model_id":"m","role":"primary","status":"success","attempt":1,"project_id":"b0000000-0000-0000-0000-000000000002"}]')$q$,'project_id override rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"visual_context","provider":"nvidia","model_id":"m","role":"primary","status":"success","attempt":1,"api_key":"nvapi-x"}]')$q$,'api_key field rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"visual_context","provider":"nvidia","model_id":"m","role":"primary","status":"success","attempt":1,"prompt":"transcript text"}]')$q$,'prompt/transcript field rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"transcription","provider":"nvidia","model_id":"m","role":"fallback","status":"success","attempt":1}]')$q$,'hosted fallback for Whisper rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"visual_context","provider":"gemini","model_id":"m","role":"primary","status":"success","attempt":1}]')$q$,'unknown provider rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"visual_context","provider":"nvidia","model_id":"m","role":"primary","status":"error","attempt":1,"error_class":"Traceback: secret"}]')$q$,'free-form error_class rejected');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[{"task":"visual_context","provider":"nvidia","model_id":"bad model id; drop","role":"primary","status":"success","attempt":1}]')$q$,'malformed model id rejected');
reset role;

set role authenticated;
select set_config('request.jwt.claims','{"role":"authenticated","sub":"10000000-0000-0000-0000-000000000001"}',false);
select public.nc_assert((select count(*) from public.model_runs)=3,'owner A sees only own project runs');
select public.nc_rejects($q$insert into public.model_runs(job_id,project_id,task,provider,model_id,role,status,attempt) values('a1000000-0000-0000-0000-000000000001','a0000000-0000-0000-0000-000000000001','visual_context','nvidia','m','primary','success',1)$q$,'owner cannot insert');
select public.nc_rejects($q$update public.model_runs set status='success'$q$,'owner cannot update');
select public.nc_rejects($q$delete from public.model_runs$q$,'owner cannot delete');
select public.nc_rejects($q$select public.worker_log_model_runs('a1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','[]')$q$,'owner cannot call logging RPC');
select set_config('request.jwt.claims','{"role":"authenticated","sub":"20000000-0000-0000-0000-000000000002"}',false);
select public.nc_assert((select count(*) from public.model_runs)=1,'owner B sees only own project runs');
select set_config('request.jwt.claims','{"role":"authenticated","sub":"30000000-0000-0000-0000-000000000003"}',false);
select public.nc_assert((select count(*) from public.model_runs)=0,'stranger sees no runs');
reset role;
set role anon;
select public.nc_rejects($q$select count(*) from public.model_runs$q$,'anon cannot read');
reset role;
-- <<< assertions
