alter table public.profiles add constraint profile_preferences_size check(length(preferences::text)<=16000), add constraint avatar_url_size check(avatar_url is null or length(avatar_url)<=2048);
alter table public.brand_settings add constraint brand_settings_size check(length(settings::text)<=16000);
