create or replace function private.check_capacity(uid uuid, extra bigint) returns void language plpgsql security definer set search_path='' as $$
declare total bigint; personal bigint;
begin
 perform pg_advisory_xact_lock(809602);
 select coalesce(sum(v.byte_size*2),0) into total from public.videos v;
 select coalesce(sum(v.byte_size*2),0) into personal from public.videos v join public.projects p on p.id=v.project_id where p.owner_id=uid;
 total:=total+(select coalesce(sum(output_bytes),0) from public.clips)+(select coalesce(sum(reserved_bytes),0) from public.processing_jobs where status not in ('completed','failed','cancelled'));
 personal:=personal+(select coalesce(sum(c.output_bytes),0) from public.clips c join public.projects p on p.id=c.project_id where p.owner_id=uid)+(select coalesce(sum(j.reserved_bytes),0) from public.processing_jobs j join public.projects p on p.id=j.project_id where p.owner_id=uid and j.status not in ('completed','failed','cancelled'));
 total:=greatest(total,(select coalesce(sum((metadata->>'size')::bigint),0) from storage.objects where bucket_id in ('source-videos','rendered-clips','thumbnails','processing-artifacts','brand-assets')));
 personal:=greatest(personal,(select coalesce(sum((metadata->>'size')::bigint),0) from storage.objects where bucket_id in ('source-videos','rendered-clips','thumbnails','processing-artifacts','brand-assets') and (storage.foldername(name))[1]=uid::text));
 if total+extra>800000000 or personal+extra>200000000 then raise exception 'Storage allowance reached. Remove unused projects or exports before uploading.'; end if;
end $$;
