# -*- coding: utf-8 -*-
"""shincom-unified 猫占い /tenmob 出力修正パッチ。

前回パッチでは selfmob 側には猫占い生成処理が入りましたが、管理画面の
/ten・/tenmob ルート側で result_data['neko_uranai'] を作っていなかったため、
フォームから neko_uranai が送信されてもPDFに出ませんでした。

使い方:
  1. このZIPを shincom-unified ルートに展開
  2. python tools/apply_neko_tenmob_fix.py
  3. git add app_unified.py && git commit -m "Fix neko uranai for tenmob" && git push
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_unified.py"
BACKUP = APP.with_name(APP.name + ".bak_neko_tenmob_fix")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"{label}: target not found")
    return text.replace(old, new, 1)


def main() -> int:
    if not APP.exists():
        print("app_unified.py が見つかりません。shincom-unified のルートで実行してください。")
        return 1

    text = APP.read_text(encoding="utf-8")
    if not BACKUP.exists():
        BACKUP.write_text(text, encoding="utf-8")

    # /ten・/tenmob ルート内で、猫チェックを読み取る。
    old = '''            if output_style not in ("normal", "tokyo", "yuta_safe"):\n                output_style = "normal"\n\n            # Hard guard: style is JA-only (no side effects on en/zh/ko)\n            if output_lang != "ja":\n                output_style = "normal"\n'''
    new = '''            if output_style not in ("normal", "tokyo", "yuta_safe"):\n                output_style = "normal"\n\n            include_neko = _truthy(\n                data.get("neko_uranai")\n                or data.get("cat_uranai")\n                or data.get("include_neko")\n                or data.get("neko")\n            )\n\n            # Hard guard: style is JA-only (no side effects on en/zh/ko)\n            if output_lang != "ja":\n                output_style = "normal"\n                include_neko = False\n'''
    text = replace_once(text, old, new, "tenmob include_neko flag")

    # ログに include_neko を出して確認しやすくする。
    old = '''                print(f"[tenmob] output_lang={output_lang} keys={form_keys[:30]}")\n'''
    new = '''                print(f"[tenmob] output_lang={output_lang} include_neko={include_neko} keys={form_keys[:30]}", flush=True)\n'''
    text = replace_once(text, old, new, "tenmob debug log")

    # /ten・/tenmob の result_data に猫占いデータを追加する。
    old = '''            if full_year:\n                yearly_data = generate_yearly_fortune(birthdate, now, force_next_month=force_next_month, lang=output_lang)\n'''
    new = '''            if include_neko and eto_number:\n                try:\n                    neko_profile = get_neko_profile(eto_number)\n                    result_data["neko_uranai"] = {\n                        **neko_profile,\n                        "animal": animal,\n                        "eto": eto,\n                        "omikuji": build_neko_omikuji(result_data.get("iching_result", ""), neko_profile.get("name", "猫")),\n                    }\n                    print(f"[tenmob] neko_uranai added: {neko_profile.get('number')} {neko_profile.get('name')}", flush=True)\n                except Exception as e:\n                    print("❌ 猫占い生成エラー(/tenmob):", e, flush=True)\n\n            if full_year:\n                yearly_data = generate_yearly_fortune(birthdate, now, force_next_month=force_next_month, lang=output_lang)\n'''
    text = replace_once(text, old, new, "tenmob result_data neko")

    APP.write_text(text, encoding="utf-8")
    print("/ten・/tenmob 猫占い出力修正 完了")
    print("確認ログ: [tenmob] output_lang=ja include_neko=True ...")
    print("さらにPDF生成時に neko_uranai added が出れば、猫ページが追加されます。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
