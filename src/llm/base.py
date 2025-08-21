"""
Base LLM Provider Interface
Defines the common interface that all LLM providers must implement
"""

from abc import ABC, abstractmethod
from io import BytesIO
import pyvips
import os
from ..logger import logger

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self):
        """Initialize provider with common configuration"""
        # Get common configuration from environment
        self.max_dimension = int(os.environ.get("LLM_MAX_IMAGE_DIMENSION", "1024"))
        self.timeout = int(os.environ.get("LLM_TIMEOUT", "5"))
        self.provider_name = "base"
        logger.info(f"Initializing {self.provider_name} provider with max_dimension={self.max_dimension}, timeout={self.timeout}")
    
    @abstractmethod
    def enhance_prompt(self, prompt, image_data):
        """
        Enhance a user prompt using the image context
        
        Args:
            prompt (str): The original user prompt
            image_data (bytes): The image data as bytes
            
        Returns:
            str: The enhanced prompt
            
        Raises:
            Exception: If enhancement fails
        """
        pass
    
    def resize_image(self, image_data):
        """
        Resize image to max dimension while preserving aspect ratio using PyVips
        
        Args:
            image_data (bytes): The image data as bytes
            
        Returns:
            bytes: The resized image as bytes
        """
        try:
            # Debug: Log image data characteristics
            logger.info(f"PYVIPS DEBUG: Image data size: {len(image_data)} bytes")
            if len(image_data) > 0:
                # Log first few bytes to help identify format
                header_bytes = image_data[:16]
                header_hex = ' '.join(f'{b:02x}' for b in header_bytes)
                logger.info(f"PYVIPS DEBUG: Image header bytes: {header_hex}")
            
            # Load image from bytes using PyVips (streaming)
            # Try without format first, then with specific formats if that fails
            try:
                image = pyvips.Image.new_from_buffer(image_data, "")
            except Exception as format_error:
                logger.warning(f"PyVips auto-detection failed: {format_error}, trying specific formats...")
                # Try common formats explicitly
                for format_hint in [".jpg", ".jpeg", ".png", ".webp"]:
                    try:
                        image = pyvips.Image.new_from_buffer(image_data, format_hint)
                        logger.info(f"Successfully loaded image with format hint: {format_hint}")
                        break
                    except Exception:
                        continue
                else:
                    # If all format hints fail, re-raise the original error
                    raise format_error
            
            # Check if resizing is needed
            width, height = image.width, image.height
            if width <= self.max_dimension and height <= self.max_dimension:
                logger.info(f"Image already within size limits: {width}x{height}")
                return image_data  # Return original bytes
            
            # Use PyVips thumbnail_image for efficient resizing
            # This automatically calculates dimensions and preserves aspect ratio
            resized_image = image.thumbnail_image(self.max_dimension)
            
            # Export to bytes with basic JPEG format
            # Use JPEG with 85% quality for good balance of size/quality
            resized_bytes = resized_image.write_to_buffer('.jpg', Q=85)
            
            logger.info(f"PYVIPS: Successfully resized image from {width}x{height} to {resized_image.width}x{resized_image.height}")
            logger.info(f"PYVIPS: Original size: {len(image_data)} bytes, Resized size: {len(resized_bytes)} bytes")
            
            return resized_bytes
            
        except Exception as e:
            logger.error(f"ERROR: PyVips image resize failed: {str(e)}")
            logger.error(f"ERROR: Image data size: {len(image_data)} bytes")
            logger.error(f"ERROR: Falling back to original image")
            # Return original image bytes if resize fails
            return image_data