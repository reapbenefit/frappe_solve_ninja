from typing import Any, Dict
import uuid
import frappe
from solve_ninja.models.chat_history import ChatHistory
from solve_ninja.services.ai_manager import AIManager
from typing import List
import traceback
class ChatManager:
    """Generic chat orchestration based on use_case."""
    @classmethod
    async def initiate_chat(cls, request_data: Dict[str, Any]) -> Dict[str, Any]:
        
        if not request_data.get("use_case"):
            raise ValueError("Use case is required")
        if not request_data.get("user_message"):
            raise ValueError("User message is required and cannot be empty")

        chat_history = ChatHistory(
            user_message=request_data.get("user_message"),
            role="user",
            response_type="text",
            use_case=request_data.get("use_case"),
            session_id=str(uuid.uuid4()),
            done_signal_count=request_data.get("done_signal_count", 0),
        )
        ChatManager.add_message(chat_history)
        try:
            ai_response = await AIManager.get_response(
                [chat_history],
                request_data.get("use_case"),
            )
        
            ChatManager.add_message(ChatHistory(
                user_message=ai_response.response,
                role="assistant",
                response_type="text",
                use_case=chat_history.use_case,
                session_id=chat_history.session_id,
            ))
            
            return {
                "session_id": chat_history.session_id,
                **ai_response.model_dump(),
            }
        except Exception as e:
                    frappe.log_error(
                        title="Initiate Chat Error",
                        message=traceback.format_exc()
                    )
                    raise e
    @classmethod
    async def continue_chat(cls, request_data: Dict[str, Any]) -> Dict[str, Any]:
        if not request_data.get("use_case"):
            raise ValueError("Use case is required")
        if not request_data.get("user_message"):
            raise ValueError("User message is required and cannot be empty")
        if not request_data.get("session_id"):
            raise ValueError("Session ID is required")
        if request_data.get("done_signal_count") is None:
            raise ValueError("Done signal count is required and cannot be empty")
        chat_message = ChatHistory(
            user_message=request_data.get("user_message"),
            role="user",
            response_type="text",
            use_case=request_data.get("use_case"),
            session_id=request_data.get("session_id"),
            done_signal_count=request_data.get("done_signal_count"),
        )
        ChatManager.add_message(chat_message)

        chat_history_messages = ChatManager.get_history(chat_message.session_id)
        chat_history_messages.append(chat_message)
        
        ai_response = await AIManager.get_response(
            chat_history_messages,
            chat_message.use_case,
        )

        ChatManager.add_message(ChatHistory(
            user_message=ai_response.response,
            role="assistant",
            response_type="text",
            use_case=chat_message.use_case,
            session_id=chat_message.session_id,
        ))
        
        return {
            "session_id": chat_message.session_id,
            **ai_response.model_dump(),
        }


    @classmethod
    def end_chat(cls, request_data: Dict[str, Any]) -> Dict[str, Any]:
        request = cls._build_request(request_data)
        if not request.session_id:
            raise ValueError("Session ID is required")
        return {
            "session_id": request.session_id,
            "is_done": True,
            "response": "Chat ended",
        }

    @staticmethod
    def get_history(session_id: str) -> List[ChatHistory]:
        chat_history_messages = frappe.get_all(
            "Chat History",
            filters={"session_id": session_id},
            fields=["name", "content", "role", "response_type", "use_case", "session_id", "event_id", "user"],
            order_by="creation asc",
        )
        return [
            ChatHistory(
                user_message=chat_history_message.get("content") or "",
                role=chat_history_message.get("role") or "",
                response_type=chat_history_message.get("response_type") or "",
                use_case=chat_history_message.get("use_case") or "",
                session_id=chat_history_message.get("session_id") or "",
                event_id=chat_history_message.get("event_id") or "",
                user=chat_history_message.get("user"),
            )
            for chat_history_message in chat_history_messages
        ]
    
    @staticmethod
    def add_message(chat_history: ChatHistory):
        chat_history_doc = frappe.get_doc(
            {
                "doctype": "Chat History",
                "content": chat_history.user_message,
                "role": chat_history.role,
                "response_type": chat_history.response_type,
                "use_case": chat_history.use_case,
                "session_id": chat_history.session_id,
                "event_id": chat_history.event_id or None,
                "user": chat_history.user or None,
            }
        )
        chat_history_doc.insert(ignore_permissions=True)
        frappe.db.commit()