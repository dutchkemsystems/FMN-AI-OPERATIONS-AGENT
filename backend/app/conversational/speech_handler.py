"""Voice I/O via OpenAI Whisper when available."""
from __future__ import annotations
import io
from typing import Any

class VoiceUnavailable(RuntimeError):
    pass

class SpeechHandler:
    def __init__(self, settings: Any) -> None:
        self.enabled = settings.use_voice
        self._key = settings.openai_api_key

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        if not self.enabled:
            raise VoiceUnavailable("Voice interface disabled (USE_VOICE=false)")
        if not self._key:
            raise VoiceUnavailable("OPENAI_API_KEY required for speech-to-text")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._key)
            buf = io.BytesIO(audio_bytes)
            buf.name = filename
            transcript = client.audio.transcriptions.create(model="whisper-1", file=buf)
            return transcript.text
        except ImportError:
            raise VoiceUnavailable("openai SDK not installed")

    def synthesize(self, text: str) -> bytes | None:
        return None
