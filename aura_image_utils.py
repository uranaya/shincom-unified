import openai
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter
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

def apply_aura_effect(image: Image.Image, aura_color: str) -> Image.Image:
    """
    ユーザー画像にオーラ風の光を重ねる加工処理。
    放射状グラデーション＋光のにじみ効果を加える。
    """
    aura_overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(aura_overlay)

    color_map = {
        "赤": (255, 80, 80),
        "青": (80, 80, 255),
        "緑": (80, 255, 80),
        "黄": (255, 255, 80),
        "紫": (160, 80, 255),
        "白": (255, 255, 255),
        "黒": (80, 80, 80),
        "金": (255, 215, 0),
        "銀": (200, 200, 200)
    }
    base_color = color_map.get(aura_color.strip(), (255, 160, 220))

    center = (image.width // 2, image.height // 2)
    max_radius = max(image.width, image.height) // 2

    for r in range(max_radius, 0, -5):
        alpha = int(120 * (r / max_radius))  # 中心ほど濃く
        draw.ellipse([
            center[0] - r, center[1] - r,
            center[0] + r, center[1] + r
        ], fill=base_color + (alpha,))

    aura_overlay = aura_overlay.filter(ImageFilter.GaussianBlur(radius=20))
    image_rgba = image.convert("RGBA")
    combined = Image.alpha_composite(image_rgba, aura_overlay)

    return combined.convert("RGB")

def generate_aura_image(user_image_base64, past_prompt, spirit_prompt, aura_color="紫") -> str:
    """
    撮影画像＋前世＋守護霊の画像を合成しbase64で返す。
    ユーザー画像にはオーラ効果を追加。
    """
    # 1. ユーザー画像読み込み
    user_image_data = base64.b64decode(user_image_base64.split(",")[-1])
    user_image = Image.open(BytesIO(user_image_data)).convert("RGB").resize((256, 256))

    # ⭐️ 2. オーラ効果を追加
    user_image = apply_aura_effect(user_image, aura_color)

    # 3. DALL·Eで画像生成
    past_life_img = dalle_image(past_prompt)
    spirit_img = dalle_image(spirit_prompt)

    # 4. 横に3枚合成
    merged = Image.new("RGB", (256 * 3, 256), (255, 255, 255))
    merged.paste(user_image, (0, 0))
    merged.paste(past_life_img, (256, 0))
    merged.paste(spirit_img, (512, 0))

    # 5. base64エンコードして返す
    buffer = BytesIO()
    merged.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"
