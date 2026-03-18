"""Audio-specific tools — extract, replace, mix, segment by silence."""

import json
import os
import re

from mcp.server.fastmcp import FastMCP

from clipping.utils.ffmpeg import run_ffmpeg, probe_json
from clipping.utils.media import validate_file_exists, validate_dir_exists, generate_output_path


def register(mcp: FastMCP):

    @mcp.tool()
    async def extract_audio(
        file_path: str,
        output_path: str | None = None,
        format: str = "mp3",
    ) -> str:
        """Extract the audio track from a video file.

        Args:
            file_path: Path to the video file.
            output_path: Output audio file path. Auto-generated if not provided.
            format: Audio format — "mp3", "wav", "aac", "flac" (default: "mp3").
        """
        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "audio", f".{format}")

        codec_map = {
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "aac": "aac",
            "flac": "flac",
        }
        codec = codec_map.get(format, format)

        result = run_ffmpeg([
            "-i", file_path,
            "-vn",
            "-acodec", codec,
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def replace_audio(
        video_path: str,
        audio_path: str,
        output_path: str | None = None,
    ) -> str:
        """Replace a video's audio track with a different audio file.

        Args:
            video_path: Path to the video file.
            audio_path: Path to the replacement audio file.
            output_path: Output file path. Auto-generated if not provided.
        """
        video_path = validate_file_exists(video_path)
        audio_path = validate_file_exists(audio_path)
        if output_path is None:
            output_path = generate_output_path(video_path, "new_audio")

        result = run_ffmpeg([
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def mix_audio(
        audio1_path: str,
        audio2_path: str,
        output_path: str,
        volume1: float = 1.0,
        volume2: float = 1.0,
    ) -> str:
        """Mix two audio sources together with individual volume control.

        Args:
            audio1_path: Path to the first audio file.
            audio2_path: Path to the second audio file.
            output_path: Output file path.
            volume1: Volume multiplier for first audio (default: 1.0).
            volume2: Volume multiplier for second audio (default: 1.0).
        """
        audio1_path = validate_file_exists(audio1_path)
        audio2_path = validate_file_exists(audio2_path)

        result = run_ffmpeg([
            "-i", audio1_path,
            "-i", audio2_path,
            "-filter_complex",
            f"[0:a]volume={volume1}[a1];[1:a]volume={volume2}[a2];[a1][a2]amix=inputs=2:duration=longest",
            "-y", output_path,
        ], output_path)

        return result.to_message()

    @mcp.tool()
    async def segment_by_silence(
        file_path: str,
        output_dir: str | None = None,
        threshold_db: float = -40.0,
        min_silence_duration: float = 0.5,
    ) -> str:
        """Split a video or audio file at silent gaps.

        Args:
            file_path: Path to the media file.
            output_dir: Directory to save segments. Auto-generated if not provided.
            threshold_db: Volume threshold in dB for silence detection (default: -40).
            min_silence_duration: Minimum silence duration in seconds to split at (default: 0.5).
        """
        file_path = validate_file_exists(file_path)
        if output_dir is None:
            base = os.path.splitext(file_path)[0]
            output_dir = f"{base}_segments"
        output_dir = validate_dir_exists(output_dir)

        # Step 1: detect silence
        result = run_ffmpeg([
            "-i", file_path,
            "-af", f"silencedetect=noise={threshold_db}dB:d={min_silence_duration}",
            "-f", "null", "-",
        ])

        silences = []
        current: dict = {}
        for line in result.stderr.splitlines():
            if "silence_start:" in line:
                match = re.search(r"silence_start:\s*([\d.]+)", line)
                if match:
                    current = {"start": float(match.group(1))}
            elif "silence_end:" in line:
                match = re.search(r"silence_end:\s*([\d.]+)", line)
                if match and current:
                    current["end"] = float(match.group(1))
                    silences.append(current)
                    current = {}

        if not silences:
            return "No silent segments detected — nothing to split."

        # Step 2: get total duration
        data = probe_json(file_path)
        total_duration = float(data.get("format", {}).get("duration", 0))

        # Step 3: compute segments (non-silent parts)
        ext = os.path.splitext(file_path)[1]
        segments = []
        prev_end = 0.0

        for silence in silences:
            mid = (silence["start"] + silence["end"]) / 2
            if mid - prev_end > 0.1:
                segments.append((prev_end, mid))
            prev_end = mid

        if total_duration - prev_end > 0.1:
            segments.append((prev_end, total_duration))

        # Step 4: extract each segment
        output_files = []
        for i, (start, end) in enumerate(segments):
            seg_path = os.path.join(output_dir, f"segment_{i+1:03d}{ext}")
            seg_result = run_ffmpeg([
                "-i", file_path,
                "-ss", str(start),
                "-t", str(end - start),
                "-c", "copy",
                "-y", seg_path,
            ], seg_path)
            if seg_result.success:
                output_files.append(seg_path)

        return json.dumps({
            "segments_created": len(output_files),
            "output_dir": output_dir,
            "files": output_files,
        }, indent=2)
