import httpx
import os
import base64
import asyncio

# Don't use global async client - it causes event loop issues
# Instead create a new client for each request or use sync client

FLUX_API_URL = os.environ.get("FLUX_API_URL", "https://api.bfl.ai/v1/flux-kontext-pro")
BFL_API_KEY = os.environ.get("BFL_API_KEY")


class BFLServiceError(Exception):
    """Custom exception for BFL service issues"""
    def __init__(self, message, status_code=None, is_temporary=False):
        super().__init__(message)
        self.status_code = status_code
        self.is_temporary = is_temporary


async def edit_image_with_flux(image: bytes, prompt: str) -> bytes:
    """Calls the Flux API to edit an image asynchronously."""
    if not BFL_API_KEY:
        raise ValueError("BFL_API_KEY environment variable not set.")

    headers = {
        "accept": "application/json",
        "x-key": BFL_API_KEY,
        "Content-Type": "application/json"
    }

    encoded_image = base64.b64encode(image).decode("utf-8")

    data = {
        "prompt": prompt,
        "input_image": encoded_image,
        "safety_tolerance": 2,  # Less restrictive moderation (0=strictest, 2=balanced)
    }

    try:
        # Create a new async client for this request to avoid event loop issues
        timeout_config = httpx.Timeout(30.0, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        
        async with httpx.AsyncClient(timeout=timeout_config, limits=limits) as client:
            # Submit the edit request
            try:
                response = await client.post(FLUX_API_URL, headers=headers, json=data)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                raise BFLServiceError(
                    f"BFL service is currently unavailable (HTTP {e.response.status_code}). Please try again later.",
                    status_code=e.response.status_code,
                    is_temporary=True
                )
                elif e.response.status_code == 429:
                raise BFLServiceError(
                    "BFL service is rate limiting requests. Please try again in a few minutes.",
                    status_code=e.response.status_code,
                    is_temporary=True
                )
                else:
                raise BFLServiceError(
                    f"BFL service error (HTTP {e.response.status_code}): {e.response.text}",
                    status_code=e.response.status_code,
                    is_temporary=False
                )
            except httpx.RequestError as e:
            raise BFLServiceError(
                f"Failed to connect to BFL service: {str(e)}",
                is_temporary=True
            )

            edit_response = response.json()
            request_id = edit_response.get("id")
            polling_url = edit_response.get("polling_url")
            if not request_id or not polling_url:
                raise BFLServiceError("BFL service returned invalid response format.")

            # Poll for results with timeout
            max_poll_time = 300  # 5 minutes maximum
            poll_start_time = asyncio.get_event_loop().time()
                
            while True:
                current_time = asyncio.get_event_loop().time()
                if current_time - poll_start_time > max_poll_time:
                    raise BFLServiceError(
                        "Image processing timed out. The BFL service is taking too long to process your request.",
                        is_temporary=True
                    )
                
                await asyncio.sleep(0.5)
                
                try:
                    poll_response = await client.get(
                        polling_url,
                        headers={"accept": "application/json", "x-key": BFL_API_KEY},
                        params={"id": request_id}
                    )
                    poll_response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500:
                        raise BFLServiceError(
                            f"BFL service is experiencing issues (HTTP {e.response.status_code}). Please try again later.",
                            status_code=e.response.status_code,
                            is_temporary=True
                        )
                    else:
                        raise BFLServiceError(
                            f"Failed to check processing status (HTTP {e.response.status_code})",
                            status_code=e.response.status_code,
                            is_temporary=False
                        )
                except httpx.RequestError as e:
                    raise BFLServiceError(
                        f"Network error while checking processing status: {str(e)}",
                        is_temporary=True
                    )
                
                poll_result = poll_response.json()

                if poll_result.get("status") == "Ready":
                    image_url = poll_result.get("result", {}).get("sample")
                    if not image_url:
                        raise BFLServiceError("BFL service completed processing but did not return an image.")

                    try:
                        image_response = await client.get(image_url)
                        image_response.raise_for_status()
                        return image_response.content
                    except (httpx.HTTPStatusError, httpx.RequestError) as e:
                        raise BFLServiceError(f"Failed to download processed image: {str(e)}")
                        
                elif poll_result.get("status") in ["Error", "Failed"]:
                    error_message = poll_result.get("error", "Unknown error")
                    raise BFLServiceError(f"Image processing failed: {error_message}")
                    
    except BFLServiceError:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise BFLServiceError(f"Unexpected error during image processing: {str(e)}")


