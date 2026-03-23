# clipping-mcp

MCP server that gives Claude the power to edit your videos and audio — powered by FFmpeg and ElevenLabs.

**41 tools** for trimming, cutting, concatenating, speed changes, format conversion, audio extraction, AI voiceover, podcast multicam editing, timeline-based project editing with Remotion rendering, and more.

## Quick Start

### Prerequisites

- [FFmpeg](https://ffmpeg.org/download.html) installed and on PATH
- Python 3.11+
- [Node.js](https://nodejs.org) 18+ (for project rendering and preview via Remotion)
- (Optional) `ELEVENLABS_API_KEY` for TTS, voice cloning, and audio isolation

### Install with Claude Code

```bash
claude mcp add clipping -- uvx --from "git+https://github.com/QuantumWars/video-editor-mcp" clipping
```

With ElevenLabs API key:

```bash
claude mcp add clipping -e ELEVENLABS_API_KEY=your-key -- uvx --from "git+https://github.com/QuantumWars/video-editor-mcp" clipping
```

### Install from source

```bash
git clone https://github.com/QuantumWars/video-editor-mcp.git
cd video-editor-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then add to Claude Code:

```bash
claude mcp add clipping -- /path/to/video-editor-mcp/.venv/bin/clipping
```

## Tools

### Analysis (4 tools)

| Tool | Description |
|------|-------------|
| `get_media_info` | File duration, resolution, fps, codecs, stream details |
| `detect_silence` | Find silent segments with configurable threshold |
| `detect_scenes` | Detect scene changes with sensitivity control |
| `extract_keyframes` | Extract I-frames as PNG images |

### Video Editing (10 tools)

| Tool | Description |
|------|-------------|
| `trim_video` | Trim by start time + duration |
| `cut_segment` | Remove a segment between two timestamps |
| `concatenate_videos` | Join multiple videos in sequence |
| `change_speed` | Speed up / slow down with audio pitch correction |
| `convert_format` | Change container/codec with optional bitrate control |
| `scale_video` | Resize with auto-aspect-ratio support |
| `crop_video` | Crop a region with x,y offset |
| `add_fade` | Fade in/out effects (video + audio) |
| `add_overlay` | Overlay image or video with position control |
| `add_subtitles` | Burn subtitles into video (hard-sub) |

### Audio (4 tools)

| Tool | Description |
|------|-------------|
| `extract_audio` | Extract audio track (mp3, wav, aac, flac) |
| `replace_audio` | Swap audio track in a video |
| `mix_audio` | Mix two audio sources with volume control |
| `segment_by_silence` | Split file at silent gaps |

### ElevenLabs AI (6 tools, requires API key)

| Tool | Description |
|------|-------------|
| `generate_voiceover` | Text-to-speech with voice selection |
| `list_voices` | List available ElevenLabs voices |
| `clone_voice` | Instant voice clone from audio samples |
| `isolate_vocals` | Separate vocals from music/noise |
| `remove_background_noise` | Clean noisy audio |
| `generate_sound_effect` | Generate SFX from text description |

### Podcast Multicam (3 tools, requires API key + OpenCV)

| Tool | Description |
|------|-------------|
| `podcast_diarize` | Diarize audio via ElevenLabs Scribe v2 |
| `podcast_multicam_merge` | Merge two camera angles using speaker segments |
| `podcast_multicam_edit` | End-to-end: diarize + auto-detect speakers + merge |

### Project Timeline & Rendering (14 tools)

| Tool | Description |
|------|-------------|
| `project_create` | Create a new video editing project |
| `project_add_clip` | Add a clip to the timeline |
| `project_update_clip` | Update clip properties |
| `project_remove_clip` | Remove a clip |
| `project_reorder_clips` | Reorder clips on a track |
| `project_add_overlay` | Add text, caption, or image overlay |
| `project_update_overlay` | Update overlay properties |
| `project_remove_overlay` | Remove an overlay |
| `project_add_transition` | Add transition between clips |
| `project_remove_transition` | Remove a transition |
| `project_get_state` | View project state |
| `project_render` | Render to final video via Remotion |
| `project_preview` | Launch live preview in browser |

> **Auto-setup:** The Remotion editor is bundled with the package. On first `project_render` or `project_preview` call, it auto-extracts to `~/.clipping/editor/` and runs `npm install`. Subsequent calls skip setup unless the package version changes.

## Usage Examples

Once installed, just talk to Claude naturally:

- *"Trim the first 30 seconds off intro.mp4"*
- *"Extract the audio from interview.mp4 as mp3"*
- *"Speed up this clip 2x"*
- *"Concatenate part1.mp4 and part2.mp4"*
- *"Generate a voiceover saying 'Welcome to the show'"*
- *"Edit my podcast with two camera angles — switch between speakers automatically"*

## Architecture

```
src/clipping/
  server.py              # MCP entry point
  __init__.py            # Package version
  tools/
    analysis_tools.py    # Media info, silence/scene detection
    ffmpeg_tools.py      # Core video editing operations
    audio_tools.py       # Audio extraction, mixing, segmentation
    elevenlabs_tools.py  # AI voice and audio tools
    podcast_tools.py     # Multicam podcast editing
    project_tools.py     # Timeline, overlays, transitions, render
  utils/
    ffmpeg.py            # FFmpeg/FFprobe execution helpers
    media.py             # File validation and path utilities
  editor/                # Bundled Remotion editor (auto-extracted on first render)
```

## License

MIT
