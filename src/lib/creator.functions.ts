import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireCreatorAuth } from "./creator-auth";

export const loadCreator = createServerFn({ method: "POST" })
  .middleware([requireCreatorAuth])
  .handler(async ({ context }) => {
    const { supabase, userId } = context;
    const [profile, projects] = await Promise.all([
      supabase.from("profiles").select("*").eq("id", userId).maybeSingle(),
      supabase
        .from("projects")
        .select("*, videos(*), highlights(*), processing_jobs(id,status,progress,stage,error)")
        .eq("owner_id", userId)
        .order("created_at", { ascending: false })
        .limit(100),
    ]);
    if (profile.error) throw new Error(profile.error.message);
    if (projects.error) throw new Error(projects.error.message);
    return { profile: profile.data, projects: projects.data ?? [], userId };
  });

export const saveOnboarding = createServerFn({ method: "POST" })
  .middleware([requireCreatorAuth])
  .inputValidator(
    z.object({
      name: z.string().trim().min(1).max(80),
      platform: z.enum(["TikTok", "YouTube", "IG Reels"]),
      style: z.enum(["Bold pop", "Clean", "Karaoke"]),
    }),
  )
  .handler(async ({ data, context }) => {
    const { supabase, userId } = context;
    const previous = await supabase
      .from("profiles")
      .select("preferences")
      .eq("id", userId)
      .maybeSingle();
    if (previous.error) throw new Error(previous.error.message);
    const preferences = previous.data?.preferences;
    const base =
      preferences && typeof preferences === "object" && !Array.isArray(preferences)
        ? preferences
        : {};
    const profile = await supabase.from("profiles").upsert({
      id: userId,
      display_name: data.name,
      preferences: { ...base, platform: data.platform, onboarding_complete: true },
    });
    if (profile.error) throw new Error(profile.error.message);
    const previousBrand = await supabase
      .from("brand_settings")
      .select("settings")
      .eq("owner_id", userId)
      .maybeSingle();
    if (previousBrand.error) throw new Error(previousBrand.error.message);
    const settings = previousBrand.data?.settings;
    const brandBase =
      settings && typeof settings === "object" && !Array.isArray(settings) ? settings : {};
    const brand = await supabase.from("brand_settings").upsert({
      owner_id: userId,
      settings: {
        ...brandBase,
        caption_style: data.style === "Clean" ? "Minimal" : data.style,
        platform: data.platform,
      },
    });
    if (brand.error) throw new Error(brand.error.message);
    return { success: true };
  });

export const prepareVideo = createServerFn({ method: "POST" })
  .middleware([requireCreatorAuth])
  .inputValidator(
    z.object({
      requestId: z.string().uuid(),
      filename: z.string().min(1).max(255),
      mime: z.string().startsWith("video/"),
      bytes: z.number().int().positive(),
      instructions: z.string().max(2000),
    }),
  )
  .handler(async ({ data, context }) => {
    const { requireCreatorAdmission } = await import("./creator-admission.server");
    await requireCreatorAdmission(context.supabase, context.userId);
    const result = await context.supabase.rpc("prepare_upload", {
      request_id: data.requestId,
      filename: data.filename,
      mime_type: data.mime,
      byte_size: data.bytes,
      instructions: data.instructions,
    });
    if (result.error) throw new Error(result.error.message);
    return result.data;
  });

export const finalizeVideo = createServerFn({ method: "POST" })
  .middleware([requireCreatorAuth])
  .inputValidator(z.object({ projectId: z.string().uuid() }))
  .handler(async ({ data, context }) => {
    const { requireCreatorAdmission } = await import("./creator-admission.server");
    await requireCreatorAdmission(context.supabase, context.userId);
    const result = await context.supabase.rpc("finalize_upload", { pid: data.projectId });
    if (result.error) throw new Error(result.error.message);
    return result.data;
  });
