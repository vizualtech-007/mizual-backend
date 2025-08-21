from abc import ABC, abstractmethod
from .prompts import get_prompt_template
import os

class LLMProvider(ABC):
    @abstractmethod
    def enhance_prompt(self, prompt: str, image_data: bytes) -> str:
        pass

    def _is_image_a_photo(self, image_data: bytes) -> bool:
        """Check if an image is photographic using pyvips."""
        import pyvips
        try:
            # Check for a color profile, a common indicator of photos
            image = pyvips.Image.new_from_buffer(image_data, "")
            return image.get_typeof('icc-profile-data') != 0
        except pyvips.Error:
            return False

    def _get_image_format(self, image_data: bytes) -> str:
        """Get image format using pyvips."""
        import pyvips
        try:
            image = pyvips.Image.new_from_buffer(image_data, "")
            return image.get('vips-loader')
        except pyvips.Error:
            return 'unknown'

    def get_final_prompt(self, prompt: str, image_data: bytes) -> str:
        """Get the final prompt based on image type."""
        is_photo = self._is_image_a_photo(image_data)
        image_format = self._get_image_format(image_data)
        
        # Get the appropriate prompt template
        prompt_template = get_prompt_template(is_photo)
        
        # Format the final prompt
        final_prompt = prompt_template.format(
            user_prompt=prompt,
            image_format=image_format
        )
        
        return final_prompt

def _get_image_format(image_data: bytes) -> str:
    """Helper to get image format without a class instance."""
    import pyvips
    try:
        # Use a format hint if possible for better accuracy
        format_hint = ""
        if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            format_hint = ".png"
        elif image_data.startswith(b'\xff\xd8\xff'):
            format_hint = ".jpeg"
        
        if format_hint:
            image = pyvips.Image.new_from_buffer(image_data, format_hint)
        else:
            image = pyvips.Image.new_from_buffer(image_data, "")
            
        return image.get('vips-loader')
    except pyvips.Error:
        return 'unknown'
