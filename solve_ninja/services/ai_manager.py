import os
from typing import Any, Dict, List, Optional, Type, TypedDict
import instructor
import backoff
from pathlib import Path
import frappe
from solve_ninja.models.ai import BaseAIModel, MentorshipRequestModel, ActionRecordingModel
from functools import lru_cache
from solve_ninja.models.chat_history import ChatHistory
import traceback
logger = frappe.logger("ai_manager", allow_site=True, file_count=10)


class UseCaseConfig(TypedDict):
    model: Type[BaseAIModel]
    max_done_signals: int
    system_prompt: str
    closure_message: str


@lru_cache(maxsize=None)
def _load_prompt(filename: str) -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / filename
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to load prompt: %s", prompt_path)
        return ""


MENTORSHIP_REQUEST_PROMPT = _load_prompt("mentorship_request.md")  # type: ignore

class AIManager:
    """Domain manager for AI chat responses."""

    USE_CASE_REGISTRY: Dict[str, UseCaseConfig] = {
        "Mentorship Request": {
            "model": MentorshipRequestModel,
            "max_done_signals": 2,
            "system_prompt": MENTORSHIP_REQUEST_PROMPT,
            "closure_message": "Thank you for your input. We'll be in touch soon.",
        },
        "Action Recording": {
            "model": ActionRecordingModel,
            "max_done_signals": 2,
            "system_prompt": "",
            "closure_message": "Thanks, we've recorded your action. Our team will be in touch soon.",
        },
    }
    DEFAULT_MODEL: str = "gpt-4.1-2025-04-14"
    MAX_OUTPUT_TOKENS: int = 8096
    TEMPERATURE: float = 0.1
    RESPONSE_MODEL: Type[BaseAIModel] = BaseAIModel
    API_KEY: Optional[str] = frappe.conf.get("openai_api_key")
    MODE = instructor.Mode.RESPONSES_TOOLS
    MAX_DONE_SIGNALS = 2

    @classmethod
    def get_use_cases(cls) -> List[str]:
        return list(cls.USE_CASE_REGISTRY.keys())

    @staticmethod
    def _response_to_dict(response: Any) -> Dict[str, Any]:
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "dict"):
            return response.dict()
        return {}

    @staticmethod
    def _is_closure_prompt(text: str) -> bool:
        normalized = text.lower()
        return "anything else" in normalized and "wrap up" in normalized

    @staticmethod
    def use_case_fields_complete(ai_response: BaseAIModel) -> bool:
        response_type = type(ai_response)
        try:
            base_fields = set(BaseAIModel.model_fields.keys())
            response_fields = set(response_type.model_fields.keys())
        except Exception:
            return False

        use_case_fields = response_fields - base_fields
        if not use_case_fields:
            return True
        for field_name in use_case_fields:
            value = getattr(ai_response, field_name, None)
            if value is None:
                return False
            if isinstance(value, str) and not value.strip():
                return False
        return True

    @classmethod
    async def get_response(
        cls,
        list_chat_history: List[ChatHistory],
        use_case: str,
    ) -> BaseAIModel:
        try:
            if use_case not in cls.USE_CASE_REGISTRY:
                raise ValueError(f"Unknown use case for AI response: {use_case}")
            
            response_model = AIManager.USE_CASE_REGISTRY[use_case]["model"]

            system_prompt = AIManager.USE_CASE_REGISTRY[use_case]["system_prompt"]

            response = await run_llm_responses_with_instructor(
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    }
                ]
                + [
                    {
                        "role": msg.role,
                        "content": msg.user_message,
                    }
                    for msg in list_chat_history
                ],
                response_model=response_model,
            )

            response_dict = AIManager._response_to_dict(response)
            use_case_result = response_model.model_validate(response_dict)

            check_if_complete = cls.use_case_fields_complete(use_case_result)
            current_done_signal_count = list_chat_history[-1].done_signal_count

            if check_if_complete or current_done_signal_count > 0:
                use_case_result.done_signal_count = current_done_signal_count + 1

            if use_case_result.done_signal_count >= AIManager.USE_CASE_REGISTRY[use_case]["max_done_signals"]:
                use_case_result.response = AIManager.USE_CASE_REGISTRY[use_case]["closure_message"]
                use_case_result.is_done = True

            
            
            return use_case_result
        except Exception as e:
            frappe.log_error(
                title="AI Manager Error",
                message=traceback.format_exc()
            )
            raise e

def is_reasoning_model(model: str) -> bool:
    return model in [
        "o3-mini-2025-01-31",
        "o3-mini",
        "o1-preview-2024-09-12",
        "o1-preview",
        "o1-mini",
        "o1-mini-2024-09-12",
        "o1",
        "o1-2024-12-17",
    ]

@backoff.on_exception(backoff.expo, Exception, max_tries=5, factor=2)
async def run_llm_responses_with_instructor(
    input: List,
    response_model: Type[BaseAIModel],
    **kwargs,
):
    api_key = AIManager.API_KEY
    if not api_key:
        raise ValueError("Missing OpenAI API key. Set `openai_api_key` in your site config.")
    os.environ["OPENAI_API_KEY"] = api_key

    client = instructor.from_provider(
        model=f"openai/{AIManager.DEFAULT_MODEL}",
        mode=AIManager.MODE,
        async_client=True,
    )

    model_kwargs = {}

    if not is_reasoning_model(AIManager.DEFAULT_MODEL):
        model_kwargs["temperature"] = 0

    model_kwargs.update(kwargs)

    return await client.responses.create(
        input=input,
        max_output_tokens=AIManager.MAX_OUTPUT_TOKENS,
        response_model=response_model,
        store=True,
        **model_kwargs,
    )
