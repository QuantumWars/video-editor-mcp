import { AbsoluteFill, Img } from "remotion";
import type { ImageOverlayData } from "../../types";
import { buildPositionStyle } from "../../lib/positions";
import { useAnimationStyle } from "./animations";
import { resolveMediaSrc } from "../../lib/media-src";

interface Props {
  data: ImageOverlayData;
}

export const ImageOverlay: React.FC<Props> = ({ data }) => {
  const animStyle = useAnimationStyle(data.animation, 0.5, data.duration);
  const containerStyle = buildPositionStyle(data.x, data.y);

  return (
    <AbsoluteFill style={containerStyle}>
      <Img
        src={resolveMediaSrc(data.source)}
        width={data.width}
        height={data.height}
        style={{
          opacity: data.opacity,
          ...animStyle,
        }}
      />
    </AbsoluteFill>
  );
};
