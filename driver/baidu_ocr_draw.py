import base64
import json
import os
import urllib
from PIL import Image, ImageDraw, ImageFont

import requests

from driver.logger import print_action
from driver.typings import LabelMap

# 可以在百度智能云平台申请免费API KEY
API_KEY = ""
SECRET_KEY = ""


def annotate_image_with_ocr(input_image_path):
    print_action("Baidu OCR Annotating screenshot")
    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate?access_token=" + get_access_token()
    payload = 'detect_direction=false&vertexes_location=true&paragraph=false&probability=false&image=' + get_file_content_as_base64(
        input_image_path, True)
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
    if response.status_code != 200 or 'error_code' in json.loads(response.text):
        print("Baidu OCR failed to annotate screenshot")
        return
    print("Baidu OCR successfully annotated screenshot")
    words = json.loads(response.text)["words_result"]

    original_image = Image.open(input_image_path)
    label_counter = 1
    label_prefix = "A"
    drawn_positions = []
    label_map: LabelMap = {}

    for word in words:
        print(word)
        if len(word['words']) < 2:
            continue
        vertices = [(vertex['x'], vertex['y']) for vertex in word['vertexes_location']]
        too_close = any(
            abs(vertices[0][0] - pos[0]) < 48 * 2
            and abs(vertices[0][1] - pos[1]) < 24 * 2
            for pos in drawn_positions
        )

        if not too_close:
            if label_counter > 9:
                label_counter = 1
                next_char = chr(ord(label_prefix[-1]) + 1)
                if next_char == "I":
                    next_char = "J"  # Skip 'I' to avoid confusion with 'l'
                if label_prefix[-1] == "Z":
                    label_prefix += "A"
                else:
                    label_prefix = label_prefix[:-1] + next_char
            label = f"{label_prefix}{label_counter}"
            draw_square(original_image, vertices[0], label)
            drawn_positions.append(vertices[0])
            label_map[label] = {"text": word['words'], "position": vertices[0]}
            label_counter += 1

    output_filename = f"./annotated_{os.path.basename(input_image_path)}"
    original_image.save(output_filename)

    print(f"{len(label_map.keys())} elements found on the screen", end="")

    return label_map, output_filename


def draw_square(
        image,
        position,
        code,
        width=48,
        height=24,
        fill_color_start="#EFDD88",
        fill_color_end="#EBD872",
        outline_color="#EBD872",
):
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        font = ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 22)
    x, y = position
    x, y = x - width, y - height
    x1, y1 = x + width, y + height

    # Create a gradient
    gradient = Image.new("RGB", (1, 24), color=fill_color_start)
    for i in range(height):
        gradient.putpixel(
            (0, i),
            tuple(
                int(fill_color_start[j: j + 2], 16)
                + int(
                    (
                            int(fill_color_end[j: j + 2], 16)
                            - int(fill_color_start[j: j + 2], 16)
                    )
                    * (i / height)
                )
                for j in (1, 3, 5)
            ),  # type: ignore
        )

    # Apply gradient
    for i in range(x, x1):
        image.paste(gradient, (i, y, i + 1, y1))

    draw.rounded_rectangle((x, y, x1, y1), radius=5, outline=outline_color, width=2)
    _, _, w, h = draw.textbbox(xy=(0, 0), text=code, font=font)  # type: ignore
    draw.text(
        (x + (width - w) / 2, y - 1 + (height - h) / 2),
        code,
        fill="black",
        font=font,
    )


def get_file_content_as_base64(path, urlencoded=False):
    """
    获取文件base64编码
    :param path: 文件路径
    :param urlencoded: 是否对结果进行urlencoded
    :return: base64编码信息
    """
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf8")
        if urlencoded:
            content = urllib.parse.quote_plus(content)
    return content


def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
    return str(requests.post(url, params=params).json().get("access_token"))
