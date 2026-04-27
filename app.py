import os
import gradio as gr

from src.api_clients.hf_client import (
    generate_image_caption,
    generate_chat_response,
    generate_image_from_prompt,
)
from src.analysis.critique_engine import build_critique
from src.generation.prompt_builder import build_sd_prompt

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def analyze_art(image, description):
    """
    Main Gradio function.
    image -> filepath string from gr.Image(type="filepath")
    description -> user text input
    """

    caption = ""
    generated_image = None

    # Try image captioning first
    try:
        if image is not None:
            print(f"[DEBUG] Uploaded image path: {image}")
            caption = generate_image_caption(image)
            print(f"[DEBUG] Caption: {caption}")
    except Exception as e:
        print(f"[ERROR] Image analysis failed: {e}")
        caption = f"Image analysis failed: {str(e)}"

    # Fallback to user description if image caption is unavailable
    if (not caption or caption.startswith("Image analysis failed")) and description and description.strip():
        caption = description.strip()

    # If both are missing, use a default text
    if not caption:
        caption = "No image caption or description available."

    # Build critique
    try:
        critique_data = build_critique(caption, description)
    except Exception as e:
        print(f"[ERROR] Critique generation failed: {e}")
        return (
            caption,
            "Error",
            "Error",
            "Error",
            f"Critique generation failed: {str(e)}",
            "Error",
            "Error",
            "Error",
            generated_image,
        )

    # Build Stable Diffusion prompts
    try:
        prompt_data = build_sd_prompt(
            critique_data["style"],
            critique_data["emotion"],
            critique_data["composition"],
            description if description else ""
        )
    except Exception as e:
        print(f"[ERROR] Prompt generation failed: {e}")
        return (
            caption,
            critique_data.get("style", "Unknown"),
            critique_data.get("emotion", "Unknown"),
            critique_data.get("composition", "Unknown"),
            critique_data.get("critique", "No critique available."),
            f"Prompt generation failed: {str(e)}",
            "Error",
            "Error",
            generated_image,
        )

    # Optional refinement using chat model
    try:
        llm_prompt = f"""
You are an art critic assistant.

Image caption: {caption}
User description: {description}

Detected style: {critique_data['style']}
Detected emotion: {critique_data['emotion']}
Composition analysis: {critique_data['composition']}

Write a short art critique in a clear and friendly tone.
Mention:
1. style
2. composition
3. emotion
4. one suggestion for improvement
"""
        refined_critique = generate_chat_response(llm_prompt)
    except Exception as e:
        print(f"[WARNING] Chat refinement failed: {e}")
        refined_critique = critique_data["critique"]

    try:
        generated_image = generate_image_from_prompt(
            prompt_data["positive_prompt"],
            prompt_data["negative_prompt"],
        )
    except Exception as e:
        print(f"[WARNING] Image generation failed: {e}")
        generated_image = None

    return (
        caption,
        critique_data["style"],
        critique_data["emotion"],
        critique_data["composition"],
        refined_critique,
        prompt_data["positive_prompt"],
        prompt_data["negative_prompt"],
        prompt_data["edit_suggestion"],
        generated_image,
    )


CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&display=swap');

:root {
    --bg-deep: #0a1118;
    --bg-panel: #121b24;
    --bg-soft: #1a2633;
    --line: #2f4357;
    --text-main: #f2f6fa;
    --text-muted: #b5c4d3;
    --accent: #ff7b2f;
    --accent-2: #18b6a3;
}

body, .gradio-container {
    font-family: 'Space Grotesk', sans-serif !important;
    background:
        radial-gradient(1000px 600px at 10% 8%, #1b2a3a 0%, transparent 55%),
        radial-gradient(900px 500px at 95% 12%, #322014 0%, transparent 60%),
        var(--bg-deep) !important;
    color: var(--text-main);
}

.hero {
    border: 1px solid var(--line);
    background: linear-gradient(125deg, rgba(24,182,163,0.12), rgba(255,123,47,0.12));
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 10px;
}

.hero h1 {
    font-family: 'IBM Plex Serif', serif;
    font-size: 2rem;
    line-height: 1.2;
    margin: 0;
}

.hero p {
    color: var(--text-muted);
    margin: 8px 0 0;
}

.panel {
    border: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border-radius: 16px;
    padding: 14px;
}

.section-title {
    font-weight: 700;
    margin: 4px 0 10px;
    color: var(--text-main);
}

.compact textarea {
    min-height: 82px !important;
}

.primary-btn {
    background: linear-gradient(90deg, var(--accent), #ff9e47) !important;
    border: none !important;
    color: #0c0f13 !important;
    font-weight: 700 !important;
}

.ghost-btn {
    border: 1px solid var(--line) !important;
}

@media (max-width: 900px) {
    .hero h1 {
        font-size: 1.5rem;
    }
}
"""


def run_chat_turn(image, description, history):
        if history is None:
                history = []

        (
                caption,
                style,
                emotion,
                composition,
                critique,
                positive_prompt,
                negative_prompt,
                edit_suggestion,
                generated_image,
        ) = analyze_art(image, description)

        user_message = (description or "").strip()
        if not user_message and image is not None:
                user_message = "Analyze this uploaded artwork and generate a creative variation."
        if not user_message:
                user_message = "Analyze and generate artwork."

        assistant_summary = (
                f"Style: {style}\n"
                f"Emotion: {emotion}\n"
                f"Composition: {composition}\n\n"
                f"Critique:\n{critique}"
        )

        updated_history = history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_summary},
        ]

        return (
                updated_history,
                caption,
                style,
                emotion,
                composition,
                critique,
                positive_prompt,
                negative_prompt,
                edit_suggestion,
                generated_image,
        )


with gr.Blocks(title="Multimodal Art Critic Bot") as demo:
        gr.HTML(
                """
                <div class='hero'>
                    <h1>Multimodal Art Critic Bot</h1>
                    <p>Talk to your art critic, upload visuals, and get both a critique and a newly generated image in one flow.</p>
                </div>
                """
        )

        with gr.Row(equal_height=False):
                with gr.Column(scale=5):
                        with gr.Group(elem_classes=["panel"]):
                                gr.Markdown("### Creative Input")
                                image_input = gr.Image(type="filepath", label="Upload Artwork")
                                text_input = gr.Textbox(
                                        label="Describe your idea or ask for a critique",
                                        placeholder="Example: Turn these chess pieces into characters having a midnight conversation in a surreal gallery.",
                                        lines=3,
                                        elem_classes=["compact"],
                                )
                                with gr.Row():
                                        submit_btn = gr.Button("Send", elem_classes=["primary-btn"], variant="primary")
                                        clear_btn = gr.Button("Clear", elem_classes=["ghost-btn"])

                        with gr.Group(elem_classes=["panel"]):
                                gr.Markdown("### Critic Chat")
                                chatbot = gr.Chatbot(height=420, layout="bubble")

                with gr.Column(scale=6):
                        with gr.Group(elem_classes=["panel"]):
                                gr.Markdown("### Analysis Snapshot")
                                caption_out = gr.Textbox(label="Image Caption", lines=2)
                                style_out = gr.Textbox(label="Predicted Style", lines=1)
                                emotion_out = gr.Textbox(label="Predicted Emotion", lines=1)
                                composition_out = gr.Textbox(label="Composition Analysis", lines=2)
                                critique_out = gr.Textbox(label="Art Critique", lines=8)

                        with gr.Group(elem_classes=["panel"]):
                                gr.Markdown("### Prompt Studio")
                                positive_out = gr.Textbox(label="Positive Prompt", lines=3)
                                negative_out = gr.Textbox(label="Negative Prompt", lines=2)
                                edit_out = gr.Textbox(label="Edit Suggestion", lines=3)
                                generated_image_out = gr.Image(label="Generated Artwork", type="pil")

        submit_btn.click(
                fn=run_chat_turn,
                inputs=[image_input, text_input, chatbot],
                outputs=[
                        chatbot,
                        caption_out,
                        style_out,
                        emotion_out,
                        composition_out,
                        critique_out,
                        positive_out,
                        negative_out,
                        edit_out,
                        generated_image_out,
                ],
        )

        clear_btn.click(
            fn=lambda: (None, "", [], "", "", "", "", "", "", "", "", None),
                outputs=[
                        image_input,
                        text_input,
                        chatbot,
                        caption_out,
                        style_out,
                        emotion_out,
                        composition_out,
                        critique_out,
                        positive_out,
                        negative_out,
                        edit_out,
                        generated_image_out,
                ],
        )


if __name__ == "__main__":
    demo.launch(css=CUSTOM_CSS)