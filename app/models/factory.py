from models.gpt4o import GPT4o
from models.gpt4v import GPT4v
from models.gpt5 import GPT5
from models.moondream_hybrid import MoondreamHybrid
from models.openai_computer_use import OpenAIComputerUse
from models.gemini import Gemini
from models.claude import Claude
from models.chat_completions import ChatCompletionsModel


class ModelFactory:
    @staticmethod
    def create_model(model_name, *args, provider=None):
        """
        Create a model instance based on provider and/or model name.

        args: (base_url, api_key, context, screen)

        When *provider* is set, it takes priority over model-name-based
        routing.  This enables OpenRouter, Ollama, and Claude support.
        """
        try:
            # ── Provider-based routing (new) ──
            if provider == 'Claude':
                # Claude uses its own SDK — skip base_url
                return Claude(model_name, *args[1:])

            if provider in ('OpenRouter', 'Ollama'):
                # OpenAI-compatible Chat Completions API
                return ChatCompletionsModel(model_name, *args)

            if provider == 'Gemini':
                # Gemini uses its own SDK — skip base_url
                return Gemini(model_name, *args[1:])

            # ── Model-name-based routing (backward compat) ──
            if model_name == 'moondream2':
                return MoondreamHybrid(model_name, *args)
            elif model_name == 'gpt-4o' or model_name == 'gpt-4o-mini':
                return GPT4o(model_name, *args)
            elif model_name == 'computer-use-preview':
                return OpenAIComputerUse(model_name, *args)
            elif model_name.startswith('gpt-5'):
                return GPT5(model_name, *args)
            elif model_name == 'gpt-4-vision-preview' or model_name == 'gpt-4-turbo':
                return GPT4v(model_name, *args)
            elif model_name.startswith("gemini"):
                # Gemini doesn't use base_url, so skip it; pass (api_key, context, screen)
                return Gemini(model_name, *args[1:])
            else:
                # Llama/Llava models will work with the standard code I wrote for GPT4V without the assitant mode features of gpt4o
                return GPT4v(model_name, *args)
        except Exception as e:
            raise ValueError(f'Unsupported model type {model_name}. Create entry in app/models/. Error: {e}')
