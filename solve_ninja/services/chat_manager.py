from typing import Any, Dict
import uuid
import frappe
from solve_ninja.models.chat_history import ChatHistory
from solve_ninja.services.ai_manager import AIManager
from typing import List
import traceback
from solve_ninja.models.result import Result
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

        chat_history_messages = cls.get_history(chat_message.session_id)
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
            fields=["name", "content", "role", "response_type", "use_case", "session_id", "event_id", "user", "sequence_number", "creation"],
            order_by="sequence_number desc, creation asc",
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
                sequence_number=chat_history_message.get("sequence_number"),
            )
            for chat_history_message in chat_history_messages
        ]
    
    @staticmethod
    def add_message(chat_history: ChatHistory) -> str:
        try:
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
                    "sequence_number": chat_history.sequence_number or 0,
                }
            )
            chat_history_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return chat_history_doc.name
        except Exception as e:
            frappe.log_error(
                title="Error in add_message",
                message=traceback.format_exc()
            )
            raise Exception(f"Failed to add message: {str(e)}")
        

    @classmethod
    def add_chat_message(cls, request_data: Dict[str, Any]) -> Result:
        if not request_data.get("content"):
            raise ValueError("Content is required and cannot be emptyddd")
        if not request_data.get("role"):
            raise ValueError("Role is required and cannot be empty")
        if not request_data.get("response_type"):
            raise ValueError("Response type is required and cannot be empty")
        if not request_data.get("use_case"):
            raise ValueError("Use case is required and cannot be empty")
        
        if request_data.get("session_id") is None:
            session_id = cls.create_session(request_data.get("use_case"))
            request_data["session_id"] = session_id
            request_data["sequence_number"] = 1
        else:
            last_sequence_number = cls.get_last_message_sequence_number(request_data.get("session_id"))
            request_data["sequence_number"] = last_sequence_number + 1
        chat_history = ChatHistory(
            user_message=request_data.get("content"),
            role=request_data.get("role"),
            response_type=request_data.get("response_type"),
            use_case=request_data.get("use_case"),
            session_id=request_data.get("session_id"),
            event_id=request_data.get("event_id") or "",
            user=request_data.get("user") or "",
            sequence_number=request_data.get("sequence_number"),
        )
        message_id = cls.add_message(chat_history)
        return Result.success(message="Chat message added successfully", data={
            "session_id": chat_history.session_id,
            "chat_id": message_id,
            "sequence_number": chat_history.sequence_number,
        })

    @classmethod
    def submit_feedback_for_session(cls, request_data: Dict[str, Any]) -> Result:
        if not request_data.get("session_id"):
            raise ValueError("Session ID is required and cannot be empty")
        if not request_data.get("feedback_rating"):
            raise ValueError("Feedback rating is required and cannot be empty")

        try:
            chat_session_doc = frappe.get_doc("Chat Session", {"session_id": request_data.get("session_id")})
            chat_session_doc.feedback_rating = request_data.get("feedback_rating")
            chat_session_doc.feedback_comments = request_data.get("feedback_comments")
            chat_session_doc.save(ignore_permissions=True)
            frappe.db.commit()
            return Result.success(message="Feedback submitted successfully")
        except Exception as e:
            frappe.log_error(
                title="Error in submit_feedback_for_session",
                message=traceback.format_exc()
            )
            return Result.failure(message=f"Failed to submit feedback for session: {str(e)}", error_data=traceback.format_exc())

    @staticmethod
    def create_session(use_case: str) -> str:
        if not use_case:
            raise ValueError("Use case is required and cannot be empty")
        chat_session_doc = frappe.get_doc({
            "doctype": "Chat Session",
            "use_case": use_case,
            "session_id": str(uuid.uuid4()),
        })
        chat_session_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return chat_session_doc.session_id
    
    @classmethod
    def submit_feedback_for_chat_message(cls, request_data: Dict[str, Any]) -> Result:
        if not request_data.get("chat_id"):
            raise ValueError("Chat ID  is required and cannot be empty")
        if not request_data.get("feedback_rating"):
            raise ValueError("Feedback rating is required and cannot be empty")
       
        try:
            chat_feedback_doc = frappe.get_doc(
                {
                    "doctype": "Chat Feedback",
                    "chat_history_message": request_data.get("chat_id"),
                    "chat_feedback": request_data.get("feedback_rating"),
                    "chat_feedback_comment": request_data.get("feedback_comments"),
                }
            )
            chat_feedback_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return Result.success(message="Feedback submitted successfully")
        except Exception as e:
            frappe.log_error(
                title="Error in submit_feedback_for_chat_message",
                message=traceback.format_exc()
            )
            return Result.failure(message=f"Failed to submit feedback for chat message: {str(e)}", error_data=traceback.format_exc())
    
    @classmethod
    def get_last_message_sequence_number(cls, session_id: str) -> int:
        last_message = frappe.get_all(
            "Chat History",
            filters={"session_id": session_id},
            fields=["name", "sequence_number"],
            order_by="sequence_number desc",
            limit=1,
        )
        if last_message:
            return last_message[0].get("sequence_number")
        return 0

    @classmethod
    def get_chat_history_by_session_id(cls, session_id: str) -> Result:
        if not session_id:
            raise ValueError("Session ID is required and cannot be empty")
        try:
            chat_history_messages = cls.get_history(session_id)
            return Result.success(message="Chat history fetched successfully", data=[chat_history_message.model_dump() for chat_history_message in chat_history_messages])
        except Exception as e:
            frappe.log_error(
                title="Error in get_chat_history_by_session_id",
                message=traceback.format_exc()
            )
            return Result.failure(message=f"Failed to get chat history by session ID: {str(e)}", error_data=traceback.format_exc())