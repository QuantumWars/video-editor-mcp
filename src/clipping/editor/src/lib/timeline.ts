import type { Clip, ProjectData } from "../types";

/**
 * Get the visual duration of a clip in seconds (accounting for speed).
 */
export function clipDurationSecs(clip: Clip): number {
  return (clip.endTime - clip.startTime) / clip.speed;
}

/**
 * Get the visual duration of a clip in frames.
 */
export function clipDurationFrames(clip: Clip, fps: number): number {
  return Math.round(clipDurationSecs(clip) * fps);
}

/**
 * Calculate total frames for the project, accounting for transition overlaps.
 * Transitions subtract their duration from the total because two clips overlap.
 */
export function calculateTotalFrames(project: ProjectData): number {
  const { clips, overlays, fps } = project;
  const track0 = clips.filter((c) => c.track === 0);

  let totalSecs = 0;
  for (let i = 0; i < track0.length; i++) {
    totalSecs += clipDurationSecs(track0[i]);
    // Transitions overlap: subtract the transition duration
    if (track0[i].transition && i < track0.length - 1) {
      totalSecs -= track0[i].transition!.duration;
    }
  }

  // Extend if any overlay ends beyond the clips
  for (const ovr of overlays) {
    const ovrEnd = ovr.startTime + ovr.duration;
    if (ovrEnd > totalSecs) {
      totalSecs = ovrEnd;
    }
  }

  return Math.ceil(totalSecs * fps);
}
