# 猫占いPDF表示 修正パッチ

## 目的

前回の `apply_neko_detail_fix.py` は SyntaxError で途中停止しました。
そのため、`neko_uranai_utils.py` の性格説明は入っていても、`pdf_generator_unified.py` が古いままで、

- 「対応する動物占い」がPDFに出る
- 性質・性格説明がPDFに出ない

という状態になっています。

このパッチは PDF 側だけを修正します。

## 適用方法

shincom-unified のルートで実行してください。

```bash
python tools/fix_neko_pdf_detail.py
git add pdf_generator_unified.py tools/fix_neko_pdf_detail.py
git commit -m "Fix neko uranai PDF details"
git push
```

※ 以前pushされた `tools/apply_neko_detail_fix.py` は壊れたパッチファイルですが、アプリ本体から import されない限り Render の動作には影響しません。
気になる場合は後で削除して構いません。

```bash
git rm tools/apply_neko_detail_fix.py
git commit -m "Remove broken neko detail patch script"
git push
```

## 修正後の表示

- PDF上の「対応する動物占い：〇〇」は削除
- 「◆ 性質・性格」を追加
- `neko_uranai_utils.py` の `description` を表示
- 猫画像を少し小さくして説明文スペースを確保
- 「◆ 猫御籤」はそのまま表示
