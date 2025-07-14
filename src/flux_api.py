import httpx
import os
import base64
import asyncio
import time

FLUX_API_URL = os.environ.get("FLUX_API_URL", "https://api.bfl.ai/v1/flux-kontext-pro")
BFL_API_KEY = os.environ.get("BFL_API_KEY")


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
    }

    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(FLUX_API_URL, headers=headers, json=data)
        response.raise_for_status()

        edit_response = response.json()
        request_id = edit_response.get("id")
        polling_url = edit_response.get("polling_url")
        if not request_id or not polling_url:
            raise ValueError("Could not get request ID or polling URL from response.")

        while True:
            await asyncio.sleep(0.5)
            poll_response = await client.get(
                polling_url,
                headers={"accept": "application/json", "x-key": BFL_API_KEY},
                params={"id": request_id}
            )
            poll_response.raise_for_status()
            poll_result = poll_response.json()

            if poll_result.get("status") == "Ready":
                image_url = poll_result.get("result", {}).get("sample")
                if not image_url:
                    raise ValueError("Image URL not found in completed response.")

                image_response = await client.get(image_url)
                image_response.raise_for_status()
                return image_response.content
            elif poll_result.get("status") in ["Error", "Failed"]:
                error_message = poll_result.get("error", "Unknown error")
                raise Exception(f"Image editing failed: {error_message}")


