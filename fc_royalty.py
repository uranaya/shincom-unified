"""FCコンピューター占い: 請求先マスタ・月次売上・ロイヤリティ請求PDF。"""
import io
import os
import re
import secrets
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import psycopg2
import psycopg2.extras
from flask import Blueprint, abort, redirect, render_template, request, send_file, session, url_for
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

fc_bp = Blueprint('fc', __name__)


def db():
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL が設定されていません')
    return psycopg2.connect(url)


def init_fc_tables():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS fc_customers (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, contact_name TEXT NOT NULL DEFAULT '',
                postal_code TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
                royalty_rate NUMERIC(6,4) NOT NULL DEFAULT 0.20 CHECK (royalty_rate >= 0 AND royalty_rate <= 1),
                note TEXT NOT NULL DEFAULT '', active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS fc_royalty_invoices (
                id SERIAL PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES fc_customers(id),
                sales_month VARCHAR(7) NOT NULL, sales_amount BIGINT NOT NULL CHECK (sales_amount >= 0),
                royalty_rate NUMERIC(6,4) NOT NULL, fee_amount BIGINT NOT NULL,
                tax_rate NUMERIC(5,3) NOT NULL DEFAULT 0.10, tax_amount BIGINT NOT NULL,
                total_amount BIGINT NOT NULL, issued_on DATE NOT NULL, due_on DATE,
                invoice_number TEXT NOT NULL UNIQUE, customer_name TEXT NOT NULL,
                contact_name TEXT NOT NULL DEFAULT '', postal_code TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '', memo TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(customer_id, sales_month)
            )''')


def csrf():
    if '_fc_csrf' not in session:
        session['_fc_csrf'] = secrets.token_urlsafe(32)
    return session['_fc_csrf']


def guard(post=False):
    if not session.get('admin'):
        abort(403)
    if post and (not request.form.get('_csrf') or not secrets.compare_digest(request.form['_csrf'], csrf())):
        abort(400, 'フォームの認証が無効です。ページを再表示してください。')


def month_valid(value):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value):
        abort(400, '売上月が不正です')
    return value


def yen(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def fetch_customers():
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM fc_customers ORDER BY active DESC, name, id')
            return cur.fetchall()


@fc_bp.route('/admin/fc', methods=['GET'])
def index():
    guard()
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('''SELECT i.*, c.email FROM fc_royalty_invoices i
                JOIN fc_customers c ON c.id = i.customer_id
                ORDER BY i.sales_month DESC, i.id DESC LIMIT 200''')
            invoices = cur.fetchall()
    return render_template('fc_invoices.html', customers=fetch_customers(), invoices=invoices,
                           token=csrf(), current_month=date.today().strftime('%Y-%m'))


@fc_bp.route('/admin/fc/customers', methods=['GET', 'POST'])
def customers():
    guard(request.method == 'POST')
    target = None
    customer_id = request.args.get('id', type=int)
    if request.method == 'POST':
        customer_id = request.form.get('id', type=int)
        name = request.form.get('name', '').strip()
        if not name:
            abort(400, '請求先名は必須です')
        rate = Decimal('0.20')  # FC売上の20%固定
        values = (name, request.form.get('contact_name','').strip(), request.form.get('postal_code','').strip(),
                  request.form.get('address','').strip(), request.form.get('email','').strip(),
                  request.form.get('phone','').strip(), rate, request.form.get('note','').strip(),
                  request.form.get('active') == 'on')
        with db() as conn:
            with conn.cursor() as cur:
                if customer_id:
                    cur.execute('''UPDATE fc_customers SET name=%s,contact_name=%s,postal_code=%s,
                      address=%s,email=%s,phone=%s,royalty_rate=%s,note=%s,active=%s WHERE id=%s''',
                                values + (customer_id,))
                    if cur.rowcount == 0:
                        abort(404)
                else:
                    cur.execute('''INSERT INTO fc_customers
                      (name,contact_name,postal_code,address,email,phone,royalty_rate,note,active)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', values)
        return redirect(url_for('fc.index'))
    if customer_id:
        with db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute('SELECT * FROM fc_customers WHERE id=%s', (customer_id,))
                target = cur.fetchone()
        if not target:
            abort(404)
    return render_template('fc_customer_form.html', customer=target, token=csrf())


@fc_bp.route('/admin/fc/invoices', methods=['POST'])
def create_invoice():
    guard(True)
    cid = request.form.get('customer_id', type=int)
    month = month_valid(request.form.get('sales_month',''))
    try:
        sales = int(request.form.get('sales_amount', ''))
    except ValueError:
        abort(400, '売上金額は整数で入力してください')
    if sales < 0 or sales > 10**12:
        abort(400, '売上金額が不正です')
    try:
        issued = date.fromisoformat(request.form.get('issued_on', ''))
        due_str = request.form.get('due_on','')
        due = date.fromisoformat(due_str) if due_str else None
    except ValueError:
        abort(400, '請求日または支払期限が不正です')
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM fc_customers WHERE id=%s AND active=TRUE', (cid,))
            cust = cur.fetchone()
            if not cust:
                abort(404, '有効な請求先がありません')
            rate = Decimal('0.20')
            fee = yen(Decimal(sales) * rate)
            tax_rate = Decimal('0.10')
            tax = yen(Decimal(fee) * tax_rate)
            # 同一請求先・同一月は一件だけ。再発行は既存PDFを使用する。
            cur.execute('''INSERT INTO fc_royalty_invoices
               (customer_id,sales_month,sales_amount,royalty_rate,fee_amount,tax_rate,tax_amount,
                total_amount,issued_on,due_on,invoice_number,customer_name,contact_name,postal_code,address,memo)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (customer_id,sales_month) DO NOTHING RETURNING id''',
               (cid,month,sales,rate,fee,tax_rate,tax,fee+tax,issued,due,
                'FC-'+month.replace('-','')+'-'+str(cid).zfill(4),cust['name'],cust['contact_name'],
                cust['postal_code'],cust['address'],request.form.get('memo','').strip()))
            row = cur.fetchone()
            if not row:
                abort(409, 'この請求先・売上月の請求書は登録済みです。請求一覧からPDFを再取得してください。')
            invoice_id = row['id']
    return redirect(url_for('fc.pdf_invoice', invoice_id=invoice_id))


def pdf_font():
    name = 'FC-IPAexGothic'
    if name not in pdfmetrics.getRegisteredFontNames():
        path = os.path.join(os.path.dirname(__file__), 'static', 'ipaexg.ttf')
        pdfmetrics.registerFont(TTFont(name, path))
    return name


@fc_bp.route('/admin/fc/invoices/<int:invoice_id>/pdf')
def pdf_invoice(invoice_id):
    guard()
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM fc_royalty_invoices WHERE id=%s', (invoice_id,))
            inv = cur.fetchone()
    if not inv:
        abort(404)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle('FCロイヤリティ請求書 '+inv['invoice_number'])
    font = pdf_font()
    W,H = A4
    def line(text, x, y, size=10):
        c.setFont(font,size)
        c.drawString(x*mm,H-y*mm,str(text))
    def right(text,x,y,size=10):
        c.setFont(font,size)
        c.drawRightString(x*mm,H-y*mm,str(text))
    line('請 求 書',90,29,20)
    line('請求番号：'+inv['invoice_number'],130,43,9)
    line('発行日：'+str(inv['issued_on']),130,49,9)
    line(inv['customer_name']+' 御中',20,64,14)
    if inv['postal_code']:
        line('〒'+inv['postal_code'],20,72,9)
    # 長すぎる住所がPDF外にはみ出さないように分割
    for i, part in enumerate([inv['address'][j:j+32] for j in range(0,len(inv['address']),32)][:3]):
        line(part,20,79+i*5,9)
    line('合同会社むすび家プランニング',120,68,11)
    line('山口県山陽小野田市大字小野田730番地2',120,75,8)
    line('TEL: 090-7506-2065',120,81,8)
    line('Email: musubiya.planning@gmail.com',120,87,8)
    line('下記のとおりご請求申し上げます。',20,108,10)
    line('ご請求金額（税込）',20,120,11)
    right(f"¥{inv['total_amount']:,}",187,120,18)
    c.line(20*mm,(H-125*mm),190*mm,(H-125*mm))
    line('対象売上月',23,140,10)
    line('シンコンピューター占い FC使用料',65,140,10)
    right('金額',187,140,10)
    c.line(20*mm,H-144*mm,190*mm,H-144*mm)
    line(inv['sales_month'],23,153,10)
    line(f"売上 ¥{inv['sales_amount']:,} × 20%",65,153,10)
    right(f"¥{inv['fee_amount']:,}",187,153,10)
    c.line(20*mm,H-159*mm,190*mm,H-159*mm)
    line('使用料（税抜）',119,170,10)
    right(f"¥{inv['fee_amount']:,}",187,170,10)
    line('消費税（10%）',119,178,10)
    right(f"¥{inv['tax_amount']:,}",187,178,10)
    line('合計（税込）',119,188,11)
    right(f"¥{inv['total_amount']:,}",187,188,12)
    if inv['due_on']:
        line('お支払期限：'+str(inv['due_on']),20,207,10)
    if inv['memo']:
        line('備考',20,219,10)
        for i, part in enumerate([inv['memo'][j:j+50] for j in range(0,len(inv['memo']),50)][:7]):
            line(part,20,227+i*6,9)
    line('※振込先・適格請求書発行事業者登録番号は必要に応じて別途ご案内ください。',20,279,8)
    c.save()
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True,
                     download_name=inv['invoice_number']+'.pdf')
