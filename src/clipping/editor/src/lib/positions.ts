import type { CSSProperties } from "react";

/**
 * Parse a position string into CSS positioning.
 * Supports: "center", percentage like "50%", or pixel value like "100".
 */
export function parsePosition(
  value: string,
  axis: "x" | "y"
): CSSProperties {
  if (value === "center") {
    // Centering handled by the parent's flexbox or transform
    return {};
  }

  if (value.endsWith("%")) {
    const pct = parseFloat(value);
    return axis === "x" ? { left: `${pct}%` } : { top: `${pct}%` };
  }

  const px = parseFloat(value);
  if (!isNaN(px)) {
    return axis === "x" ? { left: `${px}px` } : { top: `${px}px` };
  }

  return {};
}

/**
 * Build a CSS style object for positioning an overlay.
 * When both x and y are "center", uses flexbox centering.
 * Otherwise uses absolute positioning.
 */
export function buildPositionStyle(x: string, y: string): CSSProperties {
  const isCenteredX = x === "center";
  const isCenteredY = y === "center";

  if (isCenteredX && isCenteredY) {
    return {
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
    };
  }

  const style: CSSProperties = { position: "absolute" };

  if (isCenteredX) {
    style.left = "50%";
    style.transform = "translateX(-50%)";
  } else {
    Object.assign(style, parsePosition(x, "x"));
  }

  if (isCenteredY) {
    style.top = "50%";
    // Combine transforms if needed
    style.transform = style.transform
      ? `${style.transform} translateY(-50%)`
      : "translateY(-50%)";
  } else {
    Object.assign(style, parsePosition(y, "y"));
  }

  return style;
}
