猫占いが /tenmob で出ない問題の修正パッチです。

原因:
- フォーム送信ログには neko_uranai が含まれている
- しかし /tenmob ルート側の result_data に neko_uranai を追加する処理が無かった
- pdf_generator_unified.py 側は data['neko_uranai'] があればページ追加する状態なので、app_unified.py の /tenmob 側だけ修正すれば出ます

適用:
1. このZIPを shincom-unified のルートに展開
2. python tools/apply_neko_tenmob_fix.py
3. git add app_unified.py
4. git commit -m "Fix neko uranai for tenmob"
5. git push
6. Renderの再デプロイ後に /tenmob でテスト

確認ログ:
[tenmob] output_lang=ja include_neko=True keys=[...]
[tenmob] neko_uranai added: 14 黒豹猫

この2行が出れば、PDFに猫占いページが追加されます。
