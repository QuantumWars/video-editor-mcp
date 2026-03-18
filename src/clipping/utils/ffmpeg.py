"""FFmpeg subprocess helper — run commands, parse output, handle errors."""

import json
import subprocess
import shutil
from dataclasses import dataclass


@dataclass
class FFmpegResult:
    success: bool
    output_path: str | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    def to_message(self, extra: str = "") -> str:
        if self.success:
            parts = ["Success."]
            if self.output_path:
                parts.append(f"Output: {self.output_path}")
            if extra:
                parts.append(extra)
            return " ".join(parts)
        return f"Error: {self.error or self.stderr}"


def get_ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found on PATH. Please install ffmpeg.")
    return path


def get_ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise RuntimeError("ffprobe not found on PATH. Please install ffmpeg.")
    return path


def run_ffmpeg(args: list[str], output_path: str | None = None) -> FFmpegResult:
    """Run an ffmpeg command with the given arguments.

    Args:
        args: Arguments to pass to ffmpeg (without the 'ffmpeg' binary itself).
        output_path: Expected output file path for the result.
    """
    cmd = [get_ffmpeg_path()] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        if result.returncode != 0:
            return FFmpegResult(
                success=False,
                stderr=result.stderr,
                error=_extract_error(result.stderr),
            )
        return FFmpegResult(
            success=True,
            output_path=output_path,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired:
        return FFmpegResult(success=False, error="FFmpeg command timed out after 10 minutes")
    except Exception as e:
        return FFmpegResult(success=False, error=str(e))


def run_ffprobe(args: list[str]) -> FFmpegResult:
    """Run an ffprobe command with the given arguments."""
    cmd = [get_ffprobe_path()] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return FFmpegResult(
                success=False,
                stderr=result.stderr,
                error=_extract_error(result.stderr),
            )
        return FFmpegResult(
            success=True,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired:
        return FFmpegResult(success=False, error="FFprobe command timed out after 60 seconds")
    except Exception as e:
        return FFmpegResult(success=False, error=str(e))


def probe_json(file_path: str) -> dict:
    """Run ffprobe and return parsed JSON output."""
    result = run_ffprobe([
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ])
    if not result.success:
        raise RuntimeError(f"ffprobe failed: {result.error}")
    return json.loads(result.stdout)


def _extract_error(stderr: str) -> str:
    """Extract the most useful error line from ffmpeg stderr."""
    lines = stderr.strip().splitlines()
    for line in reversed(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("frame="):
            return stripped
    return stderr[-500:] if stderr else "Unknown error"
