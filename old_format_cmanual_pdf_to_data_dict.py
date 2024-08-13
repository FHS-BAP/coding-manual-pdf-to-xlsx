"""
old_format_cmanual_pdf_to_data_dict.py
script to read coding manual PDFs, parse info, and create xlsx summary
NOTE: intended for coding manuals in the old format
"""

from collections import defaultdict
import os
import re
import pdfplumber
from cmanual_pdf_to_data_dict import Variable, write_variables_to_xlsx

def get_var_names_x_coord():
    """
    returns number representing starting point on scan for var_names
    """
    return 72

def get_not_var_names():
    """
    list of words that can not be var names
    """
    return ['framingham', 'variable', 'word', 'data', 'sas', 'number',
            'missing', 'ray', 'original', 'coding', 'records', 'with',
            'should', 'cohort', 'collection', 'dataset', 'question',
            'time', 'study', 'description', 'set', 'stairs', 'information',
            'alive', 'chd', 'other', 'participant', 'exam', 'variables',
            'assigned', 'manual', 'offspring', 'version']

def is_var_name(s):
    """
    returns True if s could be a variable name (WIP)
    conditions:
        - not made of up only '-'s, '*'s, or '_'s
        - s not in get_not_var_names()
        - s is all uppercase
        - s is not all digits
        - ':' or '+' in s
    """
    return not ((s.replace('-', '') == '') or (s.replace('*', '') == '') or (s.replace('_', '') == '')\
        or (s.lower() in get_not_var_names())\
        or (s.upper() != s) or (re.sub(r'\d', '', s) == '')\
        or (':' in s) or ('+' in s) or ('=' in s) or (',' in s) or ('/' in s) or ('.' in s)
        or ('(' in s) or (')' in s) or ('-' in s) or ('"' in s) or ('“' in s))

def read_words_and_locations_on_page(pdf, pg_num):
    """
    
    """
    page = pdf.pages[pg_num]
    words = page.extract_words()

    return [{'text': word['text'],
             'x_start': word['x0'],
             'x_end': word['x1'],
             'y': word['top'],
             'y_bottom': word['bottom']} for word in words]

def extract_page_var_names(words, offset=0, is_first_page=False):
    """
    
    """
    x = get_var_names_x_coord() + offset
    var_names = []
    for word in words:
        if word['x_start'] <= x and word['x_end'] >= x:
            var_names.append(word)
    
    if is_first_page:
        for i, var in enumerate(var_names):
            if var['text'].replace('-', '') == '' or var['text'].replace('_', '') == '':
                var_names = var_names[i+1:]
                break

    to_remove = []
    for var in var_names:
        if not is_var_name(var['text']):
            to_remove.append(var)

    for var in to_remove:
        var_names.remove(var)

    return var_names

def extract_pdf_var_names(pdf):
    """
    
    """
    var_names_by_page = []

    x=0
    for i in range(len(pdf.pages)):
        words = read_words_and_locations_on_page(pdf, i)
        
        if i == 0:
            while len(extract_page_var_names(words, offset=x, is_first_page=(i==0))) < 2 \
            and 'IDTYPE' not in extract_page_var_names(words, offset=x, is_first_page=(i==0))\
            and 'ID' not in extract_page_var_names(words, offset=x, is_first_page=(i==0)):
                x += 0.05
                if x > 500:
                    break

        var_names_by_page.append(extract_page_var_names(words, offset=x, is_first_page=(i==0)))

    return var_names_by_page

def extract_var_text(pdf, var_names_by_page):
    """
    
    """
    name_to_text = {}

    for i, page in enumerate(var_names_by_page):
        # get all words on page
        words = read_words_and_locations_on_page(pdf, i)
        
        # get next page words and var names on page if exist
        next_page_words, next_page_vars = None, None
        if i+1 < len(var_names_by_page):
            next_page_words = read_words_and_locations_on_page(pdf, i+1)
            next_page_vars = var_names_by_page[i+1]
        
        # iterate through all vars on current page
        for j, var in enumerate(page):
            y1 = var['y']
            if j + 1 < len(page):
                # logic for if variable is not last on page
                y2 = page[j+1]['y']
                name_to_text[var['text']] = pull_text_between(y1, y2, words)
            else:
                # logic for if variable is last on page
                if not next_page_vars:
                    name_to_text[var['text']] = pull_text_between(y1, 9999, words)
                elif len(next_page_vars) > 0:
                    y2 = next_page_vars[0]['y']
                    name_to_text[var['text']] = handle_broken_var_text(y1, y2, words, next_page_words)
                else:
                    name_to_text[var['text']] = pull_text_between(y1, 9999, words)
    return name_to_text

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

def get_coded_values_patterns():
    """
    
    """
    return [r'\d{1,4}-\d{1,4}[\s=]{1}', r'\d{1,4}[\s=]{1}']

def parse_var_text_for_coded_values(var_text):
    """
    
    """
    var_text = re.sub(r'[-‐‑‒–—]', '-', var_text)
    patterns = get_coded_values_patterns()

    values = defaultdict(dict)
    curr_code = None

    lines = var_text.split('\n')[1:]
    for i, line in enumerate(lines):
        code = None
        for pattern in patterns:
            code = re.search(pattern, line)
            if code:
                if code.group().strip() not in line.strip().split(' ')[0]:
                    continue

                curr_code = code.group().replace('=', '').strip()
                
                value_desc = line.replace(code.group(), '').replace('=', '').strip()

                values[curr_code]['Description'] = value_desc
                values[curr_code]['Count'] = None
                break

        if code is None:
            if i == 0:
                continue
            else:
                if curr_code:
                    if line.upper() == line and 'Description' in values[curr_code]:
                        values[curr_code]['Description'] += f' {line.strip()}'
    
    return values

def parse_var_text_for_description(var_text):
    """
    
    """
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
            words = line.strip().split(' ')
            if len(words) <= 0:
                break
            elif code.group() in line.strip().split(' ')[0]:
                break
            else:
                s += f' {line}'

    return s.replace('=', '').strip()

def process_pdf(pdf_fp):
    """
    
    """
    variables = []
    with pdfplumber.open(pdf_fp) as pdf:
        var_names =  extract_pdf_var_names(pdf)
        name_to_text = extract_var_text(pdf, var_names)
        for var_name, var_text in name_to_text.items():
            desc = parse_var_text_for_description(var_text)
            coded_values = parse_var_text_for_coded_values(var_text)
            variables.append(Variable(var_name, desc, coded_values, None))
    
    write_variables_to_xlsx(pdf_fp, variables)
    print('Done!')

def main():
    pdf_dir = r'PDFs\old_format'

    for file in os.listdir(pdf_dir):
        if '.pdf' not in file.lower():
            continue

        fp = os.path.join(pdf_dir, file)
        process_pdf(fp)

if __name__ == '__main__':
    main()