export interface ProjectData {
  id: string;
  name: string;
  fps: number;
  width: number;
  height: number;
  clips: Clip[];
  overlays: Overlay[];
}

export interface Clip {
  id: string;
  source: string;
  startTime: number;
  endTime: number;
  speed: number;
  volume: number;
  track: number;
  transition?: Transition;
}

export interface Transition {
  id: string;
  type: "fade" | "slide" | "wipe" | "flip" | "clockWipe" | "none";
  duration: number;
  timing: "linear" | "spring";
  direction?: "from-left" | "from-right" | "from-top" | "from-bottom";
}

export type OverlayType = "text" | "caption" | "image";

export interface BaseOverlay {
  id: string;
  type: OverlayType;
  startTime: number;
  duration: number;
}

export interface TextOverlayData extends BaseOverlay {
  type: "text";
  text: string;
  x: string;
  y: string;
  fontSize: number;
  fontFamily: string;
  fontWeight: string;
  color: string;
  backgroundColor?: string;
  padding?: number;
  borderRadius?: number;
  animation: string;
  animationDuration: number;
}

export interface CaptionWord {
  text: string;
  startTime: number;
  endTime: number;
}

export interface CaptionOverlayData extends BaseOverlay {
  type: "caption";
  words: CaptionWord[];
  style: "default" | "karaoke" | "bounce" | "highlight";
  position: "bottom" | "center" | "top";
  fontSize: number;
  color: string;
  activeColor: string;
  maxWordsPerLine: number;
  backgroundColor?: string;
}

export interface ImageOverlayData extends BaseOverlay {
  type: "image";
  source: string;
  x: string;
  y: string;
  width: number;
  height: number;
  opacity: number;
  animation: string;
}

export type Overlay = TextOverlayData | CaptionOverlayData | ImageOverlayData;
