"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { cn } from "@caretwin/shared";

const VIDEO_SRC = "/videos/human-digital-twin.mp4";
const POSTER_SRC = "/videos/human-digital-twin-poster.jpg";

/**
 * Illustrative rotating Digital Twin.
 *
 * The poster is the first frame of the supplied animation and is always painted
 * underneath the video, so the panel is never blank: it doubles as the loading
 * state, the reduced-motion state and the playback-failure fallback. The
 * animation is decorative and never represents a live scan, patient-specific
 * anatomy or any clinical measurement.
 */
export function TwinVideo({
  className,
  sizes = "(min-width: 1280px) 34vw, (min-width: 1024px) 40vw, 100vw",
}: {
  className?: string;
  sizes?: string;
}) {
  const [reducedMotion, setReducedMotion] = useState<boolean | null>(null);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (reducedMotion !== false || failed) return;
    const video = videoRef.current;
    if (!video) return;
    // Autoplay is muted and inline. If the browser still blocks it, the poster
    // frame stays visible instead of the panel going blank.
    const attempt = () => {
      video.muted = true;
      void video.play().catch(() => undefined);
    };
    if (video.readyState >= 2) attempt();
    else video.addEventListener("loadeddata", attempt, { once: true });
    return () => video.removeEventListener("loadeddata", attempt);
  }, [reducedMotion, failed]);

  const showVideo = reducedMotion === false && !failed;

  return (
    <div className={cn("relative h-full w-full overflow-hidden", className)}>
      <Image
        src={POSTER_SRC}
        alt="Illustrative rotating human digital twin"
        fill
        sizes={sizes}
        priority
        className="pointer-events-none object-contain"
      />

      {showVideo && (
        <video
          ref={videoRef}
          src={VIDEO_SRC}
          poster={POSTER_SRC}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          controls={false}
          disablePictureInPicture
          tabIndex={-1}
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 h-full w-full object-contain"
          onLoadedData={() => setReady(true)}
          onError={() => setFailed(true)}
        />
      )}

      {showVideo && !ready && (
        <div
          role="status"
          aria-live="polite"
          className="pointer-events-none absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-slate-900/60 px-3 py-1.5 backdrop-blur-sm"
        >
          <span
            aria-hidden="true"
            className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
          />
          <span className="text-[0.58rem] font-semibold uppercase tracking-[0.16em] text-white/80">
            Loading animation
          </span>
        </div>
      )}
    </div>
  );
}
