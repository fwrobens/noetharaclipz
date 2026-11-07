import { useEffect, useRef, useState } from "react";
import { Play, Pause } from "lucide-react";
import { useMediaUrl } from "@/lib/media";
import { fmt } from "@/lib/domain";
export function VideoPlayer({
  path,
  poster,
  seekTo,
  onTime,
  cropX = 0.5,
  cropY = 0.5,
  volume = 1,
  segmentEnd,
  children,
}: {
  path: string | undefined;
  poster: string;
  seekTo?: number | undefined;
  onTime?: (t: number) => void;
  cropX?: number;
  cropY?: number;
  volume?: number;
  segmentEnd?: number;
  children?: React.ReactNode;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const position = useRef(seekTo ?? 0);
  const media = useMediaUrl("source-videos", path);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (video.current && seekTo !== undefined && Number.isFinite(seekTo)) {
      position.current = seekTo;
      video.current.currentTime = seekTo;
      setTime(seekTo);
    }
  }, [seekTo]);
  useEffect(() => {
    if (video.current) video.current.volume = Math.min(1, volume);
  }, [volume]);
  async function toggle() {
    if (!video.current) return;
    try {
      if (video.current.paused) {
        if (segmentEnd !== undefined && video.current.currentTime >= segmentEnd - 0.05) {
          video.current.currentTime = seekTo ?? 0;
          position.current = seekTo ?? 0;
        }
        await video.current.play();
      } else video.current.pause();
    } catch {
      setError("This video could not play. The worker may need to prepare a compatible preview.");
    }
  }
  return (
    <div className="relative h-full w-full overflow-hidden bg-black">
      <video
        ref={video}
        src={media.data}
        poster={poster}
        preload="metadata"
        playsInline
        onLoadedMetadata={(e) => {
          setDuration(e.currentTarget.duration);
          e.currentTarget.currentTime = position.current;
        }}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onError={() =>
          setError("Preview unavailable. Processing may still be preparing this format.")
        }
        onTimeUpdate={(e) => {
          const t = e.currentTarget.currentTime;
          if (e.currentTarget.readyState >= 1) position.current = t;
          setTime(t);
          onTime?.(t);
          if (segmentEnd !== undefined && t >= segmentEnd) e.currentTarget.pause();
        }}
        style={{ objectPosition: `${cropX * 100}% ${cropY * 100}%` }}
        className="h-full w-full object-cover"
      />
      {children}
      <button
        onClick={() => void toggle()}
        disabled={!media.data}
        className="absolute left-1/2 top-1/2 grid h-14 w-14 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-card/90 text-foreground shadow-float backdrop-blur transition hover:scale-110 disabled:opacity-40"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? <Pause className="h-6 w-6" /> : <Play className="ml-1 h-6 w-6" />}
      </button>
      <div className="absolute inset-x-0 bottom-0 bg-black/70 p-2 text-xs text-white">
        <div className="flex items-center gap-2">
          <span className="shrink-0 font-mono">{fmt(time)}</span>
          <input
            aria-label="Seek video"
            type="range"
            min={0}
            max={duration || 1}
            step={0.05}
            value={time}
            onChange={(e) => {
              const t = +e.target.value;
              if (video.current) video.current.currentTime = t;
              setTime(t);
              onTime?.(t);
            }}
            className="min-w-0 flex-1 accent-primary"
          />
          <span className="shrink-0 font-mono">{fmt(duration)}</span>
        </div>
        {(error || media.error) && <p role="status">{error || media.error?.message}</p>}
      </div>
    </div>
  );
}
