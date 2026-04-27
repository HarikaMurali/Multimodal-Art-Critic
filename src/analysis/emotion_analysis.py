from config.settings import EMOTION_LABELS

def detect_emotion(text: str):
    text = text.lower()
    if any(word in text for word in ["dark", "lonely", "sad", "gloom"]):
        return "melancholy"
    if any(word in text for word in ["bright", "happy", "warm", "joy"]):
        return "joy"
    if any(word in text for word in ["dream", "strange", "mystic"]):
        return "mystery"
    return "awe"