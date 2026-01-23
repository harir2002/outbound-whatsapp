"""
Sarvam AI Voice Service
Text-to-Speech and Speech-to-Text for multilingual voice calls
"""

import httpx
import base64
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.logging import logger


class SarvamVoiceService:
    """Sarvam AI service for voice synthesis and recognition"""
    
    def __init__(self):
        self.api_key = settings.SARVAM_API_KEY
        self.api_url = settings.SARVAM_API_URL
        self.tts_model = settings.SARVAM_TTS_MODEL
        self.stt_model = settings.SARVAM_STT_MODEL
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def text_to_speech(
        self,
        text: str,
        language: str = "en",
        speaker: str = "meera",
        speed: float = 1.0
    ) -> bytes:
        """
        Convert text to speech
        
        Args:
            text: Text to convert
            language: Language code (en, hi, ta, te, etc.)
            speaker: Voice speaker name
            speed: Speech speed (0.5-2.0)
        
        Returns:
            Audio bytes (WAV format)
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/text-to-speech",
                    headers=self.headers,
                    json={
                        "text": text,
                        "language_code": language,
                        "speaker": speaker,
                        "speed": speed,
                        "model": self.tts_model
                    },
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                # Get audio from response
                result = response.json()
                audio_base64 = result.get("audio", "")
                audio_bytes = base64.b64decode(audio_base64)
                
                logger.info(f"✅ TTS generated: {len(text)} chars -> {len(audio_bytes)} bytes")
                
                return audio_bytes
                
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Sarvam TTS HTTP Error: Status {e.response.status_code}")
            logger.error(f"   Response body: {e.response.text[:500]}")
            logger.warning(f"⚠️ TTS API failed, using demo mode")
            # Return mock audio data for demo purposes
            mock_audio = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
            logger.info(f"✅ TTS demo mode: {len(text)} chars -> mock audio")
            return mock_audio
                
        except Exception as e:
            logger.error(f"❌ Sarvam TTS Exception: {type(e).__name__}: {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
            logger.warning(f"⚠️ TTS API failed, using demo mode")
            # Return mock audio data for demo purposes
            mock_audio = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
            logger.info(f"✅ TTS demo mode: {len(text)} chars -> mock audio")
            return mock_audio
    
    async def speech_to_text(
        self,
        audio_bytes: bytes,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Convert speech to text
        
        Args:
            audio_bytes: Audio data (WAV/MP3)
            language: Expected language code
        
        Returns:
            Transcription result with text and confidence
        """
        try:
            # Encode audio to base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/speech-to-text",
                    headers=self.headers,
                    json={
                        "audio": audio_base64,
                        "language_code": language,
                        "model": self.stt_model
                    },
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                result = response.json()
                transcript = result.get("transcript", "")
                confidence = result.get("confidence", 0.0)
                
                logger.info(f"✅ STT transcribed: {len(audio_bytes)} bytes -> '{transcript[:50]}...'")
                
                return {
                    "transcript": transcript,
                    "confidence": confidence,
                    "language": language
                }
                
        except Exception as e:
            logger.error(f"❌ STT failed: {str(e)}")
            raise
    
    async def detect_language(self, audio_bytes: bytes) -> str:
        """
        Detect language from audio
        
        Args:
            audio_bytes: Audio data
        
        Returns:
            Detected language code
        """
        try:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/language-detection",
                    headers=self.headers,
                    json={"audio": audio_base64},
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                result = response.json()
                language = result.get("language_code", "en")
                
                logger.info(f"✅ Language detected: {language}")
                
                return language
                
        except Exception as e:
            logger.error(f"❌ Language detection failed: {str(e)}")
            return "en"  # Default to English
    
    async def get_available_voices(self, language: str = "en") -> List[Dict[str, Any]]:
        """
        Get available voice speakers
        
        Args:
            language: Language code
        
        Returns:
            List of available voices
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/voices",
                    headers=self.headers,
                    params={"language_code": language},
                    timeout=10.0
                )
                
                response.raise_for_status()
                
                voices = response.json().get("voices", [])
                
                logger.info(f"✅ Retrieved {len(voices)} voices for {language}")
                
                return voices
                
        except Exception as e:
            logger.error(f"❌ Failed to get voices: {str(e)}")
            return []
    
    def get_language_config(self, language: str) -> Dict[str, Any]:
        """
        Get language-specific configuration
        
        Args:
            language: Language code
        
        Returns:
            Language configuration
        """
        configs = {
            "en": {
                "name": "English",
                "speaker": "meera",
                "speed": 1.0
            },
            "hi": {
                "name": "Hindi",
                "speaker": "arvind",
                "speed": 0.95
            },
            "ta": {
                "name": "Tamil",
                "speaker": "amudha",
                "speed": 0.95
            },
            "te": {
                "name": "Telugu",
                "speaker": "bhavani",
                "speed": 0.95
            },
            "mr": {
                "name": "Marathi",
                "speaker": "aarohi",
                "speed": 0.95
            },
            "bn": {
                "name": "Bengali",
                "speaker": "ananya",
                "speed": 0.95
            }
        }
        
        return configs.get(language, configs["en"])


# Create singleton instance
sarvam_service = SarvamVoiceService()


# Export
__all__ = ["sarvam_service", "SarvamVoiceService"]
