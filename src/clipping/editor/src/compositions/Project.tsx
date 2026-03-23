import {
  AbsoluteFill,
  Sequence,
  useVideoConfig,
} from "remotion";
import {
  TransitionSeries,
} from "@remotion/transitions";
import { ClipSequence } from "../components/ClipSequence";
import { resolveTransition } from "../components/TransitionResolver";
import { TextOverlay } from "../components/overlays/TextOverlay";
import { CaptionOverlay } from "../components/overlays/CaptionOverlay";
import { ImageOverlay } from "../components/overlays/ImageOverlay";
import { clipDurationFrames, calculateTotalFrames } from "../lib/timeline";
import type { ProjectData, Overlay } from "../types";

export const Project: React.FC<ProjectData> = (props) => {
  const { fps, width, height } = useVideoConfig();
  const track0Clips = props.clips.filter((c) => c.track === 0);
  const totalFrames = calculateTotalFrames(props);

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {/* Video track */}
      {track0Clips.length > 0 && (
        <TransitionSeries name="Video">
          {track0Clips.map((clip, i) => {
            const durationInFrames = clipDurationFrames(clip, fps);
            const elements: React.ReactNode[] = [
              <TransitionSeries.Sequence
                key={clip.id}
                durationInFrames={durationInFrames}
              >
                <ClipSequence clip={clip} />
              </TransitionSeries.Sequence>,
            ];

            if (clip.transition && clip.transition.type !== "none" && i < track0Clips.length - 1) {
              const { presentation, timing } = resolveTransition(
                clip.transition,
                fps,
                width,
                height
              );
              elements.push(
                <TransitionSeries.Transition
                  key={`${clip.id}-transition`}
                  presentation={presentation}
                  timing={timing}
                />
              );
            }

            return elements;
          })}
        </TransitionSeries>
      )}

      {/* Overlays track */}
      {props.overlays.length > 0 && (
        <Sequence
          name="Overlays"
          from={0}
          durationInFrames={totalFrames}
          layout="none"
        >
          {props.overlays.map((overlay: Overlay) => {
            const from = Math.round(overlay.startTime * fps);
            const dur = Math.round(overlay.duration * fps);

            return (
              <Sequence
                key={overlay.id}
                from={from}
                durationInFrames={dur}
                layout="none"
                showInTimeline={false}
              >
                <AbsoluteFill>
                  {overlay.type === "text" && <TextOverlay data={overlay} />}
                  {overlay.type === "caption" && (
                    <CaptionOverlay data={overlay} />
                  )}
                  {overlay.type === "image" && <ImageOverlay data={overlay} />}
                </AbsoluteFill>
              </Sequence>
            );
          })}
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
