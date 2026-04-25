"""
Speech-to-text module powered by OpenAI Whisper.
Converts Telegram audio messages into text for expense processing.
"""

import os
import logging
import re
import unicodedata
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from config/
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
load_dotenv(config_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|\b[a-z0-9][a-z0-9.-]*\.(?:com|co|net|org|info|io)\b)",
    re.IGNORECASE,
)
_KNOWN_BAD_TRANSCRIPTIONS = {
    "mas informacion www.alimmenta.com",
    "mas informacion en www.alimmenta.com",
}
_SPEECH_MODEL = "whisper-1"


class SpeechToTextProcessor:
    """Speech-to-text processor powered by OpenAI Whisper."""
    
    def __init__(self):
        """Initialize the processor with the OpenAI API key."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        logger.info("Speech-to-text processor initialized with OpenAI Whisper")
    
    def transcribe_audio(self, audio_file_path: str, language: str = "es") -> Optional[str]:
        """
        Transcribe an audio file to text with Whisper.
        
        Args:
            audio_file_path: Path to the audio file
            language: Language code (defaults to 'es' for Spanish)
            
        Returns:
            Transcribed text, or None if an error occurs
        """
        try:
            logger.debug(f"Transcribing audio file: {audio_file_path}")
            
            # Check the file size
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"Audio file size: {file_size / 1024:.1f} KB")
            
            # Whisper accepts files up to 25 MB
            if file_size > 25 * 1024 * 1024:
                logger.error("Audio file is too large (>25 MB)")
                return None
            
            with open(audio_file_path, "rb") as audio_file:
                # Use Whisper to transcribe the audio with a domain-specific prompt
                transcript = self.client.audio.transcriptions.create(
                    model=_SPEECH_MODEL,
                    file=audio_file,
                    language=language,
                    response_format="text",
                    # Improve transcription quality for expense-related audio
                    prompt="Transcribir mensaje sobre gastos en pesos colombianos. Incluye cantidades, lugares y cuentas bancarias."
                )
            
            # Whisper returns the raw text directly when response_format="text"
            transcribed_text = transcript.strip()
            
            if transcribed_text:
                logger.debug(
                    "Successful transcription",
                    extra={
                        "speech_model": _SPEECH_MODEL,
                        "transcript_preview": self._redacted_preview(transcribed_text),
                    },
                )
                return transcribed_text
            else:
                logger.warning("Received an empty transcription")
                return None
                
        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                logger.error("Audio transcription timed out; try a shorter recording")
                return "timeout_error"
            elif "rate_limit" in error_msg:
                logger.error("API rate limit reached during audio transcription")
                return "rate_limit_error"
            else:
                logger.error(f"Error transcribing audio: {e}")
                return None
    
    def process_telegram_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Process a Telegram audio file and return the transcribed text.
        
        Args:
            audio_file_path: Path to the audio file downloaded from Telegram
            
        Returns:
            Transcribed text optimized for expense processing
        """
        # Transcribe the audio first
        transcribed_text = self.transcribe_audio(audio_file_path, language="es")
        
        if not transcribed_text:
            return None

        if transcribed_text in {"timeout_error", "rate_limit_error"}:
            logger.warning(
                "Speech transcription provider returned an error marker",
                extra={"speech_model": _SPEECH_MODEL, "failure_class": transcribed_text},
            )
            return None
        
        # Clean and normalize the result for expense processing
        cleaned_text = self._clean_transcription(transcribed_text)

        rejection_reason = self._suspicious_transcription_reason(cleaned_text)
        if rejection_reason:
            logger.warning(
                "Rejected suspicious transcription",
                extra={
                    "speech_model": _SPEECH_MODEL,
                    "failure_class": rejection_reason,
                    "transcript_preview": self._redacted_preview(cleaned_text),
                },
            )
            return None
        
        logger.debug(
            "Cleaned transcription",
            extra={
                "speech_model": _SPEECH_MODEL,
                "transcript_preview": self._redacted_preview(cleaned_text),
            },
        )
        return cleaned_text

    @staticmethod
    def _normalize_for_detection(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        without_accents = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        return " ".join(without_accents.lower().split())

    @staticmethod
    def _redacted_preview(text: str, max_chars: int = 48) -> str:
        redacted = _URL_PATTERN.sub("[url]", text)
        redacted = " ".join(redacted.split())
        if len(redacted) <= max_chars:
            return redacted
        return f"{redacted[:max_chars].rstrip()}..."

    def _suspicious_transcription_reason(self, text: str) -> Optional[str]:
        normalized = self._normalize_for_detection(text)
        if not normalized:
            return "empty_transcription"

        if normalized in _KNOWN_BAD_TRANSCRIPTIONS:
            return "known_bad_boilerplate"

        urls = _URL_PATTERN.findall(normalized)
        if not urls:
            return None

        without_urls = _URL_PATTERN.sub("", normalized)
        non_url_tokens = re.findall(r"[a-záéíóúñü0-9]+", without_urls, re.IGNORECASE)
        if len(non_url_tokens) <= 2:
            return "url_dominant_transcription"

        boilerplate_terms = {"mas", "más", "informacion", "información", "info", "en"}
        if all(token in boilerplate_terms for token in non_url_tokens):
            return "url_boilerplate_transcription"

        return None
    
    def _clean_transcription(self, text: str) -> str:
        """
        Clean and normalize a transcription for downstream processing.
        
        Args:
            text: Original transcribed text
            
        Returns:
            Cleaned and normalized text
        """
        # Remove extra whitespace and normalize the text
        cleaned = text.strip()
        
        # Convert common spoken number patterns into numeric-friendly text
        replacements = {
            "mil": "000",
            "lucas": "000",
            "k": "000",
            "pesos": "",
            "peso": "",
            "con mi": "con mi",
            "usando": "con mi",
            "pagué con": "con mi",
            "gasté con": "con mi"
        }
        
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        
        # Collapse repeated whitespace
        cleaned = " ".join(cleaned.split())
        
        return cleaned

# Utility helper for manual testing
def test_speech_to_text():
    """Run a simple smoke test for the speech-to-text module."""
    try:
        processor = SpeechToTextProcessor()
        print("Speech-to-text processor initialized successfully")
        print("Ready to process Telegram audio messages")
        return True
    except Exception as e:
        print(f"Error initializing speech-to-text processor: {e}")
        return False

if __name__ == "__main__":
    test_speech_to_text()
