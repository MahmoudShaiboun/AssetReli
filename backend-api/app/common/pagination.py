from typing import Any


class PaginationParams:
    def __init__(self, skip: int = 0, limit: int = 100):
        self.skip = max(skip, 0)
        self.limit = min(limit, 1000)


def paginated_response(items: list[Any], total: int, skip: int, limit: int) -> dict:
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }
