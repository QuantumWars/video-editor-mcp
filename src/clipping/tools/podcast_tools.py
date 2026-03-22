"""Podcast multicam editing tools — diarize, auto-map speakers, merge camera angles."""

import json
import os
import shutil
import tempfile

from mcp.server.fastmcp import FastMCP

from clipping.utils.ffmpeg import run_ffmpeg, probe_json
from clipping.utils.media import validate_file_exists, generate_output_path


def _get_elevenlabs_client():
    """Lazily create an ElevenLabs client."""
    from elevenlabs.client import ElevenLabs

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set.")
    return ElevenLabs(api_key=api_key)


def _words_to_segments(words: list[dict]) -> list[dict]:
    """Collapse word-level diarization into contiguous speaker segments.

    Each word dict should have 'speaker_id', 'start', 'end' keys.
    Returns list of {speaker, start, end} dicts.
    """
    if not words:
        return []

    segments = []
    current_speaker = words[0].get("speaker_id")
    seg_start = words[0].get("start", 0)
    seg_end = words[0].get("end", 0)

    for word in words[1:]:
        speaker = word.get("speaker_id")
        if speaker == current_speaker:
            seg_end = word.get("end", seg_end)
        else:
            segments.append({
                "speaker": current_speaker,
                "start": seg_start,
                "end": seg_end,
            })
            current_speaker = speaker
            seg_start = word.get("start", seg_end)
            seg_end = word.get("end", seg_start)

    # Append the last segment
    segments.append({
        "speaker": current_speaker,
        "start": seg_start,
        "end": seg_end,
    })

    return segments


def _merge_short_segments(segments: list[dict], min_duration: float) -> list[dict]:
    """Absorb segments shorter than min_duration into their neighbors.

    Short segments are merged into the previous segment (extending its end time).
    If there is no previous segment, they are merged into the next one.
    """
    if not segments:
        return []

    merged = [segments[0].copy()]

    for seg in segments[1:]:
        duration = seg["end"] - seg["start"]
        if duration < min_duration:
            # Absorb into the previous segment
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(seg.copy())

    # Check if the first segment is too short after merging
    if len(merged) > 1 and (merged[0]["end"] - merged[0]["start"]) < min_duration:
        merged[1]["start"] = merged[0]["start"]
        merged.pop(0)

    return merged


def _fill_gaps(segments: list[dict], total_duration: float) -> list[dict]:
    """Extend segment boundaries to cover 0..total_duration with no gaps.

    Gaps between segments are split at the midpoint and assigned to the
    adjacent segments. The first segment is extended to start at 0, and
    the last segment is extended to end at total_duration.
    """
    if not segments:
        return []

    filled = [seg.copy() for seg in segments]

    # Extend first segment to start of video
    filled[0]["start"] = 0.0

    # Fill gaps between segments
    for i in range(len(filled) - 1):
        gap_start = filled[i]["end"]
        gap_end = filled[i + 1]["start"]
        if gap_end > gap_start:
            midpoint = (gap_start + gap_end) / 2
            filled[i]["end"] = midpoint
            filled[i + 1]["start"] = midpoint

    # Extend last segment to end of video
    filled[-1]["end"] = total_duration

    return filled


def _detect_active_speaker(
    video_a: str, video_b: str, start: float, duration: float
) -> str:
    """Detect which video shows the active speaker using mouth-movement analysis.

    Extracts frames from a sample window, detects faces with OpenCV Haar cascades,
    crops the mouth region (lower 1/3 of face bbox), and computes frame-to-frame
    pixel difference variance. The video with higher variance is the active speaker.

    Returns "a" or "b".
    """
    import cv2
    import numpy as np

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    def _mouth_variance(video_path: str) -> float:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        start_frame = int(start * fps)
        end_frame = int((start + duration) * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        prev_mouth = None
        diffs = []

        frame_idx = start_frame
        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1

            # Sample every 3rd frame for performance
            if (frame_idx - start_frame) % 3 != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            if len(faces) == 0:
                continue

            # Use the largest face
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])

            # Mouth region: lower 1/3 of face bounding box
            mouth_y = y + int(2 * h / 3)
            mouth_region = gray[mouth_y : y + h, x : x + w]

            if mouth_region.size == 0:
                continue

            # Resize to consistent dimensions for comparison
            mouth_region = cv2.resize(mouth_region, (64, 32))

            if prev_mouth is not None:
                diff = np.mean(np.abs(mouth_region.astype(float) - prev_mouth.astype(float)))
                diffs.append(diff)

            prev_mouth = mouth_region

        cap.release()

        if not diffs:
            return 0.0
        return float(np.var(diffs))

    var_a = _mouth_variance(video_a)
    var_b = _mouth_variance(video_b)

    return "a" if var_a >= var_b else "b"


def register(mcp: FastMCP):

    @mcp.tool()
    async def podcast_diarize(
        file_path: str,
        num_speakers: int = 2,
        language_code: str | None = None,
    ) -> str:
        """Diarize a podcast audio/video to identify who speaks when using ElevenLabs Scribe v2.

        Returns a JSON string with speakers and timestamped segments.

        Args:
            file_path: Path to the audio or video file.
            num_speakers: Expected number of speakers (default: 2).
            language_code: Optional language code (e.g. "en", "es").
        """
        file_path = validate_file_exists(file_path)
        client = _get_elevenlabs_client()

        # Extract audio to temp mp3
        tmp_dir = tempfile.mkdtemp(prefix="podcast_diarize_")
        tmp_audio = os.path.join(tmp_dir, "audio.mp3")

        try:
            result = run_ffmpeg([
                "-i", file_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-ab", "128k",
                "-y", tmp_audio,
            ], tmp_audio)

            if not result.success:
                return f"Error extracting audio: {result.error}"

            # Call ElevenLabs Scribe v2
            kwargs = {
                "model_id": "scribe_v2",
                "diarize": True,
                "num_speakers": num_speakers,
                "timestamps_granularity": "word",
            }
            if language_code:
                kwargs["language_code"] = language_code

            with open(tmp_audio, "rb") as f:
                response = client.speech_to_text.convert(file=f, **kwargs)

            # Extract words with speaker info
            words = []
            if hasattr(response, "words") and response.words:
                for w in response.words:
                    words.append({
                        "text": w.text if hasattr(w, "text") else str(w),
                        "speaker_id": w.speaker_id if hasattr(w, "speaker_id") else None,
                        "start": w.start if hasattr(w, "start") else 0,
                        "end": w.end if hasattr(w, "end") else 0,
                    })

            # Collapse into contiguous speaker segments
            segments = _words_to_segments(words)

            # Gather unique speakers
            speakers = sorted(set(seg["speaker"] for seg in segments if seg["speaker"] is not None))

            # Get total duration
            data = probe_json(file_path)
            total_duration = float(data.get("format", {}).get("duration", 0))

            return json.dumps({
                "speakers": speakers,
                "segments": segments,
                "total_duration": total_duration,
            }, indent=2)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @mcp.tool()
    async def podcast_multicam_merge(
        video_a_path: str,
        video_b_path: str,
        segments_json: str,
        speaker_a: str,
        speaker_b: str,
        min_segment_duration: float = 0.5,
        output_path: str | None = None,
    ) -> str:
        """Merge two camera angles into one video based on speaker diarization segments.

        Takes diarization output and switches between camera A and camera B depending
        on which speaker is active. Uses audio from video A throughout for consistency.

        Args:
            video_a_path: Path to camera A video file.
            video_b_path: Path to camera B video file.
            segments_json: JSON string from podcast_diarize with speaker segments.
            speaker_a: Speaker ID that maps to camera A.
            speaker_b: Speaker ID that maps to camera B.
            min_segment_duration: Minimum segment length in seconds (default: 0.5). Shorter segments get merged.
            output_path: Output file path. Auto-generated if not provided.
        """
        video_a_path = validate_file_exists(video_a_path)
        video_b_path = validate_file_exists(video_b_path)

        if output_path is None:
            output_path = generate_output_path(video_a_path, "multicam")

        # Parse segments
        diarization = json.loads(segments_json)
        segments = diarization.get("segments", [])
        total_duration = diarization.get("total_duration", 0)

        if not segments:
            return "Error: No segments found in diarization data."

        # Filter short segments and fill gaps
        segments = _merge_short_segments(segments, min_segment_duration)
        segments = _fill_gaps(segments, total_duration)

        # Map speaker to video path
        speaker_to_video = {
            speaker_a: video_a_path,
            speaker_b: video_b_path,
        }

        # Detect codec info for both videos
        probe_a = probe_json(video_a_path)
        probe_b = probe_json(video_b_path)

        codec_a = None
        codec_b = None
        for s in probe_a.get("streams", []):
            if s.get("codec_type") == "video":
                codec_a = s.get("codec_name")
                break
        for s in probe_b.get("streams", []):
            if s.get("codec_type") == "video":
                codec_b = s.get("codec_name")
                break

        # Use stream copy if codecs match, otherwise re-encode
        use_copy = codec_a == codec_b

        tmp_dir = tempfile.mkdtemp(prefix="podcast_merge_")

        try:
            # Extract continuous audio from video A
            audio_path = os.path.join(tmp_dir, "audio.aac")
            audio_result = run_ffmpeg([
                "-i", video_a_path,
                "-vn", "-acodec", "aac", "-ab", "192k",
                "-y", audio_path,
            ], audio_path)

            if not audio_result.success:
                return f"Error extracting audio: {audio_result.error}"

            # Trim video segments from appropriate cameras
            segment_files = []
            segments_used = 0

            for i, seg in enumerate(segments):
                speaker = seg["speaker"]
                video_src = speaker_to_video.get(speaker, video_a_path)
                seg_path = os.path.join(tmp_dir, f"seg_{i:04d}.ts")

                start_time = str(seg["start"])
                duration = str(seg["end"] - seg["start"])

                if use_copy:
                    seg_result = run_ffmpeg([
                        "-i", video_src,
                        "-ss", start_time,
                        "-t", duration,
                        "-an",  # No audio — we'll mux continuous audio later
                        "-c:v", "copy",
                        "-f", "mpegts",
                        "-y", seg_path,
                    ], seg_path)
                else:
                    seg_result = run_ffmpeg([
                        "-i", video_src,
                        "-ss", start_time,
                        "-t", duration,
                        "-an",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-f", "mpegts",
                        "-y", seg_path,
                    ], seg_path)

                if seg_result.success:
                    segment_files.append(seg_path)
                    segments_used += 1

            if not segment_files:
                return "Error: No video segments were created successfully."

            # Write concat demuxer file
            concat_file = os.path.join(tmp_dir, "concat.txt")
            with open(concat_file, "w") as f:
                for seg_path in segment_files:
                    f.write(f"file '{seg_path}'\n")

            # Concatenate video segments (video only)
            video_only = os.path.join(tmp_dir, "video_only.mp4")
            concat_result = run_ffmpeg([
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-an",
                "-y", video_only,
            ], video_only)

            if not concat_result.success:
                return f"Error concatenating segments: {concat_result.error}"

            # Mux video + continuous audio
            final_result = run_ffmpeg([
                "-i", video_only,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-y", output_path,
            ], output_path)

            if not final_result.success:
                return f"Error muxing final video: {final_result.error}"

            segments_merged = len(diarization.get("segments", [])) - segments_used

            return json.dumps({
                "output_path": output_path,
                "segments_used": segments_used,
                "segments_merged": segments_merged,
                "total_duration": total_duration,
            }, indent=2)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @mcp.tool()
    async def podcast_multicam_edit(
        video_a_path: str,
        video_b_path: str,
        num_speakers: int = 2,
        min_segment_duration: float = 0.5,
        language_code: str | None = None,
        output_path: str | None = None,
    ) -> str:
        """End-to-end podcast multicam edit: diarize audio, auto-detect speaker cameras, merge.

        Given two video files of the same podcast (each focusing on one podcaster,
        same audio), this tool automatically:
        1. Diarizes the audio to identify speaker segments
        2. Auto-detects which camera shows which speaker using mouth-movement analysis
        3. Switches between cameras and merges into a final video

        Args:
            video_a_path: Path to first camera angle video.
            video_b_path: Path to second camera angle video.
            num_speakers: Expected number of speakers (default: 2).
            min_segment_duration: Minimum segment length in seconds (default: 0.5).
            language_code: Optional language code for diarization (e.g. "en").
            output_path: Output file path. Auto-generated if not provided.
        """
        video_a_path = validate_file_exists(video_a_path)
        video_b_path = validate_file_exists(video_b_path)

        if output_path is None:
            output_path = generate_output_path(video_a_path, "multicam_edit")

        # Step 1: Diarize
        diarize_result = await podcast_diarize(
            file_path=video_a_path,
            num_speakers=num_speakers,
            language_code=language_code,
        )

        diarization = json.loads(diarize_result)
        speakers = diarization.get("speakers", [])
        segments = diarization.get("segments", [])

        if len(speakers) < 2:
            return f"Error: Expected at least 2 speakers, found {len(speakers)}. Diarization result: {diarize_result}"

        # Step 2: Auto-detect speaker-to-camera mapping
        # Find a ~10-second segment where one speaker talks continuously
        speaker_a_id = speakers[0]
        sample_start = None
        sample_duration = 0

        for seg in segments:
            seg_duration = seg["end"] - seg["start"]
            if seg_duration >= 5.0:  # At least 5 seconds of continuous speech
                speaker_a_id = seg["speaker"]
                sample_start = seg["start"]
                sample_duration = min(seg_duration, 10.0)
                break

        if sample_start is None:
            # Fallback: use the longest segment
            longest = max(segments, key=lambda s: s["end"] - s["start"])
            speaker_a_id = longest["speaker"]
            sample_start = longest["start"]
            sample_duration = min(longest["end"] - longest["start"], 10.0)

        # Determine which video shows the active speaker
        active_camera = _detect_active_speaker(
            video_a_path, video_b_path, sample_start, sample_duration
        )

        # Map speakers to cameras
        # speaker_a_id was talking during the sample — active_camera shows them
        other_speaker = [s for s in speakers if s != speaker_a_id]
        speaker_b_id = other_speaker[0] if other_speaker else speakers[1]

        if active_camera == "a":
            speaker_for_cam_a = speaker_a_id
            speaker_for_cam_b = speaker_b_id
        else:
            speaker_for_cam_a = speaker_b_id
            speaker_for_cam_b = speaker_a_id

        # Step 3: Merge
        merge_result = await podcast_multicam_merge(
            video_a_path=video_a_path,
            video_b_path=video_b_path,
            segments_json=diarize_result,
            speaker_a=speaker_for_cam_a,
            speaker_b=speaker_for_cam_b,
            min_segment_duration=min_segment_duration,
            output_path=output_path,
        )

        # Enrich result with mapping info
        result = json.loads(merge_result)
        result["speaker_mapping"] = {
            "camera_a": speaker_for_cam_a,
            "camera_b": speaker_for_cam_b,
        }
        result["detection_method"] = "opencv_mouth_movement"
        result["sample_speaker"] = speaker_a_id
        result["sample_window"] = {
            "start": sample_start,
            "duration": sample_duration,
            "active_camera": active_camera,
        }

        return json.dumps(result, indent=2)
