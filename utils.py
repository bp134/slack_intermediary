import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from logic import translate_tasks_to_real_names, MASTER_CSV

def export_audit_to_excel(df, filename="Audit_Report.xlsx"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Audit Data"
    ws['A1'] = "Belfield Pharmacy Internal Audit Report"
    ws['A1'].font = Font(bold=True, size=14)
    # Add data
    for r_idx, row in enumerate(df.values.tolist(), start=4):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=value)
    wb.save(filename)
    return filename