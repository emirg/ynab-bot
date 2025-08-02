"""
Módulo de Speech-to-Text usando OpenAI Whisper
Convierte mensajes de audio de Telegram a texto para procesamiento de gastos
"""

import os
import logging
import tempfile
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# Cargar variables de entorno desde config/
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
load_dotenv(config_path)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpeechToTextProcessor:
    """Procesador de speech-to-text usando OpenAI Whisper"""
    
    def __init__(self):
        """Inicializar el procesador con la API key de OpenAI"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY no encontrada en variables de entorno")
        
        self.client = OpenAI(api_key=api_key)
        logger.info("Speech-to-Text processor inicializado con OpenAI Whisper")
    
    def transcribe_audio(self, audio_file_path: str, language: str = "es") -> Optional[str]:
        """
        Transcribe un archivo de audio a texto usando Whisper
        
        Args:
            audio_file_path: Ruta al archivo de audio
            language: Código de idioma (por defecto 'es' para español)
            
        Returns:
            Texto transcrito o None si hay error
        """
        try:
            logger.info(f"🎤 Transcribiendo audio: {audio_file_path}")
            
            # Verificar tamaño del archivo
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"📊 Tamaño del archivo: {file_size / 1024:.1f} KB")
            
            # Limite de 25MB para Whisper
            if file_size > 25 * 1024 * 1024:
                logger.error("❌ Archivo de audio demasiado grande (>25MB)")
                return None
            
            with open(audio_file_path, "rb") as audio_file:
                # Usar Whisper para transcribir con timeout personalizado
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="text",
                    # Agregar prompt para mejorar transcripción de gastos
                    prompt="Transcribir mensaje sobre gastos en pesos colombianos. Incluye cantidades, lugares y cuentas bancarias."
                )
            
            # Whisper devuelve el texto directamente cuando response_format="text"
            transcribed_text = transcript.strip()
            
            if transcribed_text:
                logger.info(f"✅ Transcripción exitosa: '{transcribed_text}'")
                return transcribed_text
            else:
                logger.warning("⚠️ Transcripción vacía")
                return None
                
        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                logger.error("❌ Timeout transcribiendo audio - intenta con un audio más corto")
                return "timeout_error"
            elif "rate_limit" in error_msg:
                logger.error("❌ Límite de API alcanzado - espera un momento")
                return "rate_limit_error"
            else:
                logger.error(f"❌ Error transcribiendo audio: {e}")
                return None
    
    def process_telegram_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Procesa un archivo de audio de Telegram y devuelve el texto transcrito
        
        Args:
            audio_file_path: Ruta al archivo de audio descargado de Telegram
            
        Returns:
            Texto transcrito optimizado para procesamiento de gastos
        """
        # Transcribir el audio
        transcribed_text = self.transcribe_audio(audio_file_path, language="es")
        
        if not transcribed_text:
            return None
        
        # Limpiar y optimizar el texto para procesamiento de gastos
        cleaned_text = self._clean_transcription(transcribed_text)
        
        logger.info(f"🧹 Texto limpio: '{cleaned_text}'")
        return cleaned_text
    
    def _clean_transcription(self, text: str) -> str:
        """
        Limpia y optimiza la transcripción para mejor procesamiento
        
        Args:
            text: Texto transcrito original
            
        Returns:
            Texto limpio y optimizado
        """
        # Remover espacios extra y normalizar
        cleaned = text.strip()
        
        # Convertir números comunes hablados a formato numérico
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
        
        # Limpiar espacios múltiples
        cleaned = " ".join(cleaned.split())
        
        return cleaned

# Función de utilidad para testing
def test_speech_to_text():
    """Función de prueba para el módulo de speech-to-text"""
    try:
        processor = SpeechToTextProcessor()
        print("✅ Speech-to-Text processor inicializado correctamente")
        print("🎤 Listo para procesar mensajes de audio de Telegram")
        return True
    except Exception as e:
        print(f"❌ Error inicializando Speech-to-Text: {e}")
        return False

if __name__ == "__main__":
    test_speech_to_text()
