"""
extract_tables_and_var_names.py
module for extracting/reading tables and parsing variable names from coding manuals using pyplumber
"""

import re
from collections import defaultdict
import pdfplumber

def get_num_observations(pdf_fp):
    """
    uses regex to search for indicators of num observations
    outputs int repreeenting num observations if found
        else None
    """
    with pdfplumber.open(pdf_fp) as pdf:
        page = pdf.pages[0]
        text_data = page.extract_words()

        words = [t['text'].lower() for t in text_data]

        s = ' '.join(words).strip()

        pattern = r'# observations: \d+'
        x = re.search(pattern, s)
        if x is not None:
            return int(x.group().split(' ')[2])

        pattern = r'there are \d+ unique fhs participants'
        x = re.search(pattern, s)
        if x is not None:
            return int(x.group().split(' ')[2])

    return None

def get_tables_on_page_by_ycoord(pdf, pg_num):
    """
    takes pdfplumber pdf object and int (falling in range(<number of pages in pdf>)
    outputs:
    - dict
        - keys: distances from table to top of page (float)
        - values:
            - dict
                'parsed': parsed table (see parse_table_cells)
                'raw_table': pdfplumber table object
    """
    pg = pdf.pages[pg_num]
    tables = pg.debug_tablefinder().tables

    final = defaultdict(dict)
    for table in tables:
        copy = pdf.pages[pg_num]
        cells = table.cells
        table_contents = []
        ycoord = copy.crop(table.bbox).extract_words()[0]['top']
        for cell in cells:
            extract_words = pg.crop(cell).extract_words()
            cell_words = ''
            for word in extract_words:
                cell_words += f'{word['text']} '
            cell_words = cell_words.rstrip()
            if cell_words == '':
                continue
            table_contents.append(cell_words)

        parsed = parse_table_cells(table_contents)
        if parsed is None:
            continue
        final[ycoord]['parsed'] = parsed
        final[ycoord]['raw_table'] = table

    return dict(final)

def get_all_tables_by_page_by_ycoord(pdf):
    """
    wrapper method
    calls get_tables_on_page_by_ycoord on all pages of pdf at pdf_fp
    outputs:
    - dict
        keys: integers in range(<number of pages in pdf>)
        values: output of get_tables_on_page_by_ycoord for that page
    """

    tables_by_pg_num = {}
    for pg_num in range(len(pdf.pages)):
        tables_by_pg_num[pg_num] = get_tables_on_page_by_ycoord(pdf, pg_num)

    return tables_by_pg_num

def fix_split_tables(tables_by_pg_num):
    """
    takes output of get_all_tables_by_page_by_ycoord
    combines tables split by page breaks (directly manipulates elements)
    """
    for pg_num, curr_page in tables_by_pg_num.items():
        for _, table_info in curr_page.items():
            if is_table_last_thing_on_page(table_info['raw_table']):
                if pg_num+1 == len(tables_by_pg_num.keys()):
                    break
                next_page = tables_by_pg_num[pg_num+1]
                for y, other_table_info in next_page.items():
                    if is_table_first_thing_on_page(other_table_info['raw_table']):
                        table_info['parsed'].update(other_table_info['parsed'])
                        del next_page[y]
                        break
                break

def get_varnames_on_page_by_ycoord(pdf, pg_num):
    """
    takes pdfplumber pdf object and int (falling in range(<number of pages in pdf>)
    outputs:
    - dict
        - keys: distances from table to top of page (float)
        - values: variable name at that distance
    """
    page = pdf.pages[pg_num]

    text_data = page.extract_words()

    ycoord_name = {}

    for i, word in enumerate(text_data):
        if i+1 == len(text_data):
            break
        if "Variable" == word['text'] and 'name:' == text_data[i+1]['text']:
            j = i+2
            name = ''
            while text_data[j]['text'] != 'Description:' and text_data[j]['text'] != 'Page':
                name += text_data[j]['text']
                j += 1

            ycoord = word['top']
            ycoord_name[ycoord] = name

    # print(ycoord_name)
    return ycoord_name

def get_all_varnames_by_page_by_ycoord(pdf):
    """
    wrapper method
    calls get_varnames_on_page_by_ycoord on all pages of pdf at pdf_fp
    outputs:
    - dict
        keys: integers in range(<number of pages in pdf>)
        values: output of get_varnames_on_page_by_ycoord for that page
    """
    vars_by_pg_num = {}
    for pg_num in range(len(pdf.pages)):
        vars_by_pg_num[pg_num] = get_varnames_on_page_by_ycoord(pdf, pg_num)

    return vars_by_pg_num

def get_all_tables_and_names_by_page_by_ycoord(pdf_fp):
    """
    wrapper method
    returns outputs of:
        - get_varnames_on_page_by_ycoord
        - get_tables_on_page_by_ycoord
    """
    with pdfplumber.open(pdf_fp) as pdf:
        vars_by_pg_num = {}
        tables_by_pg_num = {}
        for pg_num in range(len(pdf.pages)):
            vars_by_pg_num[pg_num] = get_varnames_on_page_by_ycoord(pdf, pg_num)
            tables_by_pg_num[pg_num] = get_tables_on_page_by_ycoord(pdf, pg_num)

    return vars_by_pg_num, tables_by_pg_num

def map_var_to_table(pdf_fp):
    """
    parses outputs of get_varnames_on_page_by_ycoord and get_tables_on_page_by_ycoord
    fixes split tables
    outputs dictionary binding varnames to their table
        binds based on y distance between name and table
    """
    vars_by_pg_num, tables_by_pg_num = get_all_tables_and_names_by_page_by_ycoord(pdf_fp)
    fix_split_tables(tables_by_pg_num)

    name_to_table = defaultdict(dict)
    for pg_num, ycoords_names in vars_by_pg_num.items():
        names_on_page = ycoords_names.values()
        ycoords_tables = tables_by_pg_num[pg_num]
        for name_y, name in ycoords_names.items():
            var_codes = None
            for table_y, table_info in ycoords_tables.items():
                if table_y > name_y:
                    if (table_y - name_y) > 140:
                        break
                    parsed = table_info['parsed']

                    code_values = [code_info['Description'] for code_info in parsed.values()]
                    bad_table = False
                    for n in names_on_page:
                        if n.upper() in code_values:
                            bad_table = True
                    if bad_table:
                        break

                    var_codes = parsed
                    del ycoords_tables[table_y]
                    break
            if var_codes is None and name_y > 650 and pg_num + 1 in tables_by_pg_num:
                for _, table_info in tables_by_pg_num[pg_num+1].items():
                    if is_table_almost_first_thing_on_page(table_info['raw_table']):
                        var_codes = table_info['parsed']

            name_to_table[name]['table'] = var_codes
            name_to_table[name]['location'] = f'{str(pg_num).zfill(4)}{str(round(name_y)).zfill(4)}'

    return name_to_table

def parse_table_cells(table):
    """
    takes list of strings representing the text of each table cell
        (going down columns, leftmost column to rightmost)
    ouputs dictionary of dictionaries
        keys: coded value
        values: dictionaries
            - 'Description': description of coded value
            - 'Count': if count column, str represnting count
                       else None
    """
    str_codes = ['Blank', 'Not blank']
    num_rows = 0
    for i, cell_text in enumerate(table):
        if (cell_text == cell_text.upper() or cell_text in str_codes):
            if (len(cell_text) >= 2 and '–' not in cell_text and
                '—' not in cell_text and '-' not in cell_text):
                try:
                    float(cell_text)
                except:
                    break
            num_rows += 1
        else:
            break

    final = defaultdict(dict)
    if num_rows*2 == len(table):
        for i in range(num_rows):
            code = table[i]
            desc = table[num_rows + i]
            final[code]['Description'] = desc
            final[code]['Count'] = None
    elif num_rows*3 == len(table):
        for i in range(num_rows):
            code = table[i]
            desc = table[num_rows + i]
            count = table[2*num_rows + i]
            final[code]['Description'] = desc
            final[code]['Count'] = count
    else:
        return None

    return dict(final)

def is_table_first_thing_on_page(table):
    """
    helper method
    takes pdf plumber table object
    checks whether distance from table to top of page is less than 75
    """
    dist_to_top = table.bbox[1]
    return dist_to_top < 75

def is_table_last_thing_on_page(table):
    """
    helper method
    takes pdf plumber table object
    checks whether distance from table to top of page is more than 670
    """
    dist_to_top = table.bbox[3]
    return dist_to_top > 670

def is_table_almost_first_thing_on_page(table):
    """
    helper method
    takes pdf plumber table object
    checks whether distance from table to top of page is less than 150
    """
    dist_to_top = table.bbox[1]
    return dist_to_top < 150
