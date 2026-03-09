"""Claude API model using the Anthropic SDK.

Uses the Messages API with inline base64 image support.
"""

import json
import os
from typing import Any

from utils.screen import Screen


class Claude:
    """Model using Claude via the Anthropic Messages API.

    Claude uses its own SDK and message format, supporting images
    via base64-encoded inline data.
    """

    def __init__(self, model_name, api_key, context, screen=None):
        import anthropic

        self.model_name = model_name
        self.api_key = api_key
        self.context = context
        self.screen = screen
        self.client = anthropic.Anthropic(api_key=api_key)

        if api_key:
            os.environ['ANTHROPIC_API_KEY'] = api_key

    def get_instructions_for_objective(
        self, original_user_request: str, step_num: int = 0
    ) -> dict[str, Any]:
        content = self.format_user_request_for_llm(
            original_user_request, step_num
        )
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=800,
            system=self.context,
            messages=[{'role': 'user', 'content': content}],
        )
        return self.convert_llm_response_to_json_instructions(response)

    def format_user_request_for_llm(
        self, original_user_request: str, step_num: int
    ) -> list[dict[str, Any]]:
        screen = self.screen or Screen()
        base64_img: str = screen.get_gridded_screenshot_in_base64()
        request_data: str = json.dumps({
            'original_user_request': original_user_request,
            'step_num': step_num,
        })

        return [
            {'type': 'text', 'text': request_data},
            {'type': 'image', 'source': {
                'type': 'base64',
                'media_type': 'image/jpeg',
                'data': base64_img,
            }},
        ]

    def convert_llm_response_to_json_instructions(
        self, response: Any
    ) -> dict[str, Any]:
        text = ''
        for block in response.content:
            if hasattr(block, 'text'):
                text += block.text
        text = text.strip()

        start_index = text.find('{')
        end_index = text.rfind('}')

        try:
            return json.loads(text[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'Error parsing Claude response: {e}')
            print(f'Raw response text: {text[:500]}')
            return {}

    def cleanup(self):
        pass
