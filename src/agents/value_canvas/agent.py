"""Value Canvas Agent implementation using LangGraph StateGraph."""

import json
import logging
from typing import Any, Dict, List, Literal, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from core.llm import get_model
from core.settings import settings
from schema.models import OpenAIModelName

from .models import (
    ChatAgentOutput,
    ContextPacket,
    RouterDirective,
    SectionID,
    SectionStatus,
    ValueCanvasData,
    ValueCanvasState,
)
from .prompts import (
    get_next_section,
    get_next_unfinished_section,
    SECTION_TEMPLATES,
)
from .tools import (
    create_tiptap_content,
    export_checklist,
    extract_plain_text,
    get_all_sections_status,
    get_context,
    save_section,
    validate_field,
)

logger = logging.getLogger(__name__)


# Removed complex GPT-5 parameter configuration function for better performance

# Tool setup - Chat Agent has NO tools according to design doc

# Tools used by specific nodes
router_tools = [
    get_context,
]

memory_updater_tools = [
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,  # Moved from chat_agent per design doc
]

implementation_tools = [
    export_checklist,
]

# Create tool nodes
router_tool_node = ToolNode(router_tools)
memory_updater_tool_node = ToolNode(memory_updater_tools)
implementation_tool_node = ToolNode(implementation_tools)


async def initialize_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Initialize node that ensures all required state fields are present.
    This is the first node in the graph to handle LangGraph Studio's incomplete state.
    """
    logger.info("Initialize node - Setting up default values")

    # This node no longer creates user_id or doc_id.
    # That responsibility is now in service.py, which should call
    # initialize_value_canvas_state for new conversations.
    if "user_id" not in state or not state["user_id"]:
        logger.warning("Initialize node running without a user_id.")
        # Provide a temporary ID to prevent downstream errors, but this is a sign of a problem.
        state["user_id"] = "temp-user-id"
    if "doc_id" not in state or not state["doc_id"]:
        logger.warning("Initialize node running without a doc_id.")
        state["doc_id"] = "temp-doc-id"

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
    if "messages" not in state:
        state["messages"] = []
    
    logger.info(f"Initialize complete - User: {state['user_id']}, Doc: {state['doc_id']}")
    return state


async def router_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Router node that handles navigation and context loading.
    
    Responsibilities:
    - Process router directives (stay, next, modify:section_id)
    - Update current_section
    - Call get_context when changing sections
    - Check for completion and set finished flag
    """
    # Check if there's a new user message - if so, reset awaiting_user_input
    msgs = state.get("messages", [])
    if msgs and len(msgs) >= 2:
        last_msg = msgs[-1]
        second_last_msg = msgs[-2]
        # If last message is human and second last is AI, user has responded
        if isinstance(last_msg, HumanMessage) and isinstance(second_last_msg, AIMessage):
            state["awaiting_user_input"] = False

    logger.info(
        f"Router node - Current section: {state['current_section']}, Directive: {state['router_directive']}"
    )
    
    # [DIAGNOSTIC] Log the entire state for debugging
    state_for_log = state.copy()
    logger.info(f"DEBUG_ROUTER_ENTRY: Full state dump: {state_for_log}")

    # Process router directive
    directive = state.get("router_directive", RouterDirective.STAY)
    
    if directive == RouterDirective.STAY:
        # Stay on current section, no context reload needed
        logger.info("Staying on current section")
        return state
    
    elif directive == RouterDirective.NEXT:
        # Find next unfinished section
        logger.info(f"DEBUG: Preparing to find next section. Current section states: {state.get('section_states', {})}")
        
        # DEBUG: Log current section and its state before transition
        current_section_id = state["current_section"].value
        logger.info(f"TRANSITION_DEBUG: Leaving section {current_section_id}")
        if current_section_id in state.get("section_states", {}):
            current_state = state["section_states"][current_section_id]
            logger.info(f"TRANSITION_DEBUG: Section {current_section_id} final state - status: {current_state.get('status')}, has_content: {bool(current_state.get('content'))}")
        
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        logger.info(f"DEBUG: get_next_unfinished_section decided the next section is: {next_section}")
        
        if next_section:
            logger.info(f"Moving to next section: {next_section}")
            
            # DEBUG: Check if next section already has state
            logger.info(f"TRANSITION_DEBUG: Entering section {next_section.value}")
            if next_section.value in state.get("section_states", {}):
                logger.warning(f"TRANSITION_DEBUG: WARNING! Section {next_section.value} already has state before entering!")
                existing_state = state["section_states"][next_section.value]
                logger.warning(f"TRANSITION_DEBUG: Existing state - status: {existing_state.get('status')}, has_content: {bool(existing_state.get('content'))}")
            
            state["current_section"] = next_section
            
            # Clear short_memory when transitioning to a new section to avoid context confusion
            state["short_memory"] = []
            logger.info(f"Cleared short_memory for new section {next_section.value}")
            
            # Get context for new section
            logger.debug(f"DATABASE_DEBUG: Router calling get_context for section {next_section.value}")
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "section_id": next_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            logger.debug(f"DATABASE_DEBUG: get_context returned for section {next_section.value}")
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        else:
            # All sections complete
            logger.info("All sections complete, setting finished flag")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1].lower()  # handle case-insensitive IDs like "ICP"
        try:
            new_section = SectionID(section_id)
            logger.info(f"Jumping to section: {new_section}")
            state["current_section"] = new_section
            
            # Clear short_memory when jumping to a different section
            state["short_memory"] = []
            logger.info(f"Cleared short_memory for jumped section {new_section.value}")
            
            # Get context for new section
            logger.debug(f"DATABASE_DEBUG: Router calling get_context for modify section {new_section.value}")
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "section_id": new_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            logger.debug(f"DATABASE_DEBUG: get_context returned for modify section {new_section.value}")
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        except ValueError:
            logger.error(f"Invalid section ID: {section_id}")
            state["last_error"] = f"Invalid section ID: {section_id}"
            state["error_count"] += 1
    
    return state


async def chat_agent_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Chat agent node that handles section-specific conversations.
    
    Responsibilities:
    - Generate responses based on context_packet system prompt
    - Validate user input
    - Generate section content (Tiptap JSON)
    - Set score and router_directive
    - Output structured ChatAgentOutput
    """
    logger.info(f"Chat agent node - Section: {state['current_section']}")
    
    # DEBUG: Log recent message history
    logger.info(f"MESSAGE_HISTORY_DEBUG: Last 3 messages:")
    recent_msgs = state.get("messages", [])[-3:]
    for i, msg in enumerate(recent_msgs):
        msg_type = "Human" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "AI"
        content = str(msg.content)[:100] if hasattr(msg, 'content') else str(msg)[:100]
        logger.info(f"MESSAGE_HISTORY_DEBUG: [{i}] {msg_type}: {content}...")
    
    # [DIAGNOSTIC] Log context packet
    logger.info(f"DEBUG_CHAT_AGENT: Context Packet received: {state.get('context_packet')}")

    # Get LLM - no tools for chat agent per design doc
    # Use GPT-4O model configuration
    llm = get_model(OpenAIModelName.GPT_4O)
    
    messages: List[BaseMessage] = []
    last_human_msg: Optional[HumanMessage] = None
    user_rating: Optional[int] = None  # capture explicit 0-5 rating if provided

    # 1) Hard system instruction per design doc – MUST output pure JSON.
    json_schema_instruction = (
        "You are Value Canvas Chat Agent. Respond ONLY with valid JSON matching this schema: "
        '{"reply": "string", "router_directive": "stay|next|modify:<section_id>", '
        '"score": "integer|null", "section_update": "object|null"} '
        "Do NOT output markdown, code fences, or any extra commentary."
    )
    messages.append(SystemMessage(content=json_schema_instruction))
    
    # Check if we should add summary instruction
    # Add summary instruction when:
    # 1. We're not already awaiting user input
    # 2. User hasn't provided a rating
    # 3. We have collected enough information in the conversation (check short_memory)
    awaiting = state.get("awaiting_user_input", False)
    current_section = state["current_section"]
    section_state = state.get("section_states", {}).get(current_section.value, {})
    section_has_content = bool(section_state.get("content"))
    
    # DEBUG: Log detailed section state info
    logger.info(f"SUMMARY_DEBUG: Current section: {current_section.value}")
    logger.info(f"SUMMARY_DEBUG: Section states keys: {list(state.get('section_states', {}).keys())}")
    logger.info(f"SUMMARY_DEBUG: Short memory length: {len(state.get('short_memory', []))}")
    if section_state:
        logger.info(f"SUMMARY_DEBUG: Section {current_section.value} state exists with status: {section_state.get('status')}")
        logger.info(f"SUMMARY_DEBUG: Section {current_section.value} has content: {section_has_content}")
    
    # IMPORTANT: Do NOT automatically trigger summary instructions
    # According to the design document, the Agent should decide when to show summary
    # based on whether it has collected all required information for the section.
    # The prompts in prompts.py already contain the logic for when to show summaries.
    # Forcing summary instructions here causes premature summaries.
    
    # Only add summary reminder if section already has saved content that needs rating
    if section_has_content and user_rating is None and not awaiting:
        # This is for sections that were previously saved but need rating
        summary_reminder = (
            "The user has previously worked on this section. "
            "Review the saved content and ask for their satisfaction rating if not already provided."
        )
        messages.append(SystemMessage(content=summary_reminder))
        logger.info(f"SUMMARY_REMINDER: Added reminder to check existing content for section {current_section.value}")

    # 2) Section-specific system prompt from context packet
    if state.get("context_packet"):
        messages.append(SystemMessage(content=state["context_packet"].system_prompt))
        
        # Add progress information based on section_states
        section_names = {
            "interview": "Interview",
            "icp": "Ideal Client Persona (ICP)",
            "pain": "The Pain",
            "deep_fear": "Deep Fear",
            "payoffs": "The Payoffs",
            "signature_method": "Signature Method",
            "mistakes": "Mistakes",
            "prize": "Prize"
        }
        
        completed_sections = []
        for section_id, section_state in state.get("section_states", {}).items():
            if section_state.get("status") == "done":
                section_name = section_names.get(section_id, section_id)
                completed_sections.append(section_name)
        
        current_section_name = section_names.get(state["current_section"].value, state["current_section"].value)
        
        progress_info = (
            f"\n\nSYSTEM STATUS:\n"
            f"- Total sections: 9\n"
            f"- Completed: {len(completed_sections)} sections"
        )
        if completed_sections:
            progress_info += f" ({', '.join(completed_sections)})"
        progress_info += f"\n- Currently working on: {current_section_name}\n"
        
        messages.append(SystemMessage(content=progress_info))
        
        # Add clarification for new sections without content
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id, {})
        if not section_state or not section_state.get("content"):
            new_section_instruction = (
                f"IMPORTANT: You are now in the {current_section_id} section. "
                "This is a NEW section with no content yet. "
                "Start by following the conversation flow defined in the section prompt. "
                "Do NOT generate section_update until you have collected actual data for THIS section. "
                "Do NOT reference or include content from previous sections."
            )
            messages.append(SystemMessage(content=new_section_instruction))

    # 3) Recent conversation memory
    # Keep all messages from short_memory. Note: This might lead to context window issues with very long conversations.
    messages.extend(state.get("short_memory", []))

    # 4) Last human message (if any and agent hasn't replied yet)
    if state.get("messages"):
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append(_last_msg)
            last_human_msg = _last_msg
            # Attempt to detect if user provided a simple numeric rating 0-5
            if isinstance(_last_msg.content, list):
                for item in _last_msg.content:
                    if item.get("type") == "text":
                        txt = item.get("text", "").strip()
                        if txt.isdigit() and txt in {"0","1","2","3","4","5"}:
                            user_rating = int(txt)
                        break
            else:
                txt = str(_last_msg.content).strip()
                if txt.isdigit() and txt in {"0","1","2","3","4","5"}:
                    user_rating = int(txt)

    # Check if we're in a situation where user rated but section has no content
    if user_rating is not None and current_section == SectionID.INTERVIEW:
        section_state = state.get("section_states", {}).get(current_section.value, {})
        if not section_state or not section_state.get("content"):
            logger.warning(f"User provided rating {user_rating} but {current_section.value} has no content saved!")
            # Add instruction to re-display summary WITH section_update
            messages.append(SystemMessage(content=(
                "CRITICAL ERROR: The user has provided a rating, but the Interview section has no saved content! "
                "You MUST re-display the complete summary WITH section_update before proceeding. "
                "This is causing a loop because the system cannot move forward without saved content. "
                "Display the full summary again and include section_update with all the information you've collected."
            )))
    
    # If user provided an explicit rating, override LLM output requirements
    if user_rating is not None:
        # fabricate a minimal agent output – we don't need LLM call for simple acknowledgement
        current_section = state["current_section"]
        
        # According to design doc, rating happens at the END of each section
        # High rating (>=3) should always trigger NEXT to move to next section
        calculated_directive = RouterDirective.NEXT if user_rating >= 3 else RouterDirective.STAY
        
        if calculated_directive == RouterDirective.NEXT:
            # Get the next section name for the transition message
            from .prompts import get_next_section, SECTION_TEMPLATES
            next_section = get_next_section(current_section)
            if next_section:
                next_section_name = SECTION_TEMPLATES.get(next_section.value).name
                reply_msg = f"Thank you for your rating! Let's move on to the next section: {next_section_name}."
            else:
                reply_msg = "Thank you for your rating! We've completed all sections."
        else:
            # Low rating means we need to refine current section
            reply_msg = "Thank you for your rating! Let's refine this section together – what would you like to adjust?"
        
        agent_output = ChatAgentOutput(reply=reply_msg, router_directive=calculated_directive.value, score=user_rating, section_update=None)
        state["agent_output"] = agent_output
        state["router_directive"] = calculated_directive
        state["awaiting_user_input"] = (calculated_directive==RouterDirective.STAY)
        # append to history
        state["messages"].append(AIMessage(content=agent_output.reply))
        return state

    try:
        # Force OpenAI to return JSON in one shot
        openai_args = {"response_format": {"type": "json_object"}}
        
        for attempt in range(1): # Changed max_attempts to 1 as per original code
            response = await llm.ainvoke(messages, **openai_args)
            content = response.content if hasattr(response, "content") else response

            # Attempt to parse JSON as below (reuse existing logic in local helper)
            def _extract_json(text: str):
                txt = text.strip()
                if txt.startswith("```json"):
                    txt = txt[7:]
                if txt.startswith("```"):
                    txt = txt[3:]
                if txt.endswith("```"):
                    txt = txt[:-3]
                start = txt.find("{")
                end = txt.rfind("}") + 1
                if start >= 0 and end > start:
                    return txt[start:end]
                return None

            json_str = _extract_json(content) if isinstance(content, str) else None
            if json_str:
                try:
                    output_data = json.loads(json_str)
                    parsed_successfully = True
                    break
                except json.JSONDecodeError:
                    pass

        if not parsed_successfully:
            raise ValueError("Failed to get valid JSON from LLM after retries")

        # Ensure mandatory keys present
        output_data.setdefault("reply", "I'm processing your request...")
        output_data.setdefault("router_directive", "stay")
        output_data.setdefault("score", None)
        output_data.setdefault("section_update", None)

        agent_output = ChatAgentOutput(**output_data)

        # DEBUG: Log the full agent output
        logger.info(f"AGENT_OUTPUT_DEBUG: Full output from LLM:")
        logger.info(f"AGENT_OUTPUT_DEBUG: - reply: {agent_output.reply[:100]}...")
        logger.info(f"AGENT_OUTPUT_DEBUG: - router_directive: {agent_output.router_directive}")
        logger.info(f"AGENT_OUTPUT_DEBUG: - score: {agent_output.score}")
        logger.info(f"AGENT_OUTPUT_DEBUG: - has section_update: {bool(agent_output.section_update)}")
        
        if agent_output.section_update:
            logger.warning(f"AGENT_OUTPUT_DEBUG: Section update generated for section {state['current_section'].value}")
            # Check if this looks like Interview content being saved to ICP
            if state['current_section'] == SectionID.ICP:
                # Check for Interview-specific fields in ICP section update
                if hasattr(agent_output.section_update, 'content'):
                    content_str = str(agent_output.section_update.content)
                    if any(term in content_str for term in ["Specialty:", "Proud Achievement:", "Notable Partners:"]):
                        logger.error("ERROR! ICP section is getting Interview content!")
            
            # Additional check for Interview section
            if state['current_section'] == SectionID.INTERVIEW:
                # Ensure Interview section saves actual content, not just score
                if hasattr(agent_output.section_update, 'content'):
                    content_str = str(agent_output.section_update.content)
                    # Check if it contains actual interview data
                    if not any(term in content_str for term in ["Name:", "Company:", "Industry:", "Specialty:"]):
                        logger.warning("WARNING! Interview section_update doesn't contain actual interview data!")
                        # Check if we're asking for rating without showing summary
                        if "satisfied" in agent_output.reply.lower() and "summary" in agent_output.reply.lower():
                            if "Here's what I know about you" not in agent_output.reply:
                                logger.error("ERROR! Asking for satisfaction rating without showing summary first!")
        
        # DEBUG: Check state consistency
        logger.info(f"AGENT_OUTPUT_DEBUG: Current section_states: {list(state.get('section_states', {}).keys())}")

        # CRITICAL FIX: Validate score input
        # Only accept score if the user's last message is EXACTLY a single digit 0-5
        if agent_output.score is not None:
            # Get the last user message text
            user_text = ""
            if last_human_msg and last_human_msg.content:
                if isinstance(last_human_msg.content, list):
                    for item in last_human_msg.content:
                        if item.get("type") == "text":
                            user_text = item.get("text", "").strip()
                            break
                else:
                    user_text = str(last_human_msg.content).strip()
            
            # Check if the user input is EXACTLY a single digit 0-5
            import re
            if not re.match(r'^[0-5]$', user_text):
                # User didn't provide a valid score, override the LLM's decision
                logger.info(f"DEBUG: Invalid score input '{user_text}', overriding LLM score")
                agent_output.score = None
                agent_output.router_directive = RouterDirective.STAY.value

        # Determine router directive based on score, per design doc
        if agent_output.score is not None:
            # According to design doc, rating happens at the END of each section
            # High rating (>=3) should trigger NEXT to move to next section
            if agent_output.score >= 3:
                calculated_directive = RouterDirective.NEXT
            else:
                calculated_directive = RouterDirective.STAY
                
            state["router_directive"] = calculated_directive
            
            # If score-based logic says NEXT but LLM didn't generate transition message,
            # override the reply to be a transition message
            if calculated_directive == RouterDirective.NEXT:
                # Predict what the next section will be
                current_section = state["current_section"]
                predicted_next = get_next_section(current_section)
                
                if predicted_next:
                    next_section_name = SECTION_TEMPLATES.get(predicted_next.value).name
                    agent_output.reply = f"Great! Let's move on to the next section: {next_section_name}."
                else:
                    agent_output.reply = "Great! We've completed all sections."

        else:
            # Fallback to value supplied by model (may be stay/next/modify)
            state["router_directive"] = agent_output.router_directive

        state["agent_output"] = agent_output

        # --- MVP Fallback: ensure reply包含明确提问 -----------------------
        need_question = (
            state["router_directive"] == RouterDirective.STAY
            and agent_output.score is None
        )

        if need_question:
            import re
            # 如果 reply 中既没有问号也没有明确的指令词，则追加提示
            has_question = re.search(r"[?？]", agent_output.reply, re.IGNORECASE)
            has_instruction = any(word in agent_output.reply.lower() for word in [
                "please", "provide", "describe", "tell", "share", "what", "how", "when", "where", "why"
            ])
            
            if not has_question and not has_instruction:
                # 只有在真的没有明确指令时才添加兜底文本
                agent_output.reply += (
                    "\n\nPlease provide your response to continue."
                )

        # ---------------------------------------------------------------

        # If we expect user input next, mark flag (MVP logic uses need_question)
        state["awaiting_user_input"] = need_question

        # Add AI reply to conversation history
        state["messages"].append(AIMessage(content=agent_output.reply))

        # Update short-term memory by appending new messages
        base_mem = state.get("short_memory", [])
        if last_human_msg is not None:
            base_mem.append(last_human_msg)
        base_mem.append(AIMessage(content=agent_output.reply))
        state["short_memory"] = base_mem

        # [DIAGNOSTIC] Log the output from the agent
        logger.info(f"DEBUG_CHAT_AGENT: Agent output generated: {state.get('agent_output')}")
        
        # [SAVE_SECTION_DEBUG] Track when Chat Agent generates section_update
        if state.get('agent_output') and state['agent_output'].section_update:
            logger.info(f"SAVE_SECTION_DEBUG: ✅ Chat Agent DID generate section_update for section {state['current_section']}")
            logger.debug(f"SAVE_SECTION_DEBUG: Section update content type: {type(state['agent_output'].section_update)}")
        else:
            logger.info(f"SAVE_SECTION_DEBUG: ❌ Chat Agent did NOT generate section_update for section {state['current_section']}")
            if state.get('agent_output'):
                logger.debug(f"SAVE_SECTION_DEBUG: Agent output exists but section_update is: {state['agent_output'].section_update}")
            else:
                logger.debug(f"SAVE_SECTION_DEBUG: No agent output exists at all")

    except Exception as e:
        logger.error(f"Failed to parse structured output: {e}\nResponse: {response.content if 'response' in locals() else ''}")
        default_output = ChatAgentOutput(
            reply="Sorry, I encountered a formatting error. Could you rephrase?",
            router_directive="stay",
            score=None,
            section_update=None,
        )
        state["agent_output"] = default_output
        state["router_directive"] = "stay"
        state["messages"].append(AIMessage(content=default_output.reply))
        state["awaiting_user_input"] = True
        state.setdefault("short_memory", []).append(AIMessage(content=default_output.reply))
    return state


async def memory_updater_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Memory updater node that persists section states and updates canvas data.
    
    Responsibilities:
    - Update section_states with latest content
    - Update canvas_data with extracted values
    - Manage short_memory size
    - Handle database writes
    """
    logger.info("=== DATABASE_DEBUG: memory_updater_node() ENTRY ===")
    logger.info("DATABASE_DEBUG: Memory updater node processing agent output")
    
    agent_out = state.get("agent_output")
    logger.debug(f"DATABASE_DEBUG: Agent output exists: {bool(agent_out)}")
    if agent_out:
        logger.debug(f"DATABASE_DEBUG: Agent output - section_update: {bool(agent_out.section_update)}, score: {agent_out.score}, router_directive: {agent_out.router_directive}")

    # [DIAGNOSTIC] Log state before update
    logger.info(f"DATABASE_DEBUG: section_states BEFORE update: {state.get('section_states', {})}")
    logger.debug(f"DATABASE_DEBUG: Current section: {state.get('current_section')}")
    context_packet = state.get('context_packet')
    logger.debug(f"DATABASE_DEBUG: Context packet section: {context_packet.section_id if context_packet else None}")

    # Decide status based on score and directive
    def _status_from_output(score, directive):
        """Return status *string* to align with get_next_unfinished_section() logic."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value  # "done"
        if score is not None and score >= 3:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    # [SAVE_SECTION_DEBUG] Track decision path in memory_updater_node
    logger.info(f"SAVE_SECTION_DEBUG: memory_updater_node decision analysis:")
    logger.info(f"SAVE_SECTION_DEBUG: - agent_out exists: {bool(agent_out)}")
    if agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.section_update exists: {bool(agent_out.section_update)}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.score: {agent_out.score}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.router_directive: {agent_out.router_directive}")
    else:
        logger.info(f"SAVE_SECTION_DEBUG: - No agent_out, will not call save_section")
    
    if agent_out and agent_out.section_update:
        section_id = state["current_section"].value
        logger.info(f"SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 1: Processing section_update for section {section_id}")
        logger.info(f"DATABASE_DEBUG: Processing section_update for section {section_id}")
        logger.debug(f"DATABASE_DEBUG: Section update content type: {type(agent_out.section_update)}")
        
        # DEBUG: Log what content is being saved to which section
        logger.warning(f"CONTENT_DEBUG: About to save content to section {section_id}")
        if hasattr(agent_out.section_update, 'content') and hasattr(agent_out.section_update.content, 'content'):
            # Try to extract first paragraph text for debugging
            try:
                first_para = agent_out.section_update.content.content[0]
                if hasattr(first_para, 'content') and first_para.content:
                    first_text = first_para.content[0].get('text', 'No text')
                    logger.warning(f"CONTENT_DEBUG: First paragraph starts with: {first_text[:100]}...")
            except:
                logger.warning(f"CONTENT_DEBUG: Could not extract content preview")
        
        # Save to database using save_section tool
        logger.info(f"SAVE_SECTION_DEBUG: ✅ CALLING save_section with structured content")
        logger.debug("DATABASE_DEBUG: Calling save_section tool with structured content")
        
        # [CRITICAL DEBUG] Log the exact parameters being passed to save_section
        computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
        logger.info(f"SAVE_SECTION_DEBUG: About to call save_section with:")
        logger.info(f"SAVE_SECTION_DEBUG: - user_id: {state['user_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - doc_id: {state['doc_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - section_id: {section_id}")
        logger.info(f"SAVE_SECTION_DEBUG: - score: {agent_out.score} (type: {type(agent_out.score)})")
        logger.info(f"SAVE_SECTION_DEBUG: - status: {computed_status} (type: {type(computed_status)})")
        logger.info(f"SAVE_SECTION_DEBUG: - router_directive was: {agent_out.router_directive} (type: {type(agent_out.router_directive)})")
        
        save_result = await save_section.ainvoke({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "section_id": section_id,
            "content": agent_out.section_update.content.model_dump(), # FINAL FIX: Pass the Tiptap doc directly
            "score": agent_out.score,
            "status": computed_status,
        })
        logger.debug(f"DATABASE_DEBUG: save_section returned: {bool(save_result)}")
        
        # Update local state
        logger.debug("DATABASE_DEBUG: Updating local section_states with new content")
        state["section_states"][section_id] = {
            "section_id": section_id,
            "content": agent_out.section_update.content.model_dump(),  # CORRECTED: Store Tiptap doc directly
            "score": agent_out.score,
            "status": _status_from_output(agent_out.score, agent_out.router_directive),
        }
        logger.info(f"SAVE_SECTION_DEBUG: ✅ BRANCH 1 COMPLETED: Section {section_id} saved with structured content")

        # ----------------------------------------------------------
        # NEW: Extract Interview basics and update canvas_data
        # Better approach: Use LLM to extract structured data
        # ----------------------------------------------------------
        if state.get("current_section") == SectionID.INTERVIEW:
            try:
                # Use LLM to extract structured information from the content
                plain_text = await extract_plain_text.ainvoke(agent_out.section_update.content.model_dump())
                
                # Create a simple extraction prompt for the LLM
                extraction_prompt = f"""
                Extract the following information from this interview summary:
                {plain_text}
                
                Important instructions:
                - Extract the ACTUAL values provided by the user
                - If you see "Not provided" or similar placeholders, return null
                - Look for real names, company names, and industries
                
                Return ONLY a JSON object with these fields (use null if not found or if placeholder text):
                {{"name": "...", "company": "...", "industry": "..."}}
                """
                
                # Use GPT-4O for data extraction accuracy
                llm = get_model(OpenAIModelName.GPT_4O)
                extraction_response = await llm.ainvoke(extraction_prompt)
                
                import json
                try:
                    extracted_data = json.loads(extraction_response.content)
                    name_val = extracted_data.get("name")
                    company_val = extracted_data.get("company")
                    industry_val = extracted_data.get("industry")
                    
                    # Don't save "Not provided" or similar placeholders
                    if name_val and "not provided" in name_val.lower():
                        name_val = None
                    if company_val and "not provided" in company_val.lower():
                        company_val = None
                    if industry_val and "not provided" in industry_val.lower():
                        industry_val = None
                except:
                    # Fallback to regex if LLM extraction fails
                    import re
                    def _grab(label):
                        match = re.search(fr"{label}:\s*(.+)", plain_text, re.IGNORECASE)
                        return match.group(1).strip() if match else None
                    
                    name_val = _grab("Name")
                    company_val = _grab("Company")
                    industry_val = _grab("Industry")

                canvas_data = state.get("canvas_data")
                if canvas_data:
                    if name_val:
                        canvas_data.client_name = name_val
                    if company_val:
                        canvas_data.company_name = company_val
                    if industry_val:
                        canvas_data.industry = industry_val
                    # Log for debugging
                    logger.info("CANVAS_DEBUG: Updated canvas_data with Interview info → "
                                f"name={name_val}, company={company_val}, industry={industry_val}")
            except Exception as e:
                logger.warning(f"CANVAS_DEBUG: Failed to extract Interview basics: {e}")
        logger.info(f"DATABASE_DEBUG: ✅ Section {section_id} updated with structured content")
        
        # Extract plain text and update canvas data
        # This would parse the content and update specific fields in canvas_data
        # For example, if section is ICP, extract icp_nickname, etc.
        
    # Handle cases where agent provides score/status but no structured section_update  
    elif agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 2: Processing agent output without section_update")
        logger.info("DATABASE_DEBUG: Processing agent output without section_update (likely score/status only)")
        
        if state.get("context_packet"):
            score_section_id = state["context_packet"].section_id.value
            logger.debug(f"DATABASE_DEBUG: Processing score/status update for section {score_section_id}")

            # Only proceed if there's a score to save.
            if agent_out.score is None:
                logger.info(f"DATABASE_DEBUG: No score or section_update for {score_section_id}, skipping save.")
                return state

            # We have a score, so we MUST save. We need to find the content.
            content_to_save = None

            # 1. Try to find content in the current state for the section
            if score_section_id in state.get("section_states", {}) and state["section_states"][score_section_id].get("content"):
                logger.info(f"SAVE_SECTION_DEBUG: Found content for section {score_section_id} in state.")
                # The content in state should now be the correct Tiptap document
                content_to_save = state["section_states"][score_section_id].get("content")
            
            # 2. If not in state, recover from previous message history
            if not content_to_save:
                logger.warning(f"SAVE_SECTION_DEBUG: Content for {score_section_id} not in state, recovering from history.")
                messages = state.get("messages", [])
                if len(messages) >= 2 and isinstance(messages[-1], HumanMessage) and isinstance(messages[-2], AIMessage):
                    summary_text = messages[-2].content
                    logger.info("SAVE_SECTION_DEBUG: Recovered summary text, converting to Tiptap format.")
                    content_to_save = await create_tiptap_content.ainvoke({"text": summary_text})
                else:
                    logger.error(f"SAVE_SECTION_DEBUG: Could not recover summary from message history for {score_section_id}.")

            # 3. If we found content (either from state or recovery), proceed with saving.
            if content_to_save:
                computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
                logger.info(f"SAVE_SECTION_DEBUG: ✅ Calling save_section for {score_section_id} with score and content.")
                
                await save_section.ainvoke({
                    "user_id": state["user_id"],
                    "doc_id": state["doc_id"],
                    "section_id": score_section_id,
                    "content": content_to_save,
                    "score": agent_out.score,
                    "status": computed_status,
                })

                # Update local state consistently, whether it existed before or not.
                state.setdefault("section_states", {})[score_section_id] = {
                    "section_id": score_section_id,
                    "content": content_to_save,
                    "score": agent_out.score,
                    "status": computed_status,
                }
                logger.info(f"DATABASE_DEBUG: ✅ Updated/created section state for {score_section_id} with score {agent_out.score}")
            else:
                # 4. If content recovery failed, we must not call save_section with empty content.
                logger.error(f"DATABASE_DEBUG: ❌ CRITICAL: Aborting save for section {score_section_id} due to missing content.")

        else:
            logger.warning("DATABASE_DEBUG: ⚠️ Cannot update section state as context_packet is missing")

    # [SAVE_SECTION_DEBUG] Final decision summary
    if not agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: ❌ FINAL RESULT: No agent_out - save_section was NEVER called")
    elif agent_out.section_update:
        logger.info(f"SAVE_SECTION_DEBUG: ✅ FINAL RESULT: Had section_update - save_section was called in BRANCH 1")
    elif agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: ✅ FINAL RESULT: Had agent_out but no section_update - save_section was called in BRANCH 2 (if conditions met)")
    else:
        logger.info(f"SAVE_SECTION_DEBUG: ❌ FINAL RESULT: Unknown state - save_section may not have been called")
    
    # [DIAGNOSTIC] Log state after update
    logger.info(f"DATABASE_DEBUG: section_states AFTER update: {state.get('section_states', {})}")
    logger.info("=== DATABASE_DEBUG: memory_updater_node() EXIT ===")

    return state


async def implementation_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Implementation node that generates the final checklist/PDF.
    
    Only runs when all sections are complete.
    """
    logger.info("Implementation node - Generating final deliverables")
    
    try:
        # Export checklist
        result = await export_checklist.ainvoke({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "canvas_data": state["canvas_data"].model_dump(),
        })
        
        # Add completion message
        completion_msg = AIMessage(
            content=f"Congratulations! Your Value Canvas is complete. "
            f"You can download your implementation checklist here: {result['url']}"
        )
        state["messages"].append(completion_msg)
        
    except Exception as e:
        logger.error(f"Error generating implementation: {e}")
        error_msg = AIMessage(
            content=f"I encountered an error generating your checklist: {str(e)}. "
            "Your Value Canvas data has been saved and you can try exporting again later."
        )
        state["messages"].append(error_msg)
    
    return state



def route_decision(state: ValueCanvasState) -> Literal["implementation", "chat_agent", "halt"]:
    """Determine the next node to go to based on current state."""
    # 1. All sections complete → Implementation
    if state.get("finished", False):
        return "implementation"
    
    # Helper: determine if there's an unresponded user message
    def has_pending_user_input() -> bool:
        msgs = state.get("messages", [])
        if not msgs:
            return False
        last_msg = msgs[-1]
        from langchain_core.messages import HumanMessage, AIMessage  # local import to avoid circular
        # If last message is from user, agent hasn't replied yet
        return isinstance(last_msg, HumanMessage)
    
    directive = state.get("router_directive")
    
    # 2. STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        # If the user has replied since last AI message, forward to Chat Agent.
        if has_pending_user_input():
            return "chat_agent"

        # 如果 AI 还在等用户回复，则停机等待下一次 run（防止重复提问）。
        if state.get("awaiting_user_input", False):
            return "halt"

        # 否则直接 halt（通常刚初始化时会走到这）。
        return "halt"
    
    # 3. NEXT/MODIFY directive - section transition  
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        # For NEXT/MODIFY directives, we need to let the router handle the transition
        # and then ask the first question for the new section
        
        # If there's a pending user input, it means user has acknowledged the transition
        # Let router process the directive and then go to chat_agent for new section
        if has_pending_user_input():
            return "chat_agent"
        
        # If Chat Agent just set NEXT directive but user hasn't responded yet, halt and wait
        msgs = state.get("messages", [])
        if msgs and isinstance(msgs[-1], AIMessage):
            return "halt"
        
        # Default case - go to chat_agent to ask first question of current section
        return "chat_agent"
    
    # 4. Default case - halt to prevent infinite loops
    return "halt"


# Build the graph
def build_value_canvas_graph():
    """Build the Value Canvas agent graph."""
    graph = StateGraph(ValueCanvasState)
    
    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("router", router_node)
    graph.add_node("chat_agent", chat_agent_node)
    graph.add_node("memory_updater", memory_updater_node)
    graph.add_node("implementation", implementation_node)
    
    # Add edges
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "router")
    
    # Router can go to chat agent or implementation
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "chat_agent": "chat_agent",
            "implementation": "implementation",
            "halt": END,
        }
    )
    
    # Chat agent has no tools, goes directly to memory_updater
    graph.add_edge("chat_agent", "memory_updater")
    
    # Memory updater goes back to router
    graph.add_edge("memory_updater", "router")
    
    # Implementation ends the graph
    graph.add_edge("implementation", END)
    
    return graph.compile()


# Create the runnable graph
graph = build_value_canvas_graph()


# Initialize function for new conversations
async def initialize_value_canvas_state(user_id: str = None, doc_id: str = None) -> ValueCanvasState:
    """Initialize a new Value Canvas state.
    
    Args:
        user_id: User UUID (will be generated if not provided)
        doc_id: Document UUID (will be generated if not provided)
    """
    import uuid
    
    # Ensure user_id is a valid UUID string
    if not user_id:
        user_id = str(uuid.uuid4())
        logger.info(f"Generated new user_id: {user_id}")
    else:
        try:
            uuid.UUID(user_id)
        except ValueError:
            # Deterministically derive a UUID from provided string
            user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
            logger.info(f"Converted non-UUID user_id to UUID: {user_id}")

    # Ensure doc_id is a valid UUID string
    if not doc_id:
        doc_id = str(uuid.uuid4())
        logger.info(f"Generated new doc_id: {doc_id}")
    else:
        try:
            uuid.UUID(doc_id)
        except ValueError:
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))
            logger.info(f"Converted non-UUID doc_id to UUID: {doc_id}")
    
    initial_state = ValueCanvasState(
        user_id=user_id,
        doc_id=doc_id,
        messages=[],
        current_section=SectionID.INTERVIEW,
        router_directive=RouterDirective.NEXT,  # Start by loading first section
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "doc_id": doc_id,
        "section_id": SectionID.INTERVIEW.value,
        "canvas_data": {},
    })
    
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you create your Value Canvas - "
        "a powerful framework that will transform your marketing messaging. "
        "Let's start by getting to know you and your business better."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state


__all__ = ["graph", "initialize_value_canvas_state"]