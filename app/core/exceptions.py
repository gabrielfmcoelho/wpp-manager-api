"""Custom HTTP exceptions."""

from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    """Exception raised when a resource is not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with id '{identifier}' not found",
        )


class WhatsAppAPIError(HTTPException):
    """Exception raised when WhatsApp API returns an error."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WhatsApp API error: {detail}",
        )


class UnauthorizedError(HTTPException):
    """Exception raised for authentication failures."""

    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class ForbiddenError(HTTPException):
    """Exception raised when access to a resource is forbidden."""

    def __init__(self, detail: str = "Access to this resource is forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class BadRequestError(HTTPException):
    """Exception raised for bad requests."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class ConflictError(HTTPException):
    """Exception raised when there's a resource conflict."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
