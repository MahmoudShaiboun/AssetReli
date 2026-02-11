from fastapi import Request

async def get_database(request: Request):
    return request.app.mongodb
