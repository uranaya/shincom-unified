"""pdf_generator_unified_en.py

English PDF generator adapter.

This module intentionally *delegates* to `pdf_generator_unified.create_pdf_unified`
to keep the data schema and page layout identical to the stable Japanese implementation.
Only these are changed:
- language: English (`data['lang']='en'`)
- header rendering: `header_utils_en.draw_header_en`
- wrap length for English narrative blocks: default 90 chars (configurable)

This avoids the typical drift where English-only generators diverge from the Japanese one.
"""

from header_utils_en import draw_header_en
from pdf_generator_unified import create_pdf_unified as _create_pdf_unified


def create_pdf_unified_en(filepath, data, mode, size='a4', include_yearly=False, wrap_len=90):
    data = dict(data or {})
    data['lang'] = 'en'
    # Used by pdf_generator_unified._wrap_len via create_pdf_unified.
    data['wrap_len_en'] = wrap_len
    return _create_pdf_unified(
        filepath,
        data,
        mode,
        size=size,
        include_yearly=include_yearly,
        header_drawer=draw_header_en,
        en_wrap_len=wrap_len,
    )
