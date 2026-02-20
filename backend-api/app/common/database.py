from fastapi import Request

from app.db.postgres import get_pg_session  # noqa: F401


async def get_mongo_db(request: Request):
    """FastAPI dependency that returns the MongoDB database instance."""
    return request.app.mongodb
