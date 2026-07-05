from fastapi import status


class AppError(Exception):
    """Base application error mapped to an HTTP response by the global exception handler."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found."


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Invalid request."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Not authenticated."


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "Not allowed to perform this action."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "Resource already exists."


class IntegrationError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = "An upstream integration failed."


class ApprovalRequiredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "This action requires explicit user approval before it can run."
