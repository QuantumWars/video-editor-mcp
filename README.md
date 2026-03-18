# clipping-mcp

MCP server for video/audio editing powered by FFmpeg and ElevenLabs.

## Prerequisites

- [FFmpeg](https://ffmpeg.org/download.html) installed and on PATH
- (Optional) `ELEVENLABS_API_KEY` env var for TTS, voice cloning, and audio isolation tools

## Install with Claude Code

```bash
claude mcp add clipping -- uvx --from "git+https://github.com/QuantumWars/video-editor-mcp" clipping
```

To pass your ElevenLabs API key:

```bash
claude mcp add clipping -e ELEVENLABS_API_KEY=your-key -- uvx --from "git+https://github.com/QuantumWars/video-editor-mcp" clipping
```

## Tools

### Analysis
- **get_media_info** — file duration, resolution, fps, codecs
- **detect_silence** — find silent segments
- **detect_scenes** — detect scene changes
- **extract_keyframes** — extract I-frames as images

### Video Editing
- **trim_video** — trim by start time + duration
- **cut_segment** — remove a segment
- **concatenate_videos** — join videos in sequence
- **change_speed** — speed up / slow down
- **convert_format** — change container/codec
- **scale_video** — resize
- **crop_video** — crop a region
- **add_fade** — fade in/out
- **add_overlay** — overlay image/video
- **add_subtitles** — burn subtitles (hard-sub)

### Audio
- **extract_audio** — extract audio track
- **replace_audio** — swap audio track
- **mix_audio** — mix two audio sources
- **segment_by_silence** — split at silent gaps

### ElevenLabs (requires API key)
- **generate_voiceover** — text-to-speech
- **list_voices** — list available voices
- **clone_voice** — instant voice clone
- **isolate_vocals** — separate vocals from music
- **remove_background_noise** — clean audio
- **generate_sound_effect** — text-to-SFX
