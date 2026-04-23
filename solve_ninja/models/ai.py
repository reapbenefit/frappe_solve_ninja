from typing import Any, Dict, Generic, Optional, TypeVar
from pydantic import BaseModel, Field


class BaseAIModel(BaseModel):

    chain_of_thought: str = Field(
        description="Briefly reflect on which of the three mentorship intake items are already covered (problem, what they tried, expectations) across the entire chat history, and what single question to ask next. CRITICAL: (1) Before moving to expectations, ensure what_tried is sufficiently explored. (2) Ask exactly ONE question in your response—never two or more. (3) If the user has already stated what they want help with or expect from mentorship, do not ask again; treat as answered. (4) When sending the closure message (confirm details, next steps, ask 'anything else?'), set is_done FALSE so the chat stays open; set is_done TRUE only after the user has replied to that question. Note the user's language and script choice to mirror in the response."
    )
    response: str = Field(
        description="The response to the user in the language of their last message. If they use English characters to write their native language, respond the same way. If they use native script, respond in that script. Be concise and warm: short sentences, minimal preamble, equally empathetic. Your message must contain exactly ONE question—never two or more—except when closing: then use the closure format in 2–3 short paragraphs (with line breaks): (1) confirm what we captured, (2) next steps—team will connect and find a mentor, (3) ask if anything else before we wrap up. Do not ask something the user has already answered."
    )
    is_done: bool = Field(
        description="Set to True only when the conversation is fully done and the chat can close. When you send the closure message (confirm details, next steps, ask 'anything else?'), set is_done to FALSE so the chat stays open for the user to reply. Set is_done to TRUE only after the user has responded to that question (e.g. they say nothing else, or they add something and you have acknowledged)—then the chat may close."
    )
    should_create_request: bool = Field(
        description="Set to True only when enough concrete information is collected to create a mentorship request (problem, what_tried, expectations). If the conversation ends due to repeated non-responsive or irrelevant replies, set this to False even if is_done is True."
    )
    done_signal_count: int = Field(
        default=0,
        description="Number of times is_done has been returned as true for this session. The client should send back the latest value on the next request so the server can enforce a max-close guardrail.",
    )
    language: str = Field(
        description="The language of the student, give in the format of english, hindi, kannada, etc."
    )
    




class MentorshipRequestModel(BaseAIModel):
    """LLM output for mentorship request use case."""

    problem: Optional[str] = Field(
        default=None,
        description="A concise summary of the problem the user is personally facing or experiencing, not just an observation about a broader issue. The problem should be articulated as something the user is directly affected by or feels responsible for addressing, not as something 'someone else should fix.' If it is clearly stated anywhere in the chat history, fill this field.",
    )
    what_tried: Optional[str] = Field(
        default=None,
        description="A concise summary of what the user has done so far, including both actual actions and intent signals. This should capture: (1) concrete actions taken to solve the problem, (2) intent signals such as conversations with others about the problem, research conducted (both primary and secondary), ideas they have about solutions, planning or thinking about solutions, seeking advice, or any other indicators that show the user's intent to address the problem even if not yet acted upon. IMPORTANT: If the user mentions some actions (like conversations) but hasn't shared ideas, research, or deeper thinking about solutions, this field should NOT be considered complete—probe deeper before moving to expectations. If any of these are clearly stated anywhere in the chat history, fill this field.",
    )
    expectations: Optional[str] = Field(
        default=None,
        description="A concise summary of what the user expects from mentorship. If it is clearly stated anywhere in the chat history, fill this field. Principles: (1) Stage identification (Discovery / Investigation / Solution Building) should be inferred from the conversation flow, not explicitly asked. (2) Do not route mentors purely on 'skill requested'—use it as a signal, not a decision. (3) Each probe should map clearly to a stage signal: Vague problem → Discovery, Research + learning → Investigation, Prototype / pilots → Solution Building.",
    )
    anything_else: Optional[str] = Field(
        default=None,
        description="A concise summary of anything else the user would like to share before we wrap up. Populate this ONLY when the user responds to the 'anything else?' closure question. If they say no (e.g., 'No', 'Nothing else', 'That's all'), set this to 'Nothing specific'.",
    )

class ActionRecordingModel(BaseAIModel): # TODO: Implement this
    """LLM output for action recording use case."""

class ProfileSummaryOutput(BaseModel):
    """LLM output for profile summary use case."""

    summary: str = Field(
        description="Short plain-language summary of the user's actions and skills"
    )