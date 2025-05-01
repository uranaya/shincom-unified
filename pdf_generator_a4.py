from PyPDF2 import PdfMerger
import os

def create_pdf_combined(image_data, birthdate, filename):
    os.makedirs("static", exist_ok=True)

    file_front = f"front_{filename}"
    file_year  = f"year_{filename}"

    print("📄 front作成開始:", file_front)
    try:
        palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
        create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, file_front)
        if not os.path.exists(file_front):
            print("❌ front PDFが作成されていません:", file_front)
    except Exception as e:
        print("❌ front PDF作成失敗:", e)
        raise

    print("📄 yearly作成開始:", file_year)
    try:
        create_pdf_yearly(birthdate, file_year)
        if not os.path.exists(file_year):
            print("❌ yearly PDFが作成されていません:", file_year)
    except Exception as e:
        print("❌ yearly PDF作成失敗:", e)
        raise

    try:
        print("📎 PDFマージ開始")
        merger = PdfMerger()
        merger.append(file_front)
        merger.append(file_year)
        merged_path = f"static/{filename}"
        merger.write(merged_path)
        merger.close()
        print("✅ マージ成功:", merged_path)

        # 不要な一時ファイルを削除
        os.remove(file_front)
        os.remove(file_year)

    except Exception as e:
        print("❌ PDFマージまたは削除失敗:", e)
        raise
