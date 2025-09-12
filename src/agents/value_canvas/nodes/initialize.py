"""Initialize node for Value Canvas Agent."""

import logging

from langchain_core.runnables import RunnableConfig

from ..enums import RouterDirective, SectionID
from ..models import ValueCanvasData, ValueCanvasState
from integrations.dentapp.dentapp_client import get_dentapp_client
from core.settings import settings

logger = logging.getLogger(__name__)


async def initialize_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Initialize node that ensures all required state fields are present.
    This is the first node in the graph to handle LangGraph Studio's incomplete state.
    """
    logger.info("Initialize node - Setting up default values")

    # CRITICAL FIX: Get correct IDs from config instead of using temp IDs
    # service.py now passes the correct user_id and thread_id through config
    configurable = config.get("configurable", {})
    
    if "user_id" not in state or not state["user_id"]:
        # Try to get user_id from config first
        if "user_id" in configurable and configurable["user_id"]:
            state["user_id"] = configurable["user_id"]
            logger.info(f"Initialize node - Got user_id from config: {state['user_id']}")
        else:
            logger.error("CRITICAL: Initialize node running without a user_id in both state and config!")
            raise ValueError(
                "Critical system error: No valid user_id found. "
                "This indicates a serious ID chain break that will cause data loss. "
                "Check service.py ID passing logic."
            )
    
    if "thread_id" not in state or not state["thread_id"]:
        # Try to get thread_id from config
        if "thread_id" in configurable and configurable["thread_id"]:
            state["thread_id"] = configurable["thread_id"]
            logger.info(f"Initialize node - Got thread_id from config: {state['thread_id']}")
        else:
            logger.error("CRITICAL: Initialize node running without a thread_id in state or config!")
            raise ValueError(
                "Critical system error: No valid thread_id found. "
                "This indicates a serious ID chain break that will cause data loss. "
                "Check service.py ID passing logic."
            )

    # Ensure all other required fields have default values
    if "current_section" not in state:
        state["current_section"] = SectionID.INTERVIEW
    if "router_directive" not in state:
        state["router_directive"] = RouterDirective.NEXT
    if "finished" not in state:
        state["finished"] = False
    if "section_states" not in state:
        state["section_states"] = {}
    if "canvas_data" not in state:
        state["canvas_data"] = ValueCanvasData()
    if "short_memory" not in state:
        state["short_memory"] = []
    if "error_count" not in state:
        state["error_count"] = 0
    if "last_error" not in state:
        state["last_error"] = None
    if "awaiting_satisfaction_feedback" not in state:
        state["awaiting_satisfaction_feedback"] = False
    if "messages" not in state:
        state["messages"] = []
    
    # Fetch user context from DentApp API if enabled
    if settings.USE_DENTAPP_API and state.get("user_id"):
        try:
            logger.info(f"Fetching user context from DentApp API for user_id={state['user_id']}")
            client = get_dentapp_client()
            if client:
                user_context = await client.get_agent_context(state["user_id"])
                if user_context:
                    logger.info(f"Retrieved user context: {user_context}")
                    # Update canvas_data with user information
                    if isinstance(state["canvas_data"], dict):
                        canvas_data_dict = state["canvas_data"]
                    else:
                        canvas_data_dict = state["canvas_data"].model_dump() if hasattr(state["canvas_data"], 'model_dump') else {}
                    
                    # Map API fields to canvas_data fields
                    canvas_data_dict["client_name"] = user_context.get("full_name", "Joe")  # Fallback to Joe
                    canvas_data_dict["preferred_name"] = user_context.get("preferred_name", "")
                    canvas_data_dict["company_name"] = user_context.get("company_name", "ABC Company")  # Fallback to ABC Company
                    # Industry remains hardcoded as requested
                    canvas_data_dict["industry"] = "Technology & Software"
                    
                    # Update state with new canvas_data
                    state["canvas_data"] = ValueCanvasData(**canvas_data_dict)
                    logger.info(f"Updated canvas_data with user context: client_name={canvas_data_dict['client_name']}, company_name={canvas_data_dict['company_name']}")
                else:
                    logger.warning(f"No user context found for user_id={state['user_id']}, using defaults")
                    # Set default values if API returns nothing
                    if isinstance(state["canvas_data"], dict):
                        canvas_data_dict = state["canvas_data"]
                    else:
                        canvas_data_dict = state["canvas_data"].model_dump() if hasattr(state["canvas_data"], 'model_dump') else {}
                    
                    canvas_data_dict["client_name"] = "Joe"
                    canvas_data_dict["company_name"] = "ABC Company"
                    canvas_data_dict["industry"] = "Technology & Software"
                    
                    state["canvas_data"] = ValueCanvasData(**canvas_data_dict)
        except Exception as e:
            logger.error(f"Failed to fetch user context: {e}, using default values")
            # Set default values on error
            if isinstance(state["canvas_data"], dict):
                canvas_data_dict = state["canvas_data"]
            else:
                canvas_data_dict = state["canvas_data"].model_dump() if hasattr(state["canvas_data"], 'model_dump') else {}
            
            canvas_data_dict["client_name"] = "Joe"
            canvas_data_dict["company_name"] = "ABC Company"
            canvas_data_dict["industry"] = "Technology & Software"
            
            state["canvas_data"] = ValueCanvasData(**canvas_data_dict)
    
    logger.info(f"Initialize complete - User: {state['user_id']}, Thread: {state['thread_id']}")
    return state