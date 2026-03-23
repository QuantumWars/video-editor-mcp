import { Composition } from "remotion";
import { Project } from "./compositions/Project";
import { calculateTotalFrames } from "./lib/timeline";
import type { ProjectData } from "./types";

export const Root: React.FC = () => {
  return (
    <Composition
      id="Project"
      component={Project as unknown as React.FC<Record<string, unknown>>}
      calculateMetadata={({ props }) => {
        const data = props as unknown as ProjectData;
        const totalFrames = calculateTotalFrames(data);
        return {
          durationInFrames: Math.max(totalFrames, 1),
          fps: data.fps || 30,
          width: data.width || 1920,
          height: data.height || 1080,
        };
      }}
      defaultProps={{
        id: "",
        name: "Empty Project",
        fps: 30,
        width: 1920,
        height: 1080,
        clips: [],
        overlays: [],
      } as Record<string, unknown>}
    />
  );
};
