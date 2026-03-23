import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { CSSProperties } from "react";

/**
 * Compute animation style based on animation type.
 * Returns CSS properties for the current frame within the overlay's local timeline.
 */
export function useAnimationStyle(
  animation: string,
  animationDuration: number = 0.5,
  totalDuration: number,
  text?: string
): CSSProperties {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const animFrames = Math.round(animationDuration * fps);
  const totalFrames = Math.round(totalDuration * fps);

  switch (animation) {
    case "fadeIn": {
      const opacity = interpolate(frame, [0, animFrames], [0, 1], {
        extrapolateRight: "clamp",
      });
      return { opacity };
    }

    case "fadeOut": {
      const fadeStart = totalFrames - animFrames;
      const opacity = interpolate(
        frame,
        [fadeStart, totalFrames],
        [1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
      return { opacity };
    }

    case "fadeInOut": {
      const fadeInOpacity = interpolate(frame, [0, animFrames], [0, 1], {
        extrapolateRight: "clamp",
      });
      const fadeOutStart = totalFrames - animFrames;
      const fadeOutOpacity = interpolate(
        frame,
        [fadeOutStart, totalFrames],
        [1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
      return { opacity: Math.min(fadeInOpacity, fadeOutOpacity) };
    }

    case "slideUp": {
      const translateY = interpolate(frame, [0, animFrames], [50, 0], {
        extrapolateRight: "clamp",
      });
      const opacity = interpolate(frame, [0, animFrames], [0, 1], {
        extrapolateRight: "clamp",
      });
      return {
        opacity,
        transform: `translateY(${translateY}px)`,
      };
    }

    case "typewriter": {
      if (!text) return {};
      const totalChars = text.length;
      const charsVisible = Math.round(
        interpolate(frame, [0, totalFrames * 0.8], [0, totalChars], {
          extrapolateRight: "clamp",
        })
      );
      // Return the number of visible characters as a CSS custom property
      // The component will use this to clip the text
      return {
        ["--chars-visible" as string]: charsVisible,
      };
    }

    default:
      return {};
  }
}
