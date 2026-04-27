# C:\Chatbot\src\api_clients\hf_client.py

import os
from huggingface_hub import InferenceClient
from config.settings import (
    HF_TOKEN,
    IMAGE_TO_TEXT_MODEL,
    CHAT_MODEL,
    TEXT_TO_IMAGE_MODEL,
)

client = InferenceClient(api_key=HF_TOKEN)


def _extract_text(result):
    if hasattr(result, "generated_text") and result.generated_text:
        return result.generated_text
    if isinstance(result, str):
        return result
    return ""


def _build_caption_from_labels(image_path):
    try:
        labels = client.image_classification(image=image_path)
        top_labels = []
        for item in labels[:3]:
            label = getattr(item, "label", "")
            if label:
                top_labels.append(label.replace("_", " "))

        if top_labels:
            return f"Artwork featuring {', '.join(top_labels)}."
    except Exception:
        pass

    return "Artwork with expressive visual elements."


def generate_image_caption(image_path):
    if not image_path:
        return ""

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    try:
        result = client.image_to_text(image=image_path, model=IMAGE_TO_TEXT_MODEL)
        caption = _extract_text(result)
        if caption:
            return caption

        result = client.image_to_text(image=image_path)
        caption = _extract_text(result)
        if caption:
            return caption

        return _build_caption_from_labels(image_path)

    except Exception as e:
        fallback_caption = _build_caption_from_labels(image_path)
        if fallback_caption:
            return fallback_caption
        raise RuntimeError(f"Image captioning failed: {str(e)}")


def generate_chat_response(prompt):
    try:
        messages = [
            {
                "role": "system",
                "content": "You are an art critic assistant. Give concise, insightful critique."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        result = client.chat_completion(
            model=CHAT_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        return result.choices[0].message.content

    except Exception as e:
        raise RuntimeError(f"Chat generation failed: {str(e)}")


def generate_image_from_prompt(prompt, negative_prompt=""):
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required for image generation")

    try:
        return client.text_to_image(
            prompt=prompt,
            negative_prompt=negative_prompt or None,
            model=TEXT_TO_IMAGE_MODEL,
        )
    except Exception as e:
        raise RuntimeError(f"Image generation failed: {str(e)}")