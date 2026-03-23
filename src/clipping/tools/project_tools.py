"""Project state management tools — create, modify, and render edit decision lists."""

import json
import os
import subprocess
import tempfile
import shutil
import uuid
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP

from clipping.utils.ffmpeg import run_ffmpeg, probe_json
from clipping.utils.media import validate_file_exists, generate_output_path
from clipping import __version__


# Bundled editor source (inside the installed package)
_BUNDLED_EDITOR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "editor"
)

DEFAULT_PROJECT_DIR = os.path.expanduser("~/.clipping")
DEFAULT_PROJECT_PATH = os.path.join(DEFAULT_PROJECT_DIR, "project.json")


def _load_project(project_path: str = DEFAULT_PROJECT_PATH) -> dict:
    """Load project state from disk."""
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"No project found at {project_path}. Create one first with project_create.")
    with open(project_path, "r") as f:
        return json.load(f)


def _save_project(project: dict, project_path: str = DEFAULT_PROJECT_PATH) -> None:
    """Save project state to disk."""
    project["updatedAt"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(project_path), exist_ok=True)
    with open(project_path, "w") as f:
        json.dump(project, f, indent=2)


def _get_duration(file_path: str) -> float:
    """Get duration of a media file in seconds."""
    info = probe_json(file_path)
    duration = info.get("format", {}).get("duration")
    if duration is not None:
        return float(duration)
    # Fallback: check streams
    for stream in info.get("streams", []):
        d = stream.get("duration")
        if d is not None:
            return float(d)
    raise RuntimeError(f"Could not determine duration for {file_path}")


def _ensure_editor() -> str:
    """Ensure the Remotion editor is extracted and npm-installed at ~/.clipping/editor/.

    Returns the path to the ready-to-use editor directory.
    Raises RuntimeError on failure.
    """
    target_dir = os.path.join(DEFAULT_PROJECT_DIR, "editor")
    version_file = os.path.join(target_dir, ".clipping-version")

    # Check if already set up with matching version
    if (
        os.path.isfile(version_file)
        and os.path.isdir(os.path.join(target_dir, "node_modules"))
    ):
        with open(version_file, "r") as f:
            installed_version = f.read().strip()
        if installed_version == __version__:
            return target_dir

    # Verify bundled editor exists
    if not os.path.isdir(_BUNDLED_EDITOR_DIR):
        raise RuntimeError(
            f"Bundled editor not found at {_BUNDLED_EDITOR_DIR}. "
            "Reinstall the clipping-mcp package."
        )

    # Verify Node.js is available
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Node.js is required for rendering but was not found on PATH. "
            "Install Node.js 18+ from https://nodejs.org"
        )

    # Copy bundled editor source (excluding node_modules/dist/media/preview-props)
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)

    shutil.copytree(
        _BUNDLED_EDITOR_DIR,
        target_dir,
        ignore=shutil.ignore_patterns(
            "node_modules", "dist", "media", "preview-props.json"
        ),
    )

    # Run npm ci for deterministic install from package-lock.json
    try:
        result = subprocess.run(
            ["npm", "ci"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            stderr = result.stderr[-1000:] if result.stderr else "No error output"
            raise RuntimeError(f"npm ci failed:\n{stderr}")
    except FileNotFoundError:
        raise RuntimeError(
            "npm is required for rendering but was not found on PATH. "
            "Install Node.js 18+ from https://nodejs.org"
        )

    # Write version marker on success
    with open(version_file, "w") as f:
        f.write(__version__)

    return target_dir


def register(mcp: FastMCP):

    # ── Project lifecycle ───────────────────────────────────────

    @mcp.tool()
    async def project_create(
        name: str = "Untitled Project",
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        project_path: str | None = None,
    ) -> str:
        """Create a new video editing project.

        Args:
            name: Project name.
            fps: Frames per second for the project.
            width: Output video width in pixels.
            height: Output video height in pixels.
            project_path: Where to save the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = {
            "id": str(uuid.uuid4()),
            "name": name,
            "fps": fps,
            "width": width,
            "height": height,
            "clips": [],
            "overlays": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        _save_project(project, path)
        return f"Project '{name}' created at {path}"

    # ── Clip tools ──────────────────────────────────────────────

    @mcp.tool()
    async def project_add_clip(
        source: str,
        start_time: float = 0.0,
        end_time: float | None = None,
        speed: float = 1.0,
        volume: float = 1.0,
        track: int = 0,
        position: int | None = None,
        project_path: str | None = None,
    ) -> str:
        """Add a clip to the project timeline.

        Args:
            source: Path to the source video/audio file.
            start_time: In-point in seconds (where to start in the source).
            end_time: Out-point in seconds (where to stop in the source). Defaults to end of file.
            speed: Playback speed multiplier (1.0 = normal).
            volume: Volume multiplier (1.0 = normal, 0.0 = mute).
            track: Track number (0 = V1, 1 = V2, etc. Negative = audio-only, -1 = A1).
            position: Insert position among clips on the same track (0-indexed). Defaults to end.
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        source = validate_file_exists(source)
        project = _load_project(path)

        if end_time is None:
            end_time = _get_duration(source)

        if start_time < 0:
            return "Error: start_time must be >= 0"
        if end_time <= start_time:
            return "Error: end_time must be greater than start_time"
        if speed <= 0:
            return "Error: speed must be > 0"

        clip = {
            "id": f"clip_{uuid.uuid4().hex[:8]}",
            "source": source,
            "startTime": start_time,
            "endTime": end_time,
            "speed": speed,
            "volume": volume,
            "track": track,
        }

        # Scope position to clips on the same track
        track_clips = [c for c in project["clips"] if c.get("track", 0) == track]
        other_clips = [c for c in project["clips"] if c.get("track", 0) != track]

        if position is not None and 0 <= position <= len(track_clips):
            track_clips.insert(position, clip)
        else:
            track_clips.append(clip)

        project["clips"] = other_clips + track_clips

        _save_project(project, path)
        clip_duration = (end_time - start_time) / speed
        return f"Added clip '{clip['id']}' from {os.path.basename(source)} ({start_time:.1f}s - {end_time:.1f}s, {clip_duration:.1f}s at {speed}x) on track {track}. Total clips: {len(project['clips'])}"

    @mcp.tool()
    async def project_update_clip(
        clip_id: str,
        start_time: float | None = None,
        end_time: float | None = None,
        speed: float | None = None,
        volume: float | None = None,
        source: str | None = None,
        track: int | None = None,
        project_path: str | None = None,
    ) -> str:
        """Update properties of an existing clip.

        Args:
            clip_id: ID of the clip to update.
            start_time: New in-point in seconds.
            end_time: New out-point in seconds.
            speed: New playback speed multiplier.
            volume: New volume multiplier.
            source: New source file path.
            track: New track number (0 = V1, 1 = V2, negative = audio-only).
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        clip = next((c for c in project["clips"] if c["id"] == clip_id), None)
        if clip is None:
            return f"Error: Clip '{clip_id}' not found"

        if source is not None:
            clip["source"] = validate_file_exists(source)
        if start_time is not None:
            clip["startTime"] = start_time
        if end_time is not None:
            clip["endTime"] = end_time
        if speed is not None:
            if speed <= 0:
                return "Error: speed must be > 0"
            clip["speed"] = speed
        if volume is not None:
            clip["volume"] = volume
        if track is not None:
            clip["track"] = track

        if clip["endTime"] <= clip["startTime"]:
            return "Error: endTime must be greater than startTime"

        _save_project(project, path)
        return f"Updated clip '{clip_id}'"

    @mcp.tool()
    async def project_remove_clip(
        clip_id: str,
        project_path: str | None = None,
    ) -> str:
        """Remove a clip from the project timeline.

        Args:
            clip_id: ID of the clip to remove.
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        original_count = len(project["clips"])
        project["clips"] = [c for c in project["clips"] if c["id"] != clip_id]

        if len(project["clips"]) == original_count:
            return f"Error: Clip '{clip_id}' not found"

        _save_project(project, path)
        return f"Removed clip '{clip_id}'. Remaining clips: {len(project['clips'])}"

    @mcp.tool()
    async def project_reorder_clips(
        clip_ids: list[str],
        track: int = 0,
        project_path: str | None = None,
    ) -> str:
        """Reorder clips on the timeline by providing the full list of clip IDs in the desired order.

        Args:
            clip_ids: Ordered list of all clip IDs defining the new order.
            track: Track number to reorder clips on (default 0). Only clips on this track are affected.
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        track_clips = [c for c in project["clips"] if c.get("track", 0) == track]
        other_clips = [c for c in project["clips"] if c.get("track", 0) != track]

        existing_ids = {c["id"] for c in track_clips}
        provided_ids = set(clip_ids)

        if existing_ids != provided_ids:
            missing = existing_ids - provided_ids
            extra = provided_ids - existing_ids
            parts = []
            if missing:
                parts.append(f"missing: {missing}")
            if extra:
                parts.append(f"unknown: {extra}")
            return f"Error: Clip IDs don't match for track {track}. {', '.join(parts)}"

        clip_map = {c["id"]: c for c in track_clips}
        reordered = [clip_map[cid] for cid in clip_ids]

        project["clips"] = other_clips + reordered

        _save_project(project, path)
        return f"Reordered {len(reordered)} clips on track {track}"

    # ── Overlay tools ───────────────────────────────────────────

    @mcp.tool()
    async def project_add_overlay(
        overlay_type: str,
        start_time: float,
        duration: float,
        text: str | None = None,
        x: str = "center",
        y: str = "center",
        font_size: int = 64,
        font_family: str = "sans-serif",
        font_weight: str = "bold",
        color: str = "#ffffff",
        background_color: str | None = None,
        padding: int | None = None,
        border_radius: int | None = None,
        animation: str = "none",
        animation_duration: float = 0.5,
        words_json: str | None = None,
        caption_style: str = "default",
        caption_position: str = "bottom",
        active_color: str = "#FFD700",
        max_words_per_line: int = 6,
        source: str | None = None,
        width: int = 200,
        height: int = 200,
        opacity: float = 1.0,
        project_path: str | None = None,
    ) -> str:
        """Add a text, caption, or image overlay to the project.

        Args:
            overlay_type: Type of overlay — "text", "caption", or "image".
            start_time: When the overlay appears (in seconds from project start).
            duration: How long the overlay is visible (in seconds).
            text: Text content (for "text" overlays).
            x: Horizontal position — "center", a percentage like "50%", or pixels like "100".
            y: Vertical position — "center", a percentage like "50%", or pixels like "100".
            font_size: Font size in pixels (for text/caption overlays).
            font_family: CSS font family (for text overlays).
            font_weight: CSS font weight (for text overlays).
            color: Text color as hex string (for text/caption overlays).
            background_color: Background color as hex string (optional).
            padding: Padding in pixels (for text overlays).
            border_radius: Border radius in pixels (for text overlays).
            animation: Animation type — "none", "fadeIn", "fadeOut", "fadeInOut", "slideUp", "typewriter" (for text/image overlays).
            animation_duration: Duration of the animation in seconds.
            words_json: JSON array of {text, startTime, endTime} objects (for "caption" overlays).
            caption_style: Caption display style — "default", "karaoke", "bounce", "highlight".
            caption_position: Caption position — "bottom", "center", "top".
            active_color: Color for the currently spoken word (for captions).
            max_words_per_line: Maximum words per line (for captions).
            source: Path to image file (for "image" overlays).
            width: Width in pixels (for image overlays).
            height: Height in pixels (for image overlays).
            opacity: Opacity 0.0-1.0 (for image overlays).
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        if "overlays" not in project:
            project["overlays"] = []

        overlay_id = f"ovr_{uuid.uuid4().hex[:8]}"

        if overlay_type == "text":
            if not text:
                return "Error: 'text' is required for text overlays"
            overlay = {
                "id": overlay_id,
                "type": "text",
                "text": text,
                "startTime": start_time,
                "duration": duration,
                "x": x,
                "y": y,
                "fontSize": font_size,
                "fontFamily": font_family,
                "fontWeight": font_weight,
                "color": color,
                "animation": animation,
                "animationDuration": animation_duration,
            }
            if background_color:
                overlay["backgroundColor"] = background_color
            if padding is not None:
                overlay["padding"] = padding
            if border_radius is not None:
                overlay["borderRadius"] = border_radius

        elif overlay_type == "caption":
            if not words_json:
                return "Error: 'words_json' is required for caption overlays (JSON array of {text, startTime, endTime})"
            try:
                words = json.loads(words_json)
            except json.JSONDecodeError:
                return "Error: 'words_json' is not valid JSON"
            overlay = {
                "id": overlay_id,
                "type": "caption",
                "words": words,
                "startTime": start_time,
                "duration": duration,
                "style": caption_style,
                "position": caption_position,
                "fontSize": font_size,
                "color": color,
                "activeColor": active_color,
                "maxWordsPerLine": max_words_per_line,
            }
            if background_color:
                overlay["backgroundColor"] = background_color

        elif overlay_type == "image":
            if not source:
                return "Error: 'source' is required for image overlays"
            source = validate_file_exists(source)
            overlay = {
                "id": overlay_id,
                "type": "image",
                "source": source,
                "startTime": start_time,
                "duration": duration,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "opacity": opacity,
                "animation": animation,
            }
        else:
            return f"Error: Unknown overlay type '{overlay_type}'. Use 'text', 'caption', or 'image'."

        project["overlays"].append(overlay)
        _save_project(project, path)
        return f"Added {overlay_type} overlay '{overlay_id}' at {start_time:.1f}s for {duration:.1f}s. Total overlays: {len(project['overlays'])}"

    @mcp.tool()
    async def project_update_overlay(
        overlay_id: str,
        text: str | None = None,
        start_time: float | None = None,
        duration: float | None = None,
        x: str | None = None,
        y: str | None = None,
        font_size: int | None = None,
        font_family: str | None = None,
        font_weight: str | None = None,
        color: str | None = None,
        background_color: str | None = None,
        animation: str | None = None,
        animation_duration: float | None = None,
        active_color: str | None = None,
        caption_style: str | None = None,
        caption_position: str | None = None,
        opacity: float | None = None,
        width: int | None = None,
        height: int | None = None,
        project_path: str | None = None,
    ) -> str:
        """Update properties of an existing overlay.

        Args:
            overlay_id: ID of the overlay to update.
            text: New text content (for text overlays).
            start_time: New start time in seconds.
            duration: New duration in seconds.
            x: New horizontal position.
            y: New vertical position.
            font_size: New font size.
            font_family: New font family.
            font_weight: New font weight.
            color: New text color.
            background_color: New background color.
            animation: New animation type.
            animation_duration: New animation duration.
            active_color: New active word color (for captions).
            caption_style: New caption style.
            caption_position: New caption position.
            opacity: New opacity (for image overlays).
            width: New width (for image overlays).
            height: New height (for image overlays).
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)
        overlays = project.get("overlays", [])

        overlay = next((o for o in overlays if o["id"] == overlay_id), None)
        if overlay is None:
            return f"Error: Overlay '{overlay_id}' not found"

        field_map = {
            "text": text,
            "startTime": start_time,
            "duration": duration,
            "x": x,
            "y": y,
            "fontSize": font_size,
            "fontFamily": font_family,
            "fontWeight": font_weight,
            "color": color,
            "backgroundColor": background_color,
            "animation": animation,
            "animationDuration": animation_duration,
            "activeColor": active_color,
            "style": caption_style,
            "position": caption_position,
            "opacity": opacity,
            "width": width,
            "height": height,
        }

        updated = []
        for key, value in field_map.items():
            if value is not None:
                overlay[key] = value
                updated.append(key)

        if not updated:
            return "No fields to update"

        _save_project(project, path)
        return f"Updated overlay '{overlay_id}': {', '.join(updated)}"

    @mcp.tool()
    async def project_remove_overlay(
        overlay_id: str,
        project_path: str | None = None,
    ) -> str:
        """Remove an overlay from the project.

        Args:
            overlay_id: ID of the overlay to remove.
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)
        overlays = project.get("overlays", [])

        original_count = len(overlays)
        project["overlays"] = [o for o in overlays if o["id"] != overlay_id]

        if len(project["overlays"]) == original_count:
            return f"Error: Overlay '{overlay_id}' not found"

        _save_project(project, path)
        return f"Removed overlay '{overlay_id}'. Remaining overlays: {len(project['overlays'])}"

    # ── Transition tools ────────────────────────────────────────

    @mcp.tool()
    async def project_add_transition(
        clip_id: str,
        transition_type: str = "fade",
        duration: float = 0.5,
        direction: str | None = None,
        timing: str = "linear",
        project_path: str | None = None,
    ) -> str:
        """Add a transition after a clip (plays between this clip and the next).

        Args:
            clip_id: ID of the clip to attach the transition to.
            transition_type: Transition type — "fade", "slide", "wipe", "flip", "clockWipe".
            duration: Duration of the transition in seconds.
            direction: Direction for slide/wipe/flip — "from-left", "from-right", "from-top", "from-bottom".
            timing: Timing function — "linear" or "spring".
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        valid_types = {"fade", "slide", "wipe", "flip", "clockWipe", "none"}
        if transition_type not in valid_types:
            return f"Error: Invalid transition type '{transition_type}'. Use one of: {', '.join(sorted(valid_types))}"

        clip = next((c for c in project["clips"] if c["id"] == clip_id), None)
        if clip is None:
            return f"Error: Clip '{clip_id}' not found"

        # Check it's not the last clip
        clip_index = next(i for i, c in enumerate(project["clips"]) if c["id"] == clip_id)
        if clip_index >= len(project["clips"]) - 1:
            return "Error: Cannot add a transition to the last clip (transitions play between two clips)"

        transition = {
            "id": f"tr_{uuid.uuid4().hex[:8]}",
            "type": transition_type,
            "duration": duration,
            "timing": timing,
        }
        if direction:
            transition["direction"] = direction

        clip["transition"] = transition
        _save_project(project, path)
        return f"Added {transition_type} transition ({duration:.1f}s) after clip '{clip_id}'"

    @mcp.tool()
    async def project_remove_transition(
        clip_id: str,
        project_path: str | None = None,
    ) -> str:
        """Remove the transition from a clip.

        Args:
            clip_id: ID of the clip to remove the transition from.
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        clip = next((c for c in project["clips"] if c["id"] == clip_id), None)
        if clip is None:
            return f"Error: Clip '{clip_id}' not found"

        if "transition" not in clip or clip["transition"] is None:
            return f"Clip '{clip_id}' has no transition to remove"

        del clip["transition"]
        _save_project(project, path)
        return f"Removed transition from clip '{clip_id}'"

    # ── Project state ───────────────────────────────────────────

    @mcp.tool()
    async def project_get_state(
        project_path: str | None = None,
    ) -> str:
        """Get the current project state as JSON.

        Args:
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        # Build a human-readable summary alongside the JSON
        clips_summary = []
        total_duration = 0.0
        for i, clip in enumerate(project["clips"]):
            clip_dur = (clip["endTime"] - clip["startTime"]) / clip.get("speed", 1.0)
            total_duration += clip_dur
            transition_info = ""
            if clip.get("transition"):
                t = clip["transition"]
                transition_info = f" → [{t['type']} {t.get('duration', 0.5)}s]"
                total_duration -= t.get("duration", 0) if i < len(project["clips"]) - 1 else 0
            effects_info = ""
            if clip.get("effects"):
                effects_info = f" [effects: {', '.join(e['type'] for e in clip['effects'])}]"
            clips_summary.append(
                f"  {i}: [{clip['id']}] {os.path.basename(clip['source'])} "
                f"{clip['startTime']:.1f}s-{clip['endTime']:.1f}s "
                f"(speed={clip.get('speed', 1.0)}x, vol={clip.get('volume', 1.0)}, dur={clip_dur:.1f}s)"
                f"{transition_info}{effects_info}"
            )

        overlays = project.get("overlays", [])
        overlays_summary = []
        for i, ovr in enumerate(overlays):
            label = ""
            if ovr["type"] == "text":
                label = f" \"{ovr.get('text', '')[:30]}\""
            elif ovr["type"] == "caption":
                word_count = len(ovr.get("words", []))
                label = f" ({word_count} words, {ovr.get('style', 'default')})"
            elif ovr["type"] == "image":
                label = f" {os.path.basename(ovr.get('source', ''))}"
            overlays_summary.append(
                f"  {i}: [{ovr['id']}] {ovr['type']}{label} "
                f"{ovr['startTime']:.1f}s-{ovr['startTime'] + ovr['duration']:.1f}s"
            )

        summary_parts = [
            f"Project: {project['name']} ({project['width']}x{project['height']} @ {project['fps']}fps)",
            f"Total duration: {total_duration:.1f}s",
            f"Clips ({len(project['clips'])}):",
        ]
        if clips_summary:
            summary_parts.extend(clips_summary)
        else:
            summary_parts.append("  (none)")

        if overlays:
            summary_parts.append(f"Overlays ({len(overlays)}):")
            summary_parts.extend(overlays_summary)

        summary = "\n".join(summary_parts)
        return f"{summary}\n\n---\n{json.dumps(project, indent=2)}"

    # ── Render ──────────────────────────────────────────────────

    @mcp.tool()
    async def project_render(
        output_path: str | None = None,
        project_path: str | None = None,
    ) -> str:
        """Render the project to a final video file using Remotion.

        Renders all clips with transitions, overlays, captions, and animations
        into a single output video.

        Args:
            output_path: Path for the rendered output file. Auto-generated if not provided.
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        if not project["clips"]:
            return "Error: Project has no clips to render"

        try:
            editor_dir = _ensure_editor()
        except RuntimeError as e:
            return f"Error: {e}"

        if output_path is None:
            safe_name = project["name"].replace(" ", "_").lower()
            output_path = os.path.join(os.getcwd(), f"{safe_name}_render.mp4")
            counter = 1
            base, ext = os.path.splitext(output_path)
            while os.path.exists(output_path):
                output_path = f"{base}_{counter}{ext}"
                counter += 1

        output_path = os.path.abspath(output_path)

        # Write project JSON to a temp file for Remotion to read
        tmp_props = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="clipping_props_"
        )
        try:
            json.dump(project, tmp_props, indent=2)
            tmp_props.close()

            cmd = [
                "npx", "remotion", "render",
                "src/index.ts",
                "Project",
                output_path,
                "--props", tmp_props.name,
            ]

            result = subprocess.run(
                cmd,
                cwd=editor_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                stderr = result.stderr[-1000:] if result.stderr else "No error output"
                return f"Error rendering: {stderr}"

            total_dur = sum(
                (c["endTime"] - c["startTime"]) / c.get("speed", 1.0)
                for c in project["clips"]
            )
            return f"Rendered {len(project['clips'])} clips ({total_dur:.1f}s) to {output_path}"

        finally:
            os.unlink(tmp_props.name)

    @mcp.tool()
    async def project_preview(
        project_path: str | None = None,
    ) -> str:
        """Launch Remotion Studio for browser-based live preview of the project.

        Opens a local dev server where you can preview the composition,
        scrub through the timeline, and see changes live.

        Args:
            project_path: Path to the project file. Defaults to ~/.clipping/project.json.
        """
        path = project_path or DEFAULT_PROJECT_PATH
        project = _load_project(path)

        try:
            editor_dir = _ensure_editor()
        except RuntimeError as e:
            return f"Error: {e}"

        # Symlink media files into editor/public/media/ so the browser can
        # access them, and rewrite the project JSON to use relative paths.
        media_dir = os.path.join(editor_dir, "public", "media")
        os.makedirs(media_dir, exist_ok=True)

        preview_project = json.loads(json.dumps(project))

        def _link_source(abs_path: str) -> str:
            """Create a symlink in public/media/ and return the relative path."""
            basename = os.path.basename(abs_path)
            link_path = os.path.join(media_dir, basename)
            # Handle name collisions by appending a hash
            if os.path.exists(link_path) and os.path.realpath(link_path) != os.path.realpath(abs_path):
                name, ext = os.path.splitext(basename)
                short_hash = uuid.uuid4().hex[:6]
                basename = f"{name}_{short_hash}{ext}"
                link_path = os.path.join(media_dir, basename)
            if not os.path.exists(link_path):
                os.symlink(os.path.abspath(abs_path), link_path)
            return f"media/{basename}"

        for clip in preview_project.get("clips", []):
            if clip.get("source") and os.path.isabs(clip["source"]):
                clip["source"] = _link_source(clip["source"])

        for ovr in preview_project.get("overlays", []):
            if ovr.get("source") and os.path.isabs(ovr["source"]):
                ovr["source"] = _link_source(ovr["source"])

        # Write the rewritten project JSON for the studio
        props_path = os.path.join(editor_dir, "public", "preview-props.json")
        with open(props_path, "w") as f:
            json.dump(preview_project, f, indent=2)

        cmd = [
            "npx", "remotion", "studio",
            "src/index.ts",
            "--props", props_path,
        ]

        subprocess.Popen(
            cmd,
            cwd=editor_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return (
            f"Remotion Studio launched. Open http://localhost:3000 to preview.\n"
            f"Media symlinked to {media_dir}\n"
            f"Props: {props_path}"
        )
