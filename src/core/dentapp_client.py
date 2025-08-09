"""DentApp AI Builder API HTTP client."""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from httpx import AsyncClient, HTTPStatusError, RequestError, TimeoutException

from core.settings import settings

logger = logging.getLogger(__name__)

class DentAppClient:
    """HTTP client for DentApp AI Builder API."""
    
    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = base_url or getattr(settings, 'DENTAPP_API_URL', 'https://dentappaibuilder.enspirittech.co.uk')
        self.timeout = timeout
        self._client: Optional[AsyncClient] = None
        
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
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
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
                logger.debug(f"DentApp API response successful: {response.status_code}")
                return result
                
            except HTTPStatusError as e:
                logger.warning(f"DentApp API HTTP error {e.response.status_code}: {e.response.text}")
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
    ) -> Optional[Dict[str, Any]]:
        """Get section state from DentApp API."""
        logger.info(f"Getting section state for agent={agent_id}, section={section_id}, user={user_id}")
        
        try:
            result = await self._make_request(
                method="GET",
                url=f"/section_states/{agent_id}/{section_id}",
                params={"user_id": user_id}
            )
            logger.info(f"Successfully retrieved section state")
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
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
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
            logger.info(f"Successfully saved section state")
            return result
            
        except Exception as e:
            logger.error(f"Failed to save section state: {e}")
            return None
    
    async def get_all_sections_status(
        self, 
        agent_id: int, 
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get all sections status from DentApp API."""
        logger.info(f"Getting all sections status for agent={agent_id}, user={user_id}")
        
        payload = {"user_id": user_id}
        
        try:
            result = await self._make_request(
                method="POST",
                url=f"/agent/get-all-sections-status/{agent_id}",
                json=payload
            )
            logger.info(f"Successfully retrieved all sections status")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get all sections status: {e}")
            return None
    
    async def export_agent_data(
        self, 
        user_id: int, 
        agent_id: int
    ) -> Optional[Dict[str, Any]]:
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
            logger.info(f"Successfully exported agent data")
            return result
            
        except Exception as e:
            logger.error(f"Failed to export agent data: {e}")
            return None


# Global client instance for easy access
_dentapp_client: Optional[DentAppClient] = None

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