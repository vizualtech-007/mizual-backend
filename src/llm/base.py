"""
Base LLM Provider Interface
Defines the common interface that all LLM providers must implement
"""

from abc import ABC, abstractmethod
import os
import pyvips
from ..logger import logger

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self):
        """Initialize provider with common configuration"""
        self.max_dimension = int(os.environ.get("LLM_MAX_IMAGE_DIMENSION", "1024"))

    @abstractmethod
    def enhance_prompt(self, prompt, image_data):
        """
        Enhance a user prompt using the image context
        """
        pass

    def _get_image_format(self, image_data: bytes) -> str:
        """Get image format using pyvips."""
        try:
            image = pyvips.Image.new_from_buffer(image_data, "")
            return image.get('vips-loader')
        except pyvips.Error:
            return 'unknown'

    def resize_image(self, image_data):
        """
        Resize image to max dimension while preserving aspect ratio using PyVips
        """
        try:
            image = pyvips.Image.new_from_buffer(image_data, "")
            
            width, height = image.width, image.height
            if width <= self.max_dimension and height <= self.max_dimension:
                logger.info(f"Image already within size limits: {width}x{height}")
                return image_data
            
            resized_image = image.thumbnail_image(self.max_dimension)
            resized_bytes = resized_image.write_to_buffer('.jpg', Q=85)
            
            logger.info(f"PYVIPS: Successfully resized image from {width}x{height} to {resized_image.width}x{resized_image.height}")
            return resized_bytes
            
        except Exception as e:
            logger.error(f"ERROR: PyVips image resize failed: {str(e)}")
            logger.error(f"ERROR: Falling back to original image")
            return image_data