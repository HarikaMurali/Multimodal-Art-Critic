from config.settings import STYLE_LABELS

def detect_style(caption: str):
    caption_lower = caption.lower()
    for label in STYLE_LABELS:
        if label in caption_lower:
            return label
    return "expressive contemporary art"