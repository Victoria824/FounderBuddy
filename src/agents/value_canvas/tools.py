"""Tools for Value Canvas Agent with Supabase integration."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from supabase import create_client, Client

from .models import (
    ContextPacket,
    SectionContent,
    SectionID,
    SectionState,
    SectionStatus,
    TiptapDocument,
    ValidationRule,
)
from .prompts import SECTION_PROMPTS, SECTION_TEMPLATES
from core.settings import settings
from core.dentapp_client import get_dentapp_client
from core.dentapp_utils import (
    get_section_id_int,
    tiptap_to_plain_text,
    plain_text_to_tiptap,
    convert_dentapp_status_to_agent,
    log_api_operation,
    AGENT_ID,
    SECTION_ID_MAPPING,
)

# MVP: Fixed user_id for all users in DentApp API
MVP_USER_ID = 1

logger = logging.getLogger(__name__)

# Initialize Supabase client
def get_supabase_client() -> Client:
    """Get configured Supabase client."""
    logger.debug("=== DATABASE_DEBUG: Starting Supabase client initialization ===")
    
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    supabase_key = getattr(settings, 'SUPABASE_ANON_KEY', None)
    
    logger.debug(f"DATABASE_DEBUG: Raw SUPABASE_URL type: {type(supabase_url)}")
    logger.debug(f"DATABASE_DEBUG: Raw SUPABASE_ANON_KEY type: {type(supabase_key)}")
    
    # Convert SecretStr to string if needed
    if supabase_url and hasattr(supabase_url, 'get_secret_value'):
        logger.debug("DATABASE_DEBUG: Converting SUPABASE_URL from SecretStr")
        supabase_url = supabase_url.get_secret_value()
    if supabase_key and hasattr(supabase_key, 'get_secret_value'):
        logger.debug("DATABASE_DEBUG: Converting SUPABASE_ANON_KEY from SecretStr")
        supabase_key = supabase_key.get_secret_value()
    
    logger.debug(f"DATABASE_DEBUG: Final URL exists: {bool(supabase_url)}")
    logger.debug(f"DATABASE_DEBUG: Final key exists: {bool(supabase_key)}")
    
    if not supabase_url or not supabase_key:
        logger.warning("DATABASE_DEBUG: ⚠️ Supabase credentials not configured, using mock mode")
        return None
    
    logger.debug(f"DATABASE_DEBUG: Creating Supabase client for URL: {supabase_url[:30]}...")
    
    try:
        client = create_client(supabase_url, supabase_key)
        logger.info("DATABASE_DEBUG: ✅ Supabase client created successfully")
        return client
    except Exception as e:
        logger.error(f"DATABASE_DEBUG: ❌ Failed to create Supabase client: {e}")
        return None


@tool
async def get_context(
    user_id: str,
    doc_id: str,
    section_id: str,
    canvas_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get context packet for a specific Value Canvas section.
    
    This tool fetches section data from the database and generates
    the appropriate system prompt based on the section template.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        section_id: Section identifier (e.g., 'icp', 'pain_1')
        canvas_data: Current canvas data for template rendering
    
    Returns:
        Context packet with system prompt and draft content
    """
    logger.info(f"=== DATABASE_DEBUG: get_context() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Section: {section_id}, User: {user_id}, Doc: {doc_id}")
    logger.debug(f"DATABASE_DEBUG: User ID type: {type(user_id)}, Doc ID type: {type(doc_id)}")
    logger.debug(f"DATABASE_DEBUG: Canvas data provided: {bool(canvas_data)}")
    
    # Get section template
    template = SECTION_TEMPLATES.get(section_id)
    if not template:
        raise ValueError(f"Unknown section ID: {section_id}")
    
    # Generate system prompt
    base_prompt = SECTION_PROMPTS.get("base_rules", "")
    section_prompt = template.system_prompt_template
    
    # Render template with canvas data if provided
    # --- SAFE PARTIAL TEMPLATE RENDERING ---------------------------------
    if canvas_data is None:
        canvas_data = {}

    # Allow partial rendering: missing keys will be replaced with empty string
    import re
    def _replace_placeholder(match):
        key = match.group(1)
        return str(canvas_data.get(key, "")) if isinstance(canvas_data, dict) else ""

    # 只替换形如 {identifier} 的简单占位符，其他大括号保持原样
    section_prompt = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", _replace_placeholder, section_prompt)
    
    system_prompt = f"{base_prompt}\\n\\n---\\n\\n{section_prompt}"
    
    # Fetch draft from database
    logger.debug("DATABASE_DEBUG: Starting database fetch for existing section state...")
    draft = None
    status = "pending"
    
    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting API fetch")
        try:
            # Convert section_id for DentApp API (MVP: always use user_id=1)
            section_id_int = get_section_id_int(section_id)
            
            if section_id_int is None:
                logger.error(f"DATABASE_DEBUG: ❌ Invalid section_id: {section_id}")
                raise ValueError(f"Unknown section ID: {section_id}")
            
            log_api_operation("get_context", user_id=user_id, section_id=section_id, 
                            user_id_int=MVP_USER_ID, section_id_int=section_id_int)
            
            # Call DentApp API (MVP: always use user_id=1)
            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                result = await client.get_section_state(
                    agent_id=AGENT_ID,
                    section_id=section_id_int,
                    user_id=MVP_USER_ID
                )
            
            if result:
                # Extract data from DentApp API response
                raw_content = result.get('content', '')
                raw_status = result.get('is_completed', False)
                
                # Convert status
                status = "done" if raw_status else "pending"
                
                logger.debug(f"DATABASE_DEBUG: DentApp API found data - Status: {status}")
                logger.debug(f"DATABASE_DEBUG: Content length: {len(raw_content) if raw_content else 0}")
                
                if raw_content and raw_content.strip():
                    # Convert plain text to Tiptap format
                    tiptap_content = plain_text_to_tiptap(raw_content)
                    draft = {
                        "content": tiptap_content,
                        "plain_text": raw_content
                    }
                    logger.info(f"DATABASE_DEBUG: ✅ Successfully loaded existing draft from DentApp API")
                else:
                    logger.debug("DATABASE_DEBUG: DentApp API content is empty, no draft loaded")
                    
                logger.info(f"DATABASE_DEBUG: DentApp API fetch result - status={status}, has_draft={draft is not None}")
                
        except Exception as dentapp_error:
            logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API failed: {dentapp_error}")
            logger.debug("DATABASE_DEBUG: Falling back to Supabase...")
            
            # Fallback to Supabase (legacy)
            supabase = get_supabase_client()
            if supabase:
                logger.debug("DATABASE_DEBUG: ✅ Supabase client available, attempting legacy fetch")
                try:
                    # Option 1: Try RPC function first (using asyncio.to_thread for sync calls)
                    logger.debug("DATABASE_DEBUG: Attempting RPC call: get_section_state")
                    logger.debug(f"DATABASE_DEBUG: RPC parameters - user_id: {user_id}, doc_id: {doc_id}, section_id: {section_id}")
                    
                    def _rpc_call():
                        return supabase.rpc('get_section_state', {
                            'p_user_id': user_id,
                            'p_doc_id': doc_id, 
                            'p_section_id': section_id
                        }).execute()
                    
                    result = await asyncio.to_thread(_rpc_call)
                    logger.debug(f"DATABASE_DEBUG: RPC call completed - Data count: {len(result.data) if result.data else 0}")
                    
                    if result.data and len(result.data) > 0:
                        row = result.data[0]
                        status = row.get('status', 'pending')
                        content_data = row.get('content')
                        
                        logger.debug(f"DATABASE_DEBUG: Found existing data - Status: {status}")
                        logger.debug(f"DATABASE_DEBUG: Content data exists: {bool(content_data)}")
                        logger.debug(f"DATABASE_DEBUG: Content data type: {type(content_data) if content_data else None}")
                        
                        if content_data and content_data != {'type': 'doc', 'content': []}:
                            # Convert to SectionContent format
                            draft = {
                                "content": content_data,
                                "plain_text": await extract_plain_text.ainvoke(content_data)
                            }
                            logger.info(f"DATABASE_DEBUG: ✅ Successfully loaded existing draft content")
                        else:
                            logger.debug("DATABASE_DEBUG: Content data is empty or default, no draft loaded")
                        logger.info(f"DATABASE_DEBUG: RPC fetch result - status={status}, has_draft={draft is not None}")
                        
                except Exception as rpc_error:
                    logger.warning(f"DATABASE_DEBUG: ⚠️ RPC function failed: {rpc_error}")
                    logger.debug("DATABASE_DEBUG: Falling back to direct table query...")
                    # Option 2: Fallback to direct table query (also wrapped in to_thread)
                    try:
                        logger.debug("DATABASE_DEBUG: Attempting direct table query on section_states")
                        
                        def _table_call():
                            return supabase.table('section_states').select(
                                'content, status, score, updated_at'
                            ).eq('user_id', user_id).eq('doc_id', doc_id).eq('section_id', section_id).limit(1).execute()
                        
                        result = await asyncio.to_thread(_table_call)
                        logger.debug(f"DATABASE_DEBUG: Table query completed - Data count: {len(result.data) if result.data else 0}")
                        
                        if result.data and len(result.data) > 0:
                            row = result.data[0]
                            status = row.get('status', 'pending')
                            content_data = row.get('content')
                            
                            logger.debug(f"DATABASE_DEBUG: Table query found data - Status: {status}")
                            logger.debug(f"DATABASE_DEBUG: Content data exists: {bool(content_data)}")
                            
                            if content_data and content_data != {'type': 'doc', 'content': []}:
                                draft = {
                                    "content": content_data,
                                    "plain_text": await extract_plain_text.ainvoke(content_data)
                                }
                                logger.info(f"DATABASE_DEBUG: ✅ Successfully loaded draft via table query")
                            else:
                                logger.debug("DATABASE_DEBUG: Table content data is empty, no draft loaded")
                            logger.info(f"DATABASE_DEBUG: Table fetch result - status={status}, has_draft={draft is not None}")
                        else:
                            logger.debug("DATABASE_DEBUG: No existing data found in table query")
                    except Exception as table_error:
                        logger.error(f"DATABASE_DEBUG: ❌ Both RPC and table query failed: {table_error}")
            else:
                logger.warning("DATABASE_DEBUG: ⚠️ Supabase client not available, using default values")
    else:
        logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using default values")
    
    logger.debug(f"DATABASE_DEBUG: Final context values - status: {status}, draft: {bool(draft)}")
    
    return {
        "section_id": section_id,
        "status": status,
        "system_prompt": system_prompt,
        "draft": draft,
        "validation_rules": {str(i): rule.model_dump() for i, rule in enumerate(template.validation_rules)},
        "required_fields": template.required_fields,
    }


@tool
async def save_section(
    user_id: str,
    doc_id: str,
    section_id: str,
    content: Dict[str, Any],
    score: Optional[int] = None,
    status: str = "done",
) -> Dict[str, Any]:
    """
    Save or update a Value Canvas section in the database.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        section_id: Section identifier
        content: Section content (Tiptap JSON)
        score: Optional satisfaction score (0-5)
        status: Section status
    
    Returns:
        Updated section state
    """
    logger.info(f"=== DATABASE_DEBUG: save_section() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Saving section {section_id} for user {user_id}, doc {doc_id}")
    logger.debug(f"DATABASE_DEBUG: User ID type: {type(user_id)}, Doc ID type: {type(doc_id)}")
    logger.debug(f"DATABASE_DEBUG: Content type: {type(content)}, Score: {score}, Status: {status}")
    
    # [DIAGNOSTIC] Log all parameters passed to save_section
    logger.info(
        f"DATABASE_DEBUG: Full parameters - "
        f"user_id={user_id}, doc_id={doc_id}, section_id='{section_id}', "
        f"score={score}, status='{status}'"
    )
    logger.debug(f"DATABASE_DEBUG: Content structure: {content}")

    current_time = datetime.utcnow().isoformat() + "Z"
    logger.debug(f"DATABASE_DEBUG: Generated timestamp: {current_time}")
    
    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting API save")
        try:
            # Convert section_id for DentApp API (MVP: always use user_id=1)
            section_id_int = get_section_id_int(section_id)
            
            if section_id_int is None:
                logger.error(f"DATABASE_DEBUG: ❌ Invalid section_id: {section_id}")
                raise ValueError(f"Unknown section ID: {section_id}")
            
            # Convert Tiptap content to plain text
            plain_text = tiptap_to_plain_text(content) if content else ""
            
            log_api_operation("save_section", user_id=user_id, section_id=section_id, 
                            user_id_int=MVP_USER_ID, section_id_int=section_id_int,
                            content_length=len(plain_text), score=score, status=status)
            
            # Call DentApp API (MVP: always use user_id=1)
            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                result = await client.save_section_state(
                    agent_id=AGENT_ID,
                    section_id=section_id_int,
                    user_id=MVP_USER_ID,
                    content=plain_text,
                    metadata={}  # Empty metadata for MVP
                )
            
            if result:
                logger.info(f"DATABASE_DEBUG: ✅ Successfully saved section {section_id} via DentApp API")
                
                # Return response compatible with existing agent code
                return {
                    "id": str(result.get('id', uuid.uuid4())),
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "section_id": section_id,
                    "content": content,  # Return original Tiptap format
                    "score": score,
                    "status": status,
                    "updated_at": result.get('updated_at', current_time),
                }
            else:
                # API call failed, fall back to Supabase
                logger.warning("DATABASE_DEBUG: ⚠️ DentApp API save failed, falling back to Supabase")
                raise Exception("DentApp API save returned None")
                
        except Exception as dentapp_error:
            logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API failed: {dentapp_error}")
            logger.debug("DATABASE_DEBUG: Falling back to Supabase...")
            
            # Fallback to Supabase (legacy)
            supabase = get_supabase_client()
            if supabase:
                logger.debug("DATABASE_DEBUG: ✅ Supabase client available, proceeding with legacy upsert")
                try:
                    # Use upsert for save_section (wrapped in asyncio.to_thread)
                    logger.debug(f"DATABASE_DEBUG: Preparing legacy upsert data payload")
                    
                    upsert_data = {
                        'user_id': user_id,
                        'doc_id': doc_id,
                        'section_id': section_id,
                        'content': content,
                        'score': score,
                        'status': status,
                        'updated_at': current_time
                    }
                    logger.debug(f"DATABASE_DEBUG: Legacy upsert payload prepared - keys: {list(upsert_data.keys())}")
                    logger.info(f"DATABASE_DEBUG: Legacy upsert payload values - user_id={user_id}, section_id={section_id}, score={score}, status={status}")
                    logger.debug(f"DATABASE_DEBUG: About to execute legacy upsert on section_states table")
                    
                    def _update_or_insert_call():
                        logger.info(f"DATABASE_DEBUG: TRYING UPDATE first for existing record")
                        
                        # First try UPDATE
                        update_result = supabase.table('section_states').update({
                            'content': content,
                            'score': score,
                            'status': status,
                            'updated_at': current_time
                        }).eq('user_id', user_id).eq('doc_id', doc_id).eq('section_id', section_id).execute()
                        
                        logger.info(f"DATABASE_DEBUG: UPDATE result: {update_result}")
                        logger.info(f"DATABASE_DEBUG: UPDATE affected {len(update_result.data)} rows")
                        
                        if update_result.data and len(update_result.data) > 0:
                            logger.info("DATABASE_DEBUG: ✅ UPDATE successful, record was updated")
                            return update_result
                        else:
                            logger.info("DATABASE_DEBUG: UPDATE affected 0 rows, trying INSERT...")
                            
                            # If no rows updated, INSERT new record
                            insert_result = supabase.table('section_states').insert({
                                'user_id': user_id,
                                'doc_id': doc_id,
                                'section_id': section_id,
                                'content': content,
                                'score': score,
                                'status': status,
                                'updated_at': current_time
                            }).execute()
                            
                            logger.info(f"DATABASE_DEBUG: INSERT result: {insert_result}")
                            logger.info("DATABASE_DEBUG: ✅ INSERT successful, new record created")
                            return insert_result
                    
                    logger.debug("DATABASE_DEBUG: Calling asyncio.to_thread for legacy update/insert operation...")
                    result = await asyncio.to_thread(_update_or_insert_call)
                    logger.debug(f"DATABASE_DEBUG: Legacy upsert operation completed")
                    logger.debug(f"DATABASE_DEBUG: Legacy result data count: {len(result.data) if result.data else 0}")
                    
                    if result.data and len(result.data) > 0:
                        row = result.data[0]
                        logger.info(f"DATABASE_DEBUG: ✅ Successfully saved section {section_id} to legacy database")
                        logger.info(f"DATABASE_DEBUG: Legacy returned data - id={row.get('id')}, status={row.get('status')}, score={row.get('score')}")
                        logger.debug(f"DATABASE_DEBUG: Legacy database record created/updated with timestamp: {row.get('updated_at')}")
                        
                        # CRITICAL DEBUG: Check if returned values match what we sent
                        if row.get('status') != status:
                            logger.error(f"DATABASE_DEBUG: ❌ STATUS MISMATCH! Sent: {status}, Got: {row.get('status')}")
                        if row.get('score') != score:
                            logger.error(f"DATABASE_DEBUG: ❌ SCORE MISMATCH! Sent: {score}, Got: {row.get('score')}")
                        
                        return {
                            "id": row.get('id'),
                            "user_id": row.get('user_id'),
                            "doc_id": row.get('doc_id'),
                            "section_id": row.get('section_id'),
                            "content": row.get('content'),
                            "score": row.get('score'),
                            "status": row.get('status'),
                            "updated_at": row.get('updated_at'),
                        }
                    else:
                        logger.error(f"DATABASE_DEBUG: ❌ Legacy upsert succeeded but no data returned for section {section_id}")
                        logger.error(f"DATABASE_DEBUG: This means the legacy upsert didn't actually save anything!")
                        logger.debug("DATABASE_DEBUG: Returning constructed response with generated ID")
                        # Return what we tried to save
                        return {
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "doc_id": doc_id,
                            "section_id": section_id,
                            "content": content,
                            "score": score,
                            "status": status,
                            "updated_at": current_time,
                        }
                except Exception as e:
                    logger.error(f"DATABASE_DEBUG: ❌ Supabase save_section failed: {e}")
                    logger.error(f"DATABASE_DEBUG: Failed parameters - user_id={user_id}, doc_id={doc_id}, section_id={section_id}")
                    logger.error(f"DATABASE_DEBUG: Exception type: {type(e).__name__}")
                    logger.error(f"DATABASE_DEBUG: Exception details: {str(e)}")
                    # Don't re-raise in development to avoid blocking the agent completely
                    # Instead, fall back to mock response
                    logger.warning("DATABASE_DEBUG: ⚠️ Falling back to mock response due to database error")
                    return {
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "doc_id": doc_id,
                        "section_id": section_id,
                        "content": content,
                        "score": score,
                        "status": status,
                        "updated_at": current_time,
                    }
            else:
                # Supabase not available, use mock response
                logger.warning(f"DATABASE_DEBUG: ⚠️ Supabase client not available, using mock response for section {section_id}")
                return {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "section_id": section_id,
                    "content": content,
                    "score": score,
                    "status": status,
                    "updated_at": current_time,
                }
    else:
        # DentApp API disabled, use mock response
        logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API disabled, using mock response for section {section_id}")
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "doc_id": doc_id,
            "section_id": section_id,
            "content": content,
            "score": score,
            "status": status,
            "updated_at": current_time,
        }


@tool
async def validate_field(
    field_name: str,
    value: Any,
    validation_rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Validate a field value against defined rules.
    
    Args:
        field_name: Name of the field to validate
        value: Value to validate
        validation_rules: List of validation rules
    
    Returns:
        Validation result with is_valid flag and error messages
    """
    errors = []
    
    for rule in validation_rules:
        if rule.get("field_name") != field_name:
            continue
            
        rule_type = rule.get("rule_type")
        rule_value = rule.get("value")
        error_message = rule.get("error_message", "Validation failed")
        
        if rule_type == "required" and not value:
            errors.append(error_message)
        elif rule_type == "min_length" and len(str(value)) < rule_value:
            errors.append(error_message)
        elif rule_type == "max_length" and len(str(value)) > rule_value:
            errors.append(error_message)
        elif rule_type == "choices" and value not in rule_value:
            errors.append(error_message)
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "field_name": field_name,
        "value": value,
    }


@tool
async def get_all_sections_status(
    user_id: str,
    doc_id: str,
) -> List[Dict[str, Any]]:
    """
    Get status of all Value Canvas sections for a document.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
    
    Returns:
        List of section states with status
    """
    logger.info(f"=== DATABASE_DEBUG: get_all_sections_status() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Getting all section status for user {user_id}, doc {doc_id}")
    
    try:
        # Try DentApp API first (if enabled)
        if settings.USE_DENTAPP_API:
            logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting to fetch all sections status")
            try:
                # MVP: always use user_id=1
                log_api_operation("get_all_sections_status", user_id=user_id, doc_id=doc_id, 
                                user_id_int=MVP_USER_ID)
                
                # Call DentApp API (MVP: always use user_id=1)
                dentapp_client = get_dentapp_client()
                async with dentapp_client as client:
                    api_result = await client.get_all_sections_status(
                        agent_id=AGENT_ID,
                        user_id=MVP_USER_ID
                    )
                
                if api_result:
                    logger.info(f"DATABASE_DEBUG: ✅ Retrieved DentApp API response")
                    
                    # Extract sections data from DentApp API response
                    # The API returns a structured response with sections information
                    api_sections = api_result.get('sections', [])
                    logger.info(f"DATABASE_DEBUG: DentApp API returned {len(api_sections)} sections")
                    
                    # Convert DentApp API response to agent format
                    result = []
                    for api_section in api_sections:
                        # Map integer section_id back to string section_id
                        section_id_int = api_section.get('section_id')
                        section_id_str = None
                        
                        # Reverse lookup in section mapping
                        for str_id, int_id in SECTION_ID_MAPPING.items():
                            if int_id == section_id_int:
                                section_id_str = str_id
                                break
                                
                        if section_id_str:
                            result.append({
                                'section_id': section_id_str,
                                'status': 'done' if api_section.get('is_completed', False) else 'pending',
                                'score': api_section.get('score'),
                                'has_content': bool(api_section.get('content', '').strip()),
                                'updated_at': api_section.get('updated_at'),
                            })
                    
                    logger.info(f"DATABASE_DEBUG: ✅ Successfully converted {len(result)} sections from DentApp API")
                else:
                    logger.warning("DATABASE_DEBUG: ⚠️ DentApp API returned None, falling back to Supabase")
                    raise Exception("DentApp API returned None")
                    
            except Exception as dentapp_error:
                logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API failed: {dentapp_error}")
                logger.debug("DATABASE_DEBUG: Falling back to Supabase...")
                
                # Fallback to Supabase (legacy)
                supabase = get_supabase_client()
                if supabase:
                    logger.debug("DATABASE_DEBUG: ✅ Supabase client available, attempting legacy fetch sections")
                    try:
                        # Option 1: Try RPC function first (wrapped in asyncio.to_thread)
                        logger.debug("DATABASE_DEBUG: Attempting RPC call: get_document_sections")
                        logger.debug(f"DATABASE_DEBUG: RPC parameters - user_id: {user_id}, doc_id: {doc_id}")
                        
                        def _rpc_call():
                            return supabase.rpc('get_document_sections', {
                                'p_user_id': user_id,
                                'p_doc_id': doc_id
                            }).execute()
                        
                        rpc_result = await asyncio.to_thread(_rpc_call)
                        result = rpc_result.data if rpc_result.data else []
                        logger.info(f"DATABASE_DEBUG: ✅ Retrieved {len(result)} sections via legacy RPC")
                        logger.debug(f"DATABASE_DEBUG: Legacy RPC result sections: {[r.get('section_id') for r in result] if result else []}")
                    except Exception as rpc_error:
                        logger.warning(f"DATABASE_DEBUG: ⚠️ Legacy RPC function failed: {rpc_error}")
                        logger.debug("DATABASE_DEBUG: Falling back to legacy direct table query")
                        # Option 2: Fallback to direct table query (also wrapped)
                        try:
                            logger.debug("DATABASE_DEBUG: Attempting legacy direct table query on section_states")
                            
                            def _table_call():
                                return supabase.table('section_states').select(
                                    'section_id, status, score, content, updated_at'
                                ).eq('user_id', user_id).eq('doc_id', doc_id).execute()
                            
                            table_result = await asyncio.to_thread(_table_call)
                            result = table_result.data if table_result.data else []
                            logger.info(f"DATABASE_DEBUG: ✅ Retrieved {len(result)} sections via legacy table query")
                            logger.debug(f"DATABASE_DEBUG: Legacy table result sections: {[r.get('section_id') for r in result] if result else []}")
                        except Exception as table_error:
                            logger.error(f"DATABASE_DEBUG: ❌ Both legacy RPC and table query failed: {table_error}")
                            result = []
                else:
                    logger.warning("DATABASE_DEBUG: ⚠️ Supabase client not available, returning empty sections list")
                    result = []
        else:
            logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using default empty result")
            result = []
        
        # Convert database results to expected format
        logger.debug("DATABASE_DEBUG: Processing database results to section status format")
        sections = []
        existing_sections = {row['section_id']: row for row in result} if result else {}
        logger.debug(f"DATABASE_DEBUG: Found existing sections in DB: {list(existing_sections.keys())}")
        
        # Ensure all required sections are represented
        logger.debug("DATABASE_DEBUG: Processing all required sections from SectionID enum")
        for section_id in SectionID:
            if section_id.value in existing_sections:
                row = existing_sections[section_id.value]
                logger.debug(f"DATABASE_DEBUG: Processing existing section {section_id.value} - status: {row.get('status')}, score: {row.get('score')}")
                sections.append({
                    "section_id": section_id.value,
                    "status": row.get('status', SectionStatus.PENDING.value),
                    "score": row.get('score'),
                    "has_content": row.get('has_content', False),
                    "updated_at": row.get('updated_at'),
                })
            else:
                # Section doesn't exist in database yet
                logger.debug(f"DATABASE_DEBUG: Section {section_id.value} not found in DB, creating default entry")
                sections.append({
                    "section_id": section_id.value,
                    "status": SectionStatus.PENDING.value,
                    "score": None,
                    "has_content": False,
                    "updated_at": None,
                })
        
        logger.info(f"DATABASE_DEBUG: ✅ Retrieved status for {len(sections)} sections total")
        logger.debug(f"DATABASE_DEBUG: Final sections summary: {[(s['section_id'], s['status']) for s in sections]}")
        return sections
        
    except Exception as e:
        logger.error(f"Error in get_all_sections_status: {e}")
        # Return mock data on error
        sections = []
        for section_id in SectionID:
            sections.append({
                "section_id": section_id.value,
                "status": SectionStatus.PENDING.value,
                "score": None,
                "has_content": False,
                "updated_at": None,
            })
        return sections


@tool
async def export_checklist(
    user_id: str,
    doc_id: str,
    canvas_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Export completed Value Canvas as a checklist/PDF.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        canvas_data: Complete canvas data
    
    Returns:
        Export result with download URL
    """
    logger.info(f"Exporting checklist for doc {doc_id}")
    
    try:
        # First, verify that all required sections are complete
        sections_status = await get_all_sections_status.ainvoke({
            "user_id": user_id,
            "doc_id": doc_id
        })
        
        incomplete_sections = [
            s["section_id"] for s in sections_status 
            if s["status"] != SectionStatus.DONE.value and s["section_id"] != "implementation"
        ]
        
        if incomplete_sections:
            return {
                "success": False,
                "error": f"Cannot export: incomplete sections: {', '.join(incomplete_sections)}",
                "incomplete_sections": incomplete_sections,
            }
        
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # Try DentApp API export first (if enabled)
        if settings.USE_DENTAPP_API:
            logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting export via API")
            try:
                # MVP: always use user_id=1
                log_api_operation("export_checklist", user_id=user_id, doc_id=doc_id, 
                                user_id_int=MVP_USER_ID)
                
                # Call DentApp API export (MVP: always use user_id=1)
                dentapp_client = get_dentapp_client()
                async with dentapp_client as client:
                    export_result = await client.export_agent_data(
                        user_id=MVP_USER_ID,
                        agent_id=AGENT_ID
                    )
                
                if export_result:
                    logger.info(f"DATABASE_DEBUG: ✅ Successfully exported via DentApp API")
                    
                    # Return export result using DentApp API response
                    return {
                        "success": True,
                        "format": "json",  # DentApp API provides structured data
                        "url": f"/api/dentapp/exports/{MVP_USER_ID}/{AGENT_ID}",  # Mock URL
                        "content": export_result.get('canvas_data', {}),
                        "generated_at": export_result.get('exported_at', current_time),
                        "total_sections": export_result.get('total_sections', 0),
                        "total_assets": export_result.get('total_assets', 0),
                        "summary": export_result.get('summary', {}),
                    }
                else:
                    logger.warning("DATABASE_DEBUG: ⚠️ DentApp API export failed, falling back to legacy")
                    raise Exception("DentApp API export returned None")
                    
            except Exception as dentapp_error:
                logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API export failed: {dentapp_error}")
                logger.debug("DATABASE_DEBUG: Falling back to legacy export...")
                
                # Fallback to legacy export using canvas_data
                checklist_content = _generate_checklist_content(canvas_data)
                
                # Execute legacy query using Supabase SDK
                supabase = get_supabase_client()
                if supabase:
                    try:
                        def _update_call():
                            return supabase.table('value_canvas_documents').update({
                                'completed': True,
                                'completed_at': datetime.now().isoformat(),
                                'export_url': 'generated'
                            }).eq('id', doc_id).eq('user_id', user_id).execute()
                        
                        await asyncio.to_thread(_update_call)
                        logger.info(f"DATABASE_DEBUG: ✅ Legacy export updated document status")
                    except Exception as e:
                        logger.error(f"DATABASE_DEBUG: ❌ Legacy Supabase update failed: {e}")
                else:
                    logger.info("DATABASE_DEBUG: Legacy mock mode: document marked as completed")
                
                logger.info(f"Successfully exported checklist via legacy method for doc {doc_id}")
                
                return {
                    "success": True,
                    "format": "text",  # Legacy text format
                    "url": f"/api/exports/{doc_id}/checklist.txt",  # Mock URL
                    "content": checklist_content,
                    "generated_at": current_time,
                }
        else:
            logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using legacy export")
            # Generate checklist content from canvas data
            checklist_content = _generate_checklist_content(canvas_data)
            
            logger.info(f"Successfully exported checklist via legacy method for doc {doc_id}")
            
            return {
                "success": True,
                "format": "text",  # Legacy text format
                "url": f"/api/exports/{doc_id}/checklist.txt",  # Mock URL
                "content": checklist_content,
                "generated_at": current_time,
            }
        
    except Exception as e:
        logger.error(f"Error exporting checklist: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def _generate_checklist_content(canvas_data: Dict[str, Any]) -> str:
    """
    Generate implementation checklist content from canvas data.
    
    Args:
        canvas_data: Complete Value Canvas data
    
    Returns:
        Formatted checklist content
    """
    content = "# Value Canvas Implementation Checklist\\n\\n"
    
    # ICP Section
    if canvas_data.get('icp_nickname'):
        content += f"## Target Customer: {canvas_data['icp_nickname']}\\n"
        content += f"- Demographics: {canvas_data.get('icp_demographics', 'Not specified')}\\n"
        content += f"- Geography: {canvas_data.get('icp_geography', 'Not specified')}\\n\\n"
    
    # Pain Points
    content += "## Pain Points to Address:\\n"
    for i in range(1, 4):
        pain_symptom = canvas_data.get(f'pain{i}_symptom')
        if pain_symptom:
            content += f"{i}. {pain_symptom}\\n"
    content += "\\n"
    
    # Payoffs
    content += "## Expected Outcomes:\\n"
    for i in range(1, 4):
        payoff_objective = canvas_data.get(f'payoff{i}_objective')
        if payoff_objective:
            content += f"{i}. {payoff_objective}\\n"
    content += "\\n"
    
    # Signature Method
    if canvas_data.get('method_name'):
        content += f"## Signature Method: {canvas_data['method_name']}\\n"
        principles = canvas_data.get('sequenced_principles', [])
        for i, principle in enumerate(principles, 1):
            content += f"{i}. {principle}\\n"
        content += "\\n"
    
    # Prize
    if canvas_data.get('refined_prize'):
        content += f"## Transformation Promise:\\n{canvas_data['refined_prize']}\\n\\n"
    
    # Implementation steps
    content += "## Next Steps:\\n"
    content += "1. Review and validate this Value Canvas with your team\\n"
    content += "2. Create marketing materials based on these insights\\n"
    content += "3. Test messaging with target customers\\n"
    content += "4. Iterate based on feedback\\n"
    content += "5. Scale successful messaging across all channels\\n"
    
    return content


@tool
async def create_tiptap_content(
    text: str,
    format_type: str = "paragraph",
) -> Dict[str, Any]:
    """
    Create Tiptap JSON content from plain text.
    
    Args:
        text: Plain text content
        format_type: Type of formatting (paragraph, heading, list)
    
    Returns:
        Tiptap JSON document
    """
    content = []
    
    if format_type == "paragraph":
        content.append({
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        })
    elif format_type == "heading":
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        })
    elif format_type == "list":
        items = text.split("\\n")
        list_items = []
        for item in items:
            if item.strip():
                list_items.append({
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": item.strip(),
                                }
                            ],
                        }
                    ],
                })
        content.append({
            "type": "bulletList",
            "content": list_items,
        })
    
    return {
        "type": "doc",
        "content": content,
    }


@tool
async def extract_plain_text(tiptap_json: Dict[str, Any]) -> str:
    """
    Extract plain text from Tiptap JSON content.
    
    Args:
        tiptap_json: Tiptap JSON document
    
    Returns:
        Plain text string
    """
    def extract_text_from_node(node: Dict[str, Any]) -> str:
        text_parts = []
        
        if node.get("type") == "text":
            text_parts.append(node.get("text", ""))
        
        if "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                text_parts.append(extract_text_from_node(child))
        
        return " ".join(text_parts)
    
    return extract_text_from_node(tiptap_json).strip()


# Helper function to execute SQL queries
async def _execute_sql_query(query: str) -> List[Dict[str, Any]]:
    """
    Execute SQL query using Supabase MCP tool.
    
    Args:
        query: SQL query to execute
    
    Returns:
        Query results as list of dictionaries
    """
    try:
        logger.info(f"Executing SQL query: {query[:100]}...")
        supabase = get_supabase_client()
        if supabase:
            # This is a generic SQL execution function - would need specific implementation
            # For now, return empty result in development mode
            logger.warning("Generic SQL execution not implemented with Supabase SDK")
            return []
        else:
            logger.info("Mock mode: returning empty SQL result")
            return []
        
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}")
        return []


# Export all tools
__all__ = [
    "get_context",
    "save_section",
    "validate_field",
    "export_checklist",
    "get_all_sections_status",
    "create_tiptap_content",
    "extract_plain_text",
]