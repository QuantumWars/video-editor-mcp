"""ElevenLabs API tools — TTS, voice clone, vocal isolation, noise removal, SFX."""

import os

from mcp.server.fastmcp import FastMCP


def _get_client():
    """Lazily create an ElevenLabs client."""
    from elevenlabs.client import ElevenLabs
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY environment variable is not set.")
    return ElevenLabs(api_key=api_key)


def register(mcp: FastMCP):

    @mcp.tool()
    async def generate_voiceover(
        text: str,
        output_path: str,
        voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
        model_id: str = "eleven_multilingual_v2",
        language: str | None = None,
    ) -> str:
        """Generate a voiceover from text using ElevenLabs text-to-speech.

        Args:
            text: The text to convert to speech.
            output_path: Path to save the audio file (e.g. "voiceover.mp3").
            voice_id: ElevenLabs voice ID (default: George). Use list_voices to find IDs.
            model_id: Model to use (default: eleven_multilingual_v2).
            language: Optional language code (e.g. "en", "es", "fr").
        """
        client = _get_client()
        kwargs = {
            "text": text,
            "voice_id": voice_id,
            "model_id": model_id,
        }
        if language:
            kwargs["language_code"] = language

        audio = client.text_to_speech.convert(**kwargs)

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        return f"Voiceover saved to {output_path}"

    @mcp.tool()
    async def list_voices() -> str:
        """List all available ElevenLabs voices with their IDs and details."""
        import json
        client = _get_client()
        response = client.voices.get_all()
        voices = []
        for voice in response.voices:
            voices.append({
                "voice_id": voice.voice_id,
                "name": voice.name,
                "category": voice.category,
                "labels": voice.labels,
            })
        return json.dumps(voices, indent=2, default=str)

    @mcp.tool()
    async def clone_voice(
        name: str,
        audio_sample_paths: list[str],
        description: str = "",
    ) -> str:
        """Create an instant voice clone from audio samples.

        Args:
            name: Name for the cloned voice.
            audio_sample_paths: List of paths to audio sample files (at least 1).
            description: Optional description of the voice.
        """
        from clipping.utils.media import validate_file_exists

        files = []
        for path in audio_sample_paths:
            validated = validate_file_exists(path)
            files.append(open(validated, "rb"))

        try:
            client = _get_client()
            voice = client.clone(
                name=name,
                description=description,
                files=files,
            )
            return f"Voice cloned successfully. Voice ID: {voice.voice_id}, Name: {voice.name}"
        finally:
            for f in files:
                f.close()

    @mcp.tool()
    async def isolate_vocals(
        file_path: str,
        output_path: str | None = None,
    ) -> str:
        """Separate vocals from background music/noise using ElevenLabs audio isolation.

        Args:
            file_path: Path to the audio/video file.
            output_path: Path to save the isolated vocals. Auto-generated if not provided.
        """
        from clipping.utils.media import validate_file_exists, generate_output_path

        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "vocals", ".mp3")

        client = _get_client()
        with open(file_path, "rb") as f:
            audio = client.audio_isolation.audio_isolation(audio=f)

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        return f"Isolated vocals saved to {output_path}"

    @mcp.tool()
    async def remove_background_noise(
        file_path: str,
        output_path: str | None = None,
    ) -> str:
        """Remove background noise from an audio file using ElevenLabs.

        Args:
            file_path: Path to the audio file.
            output_path: Path to save the cleaned audio. Auto-generated if not provided.
        """
        from clipping.utils.media import validate_file_exists, generate_output_path

        file_path = validate_file_exists(file_path)
        if output_path is None:
            output_path = generate_output_path(file_path, "cleaned", ".mp3")

        client = _get_client()
        with open(file_path, "rb") as f:
            audio = client.audio_isolation.audio_isolation(audio=f)

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        return f"Cleaned audio saved to {output_path}"

    @mcp.tool()
    async def generate_sound_effect(
        description: str,
        output_path: str,
        duration: float | None = None,
    ) -> str:
        """Generate a sound effect from a text description using ElevenLabs.

        Args:
            description: Text description of the desired sound effect (e.g. "thunder rolling in the distance").
            output_path: Path to save the sound effect audio file.
            duration: Optional duration in seconds. If not provided, ElevenLabs decides.
        """
        client = _get_client()
        kwargs = {
            "text": description,
        }
        if duration is not None:
            kwargs["duration_seconds"] = duration

        audio = client.text_to_sound_effects.convert(**kwargs)

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        return f"Sound effect saved to {output_path}"
