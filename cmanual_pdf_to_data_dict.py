"""
cmanual_pdf_to_data_dict.py
script to read coding manual PDFs, parse info, and create xlsx summary
NOTE: intended for coding manuals in the currently used format
"""

import os
import re
from collections import defaultdict
import cv2
import pytesseract
import pandas as pd
import pymupdf
from fhs_utility.misc import make_dir, date_ext
from extract_tables_and_var_names import map_var_to_table, get_num_observations

# make sure path points to tesseract.exe file
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

class Variable:
    """
    Class to represent a variable parsed from pdf
    Fields:
        - name: str
        - description: str
        - values: dict (optional, None if not defined)
            - keys: different values Variable can take on
            - values:
                - 'Description': description of what value means (str)
                - 'Count': count of data that has that value (int) (optional, None if not defined)
        - pdf_fp: str
            - file path to pdf variable is in
    """
    def __init__(self, name, description, values, total_obv):
        self.name = name
        self.description = description
        self.values = values
        self.total_obv = total_obv

    def __str__(self):
        values_rep = [(val, val_info) for val, val_info in self.values.items()] \
                     if self.values is not None else None
        return f'name: {self.name}\ndescription: {self.description}\nvalues: {values_rep}'

    def to_dataframe(self):
        """
        converts variable to pandas dataframe for writing to xlsx
        """
        col_names = ['Variable', 'Description', 'N', 'Miss',
                     'Minimum', 'Maximum', 'Units', 'Coded Values', 'Variable Notes']

        # N + Miss
        total = self.total_obv
        count = 0
        if self.values is not None and total is not None:
            for val, val_info in self.values.items():
                if val_info['Count'] is None:
                    break
                else:
                    count += int(val_info['Count'])

        match count:
            case 0:
                count = ''

        if total is not None and count != '':
            misses = total - count
        else:
            misses = ''

        # Minimum + Maximum
        match self.values:
            case None:
                maximum = ''
                minimum = ''
            case _:
                codes = []
                for code in self.values.keys():
                    if '–' in code or '—' in code or '-' in code:
                        code = code.replace('–', '-')
                        code = code.replace('—', '-')
                        code = re.sub(r'\s', '', code)
                        for x in code.split('-'):
                            try:
                                float(x)
                            except:
                                continue
                            else:
                                codes.append(float(x))
                    else:
                        try:
                            float(code)
                        except:
                            continue
                        else:
                            codes.append(float(code))
                if len(codes) != 0:
                    maximum = max(codes)
                    minimum = min(codes)
                else:
                    maximum = ''
                    minimum = ''

        # Coded Values
        values_rep = ''
        match self.values:
            case None:
                pass
            case _:
                for val, val_info in self.values.items():
                    s = f'{val} = {val_info['Description']}\r\n'
                    values_rep += s
        values_rep = values_rep.rstrip()

        # Variable Notes
        var_notes = ''
        if 'Note:' in self.description:
            var_notes += self.description.split('Note:')[1].strip()
            self.description = self.description.split('Note:')[0].strip()

        # Units
        units = ''
        if 'Units:' in self.description:
            units += self.description.split('Units:')[1].strip()
            self.description = self.description.split('Units:')[0].strip()

        d = [{'Variable': self.name,
            'Description': self.description,
            'N': count,
            'Miss': misses,
            'Minimum': minimum,
            'Maximum': maximum,
            'Units': units,
            'Coded Values': values_rep,
            'Variable Notes': var_notes}]

        return pd.DataFrame(d, columns=col_names, index=range(len(d)))

def convert_pdf_to_images(pdf_fp):
    """
    takes in a string representing the path to a PDF
    converts each page of pdf to png image in created directories
    """
    pdf_image_dir = 'pdf_to_image'
    filename = os.path.basename(pdf_fp).replace('.pdf', '')
    output_dir = os.path.join(pdf_image_dir, filename)
    make_dir(output_dir)

    document = pymupdf.open(pdf_fp)
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        pix = page.get_pixmap(dpi=300)
        out_fp = os.path.join(output_dir, f'page_{str(page_num).zfill(4)}.png')
        pix.save(out_fp)

    return output_dir

def read_pdf_text_ocr(pdf_fp, regen_text=False):
    """
    reads png images made by convert_pdf_to_images
    uses pytesseract to invoke tesseract ocr
    concatenates text from images into String
    writes to new txt file
    """
    pdf_image_dir = 'pdf_to_image'
    filename = os.path.basename(pdf_fp).replace('.pdf', '')
    images_dir = os.path.join(pdf_image_dir, filename)
    if not os.path.isdir(images_dir):
        convert_pdf_to_images(pdf_fp)

    txt_output = 'PDF_txts'
    make_dir(txt_output)
    filename = os.path.join(txt_output, f'{filename}.txt')
    if os.path.isfile(filename) and not regen_text:
        with open(filename, 'r', encoding='utf-8') as f:
            text =  f.read()
            return text

    page_images = os.listdir(images_dir)

    text = ''
    i=1
    for page in page_images:
        _, ext = os.path.splitext(page)
        if ext.lower() != '.png':
            continue

        print(f'reading page {i}...')
        i+=1

        image = cv2.imread(os.path.join(images_dir, page))

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        _, binary_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        enhanced_image = cv2.convertScaleAbs(binary_image, alpha=1.5, beta=0)

        page_text = pytesseract.image_to_string(enhanced_image)
        text += page_text
        text += '!!!PAGEBREAK!!!\n'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(text)

    return text

def remove_page_numbers(text):
    """
    uses regex to remove page numbers from inputted String
    """
    pattern = r'Page \d+ of \d+'
    return re.sub(pattern, '', text)

def get_descriptions(text):
    """
    pulls text from after appearances of "Description:" in text
        reads line by line until text of line indicates description has concluded 
    (assuming for now that description is not split over a pagebreak)
    """
    desc_texts = text.split('Description:')[1:]

    descriptions = []
    for desc_text in desc_texts:
        desc_text = remove_page_numbers(desc_text)
        lines = desc_text.split('\n')
        desc = ''
        for line in lines:
            line = line.strip()

            if ('Description' in line or 'Code or Value' in line or
            (re.search('[A-Z]', line) is not None and line.upper() == line and ' ' not in line)):
                break

            desc_line = re.sub(r' {2,}', ' ', line.strip())
            desc += f'{desc_line} '
        if desc.strip() == '' or desc.lower().strip() == 'units:':
            descriptions.append('!MANUALLY INPUT DESCRIPTION!')
        else:
            descriptions.append(desc.strip())
    return descriptions

def write_variables_to_xlsx(fp, variables):
    """
    takes in str representing fp and list of variables objects
    concatonates variable DataFrames into one DataFrame
    writes df to xlsx in created directories
    """
    output_dir = os.path.join('output', date_ext())
    make_dir(output_dir)
    fp_out = f"Data_Dictionary_{os.path.split(fp)[-1].replace('.pdf', '')}.xlsx"
    fp_out = os.path.join(output_dir, fp_out)
    with pd.ExcelWriter(fp_out) as writer:
        writer.book.formats[0].set_text_wrap()
        df = pd.DataFrame(columns=['Variable', 'Description', 'N', 'Miss',
                                   'Minimum', 'Maximum', 'Units', 'Coded Values', 'Variable Notes'])
        for var in variables:
            df = pd.concat([df, var.to_dataframe()])

        df.to_excel(writer, sheet_name='Data Dictionary', index=False)

def write_pdf_vars_to_xlsx(pdf_fp, regen_text=False):
    """
    takes str representing reletive path to coding manual PDF
    writes xlsx data dictionary using above methods
    """
    print(f'Reading PDF... ({':'.join(date_ext(full=True).split('_')[1:])})')
    pdf_text = read_pdf_text_ocr(pdf_fp, regen_text=regen_text)

    print(f'Collecting descriptions... ({':'.join(date_ext(full=True).split('_')[1:])})')
    descriptions = get_descriptions(pdf_text)

    print(f'Collecting names and tables... ({':'.join(date_ext(full=True).split('_')[1:])})')
    name_to_table = map_var_to_table(pdf_fp)
    names = list(name_to_table.keys())
    names.sort(key=lambda name: name_to_table[name]['location'])

    print(f'Creating variable objects... ({':'.join(date_ext(full=True).split('_')[1:])})')
    total = get_num_observations(pdf_fp)
    variable_dict = defaultdict(dict)
    var_objs = []
    for name in names:
        variable_dict[name]['name'] = name

        if len(descriptions) == 0:
            descriptions.append('ran out of descriptions') # precaution

        variable_dict[name]['description'] = descriptions[0]
        descriptions = descriptions[1:]

        variable_dict[name]['values'] = name_to_table[name]['table']
        var_objs.append(Variable(name, variable_dict[name]['description'],
                                    variable_dict[name]['values'], total))

    print(f'Writing to xlsx... ({':'.join(date_ext(full=True).split('_')[1:])})')
    write_variables_to_xlsx(pdf_fp, var_objs)

    print(f'Done! ({':'.join(date_ext(full=True).split('_')[1:])})')

def main():
    """
    basic text-based UI for processing PDFs one at a time
    """
    fp = input('Please input relative path of PDF:\n')
    write_pdf_vars_to_xlsx(fp)

if __name__ == '__main__':
    main()
