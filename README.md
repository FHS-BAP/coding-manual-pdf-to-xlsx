# coding-manual-pdf-to-xlsx
A collection of scripts and modules for processing and collecting variables from FHS coding manual PDFs and packaging the information into XLSX data dictionaries.

## cmanual_pdf_to_data_dict.py
Main script for processing current format coding manuals (see PDFs in PDFs/current_format). Defines Variable class for easy packaging to XLSX. Uses OCR to extract text from PDF for scraping descriptions.

## extract_tables_and_var_names.py
Helper module for cmanual_pdf_to_data_dict.py that uses pdfplumber to precisely extract tables and variable names.

## old_format_cmanual_pdf_to_data_dict.py
Main script for processing old format coding manuals (see PDFs in PDFs/old_format). Uses pdfplumber to pull words and their locations and regex to parse relevant information.

*Run this script to see its outputs for the PDFs in PDFs/old_format.*

## PDFs
Folder containing sample coding manual PDFs. Each can be processed by the script for its respective format.
