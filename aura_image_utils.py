import openai
import base64
from io import BytesIO
from PIL import Image
import requests

def dalle_image(prompt, size="256x256") -> Image.Image:
    """
    OpenAIでイメージ画像を生成（DALL·E使用）
    """
    response = openai.Image.create(
        prompt=prompt,
        n=1,
        size=size,
        response_format="url"
    )
    image_url = response['data'][0]['url']
    image_bytes = requests.get(image_url).content
    return Image.open(BytesIO(image_bytes))

def map_color_name_to_rgba(aura_prompt):
    """
    オーラプロンプト内の色名を簡易判定してRGBAを返す
    """
    aura_prompt = aura_prompt.lower()
    if "purple" in aura_prompt or "lavender" in aura_prompt:
        return (180, 140, 255, 100)
    if "blue" in aura_prompt:
        return (100, 150, 255, 100)
    if "green" in aura_prompt:
        return (100, 255, 150, 100)
    if "pink" in aura_prompt or "rose" in aura_prompt:
        return (255, 160, 200, 100)
    if "yellow" in aura_prompt:
        return (255, 255, 150, 100)
    return (200, 200, 255, 80)  # fallback light aura

def apply_aura_overlay(image: Image.Image, rgba_color) -> Image.Image:
    """
    与えられた画像にRGBA色のオーラを重ねて返す
    """
    aura_layer = Image.new("RGBA", image.size, rgba_color)
    base = image.convert("RGBA")
    blended = Image.alpha_composite(base, aura_layer)
    return blended.convert("RGB")  # JPEG保存用にRGBへ

def generate_aura_image(user_image_base64, past_prompt, spirit_prompt, aura_prompt) -> str:
    """
    撮影画像（base64）＋オーラ色加工＋AI生成の前世・守護霊画像を結合し、base64で返す
    """
    # 1. ユーザー画像のbase64デコード
    user_image_data = base64.b64decode(user_image_base64.split(",")[-1])
    user_image = Image.open(BytesIO(user_image_data)).convert("RGB").resize((256, 256))

    # 2. オーラカラーを適用
    rgba = map_color_name_to_rgba(aura_prompt)
    user_image = apply_aura_overlay(user_image, rgba)

    # 3. DALL·Eで前世画像生成
    past_life_img = dalle_image(past_prompt)

    # 4. DALL·Eで守護霊画像生成
    spirit_img = dalle_image(spirit_prompt)

    # 5. 横に3枚並べて合成
    merged = Image.new("RGB", (256 * 3, 256), (255, 255, 255))
    merged.paste(user_image, (0, 0))
    merged.paste(past_life_img, (256, 0))
    merged.paste(spirit_img, (512, 0))

    # 6. base64エンコードして返す
    buffer = BytesIO()
    merged.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"
