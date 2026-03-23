import { AbsoluteFill } from "remotion";
import type { TextOverlayData } from "../../types";
import { buildPositionStyle } from "../../lib/positions";
import { useAnimationStyle } from "./animations";

interface Props {
  data: TextOverlayData;
}

export const TextOverlay: React.FC<Props> = ({ data }) => {
  const animStyle = useAnimationStyle(
    data.animation,
    data.animationDuration,
    data.duration,
    data.text
  );

  const containerStyle = buildPositionStyle(data.x, data.y);

  const isTypewriter = data.animation === "typewriter";
  const charsVisible = (animStyle as Record<string, number>)["--chars-visible"];
  const displayText =
    isTypewriter && typeof charsVisible === "number"
      ? data.text.slice(0, charsVisible)
      : data.text;

  // Remove custom property before applying to DOM
  const cleanAnimStyle = { ...animStyle };
  if (isTypewriter) {
    delete (cleanAnimStyle as Record<string, unknown>)["--chars-visible"];
  }

  return (
    <AbsoluteFill style={containerStyle}>
      <div
        style={{
          fontSize: data.fontSize,
          fontFamily: data.fontFamily,
          fontWeight: data.fontWeight as React.CSSProperties["fontWeight"],
          color: data.color,
          backgroundColor: data.backgroundColor,
          padding: data.padding,
          borderRadius: data.borderRadius,
          ...cleanAnimStyle,
        }}
      >
        {displayText}
      </div>
    </AbsoluteFill>
  );
};
