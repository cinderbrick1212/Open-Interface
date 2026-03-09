"""Generic model using the OpenAI Chat Completions API.

Works with OpenAI, OpenRouter, Ollama, and any OpenAI-compatible endpoint.
Unlike :class:`GPT4o` (Assistants API) or :class:`GPT5` (Responses API),
this class uses the widely-supported ``client.chat.completions.create``
endpoint.
"""

import json
from typing import Any

from models.model import Model
from utils.screen import Screen


class ChatCompletionsModel(Model):
    """Model using the standard Chat Completions API.

    Compatible with OpenAI, OpenRouter, Ollama, and other
    OpenAI-compatible providers that expose a ``/chat/completions``
    endpoint.
    """

    def get_instructions_for_objective(
        self, original_user_request: str, step_num: int = 0
    ) -> dict[str, Any]:
        messages = self.format_user_request_for_llm(
            original_user_request, step_num
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=800,
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
            {'role': 'system', 'content': self.context},
            {'role': 'user', 'content': [
                {'type': 'text', 'text': request_data},
                {'type': 'image_url', 'image_url': {
                    'url': f'data:image/jpeg;base64,{base64_img}',
                }},
            ]},
        ]

    def convert_llm_response_to_json_instructions(
        self, response: Any
    ) -> dict[str, Any]:
        text = response.choices[0].message.content.strip()

        start_index = text.find('{')
        end_index = text.rfind('}')

        try:
            return json.loads(text[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'Error parsing Chat Completions response: {e}')
            print(f'Raw response text: {text[:500]}')
            return {}
