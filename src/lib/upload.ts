import { Upload } from "tus-js-client";
import { supabase } from "./supabase/client";
import { must } from "./store";
import { betaEnabled } from "./beta";
import { requireBetaAdmission } from "./processing-consent";
export const MAX_UPLOAD = 45_000_000;
type Reservation = { project_id: string; video_id: string; path: string };
export type UploadBackend = {
  prepare: (input: {
    requestId: string;
    filename: string;
    mime: string;
    bytes: number;
    instructions: string;
  }) => Promise<unknown>;
  finalize: (projectId: string) => Promise<unknown>;
};
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
  backend?: UploadBackend,
) {
  validateVideo(file);
  if (prompt.length > 4000) throw new Error("Keep instructions under 4,000 characters.");
  // UX admission before reserving storage. Server consent-bound queue claims
  // remain the authorization boundary; a browser check cannot replace RLS.
  if (betaEnabled()) await requireBetaAdmission();
  if (signal.aborted) throw new Error("Upload cancelled");
  const reservation = (
    backend
      ? await backend.prepare({
          requestId,
          filename: file.name,
          mime: file.type,
          bytes: file.size,
          instructions: prompt,
        })
      : must(
          await supabase.rpc("prepare_upload", {
            request_id: requestId,
            filename: file.name,
            mime_type: file.type,
            byte_size: file.size,
            instructions: prompt,
          }),
        )
  ) as Reservation;
  if (!reservation?.project_id || !reservation.video_id || !reservation.path)
    throw new Error("The upload could not be prepared. Please try again.");
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
      fingerprint: async () =>
        `nccz:${session.user.id}:${reservation.path}:${file.size}:${file.lastModified}`,
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
  if (backend) await backend.finalize(reservation.project_id);
  else must(await supabase.rpc("finalize_upload", { pid: reservation.project_id }));
  return reservation.project_id;
}
