"""
Base LLM Provider Interface
Defines the common interface that all LLM providers must implement
"""

from abc import ABC, abstractmethod
from io import BytesIO
from PIL import Image
import os

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self):
        """Initialize provider with common configuration"""
        # Get common configuration from environment
        self.max_dimension = int(os.environ.get("LLM_MAX_IMAGE_DIMENSION", "1024"))
        self.timeout = int(os.environ.get("LLM_TIMEOUT", "5"))
        self.provider_name = "base"
        print(f"Initializing {self.provider_name} provider with max_dimension={self.max_dimension}, timeout={self.timeout}")
    
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
        Resize image to max dimension while preserving aspect ratio
        
        Args:
            image_data (bytes): The image data as bytes
            
        Returns:
            PIL.Image: The resized image
        """
        try:
            # Open image from bytes
            image = Image.open(BytesIO(image_data))
            
            # Check if resizing is needed
            width, height = image.size
            if width <= self.max_dimension and height <= self.max_dimension:
                print(f"Image already within size limits: {width}x{height}")
                return image
            
            # Calculate new dimensions
            if width > height:
                new_width = self.max_dimension
                new_height = int(height * (self.max_dimension / width))
            else:
                new_height = self.max_dimension
                new_width = int(width * (self.max_dimension / height))
            
            # Resize image
            resized_image = image.resize((new_width, new_height))
            print(f"Resized image from {width}x{height} to {new_width}x{new_height}")
            return resized_image
            
        except Exception as e:
            print(f"Error resizing image: {str(e)}")
            # Return original image if resize fails
            return Image.open(BytesIO(image_data))