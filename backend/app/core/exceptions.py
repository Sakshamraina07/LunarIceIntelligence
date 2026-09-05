"""
Structured Exception Handling for Lunar Ice Intelligence.
Guarantees clean error responses without exposing raw stack traces.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class LunarScienceException(Exception):
    def __init__(self, message: str, error_code: str = "SCIENCE_ERROR", details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class RasterDimensionMismatchError(LunarScienceException):
    def __init__(self, message: str = "Raster spatial dimensions do not align.", details: dict = None):
        super().__init__(message=message, error_code="RASTER_DIMENSION_MISMATCH", details=details)


class DatasetNotFoundError(LunarScienceException):
    def __init__(self, dataset_name: str):
        super().__init__(
            message=f"Target lunar dataset '{dataset_name}' was not found in repository or catalog.",
            error_code="DATASET_NOT_FOUND",
            details={"dataset_name": dataset_name}
        )


class PathPlanningFailureError(LunarScienceException):
    def __init__(self, reason: str, details: dict = None):
        super().__init__(
            message=f"No feasible rover path found: {reason}",
            error_code="NO_FEASIBLE_PATH",
            details=details or {}
        )


class UnknownCraterError(LunarScienceException):
    """
    A crater id that is not in the catalogue.

    mission_service used to answer this with CRATER_CATALOG["shackleton"], so a
    typo in the URL returned a complete, confident Shackleton payload labelled
    with whatever id was asked for. That is the cheapest possible way to
    attribute one crater's measurements to another, and it returned HTTP 200.
    """

    def __init__(self, crater_id: str, known: list):
        super().__init__(
            message=f"Unknown crater id '{crater_id}'.",
            error_code="UNKNOWN_CRATER",
            details={"crater_id": crater_id, "known_crater_ids": list(known)},
        )


def lunar_exception_handler(request: Request, exc: LunarScienceException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )
