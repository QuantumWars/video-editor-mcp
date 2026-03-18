"""Common media utilities — path validation, format detection, output path generation."""

import os

VALID_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".ts"}
VALID_AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus"}
VALID_MEDIA_EXTENSIONS = VALID_VIDEO_EXTENSIONS | VALID_AUDIO_EXTENSIONS
VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
VALID_SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}


def validate_file_exists(file_path: str) -> str:
    """Validate that a file exists and return its absolute path."""
    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")
    return abs_path


def validate_dir_exists(dir_path: str) -> str:
    """Validate that a directory exists (create if needed) and return its absolute path."""
    abs_path = os.path.abspath(dir_path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def generate_output_path(input_path: str, suffix: str, ext: str | None = None) -> str:
    """Generate an output path based on input path with a suffix.

    Example: generate_output_path("video.mp4", "trimmed") -> "video_trimmed.mp4"
    """
    base, original_ext = os.path.splitext(input_path)
    ext = ext or original_ext
    output = f"{base}_{suffix}{ext}"
    # Avoid overwriting — append number if needed
    counter = 1
    while os.path.exists(output):
        output = f"{base}_{suffix}_{counter}{ext}"
        counter += 1
    return output


def get_extension(file_path: str) -> str:
    """Return the lowercase file extension."""
    return os.path.splitext(file_path)[1].lower()


def is_video(file_path: str) -> bool:
    return get_extension(file_path) in VALID_VIDEO_EXTENSIONS


def is_audio(file_path: str) -> bool:
    return get_extension(file_path) in VALID_AUDIO_EXTENSIONS
