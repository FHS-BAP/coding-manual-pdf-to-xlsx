"""

"""

import pdfplumber

def get_page_words_and_locations(pdf_fp, pg_num):
    with pdfplumber.open(pdf_fp) as pdf:
        page = pdf.pages[pg_num]
        words = page.extract_words()

        return {word['text']: {'x': word['x0'], 'y': word['top']} for word in words}

