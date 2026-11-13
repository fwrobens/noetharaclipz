-- PROPOSAL ONLY. Do not copy into supabase/migrations/ by hand (see AGENTS.md).
-- Apply through Lovable after separate approval. Nothing in the worker depends on it:
-- worker_log_model_runs is called best-effort and a missing function is ignored.
--
-- model_runs records which model handled each refinement task, per attempt:
-- task, provider, model_id, role, status, attempt, latency and token counts, and a
-- short error class. It never stores API keys, prompts, transcript text or responses.
-- Owners can SELECT rows for their own projects; only the service-role worker can
-- insert (through the RPC below); nobody but the service role can update or delete.

create table public.model_runs (
 id uuid primary key default gen_random_uuid(),
 job_id uuid not null references public.processing_jobs(id) on delete cascade,
 project_id uuid not null references public.projects(id) on delete cascade,
 task text not null check (task in ('transcription','video_analysis','visual_context','highlight_reasoning')),
 provider text not null check (provider in ('local','nvidia','anymodel')),
 model_id text not null check (length(model_id) between 1 and 200 and model_id ~ '^[A-Za-z0-9._:@/+-]+$'),
 role text not null check (role in ('primary','fallback','local')),
 status text not null check (status in ('success','error','invalid','skipped')),
 attempt integer not null check (attempt between 0 and 10),
 latency_ms integer not null default 0 check (latency_ms between 0 and 3600000),
 input_tokens integer check (input_tokens is null or input_tokens >= 0),
 output_tokens integer check (output_tokens is null or output_tokens >= 0),
 error_class text check (error_class is null or error_class in (
  'timeout','rate_limited','server_error','client_error','transport_error','invalid_json',
  'schema_invalid','bounds_invalid','ownership_violation','text_only_violation',
  'no_credential','budget_exhausted','unexpected_error')),
 error_message text check (error_message is null or length(error_message) <= 160),
 created_at timestamptz not null default now(),
 -- Local tasks have no hosted fallback; hosted tasks never run on the local provider.
 check ((provider = 'local') = (role = 'local')),
 check ((role = 'local') = (task in ('transcription','video_analysis')))
);
create index model_runs_project_recent on public.model_runs(project_id, created_at desc);
create index model_runs_job on public.model_runs(job_id);

alter table public.model_runs enable row level security;
revoke all on table public.model_runs from public, anon, authenticated;
grant select on table public.model_runs to authenticated;
grant select, insert on table public.model_runs to service_role;
create policy owner_read on public.model_runs for select to authenticated
 using (exists (select 1 from public.projects p where p.id = model_runs.project_id and p.owner_id = (select auth.uid())));
-- No insert/update/delete policies for authenticated: those operations are denied.

-- Service-role logging RPC. The job id and lease token are verified; project ownership
-- is derived from the job row, so the worker (or a model) can never attribute runs to
-- another project or owner.
create function public.worker_log_model_runs(jid uuid, token uuid, runs jsonb)
returns integer language plpgsql security definer set search_path = '' as $$
declare j public.processing_jobs; r jsonb; n integer := 0;
begin
 perform private.require_worker();
 select * into j from public.processing_jobs where id = jid;
 if j.id is null or j.kind <> 'analysis' or j.status in ('completed','failed','cancelled')
    or token is null or j.lease_token is distinct from token
    or j.lease_until is null or j.lease_until < now() then
  raise exception 'Invalid analysis lease';
 end if;
 if jsonb_typeof(runs) <> 'array' or jsonb_array_length(runs) > 40 then
  raise exception 'Invalid model run batch';
 end if;
 for r in select * from jsonb_array_elements(runs) loop
  if jsonb_typeof(r) <> 'object' or exists (
   select 1 from jsonb_object_keys(r) k where k not in (
    'task','provider','model_id','role','status','attempt','latency_ms',
    'input_tokens','output_tokens','error_class','error_message')) then
   raise exception 'Unexpected model run field';
  end if;
  insert into public.model_runs(job_id, project_id, task, provider, model_id, role, status, attempt,
   latency_ms, input_tokens, output_tokens, error_class, error_message)
  values (j.id, j.project_id, r->>'task', r->>'provider', r->>'model_id', r->>'role', r->>'status',
   (r->>'attempt')::int, coalesce((r->>'latency_ms')::int, 0), (r->>'input_tokens')::int,
   (r->>'output_tokens')::int, r->>'error_class', left(r->>'error_message', 160));
  n := n + 1;
 end loop;
 return n;
end $$;
revoke all on function public.worker_log_model_runs(uuid, uuid, jsonb) from public, anon, authenticated;
grant execute on function public.worker_log_model_runs(uuid, uuid, jsonb) to service_role;
