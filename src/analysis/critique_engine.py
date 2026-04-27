from src.analysis.style_analysis import detect_style
from src.analysis.emotion_analysis import detect_emotion
from src.analysis.composition_analysis import analyze_composition

def build_critique(caption: str, user_text: str = ""):
    merged = f"{caption} {user_text}".strip()
    style = detect_style(merged)
    emotion = detect_emotion(merged)
    composition = analyze_composition(merged)

    critique = f"""
Style: The artwork most closely suggests {style}.

Composition: {composition}

Emotion: The emotional tone is best described as {emotion}.

Overall Critique: The piece communicates a visually engaging atmosphere with clear stylistic character and emotional depth.
""".strip()

    return {
        "style": style,
        "emotion": emotion,
        "composition": composition,
        "critique": critique
    }