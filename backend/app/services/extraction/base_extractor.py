"""
services/extraction/base_extractor.py
--------------------------------------
Base class for all Claude document extractors.
Handles the Anthropic API call, base64 encoding, and JSON parsing.
All specific extractors (electricity, fuel, water) inherit from this.
"""

import base64
import json

import anthropic


from app.config import settings


CLAUDE_MODEL = "claude-sonnet-4-6"


class BaseExtractor:

    def __init__(self):
        api_key=settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.client = anthropic.Anthropic(api_key=api_key)

    def extract(self, file_bytes: bytes, mime_type: str, prompt: str) -> dict:
        """
        Send a document to Claude with a prompt.
        Returns parsed JSON dict.
        """
        # Encode file to base64
        file_b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

        # Build the message
        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": file_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        raw = message.content[0].text.strip()

        # Strip markdown fences if Claude added them
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Return raw text in a dict so nothing is lost
            return {"raw_text": raw, "parse_error": True}