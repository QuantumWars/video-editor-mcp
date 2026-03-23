import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { CaptionOverlayData, CaptionWord } from "../../types";

interface Props {
  data: CaptionOverlayData;
}

/**
 * Group words into lines of maxWordsPerLine.
 */
function groupWords(words: CaptionWord[], maxPerLine: number): CaptionWord[][] {
  const lines: CaptionWord[][] = [];
  for (let i = 0; i < words.length; i += maxPerLine) {
    lines.push(words.slice(i, i + maxPerLine));
  }
  return lines;
}

/**
 * Find which line is currently active based on the current time.
 */
function findActiveLine(
  lines: CaptionWord[][],
  currentTimeSecs: number
): number {
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineStart = line[0].startTime;
    const lineEnd = line[line.length - 1].endTime;
    if (currentTimeSecs >= lineStart && currentTimeSecs <= lineEnd) {
      return i;
    }
  }
  // If between lines, find the next upcoming line
  for (let i = 0; i < lines.length; i++) {
    const lineStart = lines[i][0].startTime;
    if (currentTimeSecs < lineStart) {
      return Math.max(0, i - 1);
    }
  }
  return lines.length - 1;
}

export const CaptionOverlay: React.FC<Props> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Current time relative to the overlay's start
  const currentTime = frame / fps;
  // Adjust word times relative to overlay start
  const relativeWords = data.words.map((w) => ({
    ...w,
    startTime: w.startTime - data.startTime,
    endTime: w.endTime - data.startTime,
  }));

  const lines = groupWords(relativeWords, data.maxWordsPerLine);
  const activeLineIdx = findActiveLine(lines, currentTime);
  const activeLine = lines[activeLineIdx];

  if (!activeLine) return null;

  const positionStyle: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    display: "flex",
    justifyContent: "center",
    ...(data.position === "bottom"
      ? { bottom: "10%" }
      : data.position === "top"
        ? { top: "10%" }
        : { top: "50%", transform: "translateY(-50%)" }),
  };

  return (
    <AbsoluteFill>
      <div style={positionStyle}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "0.3em",
            padding: "0.3em 0.6em",
            borderRadius: 8,
            backgroundColor: data.backgroundColor,
          }}
        >
          {activeLine.map((word, i) => {
            const isActive =
              currentTime >= word.startTime && currentTime <= word.endTime;

            return (
              <span
                key={`${activeLineIdx}-${i}`}
                style={getWordStyle(data, isActive)}
              >
                {word.text}
              </span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

function getWordStyle(
  data: CaptionOverlayData,
  isActive: boolean
): React.CSSProperties {
  const base: React.CSSProperties = {
    fontSize: data.fontSize,
    fontWeight: "bold",
    color: data.color,
    transition: "all 0.1s ease",
  };

  if (!isActive) return base;

  switch (data.style) {
    case "karaoke":
      return { ...base, color: data.activeColor };

    case "bounce":
      return {
        ...base,
        color: data.activeColor,
        transform: "scale(1.2)",
        display: "inline-block",
      };

    case "highlight":
      return {
        ...base,
        backgroundColor: data.activeColor,
        color: "#000",
        padding: "0.1em 0.2em",
        borderRadius: 4,
      };

    case "default":
    default:
      return base;
  }
}
