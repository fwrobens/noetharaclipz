-- Run only in the intended project or local test database. Everything rolls back.
-- These transactional fixtures are NOT real AI output or an end-to-end acceptance test.
begin;
create temporary table nc_test (owner_id uuid,other_id uuid,pid uuid,hid uuid,cid uuid,jid uuid);
insert into nc_test values(gen_random_uuid(),gen_random_uuid(),null,gen_random_uuid(),null,null);
alter table nc_test add column old_token uuid;
grant all on nc_test to authenticated,service_role;
insert into auth.users(id,aud,role,email,raw_app_meta_data,raw_user_meta_data)
 select owner_id,'authenticated','authenticated','nc-sql-'||owner_id||'@example.com','{}'::jsonb,'{}'::jsonb from nc_test
 union all select other_id,'authenticated','authenticated','nc-sql-'||other_id||'@example.com','{}'::jsonb,'{}'::jsonb from nc_test;
select set_config('request.jwt.claims',jsonb_build_object('sub',owner_id,'role','authenticated')::text,true) from nc_test;
set local role authenticated;
update nc_test set pid=(public.prepare_upload(gen_random_uuid(),'fixture.mp4','video/mp4',1000,'Transactional boundary test')->>'project_id')::uuid;
do $$ begin
 if (select count(*) from public.projects where id=(select pid from nc_test))<>1 then raise exception 'Owner cannot read project'; end if;
 begin
  perform public.worker_claim();raise exception 'Worker RPC unexpectedly allowed';
 exception when insufficient_privilege then null;
 end;
 begin
  perform public.finalize_upload((select pid from nc_test));raise exception 'Missing object accepted';
 exception when raise_exception then if sqlerrm='Missing object accepted' then raise; end if;
 end;
end $$;
reset role;
update public.videos set duration=52 where project_id=(select pid from nc_test);
insert into public.highlights(id,project_id,start_time,end_time,title,category,score,explanation,evidence)
 select hid,pid,12,14,'Transactional fixture','Other',0,'Test only; rolled back','{"test":true}' from nc_test;
set local role authenticated;
update nc_test set cid=public.save_clip(hid,'{"version":1,"start":12,"end":14,"ratio":"9:16","crop_x":0.5,"crop_y":0.5,"volume":1,"captions":true,"caption_style":"Bold pop","caption_size":28,"caption_color":"#FFFFFF","font":"Instrument Sans","caption_overrides":{}}');
update nc_test set jid=public.export_clip(cid,1);
do $$ begin
 if (select public.export_clip(cid,1)<>jid from nc_test) then raise exception 'Duplicate render job'; end if;
 begin
  perform public.save_clip((select hid from nc_test),'{"start":-1,"end":14,"ratio":"9:16"}',1);raise exception 'Invalid edit accepted';
 exception when raise_exception then if sqlerrm='Invalid edit accepted' then raise; end if;
 end;
 perform public.cancel_job((select jid from nc_test));
 if (select status from public.processing_jobs where id=(select jid from nc_test))<>'cancelled' then raise exception 'Queued cancellation failed'; end if;
 perform public.retry_job((select jid from nc_test));
end $$;
select set_config('request.jwt.claims',jsonb_build_object('sub',other_id,'role','authenticated')::text,true) from nc_test;
do $$ begin
 if exists(select 1 from public.projects where id=(select pid from nc_test)) or exists(select 1 from public.clips where id=(select cid from nc_test)) or exists(select 1 from public.highlights where id=(select hid from nc_test)) then raise exception 'Cross-user data leak'; end if;
 begin
  perform public.export_clip((select cid from nc_test),1);raise exception 'Cross-user export allowed';
 exception when raise_exception then if sqlerrm='Cross-user export allowed' then raise; end if;
 end;
end $$;
reset role;
-- Temporarily hide other application messages; visibility changes roll back too.
select pgmq.set_vt('noetharaclipz',msg_id,3600) from pgmq.q_noetharaclipz where (message->>'job_id')::uuid<>(select jid from nc_test);
select set_config('request.jwt.claims','{"role":"service_role"}',true);
set local role service_role;
do $$ declare j jsonb;
begin
 j:=public.worker_claim();
 if j is null then raise exception 'No durable job claim'; end if;
 if public.worker_claim() is not null then raise exception 'Global worker concurrency limit failed'; end if;
 perform public.worker_tick((j->>'id')::uuid,(j->>'lease_token')::uuid,'rendering',20,'Testing lease');
 begin
  perform public.worker_finish_render((j->>'id')::uuid,(j->>'lease_token')::uuid,'missing.mp4',100);raise exception 'Missing output marked successful';
 exception when raise_exception then if sqlerrm='Missing output marked successful' then raise; end if;
 end;
 update nc_test set old_token=(j->>'lease_token')::uuid;
end $$;
reset role;
-- Administrator-only test setup: workers cannot directly access the pgmq schema.
update public.processing_jobs set lease_until=now()-interval '1 second' where id=(select jid from nc_test);
select pgmq.set_vt('noetharaclipz',message_id,0) from public.processing_jobs where id=(select jid from nc_test);
set local role service_role;
do $$ declare j jsonb;
begin
 j:=public.worker_claim();
 if j is null or (j->>'attempts')::int<>2 or (j->>'lease_token')::uuid=(select old_token from nc_test) then raise exception 'Interrupted job was not reclaimed with a fresh lease'; end if;
 begin
  perform public.worker_tick((j->>'id')::uuid,(select old_token from nc_test),'rendering',30,'Old worker');raise exception 'Stale worker token accepted';
 exception when raise_exception then if sqlerrm='Stale worker token accepted' then raise; end if;
 end;
 perform public.worker_tick((j->>'id')::uuid,(j->>'lease_token')::uuid,'failed',0,'Test stopped','Test transaction only');
 begin
  perform public.worker_tick((j->>'id')::uuid,(j->>'lease_token')::uuid,'rendering',20,'Stale heartbeat');raise exception 'Finished job resurrected';
 exception when raise_exception then if sqlerrm='Finished job resurrected' then raise; end if;
 end;
end $$;
reset role;
rollback;
select 'All transactional ownership, render, cancellation, lease and idempotency assertions passed' as result;
