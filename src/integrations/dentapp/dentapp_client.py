"""DentApp AI Builder API HTTP client."""

import asyncio
import logging
from typing import Any

from httpx import AsyncClient, HTTPStatusError, RequestError, TimeoutException

from core.settings import settings

logger = logging.getLogger(__name__)

class DentAppClient:
    """HTTP client for DentApp AI Builder API."""
    
    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = base_url or getattr(settings, 'DENTAPP_API_URL', 'https://dentappaibuilder.enspirittech.co.uk')
        self.timeout = timeout
        self._client: AsyncClient | None = None
        logger.info(f"=== DENTAPP_CLIENT_INIT: Initialized with base_url={self.base_url}, timeout={timeout}s ===")
        
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            
    async def _make_request(
        self, 
        method: str, 
        url: str, 
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retries: int = 3
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        logger.info(f"=== DENTAPP_API_REQUEST: {method} {self.base_url}{url} ===")
        if json:
            logger.info(f"DENTAPP_API_REQUEST: Request payload keys: {list(json.keys())}")
        if params:
            logger.info(f"DENTAPP_API_REQUEST: Request params: {params}")
            
        for attempt in range(retries):
            try:
                logger.debug(f"DentApp API {method} {url} - Attempt {attempt + 1}")
                
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"=== DENTAPP_API_RESPONSE: Status {response.status_code} SUCCESS ===")
                logger.info(f"DENTAPP_API_RESPONSE: Response keys: {list(result.keys()) if isinstance(result, dict) else 'Non-dict response'}")
                if isinstance(result, dict) and 'success' in result:
                    logger.info(f"DENTAPP_API_RESPONSE: success={result.get('success')}, message='{result.get('message', 'No message')}'")
                logger.debug(f"DENTAPP_API_RESPONSE: Full response: {result}")
                return result
                
            except HTTPStatusError as e:
                logger.error(f"=== DENTAPP_API_ERROR: HTTP {e.response.status_code} FAILED ===")
                logger.error(f"DENTAPP_API_ERROR: Response text: {e.response.text}")
                try:
                    error_json = e.response.json()
                    logger.error(f"DENTAPP_API_ERROR: Parsed JSON: {error_json}")
                except:
                    logger.error("DENTAPP_API_ERROR: Could not parse error response as JSON")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except (RequestError, TimeoutException) as e:
                logger.warning(f"DentApp API request error: {e}")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"DentApp API unexpected error: {e}")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
    
    async def get_section_state(
        self, 
        agent_id: int, 
        section_id: int, 
        user_id: int
    ) -> dict[str, Any] | None:
        """Get section state from DentApp API."""
        logger.info(f"Getting section state for agent={agent_id}, section={section_id}, user={user_id}")
        
        try:
            result = await self._make_request(
                method="GET",
                url=f"/section_states/{agent_id}/{section_id}",
                params={"user_id": user_id}
            )
            logger.info("Successfully retrieved section state")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get section state: {e}")
            return None
    
    async def save_section_state(
        self, 
        agent_id: int, 
        section_id: int, 
        user_id: int, 
        content: str,
        metadata: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Save section state to DentApp API."""
        logger.info(f"Saving section state for agent={agent_id}, section={section_id}, user={user_id}")
        
        payload = {
            "user_id": user_id,
            "content": content,
        }
        
        # Add metadata if provided (optional for MVP)
        if metadata:
            payload["metadata"] = metadata
            
        try:
            result = await self._make_request(
                method="POST",
                url=f"/section_states/{agent_id}/{section_id}",
                json=payload
            )
            logger.info("Successfully saved section state")
            return result
            
        except Exception as e:
            logger.error(f"Failed to save section state: {e}")
            return None
    
    async def get_all_sections_status(
        self, 
        agent_id: int, 
        user_id: int
    ) -> dict[str, Any] | None:
        """Get all sections status from DentApp API."""
        logger.info(f"Getting all sections status for agent={agent_id}, user={user_id}")
        
        payload = {"user_id": user_id}
        
        try:
            result = await self._make_request(
                method="POST",
                url=f"/agent/get-all-sections-status/{agent_id}",
                json=payload
            )
            logger.info("Successfully retrieved all sections status")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get all sections status: {e}")
            return None
    
    async def export_agent_data(
        self, 
        user_id: int, 
        agent_id: int
    ) -> dict[str, Any] | None:
        """Export agent data from DentApp API."""
        logger.info(f"Exporting agent data for user={user_id}, agent={agent_id}")
        
        payload = {
            "user_id": user_id,
            "agent_id": agent_id
        }
        
        try:
            result = await self._make_request(
                method="POST",
                url="/agent/export",
                json=payload
            )
            logger.info("Successfully exported agent data")
            return result
            
        except Exception as e:
            logger.error(f"Failed to export agent data: {e}")
            return None


# Global client instance for easy access
_dentapp_client: DentAppClient | None = None

def get_dentapp_client() -> DentAppClient:
    """Get configured DentApp client instance."""
    global _dentapp_client
    
    # Check if DentApp API is enabled
    if not getattr(settings, 'USE_DENTAPP_API', True):
        logger.warning("DentApp API is disabled, returning None")
        return None
        
    if _dentapp_client is None:
        _dentapp_client = DentAppClient()
        logger.info("Created new DentApp client instance")
    
    return _dentapp_client