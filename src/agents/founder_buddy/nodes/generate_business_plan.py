"""Generate business plan node for Founder Buddy Agent."""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model

from ..enums import SectionStatus
from ..models import FounderBuddyState

logger = logging.getLogger(__name__)


async def generate_business_plan_node(state: FounderBuddyState | dict, config: RunnableConfig) -> FounderBuddyState | dict:
    """
    Generate a comprehensive business plan document from all collected data.
    
    This node is called when all sections are complete to create a final summary document.
    """
    logger.info("Generating business plan document")
    
    # Handle both dict and FounderBuddyState types
    if isinstance(state, dict):
        messages = state.get("messages", [])
        founder_data = state.get("founder_data", {})
    else:
        messages = state.get("messages", [])
        founder_data = state.get("founder_data", {})
    
    # Extract conversation history as text
    conversation_text = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            conversation_text += f"User: {msg.content}\n\n"
        elif isinstance(msg, AIMessage):
            conversation_text += f"AI: {msg.content}\n\n"
    
    # Create business plan generation prompt
    system_prompt = """You are a professional business plan writer helping founders create a comprehensive business plan document.

Based on the complete conversation history, create a well-structured business plan document in English that includes:

# Business Plan

## 1. Executive Summary
- Business concept overview
- Core value proposition
- Target market

## 2. Mission & Vision
- Mission statement
- Vision statement
- Target audience

## 3. Product/Service Description
- Product description
- Core value proposition
- Key features
- Differentiation advantages

## 4. Team & Traction
- Team members and roles
- Key milestones
- Traction metrics

## 5. Investment Plan
- Funding amount
- Funding use
- Valuation
- Exit strategy

## 6. Next Steps
- Immediate action items
- Key milestones

Requirements:
- Use Markdown format with clear structure
- Content should be comprehensive but concise, approximately 2-3 pages
- Base all information on actual conversation content, do not use placeholders
- Use professional but accessible language
- Ensure all information comes from the conversation content"""

    messages_for_llm = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=f"""
Complete conversation history:

{conversation_text}

Please generate a complete business plan based on the above conversation content. Ensure all information comes from the actual conversation content.
""")
    ]
    
    # Generate business plan
    llm = get_model()
    response = await llm.ainvoke(messages_for_llm)
    
    business_plan_content = response.content if hasattr(response, 'content') else str(response)
    
    # Add business plan to state
    state["business_plan"] = business_plan_content
    
    # Create final message with business plan
    final_message = f"""# 🎉 Business Plan Generated

Thank you for completing all sections! Below is your complete business plan based on our conversation:

---

{business_plan_content}

---

**Next Steps:**
1. Review this business plan carefully
2. Adjust and refine based on your actual situation
3. Begin executing the action items outlined in the plan

Best of luck with your venture! 🚀"""
    
    # Add final message
    state["messages"].append(AIMessage(content=final_message))
    
    # Mark as finished and clear the flag
    state["finished"] = True
    state["should_generate_business_plan"] = False
    
    logger.info("Business plan generated successfully")
    logger.info(f"Final message added to state with content length: {len(final_message)}")
    
    return state

