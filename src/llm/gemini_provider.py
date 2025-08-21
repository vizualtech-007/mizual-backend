from .base import LLMProvider
from .prompts import get_prompt_template
import os

class GeminiProvider(LLMProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not provided or set in environment")
        
        # Configuration for the generative model
        self.generation_config = {
            "temperature": 0.4,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 4096,
        }
        
        # Safety settings to be less restrictive
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    def enhance_prompt(self, prompt: str, image_data: bytes) -> str:
        """Enhances the prompt using the Gemini model, with true lazy loading."""
        import google.generativeai as genai
        
        # Configure the API key just before use
        genai.configure(api_key=self.api_key)
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        
        # Get the base prompt with photographic context
        base_prompt = self.get_final_prompt(prompt, image_data)
        
        # Prepare image part for the model
        image_format = self._get_image_format(image_data)
        mime_type = f"image/{image_format}" if image_format != 'unknown' else "image/jpeg"
        
        image_part = {
            "mime_type": mime_type,
            "data": image_data
        }
        
        # Generate content
        response = model.generate_content([base_prompt, image_part])
        
        return response.text