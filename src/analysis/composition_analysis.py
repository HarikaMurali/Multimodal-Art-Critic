def analyze_composition(caption: str):
    caption = caption.lower()

    if "close-up" in caption or "portrait" in caption:
        return "The composition appears focused and subject-centered."
    if "landscape" in caption or "wide" in caption:
        return "The composition feels open, spacious, and scene-driven."
    return "The composition appears balanced with a readable visual focus."