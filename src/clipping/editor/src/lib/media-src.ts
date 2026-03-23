import { staticFile } from "remotion";

/**
 * Resolve a source path to a browser-accessible URL.
 *
 * During Studio preview, absolute file paths are symlinked into public/media/
 * by the Python project_preview tool. The project JSON is rewritten to use
 * relative "media/<filename>" paths that staticFile() can serve.
 *
 * During CLI rendering, OffthreadVideo reads files directly via FFmpeg,
 * so absolute paths work as-is.
 */
export function resolveMediaSrc(source: string): string {
  if (source.startsWith("http://") || source.startsWith("https://")) {
    return source;
  }
  // Relative paths (e.g. "media/clip.mp4") → serve via staticFile
  if (!source.startsWith("/")) {
    return staticFile(source);
  }
  // Absolute paths — used during CLI render (FFmpeg reads directly)
  return source;
}
