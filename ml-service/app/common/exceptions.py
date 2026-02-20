from fastapi import HTTPException, status


class ModelNotLoadedError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded",
        )


class ModelNotFoundError(HTTPException):
    def __init__(self, version: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model version {version} not found",
        )
