"""Media analysis tools — get info, detect silence, detect scenes, extract keyframes."""

import json
import os
import re

from mcp.server.fastmcp import FastMCP

from clipping.utils.ffmpeg import probe_json, run_ffmpeg, run_ffprobe
from clipping.utils.media import validate_file_exists, validate_dir_exists, generate_output_path


def register(mcp: FastMCP):

    @mcp.tool()
    async def get_media_info(file_path: str) -> str:
        """Get detailed information about a media file (duration, resolution, fps, codecs, audio info).

        Args:
            file_path: Path to the media file.
        """
        file_path = validate_file_exists(file_path)
        data = probe_json(file_path)

        fmt = data.get("format", {})
        info = {
            "file": os.path.basename(file_path),
            "path": file_path,
            "format": fmt.get("format_long_name", fmt.get("format_name", "unknown")),
            "duration": f"{float(fmt.get('duration', 0)):.2f}s",
            "size": f"{int(fmt.get('size', 0)) / (1024*1024):.2f} MB",
            "bit_rate": f"{int(fmt.get('bit_rate', 0)) / 1000:.0f} kbps",
        }

        streams = {"video": [], "audio": [], "subtitle": []}
        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type", "")
            if codec_type == "video":
                fps_str = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = fps_str.split("/")
                    fps = round(int(num) / int(den), 2) if int(den) else 0
                except (ValueError, ZeroDivisionError):
                    fps = fps_str
                streams["video"].append({
                    "codec": stream.get("codec_name"),
                    "resolution": f"{stream.get('width')}x{stream.get('height')}",
                    "fps": fps,
                    "pixel_format": stream.get("pix_fmt"),
                })
            elif codec_type == "audio":
                streams["audio"].append({
                    "codec": stream.get("codec_name"),
                    "sample_rate": stream.get("sample_rate"),
                    "channels": stream.get("channels"),
                    "channel_layout": stream.get("channel_layout"),
                })
            elif codec_type == "subtitle":
                streams["subtitle"].append({
                    "codec": stream.get("codec_name"),
                    "language": stream.get("tags", {}).get("language"),
                })

        info["streams"] = {k: v for k, v in streams.items() if v}
        return json.dumps(info, indent=2)

    @mcp.tool()
    async def detect_silence(
        file_path: str,
        threshold_db: float = -40.0,
        min_duration: float = 0.5,
    ) -> str:
        """Detect silent segments in an audio or video file.

        Args:
            file_path: Path to the media file.
            threshold_db: Volume threshold in dB below which audio is considered silent (default: -40).
            min_duration: Minimum duration in seconds for a segment to count as silence (default: 0.5).
        """
        file_path = validate_file_exists(file_path)

        result = run_ffmpeg([
            "-i", file_path,
            "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
            "-f", "null", "-",
        ])

        # Parse silencedetect output from stderr
        silences = []
        current: dict = {}
        for line in result.stderr.splitlines():
            if "silence_start:" in line:
                match = re.search(r"silence_start:\s*([\d.]+)", line)
                if match:
                    current = {"start": float(match.group(1))}
            elif "silence_end:" in line:
                match = re.search(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", line)
                if match and current:
                    current["end"] = float(match.group(1))
                    current["duration"] = float(match.group(2))
                    silences.append(current)
                    current = {}

        if not silences:
            return "No silent segments detected."

        return json.dumps({
            "count": len(silences),
            "segments": silences,
        }, indent=2)

    @mcp.tool()
    async def detect_scenes(file_path: str, threshold: float = 0.3) -> str:
        """Detect scene changes in a video file.

        Args:
            file_path: Path to the video file.
            threshold: Scene change detection threshold (0.0-1.0, default: 0.3). Lower = more sensitive.
        """
        file_path = validate_file_exists(file_path)

        result = run_ffprobe([
            "-v", "quiet",
            "-show_entries", "frame=pts_time",
            "-of", "json",
            "-f", "lavfi",
            f"movie='{file_path}',select='gt(scene\\,{threshold})'",
        ])

        if not result.success:
            # Fallback: use ffmpeg filter approach
            result = run_ffmpeg([
                "-i", file_path,
                "-vf", f"select='gt(scene,{threshold})',showinfo",
                "-f", "null", "-",
            ])
            timestamps = []
            for line in result.stderr.splitlines():
                match = re.search(r"pts_time:([\d.]+)", line)
                if match:
                    timestamps.append(float(match.group(1)))

            if not timestamps:
                return "No scene changes detected."

            return json.dumps({
                "count": len(timestamps),
                "timestamps": timestamps,
            }, indent=2)

        data = json.loads(result.stdout)
        frames = data.get("frames", [])
        timestamps = [float(f["pts_time"]) for f in frames if "pts_time" in f]

        if not timestamps:
            return "No scene changes detected."

        return json.dumps({
            "count": len(timestamps),
            "timestamps": timestamps,
        }, indent=2)

    @mcp.tool()
    async def extract_keyframes(file_path: str, output_dir: str | None = None) -> str:
        """Extract keyframes (I-frames) from a video as images.

        Args:
            file_path: Path to the video file.
            output_dir: Directory to save keyframe images. Auto-generated if not provided.
        """
        file_path = validate_file_exists(file_path)
        if output_dir is None:
            base = os.path.splitext(file_path)[0]
            output_dir = f"{base}_keyframes"
        output_dir = validate_dir_exists(output_dir)

        pattern = os.path.join(output_dir, "keyframe_%04d.png")
        result = run_ffmpeg([
            "-i", file_path,
            "-vf", "select='eq(pict_type\\,I)'",
            "-vsync", "vfr",
            pattern,
        ])

        if not result.success:
            return f"Error extracting keyframes: {result.error}"

        files = sorted(f for f in os.listdir(output_dir) if f.startswith("keyframe_"))
        return f"Extracted {len(files)} keyframes to {output_dir}"
