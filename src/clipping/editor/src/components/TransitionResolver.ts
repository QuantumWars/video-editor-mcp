import { linearTiming, springTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { flip } from "@remotion/transitions/flip";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import type { Transition } from "../types";
import type { TransitionPresentation, TransitionTiming } from "@remotion/transitions";

/**
 * Map a project transition to a Remotion presentation + timing config.
 */
export function resolveTransition(
  transition: Transition,
  fps: number,
  width: number,
  height: number
): {
  presentation: TransitionPresentation<Record<string, unknown>>;
  timing: TransitionTiming;
} {
  const durationInFrames = Math.round(transition.duration * fps);

  const timing =
    transition.timing === "spring"
      ? springTiming({ durationInFrames })
      : linearTiming({ durationInFrames });

  let presentation: TransitionPresentation<Record<string, unknown>>;

  switch (transition.type) {
    case "fade":
      presentation = fade() as unknown as TransitionPresentation<Record<string, unknown>>;
      break;
    case "slide":
      presentation = slide({ direction: transition.direction ?? "from-right" }) as unknown as TransitionPresentation<Record<string, unknown>>;
      break;
    case "wipe":
      presentation = wipe({ direction: transition.direction ?? "from-left" }) as unknown as TransitionPresentation<Record<string, unknown>>;
      break;
    case "flip":
      presentation = flip({ direction: transition.direction ?? "from-right" }) as unknown as TransitionPresentation<Record<string, unknown>>;
      break;
    case "clockWipe":
      presentation = clockWipe({ width, height }) as unknown as TransitionPresentation<Record<string, unknown>>;
      break;
    default:
      presentation = fade() as unknown as TransitionPresentation<Record<string, unknown>>;
  }

  return { presentation, timing };
}
