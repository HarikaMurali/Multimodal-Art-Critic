def format_critique_response(
    caption="",
    style="Unknown",
    emotion="Unknown",
    composition="No composition analysis available.",
    critique="No critique generated.",
    positive_prompt="",
    negative_prompt="",
    edit_suggestion=""
):
    """
    Formats the final chatbot response in a readable way.
    Returns a single string for display in Gradio/Streamlit.
    """

    sections = []

    if caption:
        sections.append(f"Artwork Summary:\n{caption}")

    sections.append(
        "Critique Report:\n"
        f"- Style: {style}\n"
        f"- Emotion: {emotion}\n"
        f"- Composition: {composition}\n"
    )

    sections.append(f"Detailed Critique:\n{critique}")

    if positive_prompt or negative_prompt or edit_suggestion:
        prompt_block = "Generation Suggestions:\n"

        if positive_prompt:
            prompt_block += f"- Positive Prompt: {positive_prompt}\n"
        if negative_prompt:
            prompt_block += f"- Negative Prompt: {negative_prompt}\n"
        if edit_suggestion:
            prompt_block += f"- Suggested Edit: {edit_suggestion}\n"

        sections.append(prompt_block.strip())

    return "\n\n".join(sections)


def format_error_response(error_message):
    """
    Formats errors in a user-friendly way.
    """
    return (
        "Something went wrong while analyzing the artwork.\n"
        f"Error details: {error_message}\n"
        "Please try again with another image or description."
    )


def build_chat_prompt(caption, style, emotion, composition, user_text=""):
    """
    Builds a prompt for an LLM or hosted chat model to create
    a more natural final critique.
    """
    return f"""
You are an art critic bot.

Analyze the artwork in a friendly and intelligent way.

Inputs:
- Caption: {caption}
- User description: {user_text}
- Predicted style: {style}
- Predicted emotion: {emotion}
- Composition analysis: {composition}

Instructions:
- Write a short and natural art critique.
- Mention style, emotional tone, and composition.
- Keep it understandable for students and beginners.
- End with one suggestion for how the artwork could be enhanced.
""".strip()