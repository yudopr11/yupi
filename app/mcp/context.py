from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.auth import User

_current_user_var: ContextVar = ContextVar("mcp_current_user")
_current_db_var: ContextVar = ContextVar("mcp_current_db")
