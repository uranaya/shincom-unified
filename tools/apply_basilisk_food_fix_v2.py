# -*- coding: utf-8 -*-
"""
バジリスク店レジに「飲食」を追加する修正版パッチ v2
- regi_multi_shop.py の現行構造に合わせて直接置換します。
- バックアップ: regi_multi_shop.py.bak_basilisk_food_v2
"""
from pathlib import Path

TARGET = Path("regi_multi_shop.py")
BACKUP = Path("regi_multi_shop.py.bak_basilisk_food_v2")


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"❌ 置換箇所が見つかりません: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit("❌ regi_multi_shop.py が見つかりません。shincom-unified のルートで実行してください。")

    text = TARGET.read_text(encoding="utf-8")
    if not BACKUP.exists():
        BACKUP.write_text(text, encoding="utf-8")
        print(f"✅ backup created: {BACKUP}")

    # すでに主要反映済みなら止める
    if '"food": Decimal("0.20")' in text and 'def current_methods(shop_key: str)' in text:
        print("✅ すでにバジリスク飲食パッチは反映済みです。")
        return

    # 1) 店舗設定: バジリスクだけ飲食20%対象にする。おのだは0%キーだけ持たせて安全化。
    text = must_replace(
        text,
        '"normal_rates": {"taimen": Decimal("0.30"), "pc": Decimal("0.50")},\n        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.40")},',
        '"normal_rates": {"taimen": Decimal("0.30"), "pc": Decimal("0.50"), "food": Decimal("0.00")},\n        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.40"), "food": Decimal("0.00")},',
        "onosun rates food key",
    )
    text = must_replace(
        text,
        '"invoice_note": "キャンペーン出店料：対面・コンピューター占いともに売上の20％。",\n        "normal_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20")},\n        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20")},',
        '"invoice_note": "キャンペーン出店料：対面・コンピューター・飲食ともに売上の20％。",\n        "normal_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20"), "food": Decimal("0.20")},\n        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20"), "food": Decimal("0.20")},',
        "basilisk rates food",
    )

    # 2) method正規化に飲食を追加
    text = must_replace(
        text,
        '    if method == "コンピューター":\n        return "コンピューター"\n    if "現金外" in (method or ""):',
        '    if method == "コンピューター":\n        return "コンピューター"\n    if method == "飲食":\n        return "飲食"\n    if "現金外" in (method or ""):',
        "normalize food",
    )

    # 3) 請求計算に飲食売上を加算できるようにする
    text = must_replace(
        text,
        'def _calc_invoice_totals(total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,\n                         shop_key: str, force_special: bool) -> Dict[str, Any]:\n    rates = _rates_for(shop_key, force_special)\n    store_fee = total_taiken * rates["taimen"] + total_pc * rates["pc"]',
        'def _calc_invoice_totals(total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,\n                         shop_key: str, force_special: bool, total_food: Decimal = Decimal("0")) -> Dict[str, Any]:\n    rates = _rates_for(shop_key, force_special)\n    store_fee = (\n        total_taiken * rates["taimen"]\n        + total_pc * rates["pc"]\n        + total_food * rates.get("food", Decimal("0"))\n    )',
        "calc invoice food",
    )

    # 4) 日別内訳に飲食を持たせる
    text = must_replace(
        text,
        'daily[key] = {"対面": Decimal("0"), "コンピューター": Decimal("0"), "現金外": Decimal("0")}',
        'daily[key] = {"対面": Decimal("0"), "コンピューター": Decimal("0"), "飲食": Decimal("0"), "現金外": Decimal("0")}',
        "daily details food bucket",
    )

    # 5) スタッフ別請求集計に飲食合計を追加
    text = must_replace(
        text,
        '    total_pc = Decimal("0")\n    total_cashless = Decimal("0")\n\n    for row in rows:',
        '    total_pc = Decimal("0")\n    total_food = Decimal("0")\n    total_cashless = Decimal("0")\n\n    for row in rows:',
        "invoice total_food init",
    )
    text = must_replace(
        text,
        '        elif cat == "コンピューター":\n            total_pc += amount\n        elif cat == "現金外":',
        '        elif cat == "コンピューター":\n            total_pc += amount\n        elif cat == "飲食":\n            total_food += amount\n        elif cat == "現金外":',
        "invoice total_food sum",
    )
    text = must_replace(
        text,
        '    totals = _calc_invoice_totals(total_taiken, total_pc, total_cashless, shop_key, force_special)',
        '    totals = _calc_invoice_totals(total_taiken, total_pc, total_cashless, shop_key, force_special, total_food)',
        "invoice calc pass food",
    )
    text = must_replace(
        text,
        '        "total_pc": total_pc,\n        "total_cashless": total_cashless,',
        '        "total_pc": total_pc,\n        "total_food": total_food,\n        "total_cashless": total_cashless,',
        "invoice return total_food",
    )

    # 6) 月別集計に飲食を通常売上として追加
    text = must_replace(
        text,
        '        if cat in ("対面", "コンピューター"):\n            details[staff]["total"] += amount',
        '        if cat in ("対面", "コンピューター", "飲食"):\n            details[staff]["total"] += amount',
        "monthly total includes food",
    )
    text = must_replace(
        text,
        '    total_pc = sum((d["methods"].get("コンピューター", Decimal("0")) for d in details.values()), Decimal("0"))\n    total_cashless = sum((d["cashless_total"] for d in details.values()), Decimal("0"))',
        '    total_pc = sum((d["methods"].get("コンピューター", Decimal("0")) for d in details.values()), Decimal("0"))\n    total_food = sum((d["methods"].get("飲食", Decimal("0")) for d in details.values()), Decimal("0"))\n    total_cashless = sum((d["cashless_total"] for d in details.values()), Decimal("0"))',
        "monthly total_food sum",
    )
    text = must_replace(
        text,
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=False\n    )',
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=False, total_food=total_food\n    )',
        "monthly normal pass food",
    )
    text = must_replace(
        text,
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=True\n    )',
        '        total_taiken, total_pc, total_cashless, shop_key, force_special=True, total_food=total_food\n    )',
        "monthly special pass food",
    )
    text = must_replace(
        text,
        '        "total_pc": total_pc,\n        "total_cashless": total_cashless,',
        '        "total_pc": total_pc,\n        "total_food": total_food,\n        "total_cashless": total_cashless,',
        "monthly return total_food",
    )

    # 7) PDF請求書に飲食売上を表示。日別内訳にも列追加。
    text = must_replace(
        text,
        'def _create_invoice_pdf(output_path: str, shop_name: str, invoice_label: str, month: str, staff: str,\n                        total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,\n                        store_fee: Decimal, store_fee_tax: Decimal, final_invoice: Decimal,',
        'def _create_invoice_pdf(output_path: str, shop_name: str, invoice_label: str, month: str, staff: str,\n                        total_taiken: Decimal, total_pc: Decimal, total_food: Decimal, total_cashless: Decimal,\n                        store_fee: Decimal, store_fee_tax: Decimal, final_invoice: Decimal,',
        "pdf signature total_food",
    )
    text = must_replace(
        text,
        '        ("対面売上合計", total_taiken),\n        ("コンピューター売上合計", total_pc),\n        ("現金外合計", total_cashless),',
        '        ("対面売上合計", total_taiken),\n        ("コンピューター売上合計", total_pc),\n        ("飲食売上合計", total_food),\n        ("現金外合計", total_cashless),',
        "pdf rows food",
    )
    text = must_replace(
        text,
        '    c.drawString(70 * mm, y, "対面")\n    c.drawString(110 * mm, y, "コンピューター")\n    c.drawString(150 * mm, y, "現金外")',
        '    c.drawString(55 * mm, y, "対面")\n    c.drawString(90 * mm, y, "コンピューター")\n    c.drawString(130 * mm, y, "飲食")\n    c.drawString(160 * mm, y, "現金外")',
        "pdf daily header food",
    )
    text = must_replace(
        text,
        '        c.drawRightString(90 * mm, y, _format_yen(amounts.get("対面", 0)))\n        c.drawRightString(130 * mm, y, _format_yen(amounts.get("コンピューター", 0)))\n        c.drawRightString(170 * mm, y, _format_yen(amounts.get("現金外", 0)))',
        '        c.drawRightString(75 * mm, y, _format_yen(amounts.get("対面", 0)))\n        c.drawRightString(120 * mm, y, _format_yen(amounts.get("コンピューター", 0)))\n        c.drawRightString(150 * mm, y, _format_yen(amounts.get("飲食", 0)))\n        c.drawRightString(180 * mm, y, _format_yen(amounts.get("現金外", 0)))',
        "pdf daily amount food",
    )

    # 8) 月別HTMLの表示追加
    text = must_replace(
        text,
        '      <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n      <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        '      <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n      {% if shop.key == "basilisk" %}<div class="summary-line"><span>飲食合計</span><strong>{{ yen(total_food) }}円</strong></div>{% endif %}\n      <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        "monthly summary food normal",
    )
    text = must_replace(
        text,
        '        <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n        <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        '        <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>\n        <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>',
        "monthly summary special unchanged",
    )
    text = must_replace(
        text,
        '      <th>コンピューター</th>\n      <th>現金外</th>\n      <th>対面+コンピューター</th>',
        '      <th>コンピューター</th>\n      {% if shop.key == "basilisk" %}<th>飲食</th>{% endif %}\n      <th>現金外</th>\n      <th>{% if shop.key == "basilisk" %}対面+コンピューター+飲食{% else %}対面+コンピューター{% endif %}</th>',
        "monthly table header food",
    )
    text = must_replace(
        text,
        '        <td>{{ yen(d.methods.get("コンピューター", 0)) }}</td>\n        <td>{{ yen(d.cashless_total) }}</td>',
        '        <td>{{ yen(d.methods.get("コンピューター", 0)) }}</td>\n        {% if shop.key == "basilisk" %}<td>{{ yen(d.methods.get("飲食", 0)) }}</td>{% endif %}\n        <td>{{ yen(d.cashless_total) }}</td>',
        "monthly table row food",
    )

    # 9) 請求書HTMLの飲食表示
    text = must_replace(
        text,
        '    <tr><td class="left">コンピューター売上合計</td><td>{{ yen(total_pc) }}</td></tr>\n    <tr><td class="left">現金外合計</td><td>{{ yen(total_cashless) }}</td></tr>',
        '    <tr><td class="left">コンピューター売上合計</td><td>{{ yen(total_pc) }}</td></tr>\n    {% if shop.key == "basilisk" %}<tr><td class="left">飲食売上合計</td><td>{{ yen(total_food) }}</td></tr>{% endif %}\n    <tr><td class="left">現金外合計</td><td>{{ yen(total_cashless) }}</td></tr>',
        "invoice html food",
    )

    # 10) 画面の選択肢: バジリスクだけ飲食を追加
    text = must_replace(
        text,
        '    methods = _normalize_method_list(method_list)\n\n    def yen(value: Any) -> str:',
        '    methods = _normalize_method_list(method_list)\n\n    def current_methods(shop_key: str) -> List[str]:\n        result = methods[:]\n        if shop_key == "basilisk" and "飲食" not in result:\n            if "コンピューター" in result:\n                result.insert(result.index("コンピューター") + 1, "飲食")\n            else:\n                result.append("飲食")\n        return result\n\n    def yen(value: Any) -> str:',
        "current_methods helper",
    )
    text = must_replace(
        text,
        '            methods=methods,\n            today=date.today().strftime("%Y-%m-%d"),',
        '            methods=current_methods(shop_key),\n            today=date.today().strftime("%Y-%m-%d"),',
        "input methods per shop",
    )
    text = must_replace(
        text,
        '            total_pc=data["total_pc"],\n            total_cashless=data["total_cashless"],',
        '            total_pc=data["total_pc"],\n            total_food=data["total_food"],\n            total_cashless=data["total_cashless"],',
        "monthly render total_food",
    )
    text = must_replace(
        text,
        '                total_pc=data["total_pc"],\n                total_cashless=data["total_cashless"],',
        '                total_pc=data["total_pc"],\n                total_food=data["total_food"],\n                total_cashless=data["total_cashless"],',
        "pdf call total_food",
    )
    text = must_replace(
        text,
        '                        methods=methods,\n                    )',
        '                        methods=current_methods(shop_key),\n                    )',
        "edit methods per shop",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("✅ バジリスク店に『飲食』を追加しました。")
    print("   - 入力画面 / 修正画面の選択肢")
    print("   - 月別集計")
    print("   - 請求書HTML/PDF")
    print("   - 飲食20%の出店料計算")


if __name__ == "__main__":
    main()
