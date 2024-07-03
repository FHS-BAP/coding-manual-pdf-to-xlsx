"""
extract_tables_and_var_names.py
module for extracting/reading tables and parsing variable names from coding manuals using pyplumber
"""

import pdfplumber
import re
from collections import defaultdict

def get_num_observations(pdf_fp):
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

def get_tables_on_page_by_ycoord(pdf_fp, pg_num):
    """
    
    """
    with pdfplumber.open(pdf_fp) as pdf:
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
            if parsed == None:
                continue
            final[ycoord]['parsed'] = parsed
            final[ycoord]['raw_table'] = table

        return dict(final)

def get_all_tables_by_page_by_ycoord(pdf_fp):
    with pdfplumber.open(pdf_fp) as pdf:
        tables_by_pg_num = {}
        for pg_num in range(len(pdf.pages)):
            tables_by_pg_num[pg_num] = get_tables_on_page_by_ycoord(pdf_fp, pg_num)
    
    return tables_by_pg_num

def fix_split_tables(tables_by_pg_num):
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

def get_varnames_on_page_by_ycoord(pdf_fp, pg_num):
    with pdfplumber.open(pdf_fp) as pdf:
        page = pdf.pages[pg_num]

        text_data = page.extract_words()

        ycoord_name = {}

        for i, word in enumerate(text_data):
            if i+1 == len(text_data): break
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
    
def get_all_varnames_by_page_by_ycoord(pdf_fp):
    with pdfplumber.open(pdf_fp) as pdf:
        vars_by_pg_num = {}
        for pg_num in range(len(pdf.pages)):
            vars_by_pg_num[pg_num] = get_varnames_on_page_by_ycoord(pdf_fp, pg_num)
    
    return vars_by_pg_num

def get_all_tables_and_names_by_page_by_ycoord(pdf_fp):
    with pdfplumber.open(pdf_fp) as pdf:
        vars_by_pg_num = {}
        tables_by_pg_num = {}
        for pg_num in range(len(pdf.pages)):
            vars_by_pg_num[pg_num] = get_varnames_on_page_by_ycoord(pdf_fp, pg_num)
            tables_by_pg_num[pg_num] = get_tables_on_page_by_ycoord(pdf_fp, pg_num)
    
    return vars_by_pg_num, tables_by_pg_num
    
def map_var_to_table(pdf_fp):
    vars_by_pg_num, tables_by_pg_num = get_all_tables_and_names_by_page_by_ycoord(pdf_fp)
    # vars_by_pg_num = get_all_varnames_by_page_by_ycoord(pdf_fp)
    # tables_by_pg_num = get_all_tables_by_page_by_ycoord(pdf_fp)
    fix_split_tables(tables_by_pg_num)

    name_to_table = defaultdict(dict)
    for pg_num, ycoords_names in vars_by_pg_num.items():
        names_on_page = ycoords_names.values()
        ycoords_tables = tables_by_pg_num[pg_num]
        for name_y, name in ycoords_names.items():
            var_codes = None
            for table_y, table_info in ycoords_tables.items():
                if table_y > name_y:
                    # print(name)
                    # print(table_y - name_y)
                    # input()
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
            if var_codes is None and name_y > 650 and pg_num + 1 in tables_by_pg_num.keys():
                for _, table_info in tables_by_pg_num[pg_num+1].items():
                    if is_table_almost_first_thing_on_page(table_info['raw_table']):
                        var_codes = table_info['parsed']

            name_to_table[name]['table'] = var_codes
            name_to_table[name]['location'] = f'{str(pg_num).zfill(4)}{str(round(name_y)).zfill(4)}'

    return name_to_table

def parse_table_cells(table):
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
    dist_to_top = table.bbox[1]
    return dist_to_top < 75

def is_table_last_thing_on_page(table):
    dist_to_top = table.bbox[3]
    return dist_to_top > 670

def is_table_almost_first_thing_on_page(table):
    dist_to_top = table.bbox[1]
    return dist_to_top < 150

def main():
    pass

if __name__ == '__main__':
    main()