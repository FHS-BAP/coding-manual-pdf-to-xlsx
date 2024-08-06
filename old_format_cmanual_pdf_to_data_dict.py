"""
old_format_cmanual_pdf_to_data_dict.py
script to read coding manual PDFs, parse info, and create xlsx summary
NOTE: intended for coding manuals in the old format
"""

from collections import defaultdict
import os
import re
import pdfplumber

def get_coded_values_patterns():
    return [r'\d{1,4}-\d{1,4}[\s=]{1}', r'\d{1,4}[\s=]{1}']

def read_words_and_locations_on_page(pdf_fp, pg_num):
    """
    
    """
    with pdfplumber.open(pdf_fp) as pdf:
        page = pdf.pages[pg_num]
        words = page.extract_words()

    return [{'text': word['text'],
             'x_start': word['x0'],
             'x_end': word['x1'],
             'y': word['top'],
             'y_bottom': word['bottom']} for word in words]


def pull_text_between(y1, y2, words, tolerance=1):
    """
    
    """
    s = ''
    last_y = None
    for word in words:
        if (word['y'] >= y1 - tolerance and word['y'] < y2):
            if last_y is not None:
                if abs(last_y - word['y_bottom']) > tolerance:
                    s = s.rstrip()
                    s += '\n'
            
            s += f'{word['text']} '
            last_y = word['y_bottom']

    return s

def handle_broken_var_text(y1, y2, words1, words2, tolerance=1):
    """
    
    """
    return f'{pull_text_between(y1, 9999, words1, tolerance=tolerance)}\n{pull_text_between(0, y2, words2, tolerance=tolerance)}'

def parse_var_text_for_coded_values(var_text):
    """
    
    """
    var_text = re.sub(r'[-‐‑‒–—]', '-', var_text)
    patterns = get_coded_values_patterns()

    values = defaultdict(lambda: defaultdict(str))
    curr_code = None

    lines = var_text.split('\n')[1:]
    for i, line in enumerate(lines):
        code = None
        for pattern in patterns:
            code = re.search(pattern, line)
            if code:
                curr_code = code.group().replace('=', '').strip()

                if curr_code not in line.strip().split(' ')[0]:
                    continue
                
                value_desc = line.replace(code.group(), '').replace('=', '').strip()

                if value_desc.upper() == value_desc:
                    values[curr_code]['Description'] += value_desc
                    values[curr_code]['Count'] = None
                break

        if code is None:
            if i == 0:
                continue
            else:
                if curr_code:
                    if line.upper() == line:
                        values[curr_code]['Description'] += f' {line.strip()}'
    
    return values

def parse_var_text_for_description(var_text):
    patterns = get_coded_values_patterns()
    lines = var_text.split('\n')
    
    s = ' '.join(lines[0].split(' ')[1:])
    lines = lines[1:]

    for line in lines:
        code = None
        for pattern in patterns:
            code = re.search(pattern, line)
        
        if code is None:
            s += f' {line}'
        else:
            break

    return s

def main():
    # testing broken var_text handling
    fp = r'PDFs\ex0_8s_v1.pdf'

    words1 = read_words_and_locations_on_page(fp, 25)
    words2 = read_words_and_locations_on_page(fp, 26)

    var1 = 'FA191'
    var2 = 'FA192'

    y1, y2 = None, None
    for word in words1:
        if word['text'] == var1 and y1 is None:
            y1 = word['y']
    for word in words2:
        if word['text'] == var2 and y2 is None:
            y2 = word['y']

    var_text = handle_broken_var_text(y1, y2, words1, words2)

    d = parse_var_text_for_coded_values(var_text)
    print(d)

    for k, v in d.items():
        print(k)
        print(v)
        input()

    s = parse_var_text_for_description(var_text)

    print(s)

if __name__ == '__main__':
    main()