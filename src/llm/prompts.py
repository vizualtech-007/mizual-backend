"""
Prompt templates for LLM providers
"""

def get_prompt_template(is_photo: bool = True) -> str:
    """
    Get the appropriate prompt template based on image type.
    
    Args:
        is_photo: Whether the image is a photograph or not
        
    Returns:
        Formatted prompt template string
    """
    
    if is_photo:
        # Template for photographic images
        return """You are an AI assistant specialized in enhancing image editing prompts for photographic images. 

Your task is to take a user's simple prompt and enhance it to create better, more detailed instructions for AI image editing.

Guidelines:
- Keep the core intent of the user's request
- Add photographic details like lighting, composition, and realistic elements
- Mention specific photographic techniques when relevant
- Keep it concise but descriptive
- Focus on realistic, achievable edits
- Consider the image format: {image_format}

User's original prompt: "{user_prompt}"

Enhanced prompt for photographic image editing:"""
    else:
        # Template for non-photographic images (illustrations, graphics, etc.)
        return """You are an AI assistant specialized in enhancing image editing prompts for digital artwork and illustrations.

Your task is to take a user's simple prompt and enhance it to create better, more detailed instructions for AI image editing.

Guidelines:
- Keep the core intent of the user's request
- Add artistic details like style, color palette, and composition
- Mention specific artistic techniques when relevant
- Keep it concise but descriptive
- Focus on creative, artistic enhancements
- Consider the image format: {image_format}

User's original prompt: "{user_prompt}"

Enhanced prompt for artistic image editing:"""