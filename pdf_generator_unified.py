
import os
from pdf_generator_a4 import (
    create_pdf as create_pdf_shincom_a4,
    create_pdf_combined as create_pdf_combined_a4
)
from pdf_generator_b4 import (
    create_pdf as create_pdf_shincom_b4,
    create_pdf_b4_combined as create_pdf_combined_b4
)
from renai_pdf_generator import (
    create_pdf as create_pdf_renai_a4,
    create_pdf_b4 as create_pdf_renai_b4
)

def create_pdf_unified(mode, size, data, filename, include_yearly=False):
    """
    mode: "shincom" or "renai"
    size: "A4" or "B4"
    data: dict containing required fields depending on mode
    filename: output PDF filename (under static/)
    include_yearly: whether to include yearly fortune pages
    """
    if mode == "renai":
        if size == "A4":
            return create_pdf_renai_a4(
                data["image_data"],
                data["compatibility_text"],
                data["overall_love_fortune"],
                data["lucky_direction"],
                data["topic_fortunes"],
                filename
            )
        else:
            return create_pdf_renai_b4(
                data["image_data"],
                data["compatibility_text"],
                data["overall_love_fortune"],
                data["lucky_direction"],
                data["topic_fortunes"],
                data.get("yearly_love_fortunes"),
                filename
            )
    else:  # shincom
        if include_yearly:
            if size == "B4":
                return create_pdf_combined_b4(
                    data["image_data"],
                    data["palm_result"],
                    data["shichu_result"],
                    data["iching_result"],
                    data["lucky_info"],
                    data["birthdate"],
                    filename
                )
            else:
                return create_pdf_combined_a4(
                    data["image_data"],
                    data["birthdate"],
                    filename
                )
        else:
            if size == "B4":
                return create_pdf_shincom_b4(
                    data["image_data"],
                    data["palm_result"],
                    data["shichu_result"],
                    data["iching_result"],
                    data["lucky_info"],
                    filename
                )
            else:
                return create_pdf_shincom_a4(
                    data["image_data"],
                    data["palm_result"],
                    data["shichu_result"],
                    data["iching_result"],
                    data["lucky_info"],
                    filename
                )
