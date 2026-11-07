import { Upload } from "tus-js-client";
import { supabase } from "./supabase/client";
import { must } from "./store";
export const MAX_UPLOAD = 45_000_000;
export function validateVideo(file: File) {
  if (!["video/mp4", "video/quicktime", "video/webm"].includes(file.type))
    throw new Error("Choose an MP4, MOV or WebM video.");
  if (!file.size || file.size > MAX_UPLOAD)
    throw new Error("The short-video workflow supports files up to 45 MB and five minutes.");
}
export async function uploadVideo(
  file: File,
  prompt: string,
  requestId: string,
  progress: (n: number) => void,
  signal: AbortSignal,
) {
  validateVideo(file);
  if (prompt.length > 4000) throw new Error("Keep instructions under 4,000 characters.");
  const reservation = must(
    await supabase.rpc("prepare_upload", {
      request_id: requestId,
      filename: file.name,
      mime_type: file.type,
      byte_size: file.size,
      instructions: prompt,
    }),
  ) as { project_id: string; video_id: string; path: string };
  if (signal.aborted) throw new Error("Upload cancelled");
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Sign in to upload.");
  await new Promise<void>((resolve, reject) => {
    const cleanup = () => signal.removeEventListener("abort", cancel);
    const upload = new Upload(file, {
      endpoint: "https://zxdnjnsghdnviflahvry.storage.supabase.co/storage/v1/upload/resumable",
      headers: { authorization: `Bearer ${session.access_token}` },
      metadata: {
        bucketName: "source-videos",
        objectName: reservation.path,
        contentType: file.type,
        cacheControl: "3600",
      },
      chunkSize: 6 * 1024 * 1024,
      uploadDataDuringCreation: true,
      removeFingerprintOnSuccess: true,
      retryDelays: [0, 1000, 3000, 5000],
      onProgress: (bytes, total) => progress(Math.round((100 * bytes) / total)),
      onError: (error) => {
        cleanup();
        reject(error);
      },
      onSuccess: () => {
        cleanup();
        resolve();
      },
    });
    const cancel = () => {
      void upload.abort(true);
      cleanup();
      reject(new Error("Upload cancelled. Choose the file again to retry."));
    };
    signal.addEventListener("abort", cancel, { once: true });
    void upload
      .findPreviousUploads()
      .then((previous) => {
        if (signal.aborted) return;
        if (previous[0]) upload.resumeFromPreviousUpload(previous[0]);
        upload.start();
      })
      .catch((error) => {
        cleanup();
        reject(error);
      });
  });
  if (signal.aborted) throw new Error("Upload cancelled");
  must(await supabase.rpc("finalize_upload", { pid: reservation.project_id }));
  return reservation.project_id;
}
