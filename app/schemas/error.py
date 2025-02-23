from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union

class ErrorDetail(BaseModel):
    """
    Base model for error details
    """
    detail: Union[str, List[Dict[str, Any]]] = Field(
        ..., 
        description="Error message or validation details"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"detail": "Not authenticated"}
            ]
        }

class ErrorResponse(BaseModel):
    """
    Standard error response with optional headers
    """
    status_code: int = Field(..., description="HTTP status code")
    detail: Union[str, List[Dict[str, Any]]] = Field(..., description="Error message or validation details")
    headers: Optional[Dict[str, str]] = Field(None, description="Optional response headers")

    def raise_exception(self):
        raise HTTPException(**self.model_dump(exclude_none=True))

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status_code": 401,
                    "detail": "Not authenticated",
                    "headers": {"WWW-Authenticate": "Bearer"}
                }
            ]
        }

# Common error responses
UNAUTHORIZED_ERROR = ErrorResponse(
    status_code=401,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"}
)

NOT_FOUND_ERROR = lambda entity: ErrorResponse(
    status_code=404,
    detail=f"{entity} not found"
)

VALIDATION_ERROR = ErrorResponse(
    status_code=422,
    detail=[{
        "loc": ["body", "field_name"],
        "msg": "field required",
        "type": "value_error.missing"
    }]
)

# Custom error responses
USERNAME_TAKEN_ERROR = ErrorResponse(
    status_code=400,
    detail="Username already registered"
)

EMAIL_TAKEN_ERROR = ErrorResponse(
    status_code=400,
    detail="Email already registered"
)

DELETE_SELF_ERROR = ErrorResponse(
    status_code=400,
    detail="Cannot delete your own superuser account"
)

AUTHOR_PERMISSION_ERROR = ErrorResponse(
    status_code=403,
    detail="Only the author or superuser can edit this post"
) 