import { OffthreadVideo, useVideoConfig } from "remotion";
import type { Clip } from "../types";
import { resolveMediaSrc } from "../lib/media-src";

interface ClipSequenceProps {
  clip: Clip;
}

export const ClipSequence: React.FC<ClipSequenceProps> = ({ clip }) => {
  const { fps } = useVideoConfig();

  const startFrame = Math.round(clip.startTime * fps);
  const endFrame = Math.round(clip.endTime * fps);

  return (
    <OffthreadVideo
      src={resolveMediaSrc(clip.source)}
      startFrom={startFrame}
      endAt={endFrame}
      playbackRate={clip.speed}
      volume={clip.volume}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "contain",
      }}
    />
  );
};
