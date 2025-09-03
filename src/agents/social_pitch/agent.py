"""Social Pitch Agent implementation using LangGraph StateGraph."""

import logging
import re
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from core.llm import get_model, LLMConfig

from .models import (
    ChatAgentOutput,
    ContextPacket,
    NameData,
    SameData,
    FameData,
    PainData,
    AimData,
    GameData,
    RouterDirective,
    SectionContent,
    SectionID,
    SectionState,
    SectionStatus,
    TiptapDocument,
    SocialPitchData,
    SocialPitchState,
)
from .prompts import (
    get_next_unfinished_section,
    SECTION_NAMES,
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
    validate_field,
]

implementation_tools = [
    export_checklist,
]

# Create tool nodes
router_tool_node = ToolNode(router_tools)
memory_updater_tool_node = ToolNode(memory_updater_tools)
implementation_tool_node = ToolNode(implementation_tools)


async def initialize_node(state: SocialPitchState, config: RunnableConfig) -> SocialPitchState:
    """
    Initialize node that ensures all required state fields are present.
    This is the first node in the graph to handle LangGraph Studio's incomplete state.
    """
    logger.info("Initialize node - Setting up default values (Social Pitch)")

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
        state["current_section"] = SectionID.NAME
    if "router_directive" not in state:
        state["router_directive"] = RouterDirective.NEXT
    if "finished" not in state:
        state["finished"] = False
    if "section_states" not in state:
        state["section_states"] = {}
    if "pitch_data" not in state:
        state["pitch_data"] = SocialPitchData()
    if "short_memory" not in state:
        state["short_memory"] = []
    if "error_count" not in state:
        state["error_count"] = 0
    if "last_error" not in state:
        state["last_error"] = None
    if "is_awaiting_rating" not in state:
        state["is_awaiting_rating"] = False
    if "messages" not in state:
        state["messages"] = []
    
    logger.info(f"Initialize complete (Social Pitch) - User: {state['user_id']}, Thread: {state['thread_id']}")
    return state


async def router_node(state: SocialPitchState, config: RunnableConfig) -> SocialPitchState:
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
        f"Router node (Social Pitch) - Current section: {state['current_section']}, Directive: {state['router_directive']}"
    )

    # Process router directive
    directive = state.get("router_directive", RouterDirective.STAY)
    
    if directive == RouterDirective.STAY:
        # Stay on current section, no context reload needed
        logger.info("Staying on current section")
        return state
    
    elif directive == RouterDirective.NEXT:
        # Find next unfinished section
        logger.info(f"DEBUG: Preparing to find next Social Pitch section. Current section states: {state.get('section_states', {})}")
        
        # DEBUG: Log current section and its state before transition
        current_section_id = state["current_section"].value
        logger.info(f"TRANSITION_DEBUG: Leaving section {current_section_id}")
        if current_section_id in state.get("section_states", {}):
            current_state = state["section_states"][current_section_id]
            logger.info(f"TRANSITION_DEBUG: Section {current_section_id} final state - status: {current_state.status}, has_content: {bool(current_state.content)}")
        
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        logger.info(f"DEBUG: get_next_unfinished_section decided the next section is: {next_section}")
        
        if next_section:
            logger.info(f"Moving to next Social Pitch section: {next_section}")
            
            previous_section = state["current_section"]
            state["current_section"] = next_section

            # Only clear short_memory when transitioning to a different section
            if previous_section != next_section:
                state["short_memory"] = []
                logger.info(f"Cleared short_memory for new Social Pitch section {next_section.value}")
            else:
                logger.info(f"Preserved short_memory on same-section NEXT directive for {next_section.value}")

            # Get context for new section
            logger.debug(f"DATABASE_DEBUG: Router calling get_context for Social Pitch section {next_section.value}")
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": next_section.value,
                "pitch_data": state["pitch_data"].model_dump(),
            })
            logger.debug(f"DATABASE_DEBUG: get_context returned for Social Pitch section {next_section.value}")
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        else:
            # All sections complete
            logger.info("All Social Pitch sections complete, setting finished flag")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1].lower()
        try:
            new_section = SectionID(section_id)
            logger.info(f"Jumping to Social Pitch section: {new_section}")
            prev_section = state.get("current_section")
            state["current_section"] = new_section
            
            # Only clear short_memory when switching to a different section
            if prev_section != new_section:
                state["short_memory"] = []
                logger.info(f"Cleared short_memory for jumped Social Pitch section {new_section.value}")
            else:
                logger.info(f"Preserved short_memory for same-section refresh {new_section.value}")
            
            # Get context for new section
            logger.debug(f"DATABASE_DEBUG: Router calling get_context for modify Social Pitch section {new_section.value}")
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": new_section.value,
                "pitch_data": state["pitch_data"].model_dump(),
            })
            logger.debug(f"DATABASE_DEBUG: get_context returned for modify Social Pitch section {new_section.value}")
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        except ValueError:
            logger.error(f"Invalid Social Pitch section ID: {section_id}")
            state["last_error"] = f"Invalid Social Pitch section ID: {section_id}"
            state["error_count"] += 1
    
    return state


async def chat_agent_node(state: SocialPitchState, config: RunnableConfig) -> SocialPitchState:
    """
    Chat agent node that handles section-specific conversations.
    
    Responsibilities:
    - Generate responses based on context_packet system prompt
    - Validate user input
    - Generate section content (Tiptap JSON)
    - Set score and router_directive
    - Output structured ChatAgentOutput
    """
    logger.info(f"Chat agent node (Social Pitch) - Section: {state['current_section']}")
    
    # Create a new context packet for this turn
    context_packet = state.get('context_packet')
    logger.info(
        f"DEBUG_CHAT_AGENT: Social Pitch Context Packet received: {context_packet}"
    )

    # Get LLM - no tools for chat agent per design doc
    llm = get_model()
    
    messages: list[BaseMessage] = []
    last_human_msg: HumanMessage | None = None

    # Check if we should add summary instruction
    awaiting = state.get("awaiting_user_input", False)
    current_section = state["current_section"]
    section_state = state.get("section_states", {}).get(current_section.value)
    section_has_content = bool(section_state and section_state.content)
    
    # Only add summary reminder if section already has saved content that needs rating
    if section_has_content and not awaiting:
        # This is for sections that were previously saved but need rating
        summary_reminder = (
            "The user has previously worked on this section. "
            "Review the saved content and ask for their satisfaction rating if not already provided."
        )
        messages.append(SystemMessage(content=summary_reminder))
        logger.info(f"SUMMARY_REMINDER: Added reminder to check existing content for Social Pitch section {current_section.value}")

    # 2) Section-specific system prompt from context packet
    if state.get("context_packet"):
        # NEW: Prioritize displaying existing section content if available
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id)

        if section_state and section_state.content:
            logger.info(f"MEMORY_DEBUG: Found existing content for Social Pitch {current_section_id}. Prioritizing it.")
            try:
                # Use the plain_text version if available, otherwise extract it.
                content_dict = section_state.content.content.model_dump()
                plain_text_summary = await extract_plain_text.ainvoke({"tiptap_json": content_dict})

                review_prompt = (
                    "CRITICAL CONTEXT: The user is reviewing a Social Pitch section they have already completed. "
                    "Their previous answers have been saved. Your primary task is to present this saved information back to them if they ask for it. "
                    "DO NOT ask the interview questions again. "
                    "Here is the exact summary of their previously provided answers. You MUST use this information:\\n\\n"
                    f"--- PREVIOUSLY SAVED SUMMARY ---\\n{plain_text_summary}\\n--- END SUMMARY ---"
                )
                messages.append(SystemMessage(content=review_prompt))
            except Exception as e:
                logger.error(f"MEMORY_DEBUG: Failed to extract plain text from existing state for Social Pitch {current_section_id}: {e}")
                # Fallback to the original prompt if extraction fails
                messages.append(SystemMessage(content=state["context_packet"].system_prompt))
        else:
            # Original behavior: use the default system prompt for the section
            messages.append(SystemMessage(content=state["context_packet"].system_prompt))

        # Add progress information based on section_states
        completed_sections = []
        for section_id, section_state in state.get("section_states", {}).items():
            if section_state.status == SectionStatus.DONE:
                section_name = SECTION_NAMES.get(SectionID(section_id), section_id)
                completed_sections.append(section_name)
        
        current_section_name = SECTION_NAMES.get(state["current_section"], state["current_section"].value)
        
        progress_info = (
            f"\\n\\nSYSTEM STATUS:\\n"
            f"- Total Social Pitch sections: 6\\n"
            f"- Completed: {len(completed_sections)} sections"
        )
        if completed_sections:
            progress_info += f" ({', '.join(completed_sections)})"
        progress_info += f"\\n- Currently working on: {current_section_name}\\n"
        
        messages.append(SystemMessage(content=progress_info))
        
        # Add clarification for new sections without content
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id)
        if not section_state or not section_state.content:
            new_section_instruction = (
                f"IMPORTANT: You are now in the {current_section_id} section of the Social Pitch. "
                "This is a NEW section with no content yet. "
                "Start by following the conversation flow defined in the section prompt. "
                "Do NOT generate section_update until you have collected actual data for THIS section. "
                "Do NOT reference or include content from previous sections."
            )
            messages.append(SystemMessage(content=new_section_instruction))

    # 3) Recent conversation memory
    messages.extend(state.get("short_memory", []))

    # 4) Last human message (if any and agent hasn't replied yet)
    if state.get("messages"):
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append(_last_msg)
            last_human_msg = _last_msg

    # --- Pre-LLM Context Injection ---
    try:
        from .prompts import SECTION_TEMPLATES, get_next_unfinished_section
        
        temp_states = state.get("section_states", {}).copy()
        current_section_id = state["current_section"].value
        
        if current_section_id not in temp_states:
            temp_states[current_section_id] = SectionState(
                section_id=SectionID(current_section_id),
                status=SectionStatus.DONE
            )
        else:
            # Assume the current section will be completed in this turn for prediction
            temp_states[current_section_id].status = SectionStatus.DONE

        next_section = get_next_unfinished_section(temp_states)
        
        if next_section:
            next_section_name = SECTION_NAMES.get(next_section, next_section.value)
            instructional_prompt = (
                f"SYSTEM INSTRUCTION: The next Social Pitch section is '{next_section_name}'. "
                "If the user confirms to proceed, you MUST use this exact name in your transition message."
            )
            messages.append(SystemMessage(content=instructional_prompt))
            logger.info(f"Injected next Social Pitch section name into context: '{next_section_name}'")
    except Exception as e:
        logger.warning(f"Could not determine next Social Pitch section for prompt injection: {e}")
    # --- End of Pre-LLM Context Injection ---

    try:
        # DEBUG: Log LLM input
        logger.info("=== LLM_INPUT_DEBUG (Social Pitch) ===")
        logger.info(f"Current section: {state['current_section']}")
        logger.info(f"Total messages count: {len(messages)}")
        logger.info("Last 2 messages:")
        for i, msg in enumerate(messages[-2:]):
            msg_type = type(msg).__name__
            content_preview = msg.content[:200] if hasattr(msg, 'content') else str(msg)[:200]
            logger.info(f"  [{i}] {msg_type}: {content_preview}...")
        
        # Use LangChain structured output with function calling for better reliability
        logger.info("🚀 Using LangChain structured output with function calling method (Social Pitch)")
        
        # Use function calling method which is more reliable than JSON parsing
        structured_llm = llm.with_structured_output(ChatAgentOutput, method="function_calling")
        
        # Add token limits to prevent infinite generation
        if hasattr(structured_llm, 'bind'):
            structured_llm = structured_llm.bind(
                max_tokens=LLMConfig.DEFAULT_MAX_TOKENS,
                top_p=LLMConfig.DEFAULT_TOP_P
            )
        
        logger.info("=== CALLING LLM WITH FUNCTION CALLING METHOD (Social Pitch) ===")
        # Use non-streaming config with tags to prevent decision data from appearing in user stream
        non_streaming_config = RunnableConfig(
            configurable={"stream": False},
            tags=["internal_decision", "do_not_stream"],
            callbacks=[]
        )
        llm_output = await structured_llm.ainvoke(messages, config=non_streaming_config)

        # DEBUG: Log the COMPLETE LLM output
        logger.info("=== LLM_OUTPUT_DEBUG (Social Pitch) ===")
        logger.info(f"Full reply: {llm_output.reply}")
        logger.info(f"Router directive: {llm_output.router_directive}")
        logger.info(f"Is requesting rating: {llm_output.is_requesting_rating}")
        logger.info(f"Score: {llm_output.score}")
        logger.info(f"Section update provided: {bool(llm_output.section_update)}")
        if llm_output.section_update:
            logger.info(f"Section update content keys: {list(llm_output.section_update.keys())}")
        else:
            logger.warning("❌ LLM did NOT provide section_update!")
        
        if llm_output.section_update:
            logger.warning(f"AGENT_OUTPUT_DEBUG: Social Pitch section update generated for section {state['current_section'].value}")
        
        # DEBUG: Check state consistency
        logger.info(f"AGENT_OUTPUT_DEBUG: Current Social Pitch section_states: {list(state.get('section_states', {}).keys())}")

        # Create the final agent_output for the state, starting with LLM output
        agent_output = llm_output
        
        # Add a safety rail: if the LLM provides a low score, force a 'stay' directive
        if agent_output.score is not None and agent_output.score < 3:
            logger.info(f"Low score ({agent_output.score}) detected from LLM. Forcing 'stay' directive.")
            agent_output.router_directive = "stay"

        # === SECTION_UPDATE ANALYSIS ===
        if agent_output.is_requesting_rating and not agent_output.section_update:
            logger.warning("=== SECTION_UPDATE_ANALYSIS (Social Pitch) ===")
            logger.warning("LLM is requesting rating but didn't provide section_update")
            
            # Analyze the reply to understand why
            reply_lower = agent_output.reply.lower()
            has_summary_keywords = any(keyword in reply_lower for keyword in [
                "summary", "gathered", "capture", "here's what", "information", 
                "name", "company", "position", "category", "achievement"
            ])
            
            logger.warning(f"Reply contains summary keywords: {has_summary_keywords}")
            logger.warning(f"Reply length: {len(agent_output.reply)}")
            logger.warning(f"Current section: {state['current_section']}")
            
            if has_summary_keywords:
                logger.error("🚨 LLM generated summary but FAILED to provide section_update!")
                logger.error("This indicates a prompt understanding issue or model limitation")
            
        # Set the is_awaiting_rating flag based on the structured output from the LLM
        if agent_output.is_requesting_rating:
            # CRITICAL VALIDATION: If requesting rating, must have section_update
            if not agent_output.section_update:
                logger.error("CRITICAL ERROR: Model requested rating but provided no section_update!")
                logger.error("This violates the core system prompt rule and will cause data loss.")
                logger.error(f"Original agent_output: {agent_output}")
                
                # Force correction to prevent infinite loops
                agent_output = ChatAgentOutput(
                    reply=(
                        "I notice I haven't properly collected all your information yet. "
                        "Let me continue with the next question. "
                        "Could you share more details about this component?"
                    ),
                    router_directive="stay",
                    is_requesting_rating=False,
                    score=None,
                    section_update=None
                )
                logger.info("FORCED CORRECTION: Created new corrected agent output to continue collecting information.")
            
            state["is_awaiting_rating"] = agent_output.is_requesting_rating
            logger.info(f"State updated: is_awaiting_rating set to {agent_output.is_requesting_rating}")
        else:
            state["is_awaiting_rating"] = False

        logger.info(f"DEBUG_CHAT_AGENT: Social Pitch agent output generated: {agent_output}")

        # Save section_update to a temporary key to be processed by the memory updater
        state["temp_agent_output"] = agent_output # Store the full agent_output for memory_updater

        # Determine router directive based on score, per design doc
        if agent_output.score is not None:
            if agent_output.score >= 3:
                calculated_directive = RouterDirective.NEXT
            else:
                calculated_directive = RouterDirective.STAY
                
            state["router_directive"] = calculated_directive
            
        else:
            # Fallback to value supplied by model (may be stay/next/modify)
            state["router_directive"] = agent_output.router_directive

        state["agent_output"] = agent_output

        # --- MVP Fallback: ensure reply contains clear question -----------------------
        need_question = (
            state["router_directive"] == RouterDirective.STAY
            and agent_output.score is None
        )

        if need_question:
            # If reply has neither question mark nor clear instruction words, append prompt
            has_question = re.search(r"[?？]", agent_output.reply, re.IGNORECASE)
            has_instruction = any(word in agent_output.reply.lower() for word in [
                "please", "provide", "describe", "tell", "share", "what", "how", "when", "where", "why"
            ])
            
            if not has_question and not has_instruction:
                # Only add fallback text when there's really no clear instruction
                agent_output.reply += (
                    "\\n\\nPlease provide your response to continue."
                )

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
        logger.info(f"DEBUG_CHAT_AGENT: Social Pitch agent output generated: {state.get('agent_output')}")
        
        # [SAVE_SECTION_DEBUG] Track when Chat Agent generates section_update
        if state.get('agent_output') and state['agent_output'].section_update:
            logger.info(f"SAVE_SECTION_DEBUG: ✅ Chat Agent DID generate section_update for Social Pitch section {state['current_section']}")
        else:
            logger.info(f"SAVE_SECTION_DEBUG: ❌ Chat Agent did NOT generate section_update for Social Pitch section {state['current_section']}")

    except Exception as e:
        logger.error(f"Failed to get structured output from LLM (Social Pitch): {e}")
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


async def memory_updater_node(state: SocialPitchState, config: RunnableConfig) -> SocialPitchState:
    """
    Memory updater node that persists section states and updates pitch data.
    
    Responsibilities:
    - Update section_states with latest content
    - Update pitch_data with extracted values
    - Manage short_memory size
    - Handle database writes
    """
    logger.info("=== DATABASE_DEBUG: memory_updater_node() ENTRY (Social Pitch) ===")
    logger.info("DATABASE_DEBUG: Memory updater node processing Social Pitch agent output")
    
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
    logger.info("SAVE_SECTION_DEBUG: memory_updater_node decision analysis (Social Pitch):")
    logger.info(f"SAVE_SECTION_DEBUG: - agent_out exists: {bool(agent_out)}")
    if agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.section_update exists: {bool(agent_out.section_update)}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.score: {agent_out.score}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.router_directive: {agent_out.router_directive}")
    else:
        logger.info("SAVE_SECTION_DEBUG: - No agent_out, will not call save_section")
    
    if agent_out and agent_out.section_update:
        section_id = state["current_section"].value
        logger.info(f"SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 1: Processing section_update for Social Pitch section {section_id}")
        logger.info(f"DATABASE_DEBUG: Processing section_update for Social Pitch section {section_id}")
        logger.debug(f"DATABASE_DEBUG: Section update content type: {type(agent_out.section_update)}")
        
        # DEBUG: Log what content is being saved to which section
        logger.warning(f"CONTENT_DEBUG: About to save content to Social Pitch section {section_id}")
        
        # Save to database using save_section tool
        logger.info("SAVE_SECTION_DEBUG: ✅ CALLING save_section with structured content (Social Pitch)")
        logger.debug("DATABASE_DEBUG: Calling save_section tool with structured content (Social Pitch)")
        
        # [CRITICAL DEBUG] Log the exact parameters being passed to save_section
        computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
        logger.info("SAVE_SECTION_DEBUG: About to call save_section with:")
        logger.info(f"SAVE_SECTION_DEBUG: - user_id: {state['user_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - thread_id: {state['thread_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - section_id: {section_id}")
        logger.info(f"SAVE_SECTION_DEBUG: - score: {agent_out.score} (type: {type(agent_out.score)})")
        logger.info(f"SAVE_SECTION_DEBUG: - status: {computed_status} (type: {type(computed_status)})")
        
        save_result = await save_section.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "section_id": section_id,
            "content": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update,
            "score": agent_out.score,
            "status": computed_status,
        })
        logger.debug(f"DATABASE_DEBUG: save_section returned: {bool(save_result)}")
        
        # Update local state
        logger.debug("DATABASE_DEBUG: Updating local section_states with new Social Pitch content")
        # Parse the section_update content properly
        if isinstance(agent_out.section_update, dict) and 'content' in agent_out.section_update:
            tiptap_doc = TiptapDocument.model_validate(agent_out.section_update['content'])
        else:
            logger.error(f"SAVE_SECTION_DEBUG: Invalid section_update structure: {type(agent_out.section_update)}")
            tiptap_doc = TiptapDocument(type="doc", content=[])
        
        state["section_states"][section_id] = SectionState(
            section_id=SectionID(section_id),
            content=SectionContent(
                content=tiptap_doc,
                plain_text=None  # Will be filled later if needed
            ),
            score=agent_out.score,
            status=_status_from_output(agent_out.score, agent_out.router_directive),
        )
        logger.info(f"SAVE_SECTION_DEBUG: ✅ BRANCH 1 COMPLETED: Social Pitch section {section_id} saved with structured content")

        # Extract data and update pitch_data
        section_to_model_map = {
            SectionID.NAME: NameData,
            SectionID.SAME: SameData,
            SectionID.FAME: FameData,
            SectionID.PAIN: PainData,
            SectionID.AIM: AimData,
            SectionID.GAME: GameData,
        }

        current_section = state.get("current_section")
        extraction_model = section_to_model_map.get(current_section)

        if extraction_model:
            try:
                # 1. Extract plain text from the Tiptap JSON content
                plain_text = await extract_plain_text.ainvoke({"tiptap_json": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update})
                logger.info(f"EXTRACTION_DEBUG: Plain text for Social Pitch {current_section.value} extraction:\\n---\\n{plain_text}\\n---")
                
                # 2. Define a simple prompt for the LLM
                extraction_prompt = f"""
                You are a data extraction specialist. Your task is to accurately extract information from the user's conversation summary and structure it according to the provided format. The context is a "Social Pitch," a 6-component business introduction framework.

                Section for Extraction: "{current_section.name}"

                User's Summary:
                ---
                {plain_text}
                ---

                Please extract the data fields based on their descriptions in the target data model. Pay close attention to nuances and ensure all relevant details are captured.
                """
                
                # 3. Get the LLM and bind it to our desired structured output model
                llm = get_model()
                structured_llm = llm.with_structured_output(extraction_model)
                # Add token limits to prevent infinite generation
                if hasattr(structured_llm, 'bind'):
                    structured_llm = structured_llm.bind(max_tokens=2000)
                
                # 4. Invoke the LLM to get a structured Pydantic object directly
                logger.info(f"EXTRACTION_DEBUG: Calling LLM with structured_output for {extraction_model.__name__}.")
                # Use non-streaming config with tags to prevent extraction data from appearing in user stream
                non_streaming_config = RunnableConfig(
                    configurable={"stream": False},
                    tags=["internal_extraction", "do_not_stream"]
                )
                extracted_data = await structured_llm.ainvoke(extraction_prompt, config=non_streaming_config)
                logger.info(f"EXTRACTION_DEBUG: Successfully extracted structured data for Social Pitch {current_section.value}: {extracted_data}")

                # 5. Safely update pitch_data with the extracted, validated data
                pitch_data = state.get("pitch_data")
                if pitch_data and extracted_data:
                    for field, value in extracted_data.model_dump().items():
                        if hasattr(pitch_data, field) and value is not None:
                            setattr(pitch_data, field, value)
                    
                    logger.info(
                        "PITCH_DEBUG: Updated pitch_data with structured info for Social Pitch section "
                        f"'{current_section.value}'"
                    )
            except Exception as e:
                logger.warning(f"PITCH_DEBUG: Failed to extract structured data for Social Pitch {current_section.value}: {e}")
            
        logger.info(f"DATABASE_DEBUG: ✅ Social Pitch section {section_id} updated with structured content")
        
    # Handle cases where agent provides score/status but no structured section_update  
    elif agent_out:
        logger.info("SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 2: Processing Social Pitch agent output without section_update")
        logger.info("DATABASE_DEBUG: Processing Social Pitch agent output without section_update (likely score/status only)")
        
        if state.get("context_packet"):
            score_section_id = state["context_packet"].section_id.value
            logger.debug(f"DATABASE_DEBUG: Processing score/status update for Social Pitch section {score_section_id}")

            # Only proceed if there's a score to save.
            if agent_out.score is None:
                logger.info(f"DATABASE_DEBUG: No score or section_update for Social Pitch {score_section_id}, skipping save.")
                return state

            # We have a score, so we MUST save. We need to find the content.
            content_to_save = None

            # 1. Try to find content in the current state for the section
            if score_section_id in state.get("section_states", {}) and state["section_states"][score_section_id].content:
                logger.info(f"SAVE_SECTION_DEBUG: Found content for Social Pitch section {score_section_id} in state.")
                content_to_save = state["section_states"][score_section_id].content.content.model_dump()
            
            # 2. If not in state, recover from previous message history with improved logic
            if not content_to_save:
                logger.warning(f"SAVE_SECTION_DEBUG: Content for Social Pitch {score_section_id} not in state, recovering from history.")
                messages = state.get("messages", [])
                summary_text = None
                # Search backwards through the message history to find the last summary message.
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage):
                        content_lower = msg.content.lower()
                        if "summary" in content_lower and ("satisfied" in content_lower or "rate 0-5" in content_lower):
                            summary_text = msg.content
                            logger.info("SAVE_SECTION_DEBUG: Found candidate summary message in history.")
                            break
                
                if summary_text:
                    logger.info("SAVE_SECTION_DEBUG: Recovered summary text, converting to Tiptap format.")
                    content_to_save = await create_tiptap_content.ainvoke({"text": summary_text})
                else:
                    logger.error(f"SAVE_SECTION_DEBUG: Could not recover summary from message history for Social Pitch {score_section_id}.")

            # 3. If we found content (either from state or recovery), proceed with saving.
            if content_to_save:
                computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
                logger.info(f"SAVE_SECTION_DEBUG: ✅ Calling save_section for Social Pitch {score_section_id} with score and content.")
                
                await save_section.ainvoke({
                    "user_id": state["user_id"],
                    "thread_id": state["thread_id"],
                    "section_id": score_section_id,
                    "content": content_to_save,
                    "score": agent_out.score,
                    "status": computed_status,
                })

                # Update local state consistently
                if isinstance(content_to_save, dict):
                    tiptap_doc = TiptapDocument.model_validate(content_to_save)
                else:
                    tiptap_doc = content_to_save
                
                state.setdefault("section_states", {})[score_section_id] = SectionState(
                    section_id=SectionID(score_section_id),
                    content=SectionContent(
                        content=tiptap_doc,
                        plain_text=None
                    ),
                    score=agent_out.score,
                    status=computed_status,
                )
                logger.info(f"DATABASE_DEBUG: ✅ Updated/created section state for Social Pitch {score_section_id} with score {agent_out.score}")
            else:
                logger.error(f"DATABASE_DEBUG: ❌ CRITICAL: Aborting save for Social Pitch section {score_section_id} due to missing content.")

        else:
            logger.warning("DATABASE_DEBUG: ⚠️ Cannot update section state as context_packet is missing")

    # [DIAGNOSTIC] Log state after update
    logger.info(f"DATABASE_DEBUG: section_states AFTER update: {state.get('section_states', {})}")
    logger.info("=== DATABASE_DEBUG: memory_updater_node() EXIT (Social Pitch) ===")

    return state


async def implementation_node(state: SocialPitchState, config: RunnableConfig) -> SocialPitchState:
    """
    Implementation node that generates the final Social Pitch deliverable.
    
    Only runs when all sections are complete.
    """
    logger.info("Implementation node (Social Pitch) - Generating final deliverables")
    
    try:
        # Export Social Pitch deliverable
        result = await export_checklist.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "pitch_data": state["pitch_data"].model_dump(),
        })
        
        # Add completion message
        completion_msg = AIMessage(
            content=f"Congratulations! Your Social Pitch is complete. "
            f"You now have a powerful 6-component framework for business introductions. "
            f"You can download your complete Social Pitch here: {result['url']}"
        )
        state["messages"].append(completion_msg)
        
    except Exception as e:
        logger.error(f"Error generating Social Pitch implementation: {e}")
        error_msg = AIMessage(
            content=f"I encountered an error generating your Social Pitch deliverable: {str(e)}. "
            "Your Social Pitch data has been saved and you can try exporting again later."
        )
        state["messages"].append(error_msg)
    
    return state


def route_decision(state: SocialPitchState) -> Literal["implementation", "chat_agent", "halt"]:
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
        from langchain_core.messages import (
            HumanMessage,
        )
        # If last message is from user, agent hasn't replied yet
        return isinstance(last_msg, HumanMessage)
    
    directive = state.get("router_directive")
    
    # 2. STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        # If the user has replied since last AI message, forward to Chat Agent.
        if has_pending_user_input():
            return "chat_agent"

        # If AI is still waiting for user response, halt and wait for next run
        if state.get("awaiting_user_input", False):
            return "halt"

        # Otherwise, halt directly
        return "halt"
    
    # 3. NEXT/MODIFY directive - section transition  
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        # For NEXT/MODIFY directives, we need to let the router handle the transition
        # and then ask the first question for the new section
        
        # If there's a pending user input, it means user has acknowledged the transition
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
def build_social_pitch_graph():
    """Build the Social Pitch agent graph."""
    graph = StateGraph(SocialPitchState)
    
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
graph = build_social_pitch_graph()


# Initialize function for new conversations
async def initialize_social_pitch_state(user_id: int = None, thread_id: str = None) -> SocialPitchState:
    """Initialize a new Social Pitch state.
    
    Args:
        user_id: Integer user ID from frontend (will use default if not provided)
        thread_id: Thread UUID (will be generated if not provided)
    """
    import uuid
    
    # Use provided integer user_id or default to 1
    if not user_id:
        user_id = 1
        logger.info(f"Using default user_id: {user_id}")
    else:
        logger.info(f"Using provided user_id: {user_id}")

    # Ensure thread_id is a valid UUID string
    if not thread_id:
        thread_id = str(uuid.uuid4())
        logger.info(f"Generated new thread_id: {thread_id}")
    else:
        try:
            uuid.UUID(thread_id)
        except ValueError:
            thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))
            logger.info(f"Converted non-UUID thread_id to UUID: {thread_id}")
    
    initial_state = SocialPitchState(
        user_id=user_id,
        thread_id=thread_id,
        messages=[],
        current_section=SectionID.NAME,
        router_directive=RouterDirective.NEXT,  # Start by loading first section
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "thread_id": thread_id,
        "section_id": SectionID.NAME.value,
        "pitch_data": {},
    })
    
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you create your Social Pitch - "
        "a compelling and concise answer to the question 'What do you do?' using the proven 6-component framework. "
        "Together, we'll build your NAME, SAME, FAME, PAIN, AIM, and GAME components. "
        "Let's start by getting to know you and your business better."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state


__all__ = ["graph", "initialize_social_pitch_state"]