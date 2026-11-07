export const supabaseUrl =
  import.meta.env["VITE_SUPABASE_URL"] || "https://zxdnjnsghdnviflahvry.supabase.co";
export const publishableKey =
  import.meta.env["VITE_SUPABASE_PUBLISHABLE_KEY"] ||
  "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk";
if (supabaseUrl !== "https://zxdnjnsghdnviflahvry.supabase.co") {
  throw new Error("NoetharaClipz is configured for an unrelated Supabase project");
}
