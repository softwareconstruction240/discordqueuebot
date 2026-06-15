def fixed_width(text: str, width: int) -> str:
    if len(text) > width:
        return text[:width - 3] + "..."
    
    return text.ljust(width)