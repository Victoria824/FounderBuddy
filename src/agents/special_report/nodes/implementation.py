"""Implementation node for Special Report Agent."""

import logging

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from core.logging_config import get_logger
from ..models import SpecialReportState
from ..tools import export_report

logger = get_logger(__name__)


async def implementation_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Implementation node that generates the final report."""
    logger.info("Implementation node - Generating final deliverables")
    
    try:
        # Export report
        result = await export_report.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "report_data": state["canvas_data"].model_dump(),
        })
        
        # Add completion message
        completion_msg = AIMessage(
            content=f"Congratulations! Your Special Report is complete. "
            f"You can download your report here: {result['url']}"
        )
        state["messages"].append(completion_msg)
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        error_msg = AIMessage(
            content=f"I encountered an error generating your report: {str(e)}. "
            "Your data has been saved and you can try exporting again later."
        )
        state["messages"].append(error_msg)
    
    return state