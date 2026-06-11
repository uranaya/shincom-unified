# -*- coding: utf-8 -*-
"""shincom-unified に猫占いチェックボックス＋猫占いPDFページを追加するパッチ。

使い方:
  1. このZIPの中身を shincom-unified のルートに展開
  2. python tools/apply_neko_patch.py
  3. Gitへ add/commit/push

このスクリプトは既存ファイルを .bak_neko_patch としてバックアップし、
同じパッチを2回当てても重複しないようにしています。
"""
from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKUP_SUFFIX = ".bak_neko_patch"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if not backup.exists() and path.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(text, encoding="utf-8")


def ensure_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            # 上書きコピー。既存の別ファイルは残す。
            for item in src.iterdir():
                ensure_copy(item, dst / item.name)
        else:
            shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def insert_once(text: str, marker: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    if marker not in text:
        raise RuntimeError(f"{label}: marker not found")
    return text.replace(marker, marker + insertion, 1)


def insert_before_once(text: str, marker: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    if marker not in text:
        raise RuntimeError(f"{label}: marker not found")
    return text.replace(marker, insertion + marker, 1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new.strip() in text:
        return text
    if old not in text:
        raise RuntimeError(f"{label}: target block not found")
    return text.replace(old, new, 1)


def patch_templates() -> None:
    # 管理画面/通常フォーム
    path = ROOT / "templates" / "index.html"
    text = read_text(path)
    checkbox = '''\n\n    <label class="option-label" for="neko_uranai">\n      <input type="checkbox" id="neko_uranai" name="neko_uranai" value="yes">\n      <span>猫占いを出す（＋A4 1ページ）</span>\n    </label>'''
    text = insert_once(
        text,
        '''    <label class="option-label" for="force_next_month">\n      <input type="checkbox" id="force_next_month" name="force_next_month" value="yes">\n      <span>来月・再来月を占う（20日以前でも来月起点にする）</span>\n    </label>''',
        checkbox,
        "templates/index.html checkbox",
    )
    text = insert_once(
        text,
        '''      const forceNextMonth = document.getElementById("force_next_month")?.checked || false;\n''',
        '''      const nekoUranai = document.getElementById("neko_uranai")?.checked || false;\n''',
        "templates/index.html js const",
    )
    text = replace_once(
        text,
        '''      const payload = { image_data: imageData, birthdate, full_year: fullYear, force_next_month: forceNextMonth,\n                        tokyo_mode: tokyoMode, yuta_mode: yutaMode, english_output: englishOutput,\n                        output_lang: outputLang, output_style: outputStyle, output_mode: mode };''',
        '''      const payload = { image_data: imageData, birthdate, full_year: fullYear, force_next_month: forceNextMonth,\n                        neko_uranai: nekoUranai,\n                        tokyo_mode: tokyoMode, yuta_mode: yutaMode, english_output: englishOutput,\n                        output_lang: outputLang, output_style: outputStyle, output_mode: mode };''',
        "templates/index.html payload",
    )
    write_text(path, text)

    # 決済後/セルフモバイル入力フォーム
    path = ROOT / "templates" / "index_selfmob.html"
    text = read_text(path)
    checkbox = '''\n\n    <label class="option-label" for="neko_uranai">\n      <input type="checkbox" id="neko_uranai" name="neko_uranai" value="yes">\n      <span>猫占いを出す（＋A4 1ページ）</span>\n    </label>'''
    text = insert_once(
        text,
        '''    <label class="option-label" for="force_next_month">\n      <input type="checkbox" id="force_next_month" name="force_next_month" value="yes">\n      <span>来月・再来月を占う（20日以前でも来月起点にする）</span>\n    </label>''',
        checkbox,
        "templates/index_selfmob.html checkbox",
    )
    text = insert_once(
        text,
        '''      const forceNextMonth = document.getElementById("force_next_month")?.checked || false;\n''',
        '''      const nekoUranai = document.getElementById("neko_uranai")?.checked || false;\n''',
        "templates/index_selfmob.html js const",
    )
    text = insert_once(
        text,
        '''        force_next_month: forceNextMonth,\n''',
        '''        neko_uranai: nekoUranai,\n''',
        "templates/index_selfmob.html payload",
    )
    write_text(path, text)


def patch_app_unified() -> None:
    path = ROOT / "app_unified.py"
    text = read_text(path)
    text = insert_once(
        text,
        '''from kyusei_utils import get_honmeisei, get_kyusei_fortune\n''',
        '''from neko_uranai_utils import get_neko_profile, build_neko_omikuji\n''',
        "app_unified import",
    )
    text = insert_once(
        text,
        '''    if output_lang not in ("ja", "en", "zh", "ko"):\n        output_lang = "ja"\n''',
        '''\n    include_neko = _truthy(\n        data.get("neko_uranai")\n        or data.get("cat_uranai")\n        or data.get("include_neko")\n        or data.get("neko")\n    )\n''',
        "app_unified include_neko",
    )
    text = insert_once(
        text,
        '''    if output_lang != "ja":\n        output_style = "normal"\n''',
        '''        include_neko = False\n''',
        "app_unified non-ja disable neko",
    )
    text = replace_once(
        text,
        '''        "iching_result": iching_result.replace("\\r\\n", "\\n").replace("\\r", "\\n") if isinstance(iching_result, str) else iching_result,\n        "palm_image": image_data\n    }\n\n    if full_year:''',
        '''        "iching_result": iching_result.replace("\\r\\n", "\\n").replace("\\r", "\\n") if isinstance(iching_result, str) else iching_result,\n        "palm_image": image_data\n    }\n\n    if include_neko and eto_number:\n        try:\n            neko_profile = get_neko_profile(eto_number)\n            result_data["neko_uranai"] = {\n                **neko_profile,\n                "animal": animal,\n                "eto": eto,\n                "omikuji": build_neko_omikuji(result_data.get("iching_result", ""), neko_profile.get("name", "猫")),\n            }\n        except Exception as e:\n            print("❌ 猫占い生成エラー:", e, flush=True)\n\n    if full_year:''',
        "app_unified result_data neko",
    )
    write_text(path, text)


def patch_pdf_generator() -> None:
    path = ROOT / "pdf_generator_unified.py"
    text = read_text(path)
    helper = r'''

def draw_neko_uranai_page(c, data, lang="ja", page_size=A4):
    """猫占いオプション用の追加1ページ。

    通常鑑定2ページの本文レイアウトを触らず、チェックON時だけ後ろにA4相当の
    猫タイプ・猫画像・猫御籤ページを追加する。
    """
    neko = (data or {}).get("neko_uranai") or {}
    if not neko:
        return

    width, height = page_size
    margin = 20 * mm
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    _set_font(c, lang, 18)
    c.drawCentredString(width / 2, y, "猫占い")
    y -= 11 * mm

    number = neko.get("number") or ""
    name = neko.get("name") or "猫"
    tag = neko.get("tag") or ""
    animal = neko.get("animal") or data.get("animal") or ""
    eto = neko.get("eto") or data.get("eto") or ""

    _set_font(c, lang, 12)
    c.drawString(margin, y, f"◆ あなたの猫タイプ：{number}. {name}")
    y -= 6 * mm
    _set_font(c, lang, 10)
    if animal or eto:
        base = []
        if eto:
            base.append(f"日柱：{eto}")
        if animal:
            base.append(f"対応する動物占い：{animal}")
        c.drawString(margin, y, " / ".join(base))
        y -= 5 * mm
    if tag:
        c.drawString(margin, y, f"猫キャラの性質：{tag}")
        y -= 7 * mm

    # 猫画像
    image_path = neko.get("image_path") or ""
    try:
        if image_path and os.path.exists(image_path):
            img = ImageReader(image_path)
            iw, ih = img.getSize()
            max_w = 72 * mm
            max_h = 72 * mm
            scale = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * scale, ih * scale
            x = (width - draw_w) / 2
            c.drawImage(img, x, y - draw_h, width=draw_w, height=draw_h, mask='auto')
            y -= draw_h + 8 * mm
        else:
            c.drawCentredString(width / 2, y, "（猫画像が見つかりません）")
            y -= 10 * mm
    except Exception as e:
        print("Neko image draw error:", e)
        c.drawCentredString(width / 2, y, "（猫画像の読み込みに失敗しました）")
        y -= 10 * mm

    # 猫御籤
    _set_font(c, lang, 13)
    c.drawString(margin, y, "◆ 猫御籤")
    y -= 7 * mm

    omikuji = neko.get("omikuji") or "今日はひげの向く方へ、ゆっくり進むにゃ。"
    _set_font(c, lang, 10.2)
    bottom = 22 * mm
    for line in smart_wrap(omikuji, 38, lang):
        if y < bottom:
            break
        c.drawString(margin, y, line)
        y -= 5.6 * mm

    y -= 4 * mm
    if y >= bottom + 14 * mm:
        _set_font(c, lang, 11)
        c.drawString(margin, y, "◆ 今日の合言葉")
        y -= 6 * mm
        _set_font(c, lang, 10)
        c.drawString(margin, y, "焦らず、すり寄りすぎず、必要な時だけ爪を出すにゃん。")
'''
    text = insert_before_once(
        text,
        '''\ndef draw_shincom_a4(c, data, include_yearly=False):\n''',
        helper,
        "pdf_generator_unified helper",
    )
    text = insert_once(
        text,
        '''    if include_yearly:\n        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'], lang)\n''',
        '''\n    if data.get('neko_uranai'):\n        draw_neko_uranai_page(c, data, lang, page_size=A4)\n''',
        "pdf_generator_unified a4 call",
    )
    text = insert_once(
        text,
        '''    if include_yearly:\n        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'], lang)\n''',
        '''\n    if data.get('neko_uranai'):\n        draw_neko_uranai_page(c, data, lang, page_size=B4)\n''',
        "pdf_generator_unified b4 call",
    )
    # 順序を「猫ページ → 年運ページ」にするため、上の insert_once だと年運の直後に入る。
    # 既存表示を壊さないことを優先しつつ、通常+猫だけなら3ページ目に猫が出る。
    write_text(path, text)


def main() -> int:
    required = [
        ROOT / "app_unified.py",
        ROOT / "pdf_generator_unified.py",
        ROOT / "templates" / "index.html",
        ROOT / "templates" / "index_selfmob.html",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        print("必要ファイルが見つかりません:", ", ".join(missing))
        return 1

    # ZIPをプロジェクトルートへ展開していれば、下記2つはそのまま存在する。
    # 念のため存在確認だけ行う。
    asset_checks = [ROOT / "neko_uranai_utils.py", ROOT / "static" / "neko60" / "01.png", ROOT / "static" / "neko60" / "60.png"]
    missing_assets = [str(p.relative_to(ROOT)) for p in asset_checks if not p.exists()]
    if missing_assets:
        print("猫占い追加ファイルが見つかりません:", ", ".join(missing_assets))
        print("ZIPの中身を shincom-unified のルートへ丸ごと展開してから再実行してください。")
        return 1

    patch_templates()
    patch_app_unified()
    patch_pdf_generator()

    print("猫占いパッチ適用完了")
    print("追加: neko_uranai_utils.py, static/neko60/*.png")
    print("更新: app_unified.py, pdf_generator_unified.py, templates/index.html, templates/index_selfmob.html")
    print("バックアップ: *.bak_neko_patch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
