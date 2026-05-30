"""UUID7 generator using uuid_utils (Rust-backed) with stdlib UUID compat."""
import uuid
from uuid_utils import uuid7 as _uuid7


def uuid7() -> uuid.UUID:
    """Generate a time-ordered UUIDv7 as a standard uuid.UUID object."""
    return uuid.UUID(str(_uuid7()))
