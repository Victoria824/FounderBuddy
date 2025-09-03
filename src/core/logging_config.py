"""
Centralized logging configuration for the entire application.

Environment Variables:
- LOG_LEVEL: Global log level (DEBUG, INFO, WARNING, ERROR)
- LOG_STATE: Show state changes (true/false)
- LOG_STREAM_EVENTS: Show streaming events (true/false)
- LOG_FORMAT: Logging format (simple/detailed)
"""

import logging
import os
import json
from typing import Any, Optional


# Get configuration from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_STATE = os.getenv("LOG_STATE", "false").lower() == "true"
LOG_STREAM_EVENTS = os.getenv("LOG_STREAM_EVENTS", "false").lower() == "true"
LOG_FORMAT = os.getenv("LOG_FORMAT", "simple").lower()


def setup_logging():
    """Configure logging for the entire application."""
    # Set base logging level
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if LOG_FORMAT == 'detailed' else '%(levelname)s - %(message)s'
    )
    
    # Configure specific loggers if needed
    if not LOG_STREAM_EVENTS:
        # Reduce stream-related logging to WARNING level
        logging.getLogger("service.service").setLevel(logging.WARNING)


class SmartLogger:
    """Smart logger that handles different log types efficiently."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._stream_event_count = 0
        self._last_state = None
    
    def info(self, message: str):
        """Standard info logging."""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Debug logging - only if DEBUG level is set."""
        if LOG_LEVEL == "DEBUG":
            self.logger.debug(message)
    
    def warning(self, message: str):
        """Warning logging."""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Error logging."""
        self.logger.error(message, exc_info=exc_info)
    
    def state_change(self, section: str, old_state: Any, new_state: Any, action: str = ""):
        """Log state changes in a concise format."""
        if LOG_STATE or LOG_LEVEL == "DEBUG":
            # Only log if state actually changed
            if old_state != new_state:
                self.logger.info(f"[STATE] {section}: {old_state} -> {new_state} {action}".strip())
    
    def stream_event(self, event_type: str, details: Optional[dict] = None):
        """Log streaming events efficiently."""
        if LOG_STREAM_EVENTS or LOG_LEVEL == "DEBUG":
            # Batch similar events
            self._stream_event_count += 1
            # Only log every 10th token event to reduce noise
            if event_type == "token" and self._stream_event_count % 10 != 0:
                return
            
            if details:
                self.logger.debug(f"[STREAM] {event_type}: {json.dumps(details, default=str)[:100]}")
            else:
                self.logger.debug(f"[STREAM] {event_type}")
    
    def stream_summary(self, total_events: int, duration: float = None):
        """Log stream summary at the end."""
        msg = f"[STREAM COMPLETE] Processed {total_events} events"
        if duration:
            msg += f" in {duration:.2f}s"
        self.logger.info(msg)
    
    def section_transition(self, from_section: str, to_section: str, directive: str):
        """Log section transitions concisely."""
        self.logger.info(f"[SECTION] {from_section} -> {to_section} ({directive})")
    
    def llm_call(self, section: str, token_count: Optional[int] = None):
        """Log LLM calls efficiently."""
        msg = f"[LLM] {section}"
        if token_count:
            msg += f" ({token_count} tokens)"
        self.logger.info(msg)
    
    def save_operation(self, section: str, status: str, has_content: bool = True):
        """Log save operations concisely."""
        content_status = "✓" if has_content else "✗"
        self.logger.info(f"[SAVE] {section}: {status} {content_status}")
    
    def decision(self, section: str, result: dict):
        """Log decision results concisely."""
        # Only log key decision outcomes
        directive = result.get('router_directive', 'unknown')
        satisfied = result.get('is_satisfied', None)
        if satisfied is not None:
            self.logger.info(f"[DECISION] {section}: {directive}, satisfied={satisfied}")
        else:
            self.logger.info(f"[DECISION] {section}: {directive}")
    
    def memory_update(self, section: str, action: str, details: Optional[str] = None):
        """Log memory updates efficiently."""
        msg = f"[MEMORY] {section}: {action}"
        if details and LOG_LEVEL == "DEBUG":
            msg += f" - {details}"
        self.logger.info(msg)
    
    def agent_output(self, section: str, has_update: bool, is_satisfied: Optional[bool], directive: str):
        """Log agent output in one line."""
        self.logger.info(
            f"[AGENT] {section}: update={has_update}, satisfied={is_satisfied}, directive={directive}"
        )


def get_logger(name: str) -> SmartLogger:
    """Get a smart logger instance."""
    return SmartLogger(name)


# Utility functions for common logging patterns
def log_node_entry(logger: SmartLogger, node_name: str, section: str):
    """Log node entry in a standard format."""
    if LOG_LEVEL == "DEBUG":
        logger.debug(f"[NODE] Entering {node_name} for {section}")


def log_node_exit(logger: SmartLogger, node_name: str, section: str):
    """Log node exit in a standard format."""
    if LOG_LEVEL == "DEBUG":
        logger.debug(f"[NODE] Exiting {node_name} for {section}")


def format_state_summary(state: dict) -> str:
    """Format state for concise logging."""
    summary = {
        'section': state.get('current_section'),
        'messages': len(state.get('messages', [])),
        'has_agent_output': bool(state.get('agent_output')),
        'awaiting_input': state.get('awaiting_user_input', False)
    }
    return json.dumps(summary, default=str)