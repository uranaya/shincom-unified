# バジリスク店レジ「飲食」追加パッチ

## 適用方法

shincom-unified のルートで実行してください。

```bash
python tools/apply_basilisk_food_patch.py
git add regi_multi_shop.py tools/apply_basilisk_food_patch.py
git commit -m "Add food method to basilisk register"
git push
```

## 内容

- `/regi/basilisk` の売上方法に「飲食」を追加
- 管理画面の月別集計に「飲食」列を追加
- 請求書HTML/PDFに「飲食売上合計」を追加
- バジリスク店では飲食売上も20%の出店料計算対象
- おのだサンパーク店の入力方法には飲食を出しません

## 注意

既存DBの構造変更は不要です。`sales.method` に文字列 `飲食` として保存します。
