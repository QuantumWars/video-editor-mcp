"""FFmpeg-based video editing tools — trim, cut, concat, speed, convert, scale, crop, fade, overlay, subtitles."""

import os

from mcp.server.fastmcp import FastMCP

from clipping.utils.ffmpeg import run_ffmpeg
from clipping.utils.media import validate_file_exists, generate_output_path


def register(mcp: FastMCP):

    @mcp.tool()
    async def trim_video(
        file_path: str,
        start_time: str,
        duration: str,
        output_path: str | None = None,
    ) -> str:
        """Trim a video starting at start_time for the given duration.

        Args:
            file_path: Path to input video file.
            start_time: Start time (format: HH:MM:SS or seconds, e.g. "00:01:30" or "90").
            duration: Duration to keep (format: HH:MM:SS or seconds).
            output_path: Output file path. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "trimmed")

        result = run_ffmpeg([
            "-i", file_path,
            "-ss", start_time,
            "-t", duration,
            "-c", "copy",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def cut_segment(
        file_path: str,
        start_time: str,
        end_time: str,
        output_path: str | None = None,
    ) -> str:
        """Remove a segment from a video (keeps everything before start_time and after end_time).

        Args:
            file_path: Path to input video file.
            start_time: Start of segment to remove (format: HH:MM:SS or seconds).
            end_time: End of segment to remove (format: HH:MM:SS or seconds).
            output_path: Output file path. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "cut")

        # Use the select/aselect filter to drop the segment
        result = run_ffmpeg([
            "-i", file_path,
            "-vf", f"select='not(between(t,{start_time},{end_time}))',setpts=N/FRAME_RATE/TB",
            "-af", f"aselect='not(between(t,{start_time},{end_time}))',asetpts=N/SR/TB",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def concatenate_videos(
        file_paths: list[str],
        output_path: str,
    ) -> str:
        """Join multiple video files together in sequence.

        Args:
            file_paths: List of video file paths to concatenate (in order).
            output_path: Output file path.
        """
        validated = [validate_file_exists(f) for f in file_paths]

        # Create concat file list
        concat_file = output_path + ".concat.txt"
        try:
            with open(concat_file, "w") as f:
                for path in validated:
                    f.write(f"file '{path}'\n")

            result = run_ffmpeg([
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y", output_path,
            ], output_path)
        finally:
            if os.path.exists(concat_file):
                os.remove(concat_file)

        return result.to_message()

    @mcp.tool()
    async def change_speed(
        file_path: str,
        speed_factor: float,
        output_path: str | None = None,
    ) -> str:
        """Speed up or slow down a video (with audio pitch correction).

        Args:
            file_path: Path to input video file.
            speed_factor: Speed multiplier (e.g. 2.0 = 2x faster, 0.5 = half speed).
            output_path: Output file path. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if output_path is None:
            label = f"{speed_factor}x".replace(".", "_")
            output_path = generate_output_path(file_path, label)

        video_filter = f"setpts={1/speed_factor}*PTS"
        audio_filter = f"atempo={speed_factor}"

        # atempo only supports 0.5-2.0 range, chain multiple for wider range
        if speed_factor > 2.0:
            parts = []
            remaining = speed_factor
            while remaining > 2.0:
                parts.append("atempo=2.0")
                remaining /= 2.0
            parts.append(f"atempo={remaining}")
            audio_filter = ",".join(parts)
        elif speed_factor < 0.5:
            parts = []
            remaining = speed_factor
            while remaining < 0.5:
                parts.append("atempo=0.5")
                remaining /= 0.5
            parts.append(f"atempo={remaining}")
            audio_filter = ",".join(parts)

        result = run_ffmpeg([
            "-i", file_path,
            "-vf", video_filter,
            "-af", audio_filter,
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def convert_format(
        file_path: str,
        output_path: str,
        codec: str | None = None,
        bitrate: str | None = None,
    ) -> str:
        """Convert a video or audio file to a different format.

        Args:
            file_path: Path to input file.
            output_path: Output file path (format is determined by extension, e.g. output.mkv).
            codec: Video codec to use (e.g. "libx264", "libx265", "copy"). Auto-detected if not provided.
            bitrate: Target bitrate (e.g. "5M", "128k"). Uses ffmpeg default if not provided.
        """
        file_path = validate_file_exists(file_path)
        args = ["-i", file_path]

        if codec:
            args += ["-c:v", codec]
        if bitrate:
            args += ["-b:v", bitrate]

        args += ["-y", output_path]
        result = run_ffmpeg(args, output_path)
        return result.to_message()

    @mcp.tool()
    async def scale_video(
        file_path: str,
        width: int = -1,
        height: int = -1,
        output_path: str | None = None,
    ) -> str:
        """Resize a video. Set one dimension to -1 to auto-scale maintaining aspect ratio.

        Args:
            file_path: Path to input video file.
            width: Target width in pixels (-1 for auto).
            height: Target height in pixels (-1 for auto).
            output_path: Output file path. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if width == -1 and height == -1:
            return "Error: At least one of width or height must be specified."

        # Ensure even dimensions for codec compatibility
        w = str(width) if width != -1 else "-2"
        h = str(height) if height != -1 else "-2"

        if output_path is None:
            output_path = generate_output_path(file_path, f"{w}x{h}")

        result = run_ffmpeg([
            "-i", file_path,
            "-vf", f"scale={w}:{h}",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def crop_video(
        file_path: str,
        width: int,
        height: int,
        x: int = 0,
        y: int = 0,
        output_path: str | None = None,
    ) -> str:
        """Crop a region from a video.

        Args:
            file_path: Path to input video file.
            width: Width of crop region.
            height: Height of crop region.
            x: X offset from top-left corner (default: 0).
            y: Y offset from top-left corner (default: 0).
            output_path: Output file path. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "cropped")

        result = run_ffmpeg([
            "-i", file_path,
            "-vf", f"crop={width}:{height}:{x}:{y}",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def add_fade(
        file_path: str,
        fade_type: str = "both",
        start_time: float = 0.0,
        duration: float = 1.0,
        output_path: str | None = None,
    ) -> str:
        """Add fade in and/or fade out to a video.

        Args:
            file_path: Path to input video file.
            fade_type: Type of fade — "in", "out", or "both" (default: "both").
            start_time: Start time for fade-in or fade-out in seconds (for "in"/"out" only).
            duration: Duration of the fade effect in seconds (default: 1.0).
            output_path: Output file path. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "faded")

        from clipping.utils.ffmpeg import probe_json
        data = probe_json(file_path)
        total_duration = float(data.get("format", {}).get("duration", 0))

        vfilters = []
        afilters = []

        if fade_type in ("in", "both"):
            vfilters.append(f"fade=t=in:st=0:d={duration}")
            afilters.append(f"afade=t=in:st=0:d={duration}")
        if fade_type in ("out", "both"):
            fade_start = total_duration - duration if fade_type == "both" else start_time
            vfilters.append(f"fade=t=out:st={fade_start}:d={duration}")
            afilters.append(f"afade=t=out:st={fade_start}:d={duration}")

        result = run_ffmpeg([
            "-i", file_path,
            "-vf", ",".join(vfilters),
            "-af", ",".join(afilters),
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def add_overlay(
        base_path: str,
        overlay_path: str,
        x: str = "0",
        y: str = "0",
        output_path: str | None = None,
    ) -> str:
        """Overlay an image or video on top of a base video.

        Args:
            base_path: Path to the base video file.
            overlay_path: Path to the overlay image or video.
            x: X position expression (e.g. "10", "(W-w)/2" for centered). Default: "0".
            y: Y position expression (e.g. "10", "(H-h)/2" for centered). Default: "0".
            output_path: Output file path. Auto-generated if not provided.
        """
        base_path = validate_file_exists(base_path)
        overlay_path = validate_file_exists(overlay_path)
        if output_path is None:
            output_path = generate_output_path(base_path, "overlay")

        result = run_ffmpeg([
            "-i", base_path,
            "-i", overlay_path,
            "-filter_complex", f"overlay={x}:{y}",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def add_subtitles(
        video_path: str,
        subtitle_path: str,
        output_path: str | None = None,
    ) -> str:
        """Burn subtitles into a video (hard-sub).

        Args:
            video_path: Path to the video file.
            subtitle_path: Path to the subtitle file (.srt, .ass, .vtt).
            output_path: Output file path. Auto-generated if not provided.
        """
        video_path = validate_file_exists(video_path)
        subtitle_path = validate_file_exists(subtitle_path)
        if output_path is None:
            output_path = generate_output_path(video_path, "subtitled")

        # Escape special characters in subtitle path for ffmpeg filter
        escaped = subtitle_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

        result = run_ffmpeg([
            "-i", video_path,
            "-vf", f"subtitles='{escaped}'",
            "-y", output_path,
        ], output_path)

        return result.to_message()
