import io
from decimal import Decimal
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from pathlib import Path
from core.models import CompanyDetails

HEADER_HEIGHT = 40
FOOTER_HEIGHT = 30

def _company():
    cd = CompanyDetails.get()
    if cd:
        lines = [l for l in [cd.address_line1, cd.address_line2, cd.city, cd.postcode, cd.country] if l]
        return {
            'name': cd.name,
            'lines': lines or [cd.city, cd.country] if (cd.city or cd.country) else [],
            'email': cd.email or getattr(settings, 'COMPANY_EMAIL', ''),
            'phone': cd.phone or getattr(settings, 'COMPANY_PHONE', ''),
            'vat': cd.vat_number or getattr(settings, 'COMPANY_VAT_NUMBER', ''),
            'logo_path': Path(cd.logo_path) if cd.logo_path else Path(getattr(settings, 'COMPANY_LOGO_PATH', Path(settings.BASE_DIR) / 'static' / 'logo.png')),
        }
    # Fallback to settings
    return {
        'name': getattr(settings, 'COMPANY_NAME', 'Prebuilt Computers UK'),
        'lines': getattr(settings, 'COMPANY_ADDRESS_LINES', ['123 Tech Park', 'Innovation Way', 'London, UK']),
        'email': getattr(settings, 'COMPANY_EMAIL', 'support@prebuiltcomputers.uk'),
        'phone': getattr(settings, 'COMPANY_PHONE', '+44 (0)20 0000 0000'),
        'vat': getattr(settings, 'COMPANY_VAT_NUMBER', 'GB000000000'),
        'logo_path': Path(getattr(settings, 'COMPANY_LOGO_PATH', Path(settings.BASE_DIR) / 'static' / 'logo.png')),
    }


def _draw_header(c, invoice):
    comp = _company()
    c.setFillColor(colors.black)
    y = A4[1] - 25
    # Logo if exists
    logo = comp['logo_path']
    if logo.exists():
        try:
            c.drawImage(str(logo), 30, y - 35, width=80, height=30, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFont('Helvetica-Bold', 16)
    c.drawString(120, y - 10, comp['name'])
    c.setFont('Helvetica', 9)
    for i, line in enumerate(comp['lines']):
        c.drawString(120, y - 25 - (i * 11), line)
    c.setFont('Helvetica-Bold', 20)
    c.drawRightString(A4[0] - 30, y - 10, 'INVOICE')
    c.setFont('Helvetica', 10)
    c.drawRightString(A4[0] - 30, y - 30, invoice.number)


def _draw_footer(c, page_num):
    comp = _company()
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.line(30, FOOTER_HEIGHT + 5, A4[0] - 30, FOOTER_HEIGHT + 5)
    c.setFont('Helvetica', 8)
    footer_y = FOOTER_HEIGHT - 2
    c.setFillColor(colors.grey)
    c.drawString(30, footer_y, f"VAT: {comp['vat']}  •  Email: {comp['email']}  •  Tel: {comp['phone']}")
    c.drawRightString(A4[0] - 30, footer_y, f"Page {page_num}")


def _money(val: Decimal):
    return f"£{Decimal(val).quantize(Decimal('0.01'))}" if val is not None else ''


def _draw_stamp(c, invoice):
    c.saveState()
    c.setFont('Helvetica-Bold', 50)
    if invoice.status == invoice.PAID:
        c.setFillColor(colors.green)
        text = 'PAID'
    else:
        c.setFillColor(colors.red)
        text = 'UNPAID'
    c.translate(A4[0] - 240, 260)
    c.rotate(25)
    c.setFillAlpha(0.15)
    c.drawString(0, 0, text)
    c.restoreState()


def generate_invoice_pdf(invoice):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    # Set document metadata so viewers show a proper title
    try:
        c.setTitle(f"Invoice {invoice.number}")
    except Exception:
        pass
    # Add author/subject metadata for better viewer display/searchability
    try:
        comp = _company()
        c.setAuthor(comp.get('name') or 'Prebuilt Computers UK')
    except Exception:
        try:
            c.setAuthor('Prebuilt Computers UK')
        except Exception:
            pass
    try:
        c.setSubject(f"Invoice {invoice.number}")
    except Exception:
        pass
    page_num = 1

    _draw_header(c, invoice)

    width, height = A4
    left = 30
    right = width - 30
    col2_x = left + 300  # second column start for quote details
    top_start = height - 110

    # Invoice meta / client / quote details
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left, top_start, 'Invoice Details')
    c.setFont('Helvetica', 9)
    c.drawString(left, top_start - 15, f"Date: {invoice.created_at.strftime('%Y-%m-%d')}")
    c.drawString(left, top_start - 28, f"Status: {invoice.get_status_display()}")

    c.setFont('Helvetica-Bold', 11)
    c.drawString(col2_x, top_start, 'Quote Details')
    c.setFont('Helvetica', 9)
    c.drawString(col2_x, top_start - 15, f"Reference: {invoice.quote.reference}")
    c.drawString(col2_x, top_start - 28, f"Title: {invoice.quote.title[:55]}")

    c.setFont('Helvetica-Bold', 11)
    c.drawString(left, top_start - 60, 'Bill To')
    c.setFont('Helvetica', 9)
    acceptance = getattr(invoice.quote, 'acceptance', None)
    bill_parts = []
    if acceptance:
        # Company first if present
        if getattr(acceptance, 'company', None):
            bill_parts.append(acceptance.company)
        if getattr(acceptance, 'full_name', None):
            bill_parts.append(acceptance.full_name)
        # Address lines
        for v in [getattr(acceptance, 'address_line1', None), getattr(acceptance, 'address_line2', None), getattr(acceptance, 'city', None), getattr(acceptance, 'postcode', None)]:
            if v:
                bill_parts.append(v)
        # Contact
        if getattr(acceptance, 'email', None):
            bill_parts.append(acceptance.email)
        if getattr(acceptance, 'phone', None):
            bill_parts.append(acceptance.phone)
    else:
        # Fallback to invoice stored client name/email (filter blanks)
        for v in [invoice.client_name, invoice.client_email]:
            if v:
                bill_parts.append(v)
    # Draw each non-empty line
    y_bill = top_start - 75
    for part in bill_parts:
        c.drawString(left, y_bill, part)
        y_bill -= 11
    # Adjust starting point for items based on rendered bill section

    # Items table (start below Bill To block)
    # Items table aligned full width under header
    y_items = min(y_bill - 25, top_start - 110)
    table_width = right - left
    c.setFont('Helvetica-Bold', 10)
    c.drawString(left, y_items, 'Items')
    y_items -= 12
    c.setFont('Helvetica', 8)
    headers = ['Description', 'Qty', 'Unit', 'VAT %', 'Line Total']
    # proportional widths
    proportions = [0.50, 0.07, 0.13, 0.10, 0.20]
    col_widths = [round(table_width * p) for p in proportions]
    # adjust last column to fill any rounding diff
    diff = table_width - sum(col_widths)
    col_widths[-1] += diff
    x_positions = [left]
    for w in col_widths[:-1]:
        x_positions.append(x_positions[-1] + w)
    c.setFillColor(colors.lightgrey)
    c.rect(left, y_items - 2, table_width, 14, stroke=0, fill=1)
    c.setFillColor(colors.black)
    for i, h in enumerate(headers):
        c.drawString(x_positions[i] + 2, y_items + 2, h)
    y_items -= 16
    c.setFont('Helvetica', 8)
    for item in invoice.quote.items.all():
        if y_items < 90:
            _draw_footer(c, page_num)
            c.showPage()
            page_num += 1
            _draw_header(c, invoice)
            y_items = height - 120
            c.setFont('Helvetica-Bold', 10)
            c.drawString(left, y_items, 'Items (cont.)')
            y_items -= 14
            c.setFont('Helvetica', 8)
            c.setFillColor(colors.lightgrey)
            c.rect(left, y_items - 2, table_width, 14, stroke=0, fill=1)
            c.setFillColor(colors.black)
            for i, h in enumerate(headers):
                c.drawString(x_positions[i] + 2, y_items + 2, h)
            y_items -= 16
        c.drawString(x_positions[0] + 2, y_items, item.description[:80])
        c.drawRightString(x_positions[1] + col_widths[1] - 6, y_items, str(item.quantity))
        c.drawRightString(x_positions[2] + col_widths[2] - 6, y_items, _money(item.unit_price))
        c.drawRightString(x_positions[3] + col_widths[3] - 6, y_items, f"{item.vat_rate}%")
        c.drawRightString(x_positions[4] + col_widths[4] - 6, y_items, _money(item.total))
        y_items -= 14

    # Totals block
    y_totals = y_items - 10
    c.setFont('Helvetica-Bold', 10)
    c.drawString(left, y_totals, 'Totals')
    y_totals -= 14
    label_x = left
    amount_x = left + 150
    c.setFont('Helvetica', 9)
    for label, value in [('Subtotal', invoice.subtotal), ('Delivery', invoice.delivery_price), ('VAT', invoice.vat_amount)]:
        c.drawString(label_x, y_totals, f"{label}:")
        c.drawRightString(amount_x + 70, y_totals, _money(value))
        y_totals -= 12
    c.setFont('Helvetica-Bold', 10)
    c.drawString(label_x, y_totals, 'Grand Total:')
    c.drawRightString(amount_x + 70, y_totals, _money(invoice.total))

    # Payments table
    y_pay = y_totals - 35
    c.setFont('Helvetica-Bold', 10)
    c.drawString(left, y_pay, 'Payments')
    y_pay -= 14
    payments = invoice.payments.all().order_by('created_at')
    if payments:
        c.setFont('Helvetica', 8)
        pay_table_width = right - left
        amount_right_x = left + pay_table_width - 5
        # Header row
        c.setFillColor(colors.lightgrey)
        c.rect(left, y_pay - 2, pay_table_width, 14, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.drawString(left + 2, y_pay + 2, 'Date')
        c.drawString(left + 90, y_pay + 2, 'Method')
        c.drawString(left + 180, y_pay + 2, 'Provider')
        c.drawString(left + 300, y_pay + 2, 'Reference')
        c.drawString(left + 430, y_pay + 2, 'Status')
        c.drawRightString(amount_right_x, y_pay + 2, 'Amount')
        y_pay -= 16
        c.setFont('Helvetica', 8)
        for pay in payments:
            if y_pay < 70:
                _draw_footer(c, page_num)
                c.showPage()
                page_num += 1
                _draw_header(c, invoice)
                c.setFont('Helvetica-Bold', 10)
                c.drawString(left, A4[1] - 120, 'Payments (cont.)')
                y_pay = A4[1] - 135
                # Re-draw header row on continuation
                c.setFont('Helvetica', 8)
                c.setFillColor(colors.lightgrey)
                c.rect(left, y_pay - 2, pay_table_width, 14, stroke=0, fill=1)
                c.setFillColor(colors.black)
                c.drawString(left + 2, y_pay + 2, 'Date')
                c.drawString(left + 90, y_pay + 2, 'Method')
                c.drawString(left + 180, y_pay + 2, 'Provider')
                c.drawString(left + 300, y_pay + 2, 'Reference')
                c.drawString(left + 430, y_pay + 2, 'Status')
                c.drawRightString(amount_right_x, y_pay + 2, 'Amount')
                y_pay -= 16
                c.setFont('Helvetica', 8)
            c.drawString(left + 2, y_pay, pay.created_at.strftime('%Y-%m-%d'))
            c.drawString(left + 90, y_pay, (pay.method or '')[:20])
            c.drawString(left + 180, y_pay, (pay.provider or '')[:20])
            c.drawString(left + 300, y_pay, (pay.provider_reference or '')[:28])
            c.drawString(left + 430, y_pay, pay.get_status_display())
            c.drawRightString(amount_right_x, y_pay, _money(pay.amount))
            y_pay -= 14
    else:
        c.setFont('Helvetica', 8)
        c.drawString(left, y_pay, 'No payments recorded.')

    # Paid stamp
    _draw_stamp(c, invoice)

    _draw_footer(c, page_num)

    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
