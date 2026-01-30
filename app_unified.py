import os
import uuid
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
from pdf_generator_unified import create_pdf_unified
from pdf_generator_unified_en import create_pdf_unified as create_pdf_unified_en

app = Flask(__name__)
CORS(app)

@app.route("/tenmob", methods=["POST"])
def tenmob():
    try:
        data = request.get_json()
        filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join("output", filename)
        os.makedirs("output", exist_ok=True)

        # 英語モードが明示的に指定された場合に英語PDFを生成
        is_english = (
            data.get("output_lang", "").lower() == "en" or
            data.get("english_output") is True
        )

        pdf_mode = data.get("pdf_mode", "shincom")
        size = data.get("size", "A4")
        include_yearly = data.get("include_yearly", True)

        if is_english:
            create_pdf_unified_en(filepath, data, pdf_mode, size=size, include_yearly=include_yearly)
        else:
            create_pdf_unified(filepath, data, pdf_mode, size=size, include_yearly=include_yearly)

        return jsonify({"result": "ok", "url": f"/preview/{filename}"})
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)})

@app.route("/preview/<filename>")
def preview(filename):
    return send_file(os.path.join("output", filename), as_attachment=False)

@app.route("/view/<filename>")
def view(filename):
    return send_file(os.path.join("output", filename), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
