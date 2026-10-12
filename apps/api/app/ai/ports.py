from abc import ABC, abstractmethod
from typing import Dict, Any

class TextGeneratorPort(ABC):
    """Puerto para generador de texto (Gemini o FakeAdapter)."""
    @abstractmethod
    async def generate_text(self, prompt: str, context: Dict[str, Any]) -> str:
        pass

class AudioProcessorPort(ABC):
    """Puerto para procesamiento de audio (extensión futura)."""
    @abstractmethod
    async def process_audio(self, audio_data: bytes) -> str:
        pass

class VisionAnalyzerPort(ABC):
    """Puerto para análisis de visión/postura (extensión futura)."""
    @abstractmethod
    async def analyze_image(self, image_data: bytes) -> Dict[str, Any]:
        pass
