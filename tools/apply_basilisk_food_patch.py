# -*- coding: utf-8 -*-
"""
バジリスク店レジに「飲食」を追加するパッチ。

対象:
- regi_multi_shop.py

内容:
- /regi/basilisk の売上方法に「飲食」を追加
- 管理画面の月別集計・スタッフ別集計・日別内訳・請求書PDFに「飲食」を表示
- バジリスク店では飲食売上も対面/コンピューターと同じ20%計算対象に含める
- おのだサンパーク店には飲食を出さない
"""

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "regi_multi_shop.py"

def fail(msg: str) -> None:
    print("❌ " + msg)
    sys.exit(1)

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            print(f"✅ already patched: {label}")
            return text
        fail(f"置換箇所が見つかりません: {label}")
    return text.replace(old, new, 1)

def main() -> None:
    if not TARGET.exists():
        fail(f"{TARGET} が見つかりません。shincom-unified のルートで実行してください。")

    text = TARGET.read_text(encoding="utf-8")
    backup = TARGET.with_suffix(TARGET.suffix + ".bak_basilisk_food")
    if not backup.exists():
        shutil.copy2(TARGET, backup)
        print(f"✅ backup created: {backup.name}")

    # 1) バジリスク店の請求注記・料率に飲食を追加
    text = replace_once(
        text,
        '"invoice_note": "キャンペーン出店料：対面・コンピューター占いともに売上の20％。",\n'
        '        "normal_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20")},\n'
        '        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20")},',
        '"invoice_note": "キャンペーン出店料：対面・コンピューター占い・飲食ともに売上の20％。",\n'
        '        "normal_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20"), "food": Decimal("0.20")},\n'
        '        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20"), "food": Decimal("0.20")},',
        "basilisk invoice_note/rates",
    )

    # 2) 正規化に飲食を追加
    text = replace_once(
        text,
        '    if method == "コンピューター":\n'
        '        return "コンピューター"\n'
        '    if "現金外" in (method or ""):',
        '    if method == "コンピューター":\n'
        '        return "コンピューター"\n'
        '    if method == "飲食":\n'
        '        return "飲食"\n'
        '    if "現金外" in (method or ""):',
        "normalize food method",
    )

    # 3) バジリスク専用の方法追加関数
    text = replace_once(
        text,
        '    def current_staffs() -> List[str]:\n'
        '        return fallback_staffs\n',
        '    def current_staffs() -> List[str]:\n'
        '        return fallback_staffs\n'
        '\n'
        '    def current_methods(shop_key: str) -> List[str]:\n'
        '        """バジリスク店だけ、対面・コンピューターと同列に飲食を出す。"""\n'
        '        shop_methods = list(methods)\n'
        '        if shop_key == "basilisk" and "飲食" not in shop_methods:\n'
        '            try:\n'
        '                idx = shop_methods.index("コンピューター") + 1\n'
        '            except ValueError:\n'
        '                idx = len(shop_methods)\n'
        '            shop_methods.insert(idx, "飲食")\n'
        '        return shop_methods\n',
        "current_methods for basilisk",
    )

    # 4) 入力画面・編集画面に店舗別methodsを渡す
    text = replace_once(
        text,
        '            methods=methods,\n'
        '            today=date.today().strftime("%Y-%m-%d"),',
        '            methods=current_methods(shop_key),\n'
        '            today=date.today().strftime("%Y-%m-%d"),',
        "input methods",
    )
    text = replace_once(
        text,
        '                        methods=methods,\n'
        '                    )',
        '                        methods=current_methods(shop_key),\n'
        '                    )',
        "edit methods",
    )

    # 5) 日別請求書内訳に飲食を追加
    text = replace_once(
        text,
        '                    daily[key] = {"対面": Decimal("0"), "コンピューター": Decimal("0"), "現金外": Decimal("0")}',
        '                    daily[key] = {"対面": Decimal("0"), "コンピューター": Decimal("0"), "飲食": Decimal("0"), "現金外": Decimal("0")}',
        "daily detail default keys",
    )

    # 6) 請求計算に飲食を追加
    text = replace_once(
        text,
        'def _calc_invoice_totals(total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,\n'
        '                         shop_key: str, force_special: bool) -> Dict[str, Any]:\n'
        '    rates = _rates_for(shop_key, force_special)\n'
        '    store_fee = total_taiken * rates["taimen"] + total_pc * rates["pc"]',
        'def _calc_invoice_totals(total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,\n'
        '                         shop_key: str, force_special: bool, total_food: Decimal = Decimal("0")) -> Dict[str, Any]:\n'
        '    rates = _rates_for(shop_key, force_special)\n'
        '    store_fee = total_taiken * rates["taimen"] + total_pc * rates["pc"] + total_food * rates.get("food", Decimal("0"))',
        "invoice calc include food",
    )

    # 7) _aggregate_invoice に total_food を追加
    text = replace_once(
        text,
        '    total_taiken = Decimal("0")\n'
        '    total_pc = Decimal("0")\n'
        '    total_cashless = Decimal("0")',
        '    total_taiken = Decimal("0")\n'
        '    total_pc = Decimal("0")\n'
        '    total_food = Decimal("0")\n'
        '    total_cashless = Decimal("0")',
        "invoice total_food init",
    )
    text = replace_once(
        text,
        '        elif cat == "現金外":\n'
        '            total_cashless += amount\n'
        '\n'
        '    totals = _calc_invoice_totals(total_taiken, total_pc, total_cashless, shop_key, force_special)',
        '        elif cat == "飲食":\n'
        '            total_food += amount\n'
        '        elif cat == "現金外":\n'
        '            total_cashless += amount\n'
        '\n'
        '    totals = _calc_invoice_totals(total_taiken, total_pc, total_cashless, shop_key, force_special, total_food)',
        "invoice total_food aggregate",
    )
    text = replace_once(
        text,
        '        "total_pc": total_pc,\n'
        '        "total_cashless": total_cashless,',
        '        "total_pc": total_pc,\n'
        '        "total_food": total_food,\n'
        '        "total_cashless": total_cashless,',
        "invoice return total_food",
    )

    # 8) 月別集計に飲食を追加（初回一致は _aggregate_monthly の details 初期化）
    text = replace_once(
        text,
        '                "cashless_total": Decimal("0"),\n'
        '                "visit_days": 0,',
        '                "cashless_total": Decimal("0"),\n'
        '                "food_total": Decimal("0"),\n'
        '                "visit_days": 0,',
        "monthly detail food_total init",
    )
    text = replace_once(
        text,
        '        if cat in ("対面", "コンピューター"):\n'
        '            details[staff]["total"] += amount\n'
        '        elif cat == "現金外":',
        '        if cat in ("対面", "コンピューター", "飲食"):\n'
        '            details[staff]["total"] += amount\n'
        '        if cat == "飲食":\n'
        '            details[staff]["food_total"] += amount\n'
        '        elif cat == "現金外":',
        "monthly total include food",
    )
    text = replace_once(
        text,
        '    total_pc = sum((d["methods"].get("コンピューター", Decimal("0")) for d in details.values()), Decimal("0"))\n'
        '    total_cashless = sum((d["cashless_total"] for d in details.values()), Decimal("0"))',
        '    total_pc = sum((d["methods"].get("コンピューター", Decimal("0")) for d in details.values()), Decimal("0"))\n'
        '    total_food = sum((d["methods"].get("飲食", Decimal("0")) for d in details.values()), Decimal("0"))\n'
        '    total_cashless = sum((d["cashless_total"] for d in details.values()), Decimal("0"))',
        "monthly total_food sum",
    )
    text = replace_once(
        text,
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=False\n'
        '    )\n'
        '    monthly_special_invoice = _calc_invoice_totals(\n'
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=True\n'
        '    )',
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=False, total_food=total_food\n'
        '    )\n'
        '    monthly_special_invoice = _calc_invoice_totals(\n'
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=True, total_food=total_food\n'
        '    )',
        "monthly invoice calc include food",
    )
    text = replace_once(
        text,
        '        "total_pc": total_pc,\n'
        '        "total_cashless": total_cashless,',
        '        "total_pc": total_pc,\n'
        '        "total_food": total_food,\n'
        '        "total_cashless": total_cashless,',
        "monthly return total_food",
    )

    # 9) 月別テンプレートに飲食表示を追加
    text = replace_once(
        text,
        '       <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n'
        '       <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        '       <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n'
        '       {% if shop.key == "basilisk" %}<div class="summary-line"><span>飲食合計</span><strong>{{ yen(total_food) }}円</strong></div>{% endif %}\n'
        '       <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        "monthly summary normal food line",
    )
    text = replace_once(
        text,
        '        <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n'
        '        <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        '        <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n'
        '        <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        "monthly summary special no-op guard",
    )
    # The previous no-op is intentional if exact same block exists only for onosun.

    text = replace_once(
        text,
        '       <th>コンピューター</th>\n'
        '       <th>現金外</th>\n'
        '       <th>対面+コンピューター</th>',
        '       <th>コンピューター</th>\n'
        '       {% if shop.key == "basilisk" %}<th>飲食</th>{% endif %}\n'
        '       <th>現金外</th>\n'
        '       <th>{% if shop.key == "basilisk" %}対面+コンピューター+飲食{% else %}対面+コンピューター{% endif %}</th>',
        "monthly table food header",
    )
    text = replace_once(
        text,
        '        <td>{{ yen(d.methods.get("コンピューター", 0)) }}</td>\n'
        '        <td>{{ yen(d.cashless_total) }}</td>',
        '        <td>{{ yen(d.methods.get("コンピューター", 0)) }}</td>\n'
        '        {% if shop.key == "basilisk" %}<td>{{ yen(d.methods.get("飲食", 0)) }}</td>{% endif %}\n'
        '        <td>{{ yen(d.cashless_total) }}</td>',
        "monthly table food cell",
    )

    # 10) 月別ルートに total_food を渡す
    text = replace_once(
        text,
        '            total_pc=data["total_pc"],\n'
        '            total_cashless=data["total_cashless"],',
        '            total_pc=data["total_pc"],\n'
        '            total_food=data.get("total_food", Decimal("0")),\n'
        '            total_cashless=data["total_cashless"],',
        "monthly render total_food",
    )

    # 11) 請求書HTMLに飲食表示を追加
    text = replace_once(
        text,
        '    <tr><td class="left">コンピューター売上合計</td><td>{{ yen(total_pc) }}</td></tr>\n'
        '    <tr><td class="left">現金外合計</td><td>{{ yen(total_cashless) }}</td></tr>',
        '    <tr><td class="left">コンピューター売上合計</td><td>{{ yen(total_pc) }}</td></tr>\n'
        '    {% if shop.key == "basilisk" %}<tr><td class="left">飲食売上合計</td><td>{{ yen(total_food) }}</td></tr>{% endif %}\n'
        '    <tr><td class="left">現金外合計</td><td>{{ yen(total_cashless) }}</td></tr>',
        "invoice html food line",
    )

    # 12) PDF生成関数の引数・表示に飲食を追加
    text = replace_once(
        text,
        'def _create_invoice_pdf(output_path: str, shop_name: str, invoice_label: str, month: str, staff: str,\n'
        '                        total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,',
        'def _create_invoice_pdf(output_path: str, shop_name: str, invoice_label: str, month: str, staff: str,\n'
        '                        total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,\n'
        '                        total_food: Decimal = Decimal("0"),',
        "pdf function total_food arg",
    )
    text = replace_once(
        text,
        '        ("コンピューター売上合計", total_pc),\n'
        '        ("現金外合計", total_cashless),',
        '        ("コンピューター売上合計", total_pc),\n'
        '        ("飲食売上合計", total_food),\n'
        '        ("現金外合計", total_cashless),',
        "pdf summary food line",
    )
    text = replace_once(
        text,
        '    c.drawString(110 * mm, y, "コンピューター")\n'
        '    c.drawString(150 * mm, y, "現金外")',
        '    c.drawString(80 * mm, y, "コンピューター")\n'
        '    c.drawString(125 * mm, y, "飲食")\n'
        '    c.drawString(155 * mm, y, "現金外")',
        "pdf daily header food",
    )
    text = replace_once(
        text,
        '        c.drawRightString(90 * mm, y, _format_yen(amounts.get("対面", 0)))\n'
        '        c.drawRightString(130 * mm, y, _format_yen(amounts.get("コンピューター", 0)))\n'
        '        c.drawRightString(170 * mm, y, _format_yen(amounts.get("現金外", 0)))',
        '        c.drawRightString(70 * mm, y, _format_yen(amounts.get("対面", 0)))\n'
        '        c.drawRightString(115 * mm, y, _format_yen(amounts.get("コンピューター", 0)))\n'
        '        c.drawRightString(145 * mm, y, _format_yen(amounts.get("飲食", 0)))\n'
        '        c.drawRightString(180 * mm, y, _format_yen(amounts.get("現金外", 0)))',
        "pdf daily row food",
    )
    text = replace_once(
        text,
        '                total_pc=data["total_pc"],\n'
        '                total_cashless=data["total_cashless"],',
        '                total_pc=data["total_pc"],\n'
        '                total_cashless=data["total_cashless"],\n'
        '                total_food=data.get("total_food", Decimal("0")),',
        "pdf call total_food",
    )

    # 13) Python構文チェック
    compile(text, str(TARGET), "exec")

    TARGET.write_text(text, encoding="utf-8")
    print("✅ バジリスク店レジに「飲食」を追加しました。")
    print("   - 入力/修正の方法選択に追加")
    print("   - 月別集計に飲食列を追加")
    print("   - 請求書HTML/PDFに飲食売上を追加")
    print("   - バジリスク店では飲食も20%計算対象")

if __name__ == "__main__":
    main()
