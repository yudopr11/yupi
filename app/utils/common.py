def escape_like(value: str) -> str:
    """Escape special characters for SQL LIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
