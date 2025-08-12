"""
OpenAI LLM Provider Implementation
"""

import os
import base64
from io import BytesIO
from openai import OpenAI
from .base import BaseLLMProvider

class OpenAIProvider(BaseLLMProvider):
    """OpenAI implementation of LLM Provider"""
    
    def __init__(self):
        """Initialize OpenAI provider with API key and model"""
        super().__init__()
        self.provider_name = "openai"
        
        # Get OpenAI-specific configuration
        api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OpenAI API key not found in environment variables")
            raise ValueError("OpenAI API key not found. Set LLM_API_KEY or OPENAI_API_KEY")
        
        self.model_name = os.environ.get("LLM_MODEL", "gpt-4o")
        print(f"Using OpenAI model: {self.model_name}")
        
        # Configure OpenAI client
        try:
            self.client = OpenAI(api_key=api_key)
            print(f"Successfully initialized OpenAI client")
        except Exception as e:
            print(f"Error initializing OpenAI client: {str(e)}")
            raise
    
    def enhance_prompt(self, prompt, image_data):
        """
        Enhance a user prompt using OpenAI and the image context
        
        Args:
            prompt (str): The original user prompt
            image_data (bytes): The image data as bytes
            
        Returns:
            str: The enhanced prompt
        """
        print(f"Enhancing prompt with OpenAI: '{prompt}'")
        
        try:
            # Resize image
            image = self.resize_image(image_data)
            
            # Convert to base64 for OpenAI
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format=image.format or 'JPEG')
            img_bytes = img_byte_arr.getvalue()
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            
            # Create OpenAI request
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": f"""You are a multi-role AI assistant that will perform a complete image editing workflow analysis in sequential steps. You must complete ALL steps in order and provide your final output.

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
    Line 1: "High-fidelity photorealistic edit."
    Line 2: "Keep intact: [List the component_parts from the JSON plan as comma-separated values, no brackets or quotes]."
    Line 3: "Edits to perform:"
    Following Lines: A numbered list of all instructions from `background_edit_instruction` and `detail_edit_instructions`. Make each instruction action-oriented and natural.

**IF the validation status is NO (FAILED):**
*   The planner's analysis is unreliable. **IGNORE the `subject_to_preserve` description in the JSON plan.**
*   Construct a "Fallback" prompt using ONLY the user's original request.
*   **Format:**
    Line 1: "High-fidelity photorealistic edit."
    Line 2: "Task: [Rephrase the user's request as a clear action]"

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
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.2,
                max_tokens=200
            )
            
            # Parse the response using exact same logic as simple_query_v2.py
            response_text = response.choices[0].message.content
            lines = response_text.split('\n')
            
            final_prompt = None
            in_prompt_section = False
            in_code_block = False
            
            for i, line in enumerate(lines):
                if 'STEP 3 - FINAL PROMPT:' in line or 'FINAL PROMPT:' in line or '### STEP 3 - FINAL PROMPT:' in line:
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
                print(f"OpenAI enhancement completed")
                print(f"Original prompt: '{prompt}'")
                print(f"Enhanced prompt: '{final_prompt}'")
                return final_prompt
            else:
                print(f"Could not extract final prompt from OpenAI response")
                return None
            
        except Exception as e:
            print(f"OpenAI enhancement failed: {str(e)}")
            # Return None to indicate failure - will fall back to original prompt
            return None