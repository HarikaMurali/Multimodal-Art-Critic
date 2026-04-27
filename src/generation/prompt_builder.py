def build_sd_prompt(style, emotion, composition, user_text=""):
    positive_prompt = (
        f"{style}, {emotion} mood, refined artistic composition, "
        f"visually expressive, detailed textures, masterpiece, {user_text}"
    )

    negative_prompt = (
        "blurry, distorted, low quality, extra fingers, watermark, text, oversaturated"
    )

    edit_suggestion = (
        f"To enhance the artwork, strengthen the {emotion} feeling, preserve the {style} identity, "
        f"and improve the visual clarity of the composition."
    )

    return {
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "edit_suggestion": edit_suggestion
    }