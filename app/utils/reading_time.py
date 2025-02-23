def calculate_reading_time(content: str) -> int:
    """
    Calculate reading time in minutes based on content length.
    Average reading speed: 300 words per minute.
    Minimum reading time: 1 minute
    """
    words = len(content.split())
    return max(1, round(words / 300)) 