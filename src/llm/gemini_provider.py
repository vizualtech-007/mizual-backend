"""
Gemini LLM Provider Implementation
"""

import os
from io import BytesIO
import google.generativeai as genai
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """Google Gemini implementation of LLM Provider"""
    
    def __init__(self):
        """Initialize Gemini provider with API key and model"""
        super().__init__()
        self.provider_name = "gemini"
        
        # Get Gemini-specific configuration
        api_key = os.environ.get("LLM_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("Error: Gemini API key not found in environment variables")
            raise ValueError("Gemini API key not found. Set LLM_API_KEY or GOOGLE_API_KEY")
        
        self.model_name = os.environ.get("LLM_MODEL", "gemini-1.5-flash")
        print(f"Using Gemini model: {self.model_name}")
        
        # Configure Gemini API
        genai.configure(api_key=api_key)
        
        # Get model
        try:
            self.model = genai.GenerativeModel(self.model_name)
            print(f"Successfully initialized Gemini model: {self.model_name}")
        except Exception as e:
            print(f"Error initializing Gemini model: {str(e)}")
            raise
    
    def enhance_prompt(self, prompt, image_data):
        """
        Enhance a user prompt using Gemini and the image context
        
        Args:
            prompt (str): The original user prompt
            image_data (bytes): The image data as bytes
            
        Returns:
            str: The enhanced prompt
        """
        print(f"Enhancing prompt with Gemini: '{prompt}'")
        
        try:
            # Resize image using PyVips (returns bytes directly)
            img_bytes = self.resize_image(image_data)
            
            # Use exact same system prompt as original working version
            system_prompt = f"""You are a multi-role AI assistant that will perform a complete image editing workflow analysis in sequential steps. You must complete ALL steps in order and provide your final output.

## STEP 1: WORKFLOW PLANNING
You are a highly analytical visual expert. Analyze the image and user's request, then create a structured JSON plan for a high-fidelity edit.

**Your process must follow these steps in order:**

**1. Identify the 'Complete Subject' for Preservation:**
    *   **Crucial Rule:** Your primary source of truth for all geometry and spatial relationships is the **provided image**.
    *   Identify the main object and all physically connected parts.
    *   Write a detailed, factual description of this 'Complete Subject.' You MUST include:
        *   **Component Parts**: A list of all parts (e.g., "blue machine", "hose", "chamber").
        *   **Proportions and Scale**: Describe the shape and size of each part relative to the others.
        *   **Spatial Relationships**: Describe how the parts are connected.

**2. Define the Background Modification:**
    *   Analyze the user's request to determine what should happen to the background.
    *   Write a clear, concise instruction for the background edit.

**3. Define the Fine-Detail Modifications:**
    *   Analyze the user's request for any small edits that need to happen *on* the 'Complete Subject'.
    *   Write a clear, concise instruction for each fine-detail edit.

**4. Create JSON Output:**
    Create your complete plan in a single, valid JSON object with this structure:
    {{
      "subject_to_preserve": {{
          "component_parts": ["list", "of", "parts"],
          "description": "The highly detailed description of the 'Complete Subject', based ONLY on the visual evidence in the image."
      }},
      "background_edit_instruction": "The instruction for what to do with the background.",
      "detail_edit_instructions": [
        "A list of instructions for small edits on the subject."
      ]
    }}

## STEP 2: PLAN VALIDATION
Now switch roles. You are a quality assurance expert with a keen eye. Review the JSON plan you just created and compare the `description` inside the `subject_to_preserve` key against the image.
Does the description accurately match the main subject in the image, including its parts and their proportions?
Provide a validation result: YES or NO.

## STEP 3: PROMPT ARCHITECTURE
You are now an expert prompt engineer. Based on your validation result from Step 2, generate the final prompt.

**Follow these rules:**

**IF the validation status is YES (PASSED):**
*   Construct a "High-Fidelity" prompt using the detailed plan.
*   **Format:**
    Line 1: "High-fidelity photographic edit of the provided image."
    Line 2: "Subject to Preserve: " followed by the component_parts formatted exactly as a Python list (e.g., ['item1', 'item2', 'item3'] with square brackets and quotes)
    Line 3: "Edits to perform:"
    Following Lines: A numbered list of all instructions from `background_edit_instruction` and `detail_edit_instructions`.
    
    **Example output format:**
    High-fidelity photographic edit of the provided image.
    Subject to Preserve: ['drum', 'drummer', 'drumsticks', 'cymbal']
    Edits to perform:
    1. [background instruction here]
    2. [detail instruction here if any]

**IF the validation status is NO (FAILED):**
*   The planner's analysis is unreliable. **IGNORE the `subject_to_preserve` description in the JSON plan.**
*   Construct a "Fallback" prompt using ONLY the user's original request.
*   **Format:**
    Line 1: "High-fidelity photographic edit of the provided image."
    Line 2: "Edits to perform based on the user's request:"
    Following Lines: A numbered list directly translating the user's original request into actions.

**User's Original Request:** "{prompt}"

## FINAL OUTPUT FORMAT
You must structure your complete response EXACTLY as follows:

### STEP 1 - JSON PLAN:
```json
[Your JSON plan here]
```

### STEP 2 - VALIDATION:
[Your validation result: YES or NO]

### STEP 3 - FINAL PROMPT:
[Your final action-oriented prompt here - plain text only, no markdown formatting or backticks]

Remember: Complete ALL three steps in sequence. Do not skip any step. The final prompt must be plain text without any markdown formatting."""
            
            # Create Gemini prompt
            prompt_parts = [
                system_prompt,
                {"mime_type": "image/jpeg", "data": img_bytes}
            ]
            generation_config = {
                "temperature": 0.1,  # Lower temperature for more deterministic output
                "top_p": 0.95,  # Slightly reduced to balance speed and quality
                "max_output_tokens": 2048,  # Enough for detailed response
            }
            # Generate response with timeout
            response = self.model.generate_content(
                prompt_parts,
                generation_config=generation_config,
                stream=False
            )
            
            # Parse the response using exact same logic as simple_query_v2.py
            response_text = response.text
            
            lines = response_text.split('\n')
            
            final_prompt = None
            in_prompt_section = False
            in_code_block = False
            
            for i, line in enumerate(lines):
                if 'STEP 3 - FINAL PROMPT:' in line or 'FINAL PROMPT:' in line:
                    in_prompt_section = True
                    prompt_lines = []
                    # Collect lines after this, skipping markdown formatting
                    for j in range(i + 1, len(lines)):
                        current_line = lines[j].strip()

                        # Check for code block markers
                        if current_line == '```':
                            in_code_block = not in_code_block
                            continue

                        # Skip empty lines and headers
                        if not current_line or current_line.startswith('#'):
                            continue

                        # Add non-empty lines that aren't markdown
                        if current_line and not current_line.startswith('```'):
                            prompt_lines.append(current_line)

                    if prompt_lines:
                        final_prompt = '\n'.join(prompt_lines)
                        break
            
            if final_prompt:
                # Log success
                print(f"Gemini enhancement completed")
                print(f"Original prompt: '{prompt}'")
                print(f"Enhanced prompt: '{final_prompt}'")
                return final_prompt
            else:
                print(f"Could not extract final prompt from Gemini response")
                return None
            
        except Exception as e:
            print(f"Gemini enhancement failed: {str(e)}")
            # Return None to indicate failure - will fall back to original prompt
            return None