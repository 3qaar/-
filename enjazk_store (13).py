import os, io, csv, json, base64, urllib.parse, secrets, smtplib
import requests
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash

"""
المكتبات المطلوبة للتشغيل (يجب تثبيتها باستخدام pip):
pip install flask flask-sqlalchemy sqlalchemy requests werkzeug weasyprint flask-cors
"""

app = Flask(__name__)
app.secret_key = "enjazk_academic_pro_v19_secure_2024"

# نظام كشف الأخطاء الذاتي - يعرض الخطأ الحقيقي بدلاً من 500 Internal Server Error
@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    err_details = traceback.format_exc()
    app.logger.error(f"Server Error: {err_details}")
    # عرض الخطأ في المتصفح للمساعدة في التشخيص
    return f"""
    <div dir="rtl" style="font-family:sans-serif;padding:20px;border:5px solid red;background:#fff5f5;">
        <h1 style="color:red;">حدث خطأ في النظام (Internal Server Error)</h1>
        <p><b>السبب المحتمل:</b> نقص في المكتبات أو خطأ في قاعدة البيانات.</p>
        <hr>
        <h3>تفاصيل الخطأ للتقني:</h3>
        <pre style="background:#eee;padding:10px;overflow:auto;direction:ltr;text-align:left;">{err_details}</pre>
    </div>
    """, 500

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'enjazk_academic.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = False


def generate_invoice_pdf(order_id):
    """إنشاء إيصال شراء PDF — يحاول xhtml2pdf ثم fpdf2 ثم Pillow PNG"""
    import json, io, os
    o = Order.query.get(order_id)
    if not o:
        return None

    try:
        cart = json.loads(o.cart_items) if o.cart_items else []
    except:
        cart = []
    if not cart:
        cart = [{"name": o.product_name or "خدمة أكاديمية", "qty": 1, "price": o.product_price or 0}]

    date_str = o.order_date.strftime('%Y/%m/%d') if o.order_date else 'N/A'
    total = f"{o.cart_total or 0:.2f}"
    status = o.status or 'جديد'

    # Build rows HTML
    rows_html = ""
    for item in cart:
        name = item.get('name','')
        qty = item.get('qty',1)
        price = float(item.get('price',0))
        rows_html += f'<tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;text-align:right;font-size:13px;color:#1e293b;font-weight:600;">{name}</td><td style="padding:12px;border-bottom:1px solid #e2e8f0;text-align:center;font-size:13px;color:#475569;">{qty}</td><td style="padding:12px;border-bottom:1px solid #e2e8f0;text-align:center;font-size:13px;color:#475569;">{price:.2f} ر.س</td></tr>'

    # === METHOD 1: xhtml2pdf (pisa) — best HTML-to-PDF support ===
    try:
        from xhtml2pdf import pisa

        html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 30px; }}
  body {{ font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif; direction: rtl; margin: 0; background: #fff; color: #1e293b; }}
  .container {{ max-width: 520px; margin: 0 auto; }}
  .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border-radius: 16px; padding: 30px 20px; text-align: center; margin-bottom: 25px; }}
  .header h1 {{ color: #fff; font-size: 28px; font-weight: 800; margin: 0; }}
  .header p {{ color: rgba(255,255,255,0.9); font-size: 13px; margin-top: 6px; }}
  .title {{ text-align: center; margin-bottom: 18px; }}
  .title h2 {{ color: #1e293b; font-size: 22px; font-weight: 800; margin: 0; }}
  .info-card {{ background: #f1f5f9; border-radius: 14px; padding: 16px 22px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; border: 1px solid #e2e8f0; }}
  .info-item {{ font-size: 14px; color: #475569; font-weight: 600; }}
  .section-title {{ text-align: right; font-size: 16px; font-weight: 800; color: #1e293b; margin-bottom: 10px; }}
  .section-line {{ height: 3px; background: #f59e0b; border-radius: 2px; margin-bottom: 14px; }}
  .customer-box {{ background: #f8fafc; border-radius: 12px; padding: 16px 20px; border: 1px solid #e2e8f0; }}
  .customer-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
  .customer-label {{ font-size: 14px; color: #1e293b; font-weight: 700; }}
  .customer-value {{ font-size: 14px; color: #1e293b; font-weight: 600; }}
  .table-wrap {{ border-radius: 12px; overflow: hidden; margin-bottom: 20px; border: 1px solid #e2e8f0; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead {{ background: #f59e0b; }}
  thead th {{ color: #fff; padding: 14px; font-size: 13px; font-weight: 700; text-align: center; border: none; }}
  thead th:first-child {{ text-align: right; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  .total-box {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border-radius: 16px; padding: 22px 20px; text-align: center; margin-bottom: 20px; }}
  .total-label {{ color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600; margin-bottom: 6px; }}
  .total-value {{ color: #fff; font-size: 26px; font-weight: 800; margin: 0; }}
  .status-box {{ background: #f1f5f9; border-radius: 12px; padding: 12px 20px; text-align: center; margin-bottom: 25px; border: 1px solid #e2e8f0; }}
  .status-text {{ color: #475569; font-size: 15px; font-weight: 700; }}
  .footer-line {{ height: 3px; background: #f59e0b; border-radius: 2px; margin-bottom: 18px; }}
  .footer {{ text-align: center; padding: 0 10px; }}
  .footer-thanks {{ color: #1e293b; font-size: 16px; font-weight: 800; margin-bottom: 8px; }}
  .footer-contact {{ color: #64748b; font-size: 12px; font-weight: 500; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>متجر انجازك</h1>
      <p>للخدمات الأكاديمية والطلابية</p>
    </div>
    <div class="title"><h2>فاتورة</h2></div>
    <div class="info-card">
      <div class="info-item"><strong>رقم الفاتورة:</strong> #{o.id}</div>
      <div class="info-item"><strong>التاريخ:</strong> {date_str}</div>
    </div>
    <div class="section-title">معلومات العميل</div>
    <div class="section-line"></div>
    <div class="customer-box">
      <div class="customer-row">
        <div class="customer-label">الاسم:</div>
        <div class="customer-value">{o.customer_name or 'عميل'}</div>
      </div>
      <div class="customer-row">
        <div class="customer-label">الهاتف:</div>
        <div class="customer-value">{o.customer_phone or 'غير متوفر'}</div>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th style="text-align:right;">الخدمة</th><th>الكمية</th><th>السعر</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    <div class="total-box">
      <div class="total-label">المجموع الإجمالي</div>
      <div class="total-value">{total} ر.س</div>
    </div>
    <div class="status-box">
      <div class="status-text">حالة الطلب: <strong>{status}</strong></div>
    </div>
    <div class="footer-line"></div>
    <div class="footer">
      <div class="footer-thanks">شكراً لاختيارك متجر انجازك!</div>
      <div class="footer-contact">للدعم: academic@enjazk.com</div>
    </div>
  </div>
</body>
</html>"""

        buf = io.BytesIO()
        pisa.CreatePDF(html, dest=buf)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        app.logger.error(f"xhtml2pdf failed: {e}")

    # === METHOD 2: fpdf2 ===
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Enjazk Store - Receipt #{o.id}", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Date: {date_str}", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Customer: {o.customer_name or 'N/A'}", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Total: {total} SAR", ln=True, align='C')
        try:
            return pdf.output(dest='S')
        except:
            return pdf.output()
    except Exception as e2:
        app.logger.error(f"FPDF failed: {e2}")

    return None


def _pre_migrate():
    import sqlite3 as _sq3
    try:
        _c = _sq3.connect(db_path)
        _cur = _c.cursor()
        def _cols(t):
            try: _cur.execute("PRAGMA table_info([{}])".format(t)); return [r[1] for r in _cur.fetchall()]
            except: return []
        def _add(t, c, tp):
            if c not in _cols(t):
                try: _cur.execute("ALTER TABLE [{}] ADD COLUMN {} {}".format(t,c,tp)); _c.commit()
                except: pass
        for c,t in [('cart_items','TEXT'),('cart_total','REAL'),('admin_notes','TEXT'),
                    ('receipt_image','TEXT'),('rating','INTEGER'),
                    ('assigned_to','TEXT'),('deadline','DATETIME'),('delivery_file','TEXT'),
                    ('referral_code','TEXT'),('num_pages','INTEGER'),('academic_level','TEXT'),
                    ('cost_price','REAL'),('customer_email','TEXT DEFAULT ""')]:
            _add('order',c,t)
        for c,t in [('price_per_page','REAL'),('base_pages','INTEGER')]:
            _add('product',c,t)
        for c,t in [('old_price','REAL'),('category','TEXT'),('description','TEXT'),('is_active','INTEGER'),('stock','INTEGER')]:
            _add('product',c,t)
        for c,t in [('moving_text','TEXT'),('whatsapp','TEXT'),('instagram','TEXT'),('tiktok','TEXT'),('snapchat','TEXT'),('twitter','TEXT'),
                    ('phone','TEXT'),('email','TEXT'),('footer_text','TEXT'),('footer_text2','TEXT'),
                    ('whatsapp_number','TEXT'),('notify_whatsapp','INTEGER'),
                    ('bank_name','TEXT'),('bank_account','TEXT'),('bank_iban','TEXT'),('bank_holder','TEXT')]:
            _add('store_settings',c,t)
        try:
            _cur.execute("""CREATE TABLE IF NOT EXISTS customer (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL, email TEXT DEFAULT '', password_hash TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
            _c.commit()
        except: pass
        _add('customer','email','TEXT DEFAULT ""')
        _add('customer','reset_password_token','TEXT DEFAULT ""')
        _add('customer','reset_password_expires','DATETIME')
        try:
            _cur.execute("""CREATE TABLE IF NOT EXISTS coupon (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, discount_type TEXT DEFAULT 'percent', discount_value REAL DEFAULT 0, max_uses INTEGER DEFAULT 0, used_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
            _c.commit()
        except: pass
        _add('coupon','expires_at','DATETIME')
        _c.close()
    except: pass

_pre_migrate()

db = SQLAlchemy(app)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

ADMIN_USERNAME = "Injazk.store"
ADMIN_PASSWORD_HASH = generate_password_hash("Injazk123")

# حالات الطلب الجديدة
ORDER_STATUSES = ["جديد", "جار التجهيز", "بانتظار الدفع", "إيصال خاطئ", "يتطلب تعديل", "ملغي", "مكتمل"]

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    price = db.Column(db.Float)
    old_price = db.Column(db.Float)
    image_data = db.Column(db.Text)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), default="ابحاث")
    is_active = db.Column(db.Boolean, default=True)
    stock = db.Column(db.Integer, default=999)  # الكمية المتاحة
    price_per_page = db.Column(db.Float, default=0)
    base_pages = db.Column(db.Integer, default=0)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(20))
    customer_notes = db.Column(db.Text)
    product_name = db.Column(db.String(200))
    product_price = db.Column(db.Float)
    cart_items = db.Column(db.Text)
    cart_total = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default="جديد")
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    admin_notes = db.Column(db.Text, default="")
    assigned_to = db.Column(db.String(100), default="")
    deadline = db.Column(db.DateTime, nullable=True)
    delivery_file = db.Column(db.Text, default="")
    referral_code = db.Column(db.String(50), default="")
    num_pages = db.Column(db.Integer, default=0)
    academic_level = db.Column(db.String(50), default="")
    cost_price = db.Column(db.Float, default=0)
    receipt_image = db.Column(db.Text, default="")  # ايصال التحويل البنكي
    customer_email = db.Column(db.String(120), default="")  # بريد العميل للإيصال

class StoreSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    footer_text = db.Column(db.String(500), default="انجازك للخدمات الطلابية")
    whatsapp = db.Column(db.String(500), default="https://wa.me/966536602928")
    whatsapp_number = db.Column(db.String(20), default="966536602928")
    instagram = db.Column(db.String(500), default="https://www.instagram.com/injazk.store/")
    tiktok = db.Column(db.String(500), default="https://www.tiktok.com/@injazk.store")
    snapchat = db.Column(db.String(500), default="")
    twitter = db.Column(db.String(500), default="")
    phone = db.Column(db.String(20), default="0500000000")
    email = db.Column(db.String(100), default="academic@enjazk.com")
    moving_text = db.Column(db.String(1000), default="جودة اكاديمية استثنائية | كتابة احترافية | سرعة في الانجاز")
    footer_text2 = db.Column(db.String(500), default="")
    notify_whatsapp = db.Column(db.Boolean, default=False)
    # بيانات البنك
    bank_name = db.Column(db.String(100), default="")
    bank_account = db.Column(db.String(100), default="")
    bank_iban = db.Column(db.String(100), default="")
    bank_holder = db.Column(db.String(100), default="")

class Customer(db.Model):
    """نموذج حسابات العملاء"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), default="")
    password_hash = db.Column(db.String(256), nullable=False)
    reset_password_token = db.Column(db.String(128), default="")
    reset_password_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Coupon(db.Model):
    __tablename__ = 'coupon'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_type = db.Column(db.String(10), default="percent")
    discount_value = db.Column(db.Float, default=0)
    max_uses = db.Column(db.Integer, default=0)
    used_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class TeamMember(db.Model):
    __tablename__ = 'team_member'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=True)

class SeasonalOffer(db.Model):
    __tablename__ = 'seasonal_offer'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    discount_percent = db.Column(db.Float, default=0)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    banner_text = db.Column(db.String(500), default="")

class Testimonial(db.Model):
    __tablename__ = 'testimonial'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Review(db.Model):
    """تقييمات العملاء على الطلبات المكتملة"""
    __tablename__ = 'review'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(200), default="")
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default="")
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def maintenance_db():
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        updates = {
            'store_settings': {
                'moving_text':'TEXT','whatsapp':'TEXT','instagram':'TEXT','tiktok':'TEXT',
                'phone':'TEXT','email':'TEXT','footer_text':'TEXT','footer_text2':'TEXT',
                'whatsapp_number':'TEXT','notify_whatsapp':'BOOLEAN',
                'bank_name':'TEXT','bank_account':'TEXT','bank_iban':'TEXT','bank_holder':'TEXT'
            },
            'product': {
                'old_price':'FLOAT','category':'VARCHAR(100)','description':'TEXT',
                'is_active':'BOOLEAN','stock':'INTEGER'
            },
            'order': {'cart_items':'TEXT','cart_total':'FLOAT','admin_notes':'TEXT','receipt_image':'TEXT'},
            'customer': {'name':'TEXT','phone':'TEXT','email':'TEXT','password_hash':'TEXT','reset_password_token':'TEXT','reset_password_expires':'DATETIME','created_at':'DATETIME'}
        }
        for table, cols in updates.items():
            try:
                existing = [c['name'] for c in inspector.get_columns(table)]
                for c_name, c_type in cols.items():
                    if c_name not in existing:
                        try:
                            db.session.execute(text("ALTER TABLE {} ADD COLUMN {} {}".format(table, c_name, c_type)))
                            db.session.commit()
                        except: db.session.rollback()
            except: pass
        if not StoreSettings.query.first():
            db.session.add(StoreSettings()); db.session.commit()

# تهيئة قاعدة البيانات عند بدء التشغيل
try:
    maintenance_db()
except Exception as e:
    print(f"Database Maintenance Error: {e}")

def send_purchase_receipt_email(order, pdf_data):
    """إرسال إيصال الشراء PDF بالبريد الإلكتروني عند اكتمال الطلب"""
    mail_server = os.environ.get('MAIL_SERVER', '').strip()
    mail_port = int(os.environ.get('MAIL_PORT', '587'))
    mail_username = os.environ.get('MAIL_USERNAME', '').strip()
    mail_password = os.environ.get('MAIL_PASSWORD', '')
    mail_sender = os.environ.get('MAIL_DEFAULT_SENDER', mail_username).strip()
    use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes', 'on')

    customer_email = order.customer_email or ""
    if not customer_email:
        cust = Customer.query.filter(Customer.phone.contains(order.customer_phone[-9:] if order.customer_phone else '')).first()
        if cust: customer_email = cust.email or ""
    if not customer_email or not mail_server:
        return False

    try:
        import email.mime.multipart as _mp
        import email.mime.base as _mb
        import email.mime.text as _mt
        from email import encoders as _enc

        msg = _mp.MIMEMultipart()
        msg['Subject'] = f'إيصال شراء - طلب #{order.id} | متجر انجازك'
        msg['From'] = mail_sender
        msg['To'] = customer_email

        body = f"""مرحباً {order.customer_name or 'عميلنا الكريم'}،

تم إنجاز طلبك بنجاح! 🎉

رقم الطلب: #{order.id}
التاريخ: {order.order_date.strftime('%Y/%m/%d') if order.order_date else 'N/A'}
الإجمالي: {order.cart_total or 0:.2f} ر.س

يمكنك تحميل الملف المُسلَّم من حسابك في الموقع.
مرفق إيصال شراء رسمي بصيغة PDF.

شكراً لثقتك بمتجر انجازك 🌟
"""
        msg.attach(_mt.MIMEText(body, 'plain', 'utf-8'))

        # إرفاق PDF
        part = _mb.MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_data)
        _enc.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="receipt_{order.id}.pdf"')
        msg.attach(part)

        with smtplib.SMTP(mail_server, mail_port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if mail_username and mail_password:
                smtp.login(mail_username, mail_password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        app.logger.error(f"Receipt email error: {e}")
        return False



def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def customer_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('customer_id'):
            return jsonify({"status":"error","message":"يجب تسجيل الدخول أولاً"}), 401
        return f(*args, **kwargs)
    return decorated

def send_password_reset_email(customer, reset_link):
    mail_server = os.environ.get('MAIL_SERVER', '').strip()
    mail_port = int(os.environ.get('MAIL_PORT', '587'))
    mail_username = os.environ.get('MAIL_USERNAME', '').strip()
    mail_password = os.environ.get('MAIL_PASSWORD', '')
    mail_sender = os.environ.get('MAIL_DEFAULT_SENDER', mail_username).strip()
    use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes', 'on')
    if not mail_server or not mail_sender:
        raise RuntimeError('SMTP settings are missing')

    msg = EmailMessage()
    msg['Subject'] = 'إعادة ضبط كلمة المرور - إنجازك'
    msg['From'] = mail_sender
    msg['To'] = customer.email
    msg.set_content(
        'مرحبا {name},\n\n'
        'طلبت إعادة ضبط كلمة المرور لحسابك في متجر إنجازك.\n'
        'اضغط الرابط التالي لتعيين كلمة مرور جديدة خلال ساعة واحدة:\n\n'
        '{link}\n\n'
        'إذا لم تطلب ذلك، تجاهل هذه الرسالة.\n'.format(name=customer.name or 'عميلنا', link=reset_link)
    )

    with smtplib.SMTP(mail_server, mail_port, timeout=20) as smtp:
        if use_tls:
            smtp.starttls()
        if mail_username and mail_password:
            smtp.login(mail_username, mail_password)
        smtp.send_message(msg)

def send_status_update_email(order, new_status):
    """إرسال إيميل للعميل عند تغيير حالة الطلب"""
    mail_server = os.environ.get('MAIL_SERVER', '').strip()
    mail_username = os.environ.get('MAIL_USERNAME', '').strip()
    mail_password = os.environ.get('MAIL_PASSWORD', '')
    mail_port = int(os.environ.get('MAIL_PORT', '587'))
    mail_sender = os.environ.get('MAIL_DEFAULT_SENDER', mail_username).strip()
    use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes', 'on')

    customer_email = order.customer_email or ""
    if not customer_email:
        cust = Customer.query.filter(Customer.phone.contains(order.customer_phone[-9:] if order.customer_phone else '')).first()
        if cust: customer_email = cust.email or ""
    if not customer_email or not mail_server:
        return False

    status_msgs = {
        "جديد": ("تم استلام طلبك", "تم استلام طلبك بنجاح وسنبدأ بتجهيزه قريباً."),
        "جار التجهيز": ("طلبك قيد التنفيذ", "طلبك رقم #{} قيد التنفيذ الآن، سنُعلمك عند الانتهاء."),
        "بانتظار الدفع": ("يرجى إتمام الدفع", "طلبك جاهز، يرجى إتمام التحويل البنكي ورفع الإيصال من الموقع."),
        "إيصال خاطئ": ("الإيصال المرفوع غير صحيح", "الإيصال الذي رفعته غير واضح أو خاطئ. يرجى رفع إيصال صحيح من صفحة طلباتك."),
        "يتطلب تعديل": ("طلبك يتطلب تعديلات", "طلبك يتطلب بعض التعديلات. تواصل معنا عبر الواتساب."),
        "مكتمل": ("تم إنجاز طلبك! 🎉", "يسعدنا إخبارك أن طلبك اكتمل بنجاح. يمكنك تحميل ملفك من حسابك."),
        "ملغي": ("تم إلغاء الطلب", "تم إلغاء طلبك. تواصل معنا إن كان هناك أي استفسار."),
    }
    subject_suffix, body_detail = status_msgs.get(new_status, ("تحديث على طلبك", "تم تحديث حالة طلبك."))
    tracking_link = "{}order/{}".format(os.environ.get('SITE_URL', ''), order.id)

    try:
        import email.mime.multipart as _mp
        import email.mime.text as _mt
        msg = _mp.MIMEMultipart()
        msg['Subject'] = f'{subject_suffix} - طلب #{order.id} | انجازك'
        msg['From'] = mail_sender
        msg['To'] = customer_email
        body = f"""مرحباً {order.customer_name or 'عميلنا الكريم'}،

{body_detail.format(order.id)}

رقم الطلب: #{order.id}
الحالة الحالية: {new_status}

تتبع طلبك مباشرة: {tracking_link}

شكراً لثقتك بمتجر انجازك 🌟
"""
        msg.attach(_mt.MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP(mail_server, mail_port, timeout=15) as smtp:
            if use_tls: smtp.starttls()
            if mail_username and mail_password: smtp.login(mail_username, mail_password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        app.logger.warning(f"Status email failed: {e}")
        return False

# =================== ROUTES ===================

# ---- مصادقة العميل ----
@app.route('/api/customer/register', methods=['POST'])
def customer_register():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name','').strip()
    phone = data.get('phone','').strip()
    email = data.get('email','').strip().lower()
    password = data.get('password','').strip()
    if not name or not phone or not email or not password:
        return jsonify({"status":"error","message":"جميع الحقول مطلوبة"}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({"status":"error","message":"البريد الإلكتروني غير صحيح"}), 400
    if len(password) < 6:
        return jsonify({"status":"error","message":"كلمة المرور يجب ان تكون 6 احرف على الاقل"}), 400
    phone_clean = ''.join(filter(str.isdigit, phone))
    existing = Customer.query.filter_by(phone=phone_clean).first()
    if existing:
        return jsonify({"status":"error","message":"هذا الرقم مسجل مسبقاً، قم بتسجيل الدخول"}), 400
    existing_email = Customer.query.filter(db.func.lower(Customer.email) == email).first()
    if existing_email:
        return jsonify({"status":"error","message":"هذا البريد الإلكتروني مسجل مسبقا"}), 400
    c = Customer(name=name, phone=phone_clean, email=email)
    c.set_password(password)
    db.session.add(c); db.session.commit()
    session['customer_id'] = c.id
    session['customer_name'] = c.name
    session['customer_phone'] = c.phone
    return jsonify({"status":"success","name":c.name,"phone":c.phone,"email":c.email or ""})

@app.route('/api/customer/login', methods=['POST'])
def customer_login():
    data = request.get_json(force=True, silent=True) or {}
    phone = ''.join(filter(str.isdigit, data.get('phone','').strip()))
    password = data.get('password','').strip()
    if not phone or not password:
        return jsonify({"status":"error","message":"ادخل رقم الجوال وكلمة المرور"}), 400
    c = Customer.query.filter_by(phone=phone).first()
    if not c or not c.check_password(password):
        return jsonify({"status":"error","message":"رقم الجوال او كلمة المرور غير صحيحة"}), 401
    session['customer_id'] = c.id
    session['customer_name'] = c.name
    session['customer_phone'] = c.phone
    return jsonify({"status":"success","name":c.name,"phone":c.phone,"email":c.email or ""})

@app.route('/api/customer/forgot-password', methods=['POST'])
def customer_forgot_password():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get('email','').strip().lower()
    if not email:
        return jsonify({"status":"error","message":"أدخل البريد الإلكتروني"}), 400

    c = Customer.query.filter(db.func.lower(Customer.email) == email).first()
    if c:
        c.reset_password_token = secrets.token_urlsafe(32)
        c.reset_password_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()
        reset_link = url_for('reset_password_page', token=c.reset_password_token, _external=True)
        try:
            send_password_reset_email(c, reset_link)
        except Exception as exc:
            app.logger.exception("Password reset email failed: %s", exc)
            c.reset_password_token = ""
            c.reset_password_expires = None
            db.session.commit()
            return jsonify({"status":"error","message":"تعذر إرسال البريد. تأكد من إعدادات SMTP في الخادم"}), 500

    return jsonify({"status":"success","message":"إذا كان البريد مسجلا، تم إرسال رابط إعادة التعيين"})

@app.route('/reset-password/<token>')
def reset_password_page(token):
    c = Customer.query.filter_by(reset_password_token=token).first()
    valid = bool(c and c.reset_password_expires and c.reset_password_expires > datetime.now(timezone.utc))
    return render_template_string("""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>إعادة ضبط كلمة المرور</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{font-family:'Tajawal','Cairo',sans-serif}</style>
</head>
<body class="min-h-screen bg-slate-950 flex items-center justify-center p-4">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl">
    <div class="text-center mb-6">
      <div class="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-key text-amber-600 text-xl"></i></div>
      <h1 class="text-xl font-black text-slate-900">إعادة ضبط كلمة المرور</h1>
      <p class="text-slate-500 text-xs mt-1">{{ 'اكتب كلمة المرور الجديدة' if valid else 'الرابط غير صالح أو انتهت صلاحيته' }}</p>
    </div>
    {% if valid %}
    <div class="space-y-3">
      <input id="newPassword" type="password" placeholder="كلمة مرور جديدة" class="w-full px-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm">
      <button onclick="resetPassword()" id="resetBtn" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-4 rounded-2xl font-black text-sm transition-all flex items-center justify-center gap-2"><i class="fas fa-save"></i> حفظ كلمة المرور</button>
      <p id="resetMsg" class="text-xs text-center hidden"></p>
    </div>
    {% else %}
    <a href="/" class="block text-center w-full bg-slate-900 text-white py-4 rounded-2xl font-black text-sm">العودة للمتجر</a>
    {% endif %}
  </div>
<script>
async function resetPassword(){
  var pwd=document.getElementById('newPassword').value.trim(),btn=document.getElementById('resetBtn'),msg=document.getElementById('resetMsg');
  msg.className='text-xs text-center hidden';
  if(pwd.length<6){msg.innerText='كلمة المرور يجب أن تكون 6 أحرف على الأقل';msg.className='text-red-500 text-xs text-center';return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  try{
    var r=await fetch('/api/customer/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:'{{ token }}',password:pwd})});
    var d=await r.json();
    msg.innerText=d.message||'';
    msg.className=(r.ok?'text-green-600':'text-red-500')+' text-xs text-center';
    if(r.ok){setTimeout(function(){window.location='/?login=1';},1200);}
  }catch(e){msg.innerText='تعذر الاتصال';msg.className='text-red-500 text-xs text-center';}
  btn.disabled=false;btn.innerHTML='<i class="fas fa-save"></i> حفظ كلمة المرور';
}
</script>
</body></html>""", token=token, valid=valid)

@app.route('/api/customer/reset-password', methods=['POST'])
def customer_reset_password():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get('token','').strip()
    password = data.get('password','').strip()
    if not token or len(password) < 6:
        return jsonify({"status":"error","message":"الرابط غير صالح أو كلمة المرور قصيرة"}), 400
    c = Customer.query.filter_by(reset_password_token=token).first()
    if not c or not c.reset_password_expires or c.reset_password_expires <= datetime.now(timezone.utc):
        return jsonify({"status":"error","message":"الرابط غير صالح أو انتهت صلاحيته"}), 400
    c.set_password(password)
    c.reset_password_token = ""
    c.reset_password_expires = None
    db.session.commit()
    return jsonify({"status":"success","message":"تم تحديث كلمة المرور بنجاح"})

@app.route('/api/customer/logout', methods=['POST'])
def customer_logout():
    session.pop('customer_id', None)
    session.pop('customer_name', None)
    session.pop('customer_phone', None)
    return jsonify({"status":"success"})

@app.route('/api/customer/me', methods=['GET'])
def customer_me():
    if session.get('customer_id'):
        c = Customer.query.get(session.get('customer_id'))
        if c:
            session['customer_name'] = c.name
            session['customer_phone'] = c.phone
            return jsonify({"status":"logged_in","name":c.name,"phone":c.phone,"email":c.email or ""})
        session.pop('customer_id', None)
        session.pop('customer_name', None)
        session.pop('customer_phone', None)
    return jsonify({"status":"guest"})

@app.route('/api/customer/profile', methods=['PUT'])
def customer_update_profile():
    if not session.get('customer_id'):
        return jsonify({"status":"error","message":"سجل دخولك أولا"}), 401
    c = Customer.query.get(session.get('customer_id'))
    if not c:
        return jsonify({"status":"error","message":"الحساب غير موجود"}), 404
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name','').strip()
    email = data.get('email','').strip().lower()
    if not name:
        return jsonify({"status":"error","message":"الاسم مطلوب"}), 400
    if not email:
        return jsonify({"status":"error","message":"البريد الإلكتروني مطلوب لاستعادة كلمة المرور"}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({"status":"error","message":"البريد الإلكتروني غير صحيح"}), 400
    existing_email = Customer.query.filter(db.func.lower(Customer.email) == email, Customer.id != c.id).first()
    if existing_email:
        return jsonify({"status":"error","message":"هذا البريد الإلكتروني مستخدم في حساب آخر"}), 400
    c.name = name
    c.email = email
    db.session.commit()
    session['customer_name'] = c.name
    session['customer_phone'] = c.phone
    return jsonify({"status":"success","message":"تم حفظ الملف الشخصي","name":c.name,"phone":c.phone,"email":c.email or ""})


@app.route('/favicon.ico')
def favicon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#000"/><circle cx="50" cy="50" r="40" fill="#d4af37"/><text x="50" y="67" text-anchor="middle" font-size="45" fill="#000" font-family="Arial Black" font-weight="bold">إ</text></svg>'''
    return svg, 200, {'Content-Type': 'image/svg+xml'}

@app.route('/')
def index():
    # تأمين جلب البيانات لمنع الخطأ 500 عند الرندر
    try:
        products = Product.query.filter_by(is_active=True).all() or []
        settings = StoreSettings.query.first() or StoreSettings()
        categories = list(set(p.category for p in products if p.category)) if products else []
        return render_template_string(STORE_HTML, products=products, settings=settings, categories=categories)
    except Exception as e:
        # إذا فشل الرندر، سيعرض معالج الأخطاء العام التفاصيل
        raise e

@app.route('/api/order', methods=['POST','OPTIONS'])
@customer_login_required
def place_order():
    if request.method == 'OPTIONS':
        return jsonify({"status":"ok"}), 200
    try:
        data = request.get_json(force=True, silent=True) or {} if request.is_json else request.form.to_dict()
        if not data.get('name') or not data.get('phone'):
            return jsonify({"status":"error","message":"الاسم ورقم الجوال مطلوبان"}), 400
        if not str(data.get('notes','')).strip():
            return jsonify({"status":"error","message":"يرجى كتابة تفاصيل طلبك - هذا الحقل مطلوب"}), 400
        cart = data.get('cart',[])
        if isinstance(cart, str):
            try: cart = json.loads(cart)
            except: cart = []
        cart_total = sum(float(i.get('price',0))*int(i.get('qty',1)) for i in cart)
        # تقدير وقت التسليم بناءً على عدد الخدمات والسعر
        def estimate_days(cart, total):
            if total >= 300 or len(cart) >= 3: return "5-7 أيام"
            elif total >= 100: return "3-5 أيام"
            else: return "24-48 ساعة"
        est_days = estimate_days(cart, cart_total)
        # جلب إيميل العميل من الجلسة
        customer_email = ""
        if data.get('email'):
            customer_email = data.get('email','').strip()
        elif session.get('customer_id'):
            from sqlalchemy.orm import load_only
            cust = Customer.query.get(session['customer_id'])
            if cust: customer_email = cust.email or ""
        # التحقق من كود الخصم وتطبيقه
        coupon_code = data.get('coupon','').strip().upper()
        coupon_discount = 0.0
        if coupon_code:
            coupon = Coupon.query.filter_by(code=coupon_code, is_active=True).first()
            if coupon:
                if coupon.max_uses > 0 and coupon.used_count >= coupon.max_uses:
                    pass  # expired, ignore
                elif coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
                    pass  # expired, ignore
                else:
                    if coupon.discount_type == "percent":
                        coupon_discount = round(cart_total * (coupon.discount_value / 100), 2)
                    else:
                        coupon_discount = min(coupon.discount_value, cart_total)
                    cart_total = round(max(0, cart_total - coupon_discount), 2)
                    coupon.used_count = (coupon.used_count or 0) + 1
                    db.session.commit()
        # التحقق من كود الإحالة وتطبيق الخصم
        referral_code = data.get('referral_code','').strip()
        referral_discount = 0.0
        if referral_code and referral_code.startswith('REF'):
            import hashlib
            # التحقق من صحة الكود
            existing_orders_with_code = Order.query.filter_by(referral_code=referral_code).count()
            if existing_orders_with_code > 0:
                # كود مستخدم من قبل - خصم 10% للعميل الجديد
                referral_discount = round(cart_total * 0.10, 2)
                cart_total = round(cart_total - referral_discount, 2)

        new_o = Order(
            customer_name=data.get('name'), customer_phone=data.get('phone'),
            product_name=cart[0]['name'] if cart else data.get('product_name',''),
            product_price=float(cart[0]['price']) if cart else 0.0,
            cart_items=json.dumps(cart, ensure_ascii=False),
            cart_total=cart_total, customer_notes=data.get('notes',''), status="جديد",
            customer_email=customer_email, referral_code=referral_code
        )
        db.session.add(new_o); db.session.commit()
        settings = StoreSettings.query.first()
        wa_link = None
        if settings and settings.whatsapp_number:
            items_txt = "\n".join(["- {} x{} = {} ر.س".format(i['name'],i.get('qty',1),float(i['price'])*int(i.get('qty',1))) for i in cart])
            msg = "طلب جديد #{}\nالاسم: {}\nالجوال: {}\n\nالمنتجات:\n{}\n\nالاجمالي: {} ر.س\nالملاحظات: {}".format(
                new_o.id, data.get('name'), data.get('phone'), items_txt, cart_total, data.get('notes',''))
            wa_link = "https://wa.me/{}?text={}".format(settings.whatsapp_number, urllib.parse.quote(msg))
        phone_clean = ''.join(filter(str.isdigit, data.get('phone','')))
        if phone_clean.startswith('0'): phone_clean = '966' + phone_clean[1:]
        elif not phone_clean.startswith('966'): phone_clean = '966' + phone_clean
        customer_wa_link = None
        if phone_clean:
            items_c = "\n".join(["- {} x{}".format(i['name'],i.get('qty',1)) for i in cart])
            confirm = "تم استلام طلبك!\n\nمرحبا {}\nرقم طلبك: #{}\n\nالخدمات:\n{}\n\nالاجمالي: {} ر.س\n\nسنتواصل معك قريبا.\nشكرا لثقتك بانجازك".format(
                data.get('name'), new_o.id, items_c, cart_total)
            customer_wa_link = "https://wa.me/{}?text={}".format(phone_clean, urllib.parse.quote(confirm))
        # بيانات البنك للعرض بعد الطلب
        bank_info = {}
        if settings and settings.bank_name:
            bank_info = {
                "bank_name": settings.bank_name or "",
                "bank_holder": settings.bank_holder or "",
                "bank_account": settings.bank_account or "",
                "bank_iban": settings.bank_iban or ""
            }
        return jsonify({"status":"success","wa_notify_link":wa_link,"customer_wa_link":customer_wa_link,"order_id":new_o.id,"estimated_days":est_days,"bank_info":bank_info})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error","message":"خطا: "+str(e)}), 500

@app.route('/api/my_orders', methods=['POST','GET'])
def my_orders():
    """API لعرض طلبات العميل - يدعم الجلسة والرقم المباشر"""
    # اذا كان مسجل دخول استخدم رقمه من الجلسة
    phone_clean = None
    if session.get('customer_phone'):
        phone_clean = ''.join(filter(str.isdigit, session['customer_phone']))
    else:
        data = request.get_json(force=True, silent=True) or {}
        phone = data.get('phone','').strip()
        if phone:
            phone_clean = ''.join(filter(str.isdigit, phone))
    if not phone_clean:
        return jsonify({"status":"error","message":"ادخل رقم الجوال"}), 400
    orders = Order.query.filter(Order.customer_phone.contains(phone_clean[-9:])).order_by(Order.order_date.desc()).limit(20).all()
    result = []
    for o in orders:
        try: cart = json.loads(o.cart_items) if o.cart_items else []
        except: cart = []
        result.append({
            "id": o.id,
            "date": o.order_date.strftime('%Y/%m/%d %H:%M'),
            "status": o.status,
            "total": o.cart_total or 0,
            "has_receipt": bool(o.receipt_image),
            "receipt_rejected": (o.status == "بانتظار الدفع" and not o.receipt_image),
            "items": [{"name":i.get('name',''),"qty":i.get('qty',1)} for i in cart] or [{"name":o.product_name,"qty":1}]
        })
    return jsonify({"status":"success","orders":result,"phone":phone_clean})

@app.route('/api/upload_receipt/<int:order_id>', methods=['POST'])
@customer_login_required
def upload_receipt(order_id):
    """رفع ايصال التحويل البنكي"""
    try:
        o = Order.query.get(order_id)
        if not o:
            return jsonify({"status":"error","message":"الطلب غير موجود"}), 404
        file = request.files.get('receipt')
        if not file or not file.filename:
            return jsonify({"status":"error","message":"لم يتم اختيار صورة"}), 400
        img_data = "data:image/jpeg;base64," + base64.b64encode(file.read()).decode('utf-8')
        o.receipt_image = img_data
        o.status = "بانتظار الدفع"
        db.session.commit()
        return jsonify({"status":"success","message":"تم رفع الايصال بنجاح"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error","message":str(e)}), 500

@app.route('/api/order_detail/<int:order_id>', methods=['GET'])
def order_detail(order_id):
    """تفاصيل طلب محدد"""
    o = Order.query.get(order_id)
    if not o:
        return jsonify({"status":"error"}), 404
    try: cart = json.loads(o.cart_items) if o.cart_items else []
    except: cart = []
    return jsonify({
        "status":"success",
        "id": o.id,
        "customer_name": o.customer_name,
        "customer_phone": o.customer_phone,
        "customer_notes": o.customer_notes or "",
        "status_val": o.status,
        "total": o.cart_total or 0,
        "date": o.order_date.strftime('%Y/%m/%d %H:%M'),
        "items": [{"name":i.get('name',''),"qty":i.get('qty',1),"price":i.get('price',0)} for i in cart],
        "product_name": o.product_name or "",
        "has_receipt": bool(o.receipt_image),
        "admin_notes": o.admin_notes or ""
    })

@app.route('/admin/view_receipt/<int:order_id>')
@login_required
def view_receipt(order_id):
    """عرض ايصال التحويل"""
    o = Order.query.get(order_id)
    if not o or not o.receipt_image:
        return "لا يوجد ايصال", 404
    return render_template_string("""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ايصال الطلب #{{ order.id }}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{font-family:'IBM Plex Sans Arabic',sans-serif;}</style>
</head>
<body class="bg-slate-900 min-h-screen flex items-center justify-center p-4">
<div class="bg-white rounded-3xl max-w-lg w-full overflow-hidden shadow-2xl">
  <div class="bg-slate-900 text-white p-6">
    <div class="flex justify-between items-start">
      <div>
        <h1 class="text-xl font-black">ايصال طلب #{{ order.id }}</h1>
        <p class="text-slate-400 text-xs mt-1">{{ order.customer_name }} | {{ order.customer_phone }}</p>
      </div>
      <a href="/cp" class="text-xs bg-white/10 px-3 py-2 rounded-xl text-slate-300 hover:bg-white/20">رجوع</a>
    </div>
  </div>
  <div class="p-6">
    <img src="{{ order.receipt_image }}" alt="ايصال التحويل" class="w-full rounded-2xl border border-slate-200 shadow">
    <div class="mt-4 bg-slate-50 rounded-2xl p-4 space-y-2 text-sm">
      <div class="flex justify-between"><span class="text-slate-500">الحالة</span><span class="font-bold text-amber-600">{{ order.status }}</span></div>
      <div class="flex justify-between"><span class="text-slate-500">الاجمالي</span><span class="font-bold">{{ "%.0f"|format(order.cart_total or 0) }} ر.س</span></div>
      <div class="flex justify-between"><span class="text-slate-500">التاريخ</span><span class="font-mono text-xs">{{ order.order_date.strftime('%Y/%m/%d %H:%M') }}</span></div>
    </div>
    <div class="mt-4 flex gap-3">
      <a href="/admin/set_order_status/{{ order.id }}/مكتمل" class="flex-1 bg-green-500 text-white py-3 rounded-2xl font-bold text-sm text-center hover:bg-green-600 transition-all">تاكيد الدفع ✓</a>
      <a href="/admin/set_order_status/{{ order.id }}/يتطلب تعديل" class="flex-1 bg-amber-500 text-white py-3 rounded-2xl font-bold text-sm text-center hover:bg-amber-600 transition-all">يتطلب تعديل</a>
    </div>
  </div>
</div>
</body></html>""", order=o)

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('username','').strip() == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, request.form.get('password','')):
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        error = "اسم المستخدم او كلمة المرور غير صحيحة"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/cp', methods=['GET','POST'])
@login_required
def admin():
    if request.method == 'POST' and 'name' in request.form:
        file = request.files.get('product_file')
        img_b64 = ""
        if file and file.filename:
            img_b64 = "data:image/png;base64," + base64.b64encode(file.read()).decode('utf-8')
        stock_val = int(request.form.get('stock', 999) or 999)
        db.session.add(Product(
            name=request.form.get('name'),
            price=float(request.form.get('price',0) or 0),
            old_price=float(request.form.get('old_price')) if request.form.get('old_price') else None,
            description=request.form.get('description',''),
            category=request.form.get('category','عام'),
            image_data=img_b64, is_active=True, stock=stock_val
        ))
        db.session.commit()
        return redirect(url_for('admin')+'#services')

    filter_period = request.args.get('period','all')
    now = datetime.now(timezone.utc)
    if filter_period == 'today':
        date_filter = now.replace(hour=0,minute=0,second=0,microsecond=0)
    elif filter_period == 'week':
        date_filter = now - timedelta(days=7)
    elif filter_period == 'month':
        date_filter = now - timedelta(days=30)
    else:
        date_filter = None

    def get_orders_by_status(status):
        q = Order.query.filter_by(status=status)
        if date_filter: q = q.filter(Order.order_date >= date_filter)
        return q.order_by(Order.order_date.desc()).all()

    all_orders_q = Order.query
    if date_filter: all_orders_q = all_orders_q.filter(Order.order_date >= date_filter)

    orders_by_status = {s: get_orders_by_status(s) for s in ORDER_STATUSES}
    products = Product.query.order_by(Product.id.desc()).all()
    settings = StoreSettings.query.first()
    total_sales = sum((o.cart_total or o.product_price or 0) for o in Order.query.filter_by(status="مكتمل").all())

    def parse_cart(o):
        if o.cart_items:
            try: return json.loads(o.cart_items)
            except: return []
        return []

    for s in ORDER_STATUSES:
        for o in orders_by_status[s]:
            o.parsed_cart = parse_cart(o)

    return render_template_string(ADMIN_HTML,
        products=products, orders_by_status=orders_by_status,
        ORDER_STATUSES=ORDER_STATUSES, settings=settings,
        total_sales=total_sales,
        total_new=len(orders_by_status["جديد"]),
        total_processing=len(orders_by_status["جار التجهيز"]),
        filter_period=filter_period
    )

@app.route('/admin/customers_invoices')
@login_required
def customers_invoices_page():
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    customer_rows = []
    for c in customers:
        orders = Order.query.filter(Order.customer_phone.contains(c.phone[-9:])).all()
        total_spent = sum((o.cart_total or o.product_price or 0) for o in orders if o.status == "مكتمل")
        last_order = max((o.order_date for o in orders if o.order_date), default=None)
        customer_rows.append({
            "id": c.id,
            "name": c.name or "عميل",
            "phone": c.phone or "",
            "email": c.email or "",
            "orders_count": len(orders),
            "total_spent": total_spent,
            "created_at": c.created_at.strftime('%Y/%m/%d') if c.created_at else "",
            "last_order": last_order.strftime('%Y/%m/%d') if last_order else ""
        })

    invoices = []
    orders = Order.query.order_by(Order.order_date.desc()).limit(300).all()
    for o in orders:
        invoices.append({
            "id": o.id,
            "customer_name": o.customer_name or "عميل",
            "customer_phone": o.customer_phone or "",
            "date": o.order_date.strftime('%Y/%m/%d %H:%M') if o.order_date else "",
            "total": o.cart_total or o.product_price or 0,
            "status": o.status or "",
            "product": o.product_name or ""
        })

    # Fetch reviews
    reviews = []
    try:
        review_list = Review.query.order_by(Review.created_at.desc()).all()
        for r in review_list:
            reviews.append({
                "id": r.id,
                "order_id": r.order_id,
                "customer_name": r.customer_name or "عميل",
                "rating": r.rating or 0,
                "comment": r.comment or "",
                "created_at": r.created_at.strftime('%Y/%m/%d %H:%M') if r.created_at else ""
            })
    except Exception:
        pass

    completed_sales = sum(i["total"] for i in invoices if i["status"] == "مكتمل")
    return render_template_string(
        CUSTOMERS_INVOICES_HTML,
        customers=customer_rows,
        invoices=invoices,
        reviews=reviews,
        customers_count=len(customer_rows),
        invoices_count=len(invoices),
        reviews_count=len(reviews),
        completed_sales=completed_sales
    )

@app.route('/admin/export_invoices')
@login_required
def export_invoices():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['receipt_id','date','customer_name','customer_phone','status','total','product'])
    for o in orders:
        writer.writerow([
            o.id,
            o.order_date.strftime('%Y-%m-%d %H:%M') if o.order_date else '',
            o.customer_name or '',
            o.customer_phone or '',
            o.status or '',
            o.cart_total or o.product_price or 0,
            o.product_name or ''
        ])
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition':'attachment; filename=enjazk_receipts.csv'}
    )

@app.route('/admin/set_order_status/<int:oid>/<path:status>')
@login_required
def set_order_status(oid, status):
    o = Order.query.get(oid)
    if o and status in ORDER_STATUSES:
        o.status = status; db.session.commit()
        if status == "مكتمل":
            phone_clean = "".join(filter(str.isdigit, o.customer_phone or ""))
            if phone_clean.startswith("0"): phone_clean = "966" + phone_clean[1:]
            elif not phone_clean.startswith("966"): phone_clean = "966" + phone_clean
            if phone_clean:
                review_msg = "مرحبا " + (o.customer_name or "") + "\n\nتم اكتمال طلبك رقم #" + str(o.id) + " بنجاح!\n\nنسعد بتقييمك:\n5 ممتاز | 4 جيد جدا | 3 جيد | 2 مقبول | 1 يحتاج تحسين\n\nشكرا لثقتك بانجازك"
                return redirect("https://wa.me/" + phone_clean + "?text=" + urllib.parse.quote(review_msg))
    return redirect(url_for('admin'))

@app.route('/admin/delete_order/<int:oid>')
@login_required
def delete_order(oid):
    o = Order.query.get(oid)
    if o: db.session.delete(o); db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/delete_product/<int:pid>')
@login_required
def delete_product(pid):
    p = Product.query.get(pid)
    if p: db.session.delete(p); db.session.commit()
    return redirect(url_for('admin')+'#services')

@app.route('/admin/toggle_product/<int:pid>')
@login_required
def toggle_product(pid):
    p = Product.query.get(pid)
    if p: p.is_active = not p.is_active; db.session.commit()
    return redirect(url_for('admin')+'#services')

@app.route('/admin/edit_product/<int:pid>', methods=['POST'])
@login_required
def edit_product(pid):
    p = Product.query.get(pid)
    if p:
        p.name = request.form.get('name', p.name)
        p.price = float(request.form.get('price', p.price) or p.price)
        p.old_price = float(request.form.get('old_price')) if request.form.get('old_price') else None
        p.description = request.form.get('description', p.description)
        p.category = request.form.get('category', p.category)
        p.stock = int(request.form.get('stock', p.stock or 999) or 999)
        file = request.files.get('product_file')
        if file and file.filename:
            p.image_data = "data:image/png;base64," + base64.b64encode(file.read()).decode('utf-8')
        db.session.commit()
    return redirect(url_for('admin')+'#services')

@app.route('/admin/update_settings', methods=['POST'])
@login_required
def update_settings():
    s = StoreSettings.query.first()
    if s:
        for f in ['whatsapp','whatsapp_number','instagram','tiktok','snapchat','twitter','phone','email','moving_text','footer_text',
                  'bank_name','bank_account','bank_iban','bank_holder']:
            setattr(s, f, request.form.get(f, getattr(s, f)))
        db.session.commit()
    return redirect(url_for('admin')+'#settings')

@app.route('/admin/export_orders')
@login_required
def export_orders():
    orders = Order.query.order_by(Order.order_date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['رقم الطلب','الاسم','الجوال','الخدمة','الاجمالي','الحالة','التاريخ','ملاحظات'])
    for o in orders:
        writer.writerow([o.id, o.customer_name, o.customer_phone, o.product_name,
            o.cart_total or o.product_price or 0, o.status,
            o.order_date.strftime('%Y-%m-%d %H:%M'), o.customer_notes or ''])
    output.seek(0)
    return Response("\ufeff"+output.getvalue(), mimetype='text/csv; charset=utf-8-sig',
        headers={"Content-Disposition":"attachment;filename=orders_enjazk.csv"})

@app.route('/api/validate_coupon', methods=['POST'])
def validate_coupon():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get('code','').strip().upper()
    cart_total = float(data.get('total', 0))
    if not code: return jsonify({"status":"error","message":"ادخل كود الخصم"}), 400
    coupon = Coupon.query.filter_by(code=code, is_active=True).first()
    if not coupon: return jsonify({"status":"error","message":"كود غير صحيح"}), 404
    if coupon.max_uses > 0 and coupon.used_count >= coupon.max_uses:
        return jsonify({"status":"error","message":"تم استنفاد هذا الكود"}), 400
    if coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
        return jsonify({"status":"error","message":"انتهت صلاحية هذا الكود"}), 400
    if coupon.discount_type == "percent":
        discount = cart_total * (coupon.discount_value / 100)
        desc = "خصم {}%".format(int(coupon.discount_value))
    else:
        discount = min(coupon.discount_value, cart_total)
        desc = "خصم {} ر.س".format(int(coupon.discount_value))
    # زيادة عداد الاستخدام
    coupon.used_count = (coupon.used_count or 0) + 1
    db.session.commit()
    return jsonify({"status":"success","discount":round(discount,2),"new_total":round(max(0,cart_total-discount),2),"desc":desc})

@app.route('/api/submit_review', methods=['POST'])
@customer_login_required
def submit_review():
    data = request.get_json(force=True, silent=True) or {}
    order_id = data.get('order_id')
    rating = int(data.get('rating', 0))
    comment = data.get('comment','').strip()
    if not order_id or not 1 <= rating <= 5:
        return jsonify({"status":"error","message":"بيانات غير صحيحة"}), 400
    o = Order.query.get(order_id)
    if not o: return jsonify({"status":"error"}), 404
    # حفظ في جدول Review المستقل
    try:
        existing = Review.query.filter_by(order_id=order_id).first()
        if existing:
            existing.rating = rating
            existing.comment = comment
        else:
            db.session.add(Review(
                order_id=order_id,
                customer_name=o.customer_name or "",
                rating=rating,
                comment=comment,
                is_approved=True
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        # fallback: حفظ في admin_notes
        o.admin_notes = (o.admin_notes or "") + " | تقييم: {}/5{}".format(rating, " - "+comment if comment else "")
        db.session.commit()
    return jsonify({"status":"success"})

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    p = Product.query.get(product_id)
    if not p or not p.is_active:
        return redirect('/')
    settings = StoreSettings.query.first()
    # Related products (same category)
    related = Product.query.filter(
        Product.category == p.category,
        Product.id != p.id,
        Product.is_active == True
    ).limit(3).all()
    return render_template_string(PRODUCT_HTML,
        product=p, settings=settings, related=related)

@app.route('/api/stats_public')
def stats_public():
    completed = Order.query.filter_by(status="مكتمل").count()
    products = Product.query.filter_by(is_active=True).count()
    return jsonify({"completed":completed,"products":products})

@app.route('/admin/coupons', methods=['GET','POST'])
@login_required
def admin_coupons():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            code = request.form.get('code','').strip().upper()
            expires_at_str = request.form.get('expires_at','').strip()
            expires_at = None
            if expires_at_str:
                try: expires_at = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M')
                except: pass
            if code and not Coupon.query.filter_by(code=code).first():
                db.session.add(Coupon(code=code,
                    discount_type=request.form.get('discount_type','percent'),
                    discount_value=float(request.form.get('discount_value',0) or 0),
                    max_uses=int(request.form.get('max_uses',0) or 0),
                    expires_at=expires_at, is_active=True))
                db.session.commit()
        elif action == 'toggle':
            c = Coupon.query.get(int(request.form.get('id',0)))
            if c: c.is_active = not c.is_active; db.session.commit()
        elif action == 'delete':
            c = Coupon.query.get(int(request.form.get('id',0)))
            if c: db.session.delete(c); db.session.commit()
        # reload page after action
        coupons = Coupon.query.order_by(Coupon.id.desc()).all()
        return jsonify([{"id":c.id,"code":c.code,"type":c.discount_type,"value":c.discount_value,
                         "max_uses":c.max_uses,"used":c.used_count,"active":c.is_active,
                         "expires_at":c.expires_at.strftime('%Y-%m-%dT%H:%M') if c.expires_at else None} for c in coupons])
    try:
        coupons = Coupon.query.order_by(Coupon.id.desc()).all()
        return jsonify([{"id":c.id,"code":c.code,"type":c.discount_type,"value":c.discount_value,
                         "max_uses":c.max_uses,"used":c.used_count,"active":c.is_active,
                         "expires_at":c.expires_at.strftime('%Y-%m-%dT%H:%M') if c.expires_at else None} for c in coupons])
    except Exception as e:
        return jsonify([])

@app.route('/admin/save_note/<int:order_id>', methods=['POST'])
@login_required
def save_admin_note(order_id):
    o = Order.query.get(order_id)
    if o:
        data = request.get_json(force=True, silent=True) or {}
        o.admin_notes = data.get('note', '')
        db.session.commit()
    return jsonify({"status":"success"})



# =================== NEW FEATURES ROUTES ===================

@app.route('/api/calculate_price', methods=['POST'])
def calculate_price():
    """حاسبة السعر"""
    data = request.get_json(force=True, silent=True) or {}
    product_id = data.get('product_id')
    num_pages = int(data.get('num_pages', 0))
    if not product_id or num_pages < 1:
        return jsonify({"status":"error","message":"بيانات ناقصة"}), 400
    p = Product.query.get(product_id)
    if not p:
        return jsonify({"status":"error"}), 404
    base = p.price or 0
    per_page = p.price_per_page or 0
    base_pages = p.base_pages or 0
    extra_pages = max(0, num_pages - base_pages)
    total = base + (extra_pages * per_page)
    # Check seasonal offer
    now = datetime.now(timezone.utc)
    offer = SeasonalOffer.query.filter(
        SeasonalOffer.is_active == True,
        SeasonalOffer.start_date <= now,
        SeasonalOffer.end_date >= now
    ).first()
    discount = 0
    if offer:
        discount = total * (offer.discount_percent / 100)
        total = max(0, total - discount)
    return jsonify({
        "status":"success","base":base,"per_page":per_page,
        "extra_pages":extra_pages,"subtotal":base+(extra_pages*per_page),
        "discount":round(discount,2),"total":round(total,2),
        "offer":offer.title if offer else None
    })

@app.route('/api/bulk_discount', methods=['POST'])
def bulk_discount():
    """خصم الكمية - يحسب من إعدادات المتجر"""
    data = request.get_json(force=True, silent=True) or {}
    item_count = int(data.get('count', 0))
    total = float(data.get('total', 0))
    # خصم قابل للتعديل من لوحة التحكم
    settings = StoreSettings.query.first()
    discount_3 = float(getattr(settings, 'bulk_discount_3', 0) or 0)
    discount_5 = float(getattr(settings, 'bulk_discount_5', 0) or 0)
    if item_count >= 5 and discount_5 > 0:
        discount = total * (discount_5/100)
        return jsonify({"status":"success","discount":round(discount,2),"percent":discount_5,"new_total":round(total-discount,2)})
    elif item_count >= 3 and discount_3 > 0:
        discount = total * (discount_3/100)
        return jsonify({"status":"success","discount":round(discount,2),"percent":discount_3,"new_total":round(total-discount,2)})
    return jsonify({"status":"success","discount":0,"percent":0,"new_total":total})

@app.route('/api/generate_referral')
def generate_referral():
    """إنشاء كود إحالة للعميل"""
    if not session.get('customer_id'):
        return jsonify({"status":"error","message":"سجل دخولك أولاً"}), 401
    import hashlib
    code = "REF" + hashlib.md5(str(session['customer_id']).encode()).hexdigest()[:6].upper()
    return jsonify({"status":"success","code":code,"customer_id":session['customer_id']})

@app.route('/api/testimonials')
def get_testimonials():
    """جلب شهادات العملاء المعتمدة"""
    try:
        tlist = Testimonial.query.filter_by(is_approved=True).order_by(Testimonial.created_at.desc()).limit(10).all()
        return jsonify([{"name":t.name,"text":t.text,"rating":t.rating} for t in tlist])
    except:
        return jsonify([])

@app.route('/api/reviews')
def get_reviews():
    """جلب تقييمات العملاء من جدول Review المستقل"""
    try:
        rlist = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).limit(20).all()
        return jsonify([{"customer_name":r.customer_name,"rating":r.rating,"comment":r.comment,"date":r.created_at.strftime('%Y/%m/%d') if r.created_at else ""} for r in rlist])
    except:
        return jsonify([])

@app.route('/order/<int:order_id>')
def order_tracking(order_id):
    """صفحة تتبع الطلب العامة -- التتبع للجميع، لكن رفع الإيصال/التقييم/التحميل يحتاج تسجيل دخول"""
    o = Order.query.get(order_id)
    if not o:
        return render_template_string("""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>الطلب غير موجود</title><script src="https://cdn.tailwindcss.com"></script></head><body class="min-h-screen bg-slate-950 flex items-center justify-center"><div class="text-center text-white"><i class="fas fa-box-open text-5xl mb-4 block text-slate-500"></i><h1 class="text-xl font-black mb-2">الطلب غير موجود</h1><a href="/" class="text-amber-400 underline text-sm">العودة للمتجر</a></div></body></html>"""), 404
    settings = StoreSettings.query.first() or StoreSettings()
    STATUS_STEPS = ["جديد","جار التجهيز","بانتظار الدفع","مكتمل"]
    current_step = STATUS_STEPS.index(o.status) if o.status in STATUS_STEPS else 0
    try: cart = json.loads(o.cart_items) if o.cart_items else []
    except: cart = []
    if not cart and o.product_name:
        cart = [{"name":o.product_name,"qty":1,"price":o.product_price or 0}]
    is_logged_in = bool(session.get('customer_id'))
    TRACKING_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>تتبع الطلب #{{ order.id }} | انجازك</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{font-family:'IBM Plex Sans Arabic',sans-serif;background:#0f172a;}</style>
</head>
<body class="min-h-screen flex items-center justify-center p-4">
  <div class="w-full max-w-md">
    <div class="text-center mb-6">
      <a href="/" class="inline-flex items-center gap-2 text-amber-400 text-sm font-bold hover:text-amber-300 mb-4">
        <i class="fas fa-arrow-right"></i> العودة للمتجر
      </a>
      <h1 class="text-2xl font-black text-white">تتبع الطلب</h1>
      <p class="text-slate-400 text-sm mt-1">رقم الطلب: <span class="text-amber-400 font-bold">#{{ order.id }}</span></p>
    </div>

    <div class="bg-white rounded-3xl p-6 shadow-2xl mb-4">
      <!-- Progress Bar -->
      <div class="mb-6">
        <div class="flex justify-between items-center mb-3">
          {% set steps = [('جديد','fa-bell'),('جار التجهيز','fa-cog'),('بانتظار الدفع','fa-dollar-sign'),('مكتمل','fa-check')] %}
          {% for step_name, step_icon in steps %}
          {% set step_idx = loop.index0 %}
          <div class="flex flex-col items-center gap-1 flex-1">
            <div class="w-9 h-9 rounded-full flex items-center justify-center text-xs font-black
              {% if step_idx <= current_step and order.status not in ['ملغي','إيصال خاطئ'] %}bg-amber-500 text-white{% else %}bg-slate-100 text-slate-400{% endif %}">
              <i class="fas {{ step_icon }}"></i>
            </div>
            <p class="text-[9px] text-center font-bold {% if step_idx <= current_step and order.status not in ['ملغي','إيصال خاطئ'] %}text-amber-600{% else %}text-slate-400{% endif %}">{{ step_name }}</p>
          </div>
          {% if not loop.last %}
          <div class="h-0.5 flex-1 mx-1 mb-5 {% if step_idx < current_step and order.status not in ['ملغي','إيصال خاطئ'] %}bg-amber-400{% else %}bg-slate-200{% endif %}"></div>
          {% endif %}
          {% endfor %}
        </div>
        {% if order.status == 'ملغي' %}
        <div class="bg-red-50 border border-red-200 rounded-2xl p-3 text-center"><p class="text-red-600 font-bold text-sm"><i class="fas fa-times-circle ml-1"></i>تم إلغاء الطلب</p></div>
        {% elif order.status == 'مكتمل' %}
        <div class="bg-green-50 border border-green-200 rounded-2xl p-3 text-center"><p class="text-green-700 font-bold text-sm"><i class="fas fa-check-circle ml-1"></i>تم إنجاز طلبك بنجاح!</p></div>
        {% else %}
        <div class="bg-amber-50 border border-amber-200 rounded-2xl p-3 text-center"><p class="text-amber-700 font-bold text-sm"><i class="fas fa-clock ml-1"></i>{{ order.status }}</p></div>
        {% endif %}
      </div>

      <!-- Order Info -->
      <div class="space-y-2 mb-4">
        <div class="flex justify-between text-sm"><span class="text-slate-500">الاسم</span><span class="font-bold">{{ order.customer_name }}</span></div>
        <div class="flex justify-between text-sm"><span class="text-slate-500">تاريخ الطلب</span><span class="font-bold text-xs">{{ order.order_date.strftime('%Y/%m/%d %H:%M') if order.order_date else '' }}</span></div>
        {% if order.cart_total %}<div class="flex justify-between text-sm"><span class="text-slate-500">الإجمالي</span><span class="font-black text-amber-600">{{ "%.0f"|format(order.cart_total) }} ر.س</span></div>{% endif %}
      </div>

      <!-- Items -->
      {% if cart %}
      <div class="bg-slate-50 rounded-2xl p-3 mb-4">
        <p class="text-xs font-black text-slate-500 mb-2">الخدمات المطلوبة</p>
        {% for item in cart %}
        <div class="flex justify-between text-xs py-1"><span class="text-slate-700">{{ item.name }} x{{ item.qty }}</span><span class="font-bold">{{ "%.0f"|format(item.price * item.qty) }} ر.س</span></div>
        {% endfor %}
      </div>
      {% endif %}

      <!-- Actions -->
      <div class="space-y-2">
        {% if order.status not in ['مكتمل','ملغي'] %}
          {% if is_logged_in %}
          <a href="/?open_orders=1" class="w-full bg-amber-600 text-white py-3 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 hover:bg-amber-500 transition-all">
            <i class="fas fa-upload"></i> رفع إيصال التحويل
          </a>
          {% else %}
          <a href="/?login=1" class="w-full bg-slate-100 text-slate-500 py-3 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 hover:bg-slate-200 transition-all">
            <i class="fas fa-lock"></i> سجّل الدخول لرفع الإيصال
          </a>
          {% endif %}
        {% endif %}

        {% if order.status == 'مكتمل' %}
          {% if is_logged_in %}
          <button onclick="openReviewModal({{ order.id }})" class="w-full bg-amber-100 text-amber-700 py-3 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 hover:bg-amber-200 transition-all">
            <i class="fas fa-star"></i> تقييم الطلب
          </button>
          {% else %}
          <a href="/?login=1" class="w-full bg-slate-100 text-slate-500 py-3 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 hover:bg-slate-200 transition-all">
            <i class="fas fa-lock"></i> سجّل الدخول للتقييم
          </a>
          {% endif %}
        {% endif %}

        {% if settings.whatsapp %}
        <a href="{{ settings.whatsapp }}?text=استفسار عن طلب رقم {{ order.id }}" target="_blank" class="w-full bg-green-500 text-white py-3 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 hover:bg-green-600 transition-all">
          <i class="fab fa-whatsapp"></i> تواصل معنا
        </a>
        {% endif %}
      </div>
    </div>
    <p class="text-center text-slate-600 text-xs">انجازك للخدمات الأكاديمية</p>
  </div>
  <script>
  async function openReviewModal(orderId){
    var rating = prompt('قيم من 1 الى 5 (5 = ممتاز):');
    if(!rating) return;
    rating = parseInt(rating);
    if(rating < 1 || rating > 5){ alert('التقييم يجب ان يكون بين 1 و 5'); return; }
    var comment = prompt('تعليق اختياري:');
    try{
      var r = await fetch('/api/submit_review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:orderId,rating:rating,comment:comment||''})});
      var d = await r.json();
      if(d.status === 'success'){ alert('شكراً لتقييمك!'); }
      else { alert(d.message || 'يجب تسجيل الدخول'); }
    }catch(e){ alert('تعذر الارسال'); }
  }
  </script>
</body></html>"""
    return render_template_string(TRACKING_HTML, order=o, cart=cart, settings=settings, current_step=current_step, is_logged_in=is_logged_in)
@app.route('/api/active_offer')
def active_offer():
    """جلب العرض الموسمي الفعال"""
    now = datetime.now(timezone.utc)
    try:
        offer = SeasonalOffer.query.filter(
            SeasonalOffer.is_active == True,
            SeasonalOffer.start_date <= now,
            SeasonalOffer.end_date >= now
        ).first()
        if offer:
            return jsonify({"status":"success","title":offer.title,
                "discount":offer.discount_percent,"banner":offer.banner_text,
                "end_date":offer.end_date.strftime('%Y-%m-%d %H:%M')})
    except: pass
    return jsonify({"status":"none"})

@app.route('/api/upload_delivery/<int:order_id>', methods=['POST'])
@login_required
def upload_delivery(order_id):
    """رفع ملف التسليم - الأدمن"""
    o = Order.query.get(order_id)
    if not o:
        return jsonify({"status":"error"}), 404
    file = request.files.get('file')
    if not file:
        return jsonify({"status":"error","message":"لم يتم اختيار ملف"}), 400
    import sqlite3 as _sq
    file_data = "data:application/octet-stream;base64," + base64.b64encode(file.read()).decode()
    file_name = file.filename
    _c = _sq.connect(db_path)
    try: _c.execute('ALTER TABLE [order] ADD COLUMN delivery_file TEXT DEFAULT ""'); _c.commit()
    except: pass
    try: _c.execute('ALTER TABLE [order] ADD COLUMN delivery_filename TEXT DEFAULT ""'); _c.commit()
    except: pass
    _c.execute('UPDATE [order] SET delivery_file=?, delivery_filename=? WHERE id=?', (file_data, file_name, order_id))
    _c.commit()
    _c.close()
    # إشعار واتساب للعميل
    wa_link = None
    settings = StoreSettings.query.first()
    if settings and settings.whatsapp_number and o.customer_phone:
        msg = "مرحباً {}! تم تسليم طلبك رقم #{} \nيمكنك تحميل الملفات من حسابك في الموقع".format(o.customer_name, order_id)
        wa_link = "https://wa.me/{}?text={}".format(o.customer_phone.replace('+',''), urllib.parse.quote(msg))
    return jsonify({"status":"success","wa_link":wa_link})




@app.route('/api/admin/customers')
@login_required
def admin_customers():
    """قائمة جميع العملاء"""
    customers = Customer.query.all()
    result = []
    for c in customers:
        orders_count = Order.query.filter(Order.customer_phone.contains(c.phone[-9:])).count()
        result.append({
            "id": c.id,
            "name": c.name or "عميل",
            "phone": c.phone,
            "email": c.email,
            "orders_count": orders_count,
            "created_at": c.created_at.strftime('%Y/%m/%d') if c.created_at else "N/A"
        })
    return jsonify({"status":"success","customers":result})

@app.route('/api/admin/customer/<int:customer_id>')
@login_required
def admin_get_customer(customer_id):
    """الحصول على بيانات عميل"""
    c = Customer.query.get(customer_id)
    if not c:
        return jsonify({"status":"error"}), 404
    return jsonify({"id": c.id,"name": c.name,"phone": c.phone,"email": c.email})

@app.route('/api/admin/customer/<int:customer_id>', methods=['PUT'])
@login_required
def admin_update_customer(customer_id):
    """تحديث بيانات عميل"""
    c = Customer.query.get(customer_id)
    if not c:
        return jsonify({"status":"error"}), 404
    data = request.get_json(silent=True) or {}
    c.name = data.get('name', c.name)
    c.phone = data.get('phone', c.phone)
    c.email = data.get('email', c.email)
    db.session.commit()
    return jsonify({"status":"success"})

@app.route('/api/admin/customer/<int:customer_id>', methods=['DELETE'])
@login_required
def admin_delete_customer(customer_id):
    """حذف عميل"""
    c = Customer.query.get(customer_id)
    if not c:
        return jsonify({"status":"error"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"status":"success"})

@app.route('/api/admin/invoices')
@login_required
def admin_invoices():
    """قائمة جميع إيصالات الشراء"""
    order_id = request.args.get('order_id')
    if order_id:
        orders = Order.query.filter_by(id=int(order_id)).all()
    else:
        orders = Order.query.filter_by(status='مكتمل').order_by(Order.id.desc()).limit(50).all()
    invoices = []
    for o in orders:
        invoices.append({
            "order_id": o.id,
            "customer_name": o.customer_name or "عميل",
            "date": o.order_date.strftime('%Y/%m/%d') if o.order_date else "N/A",
            "total": o.cart_total or 0,
            "status": o.status,
            "phone": o.customer_phone
        })
    return jsonify({"status":"success","invoices":invoices})

@app.route('/api/send_invoice_wa/<int:order_id>')
@login_required
def send_invoice_wa(order_id):
    """إرسال رابط إيصال الشراء عبر واتساب"""
    o = Order.query.get(order_id)
    if not o:
        return jsonify({"status":"error"}), 404
    base_url = request.url_root.rstrip('/')
    invoice_link = f"{base_url}/api/download_invoice/{order_id}"
    msg = f"مرحباً {o.customer_name}!\n\nإيصال الشراء جاهز للطلب رقم #{order_id}\n\nيمكنك تحميله من: {invoice_link}\n\nشكراً لثقتك بمتجر انجازك"
    phone_clean = ''.join(filter(str.isdigit, o.customer_phone))
    if phone_clean.startswith('0'):
        phone_clean = '966' + phone_clean[1:]
    elif len(phone_clean) == 9:
        phone_clean = '966' + phone_clean
    wa_link = f"https://wa.me/{phone_clean}?text={urllib.parse.quote(msg)}"
    return jsonify({"status":"success","wa_link":wa_link})

@app.route('/api/download_invoice/<int:order_id>')
def download_invoice(order_id):
    """إيصال شراء — صفحة HTML جميلة قابلة للطباعة كـ PDF من المتصفح"""
    import json as _json
    o = Order.query.get(order_id)
    if not o:
        return jsonify({"status":"error","message":"الطلب غير موجود"}), 404

    try:
        cart = _json.loads(o.cart_items) if o.cart_items else []
    except:
        cart = []
    if not cart:
        cart = [{"name": o.product_name or "خدمة أكاديمية", "qty": 1, "price": o.product_price or 0}]

    settings = StoreSettings.query.first()
    store_name = (settings.store_name if settings and hasattr(settings,'store_name') else None) or 'انجازك'
    store_email = (settings.email if settings and hasattr(settings,'email') else None) or 'academic@enjazk.com'
    store_whatsapp = (settings.whatsapp if settings and hasattr(settings,'whatsapp') else None) or ''

    date_str = o.order_date.strftime('%Y/%m/%d') if o.order_date else ''
    time_str = o.order_date.strftime('%H:%M') if o.order_date else ''
    total = o.cart_total or 0
    discount = getattr(o, 'coupon_discount', 0) or 0
    subtotal = total + discount
    status = o.status or 'جديد'
    status_colors = {
        'مكتمل': ('#dcfce7','#166534','✓'),
        'جديد': ('#fef9c3','#854d0e','◉'),
        'جار التجهيز': ('#dbeafe','#1e40af','⟳'),
        'بانتظار الدفع': ('#fff7ed','#9a3412','⏳'),
        'ملغي': ('#fee2e2','#991b1b','✕'),
    }
    s_bg, s_color, s_icon = status_colors.get(status, ('#f1f5f9','#475569','•'))

    rows = ""
    for i, item in enumerate(cart):
        n = item.get('name',''); q = item.get('qty',1); p = float(item.get('price',0))
        bg = '#fff' if i%2==0 else '#fafafa'
        rows += f'<tr style="background:{bg}"><td style="padding:11px 16px;text-align:right;color:#1e293b;font-weight:600;">{n}</td><td style="padding:11px;text-align:center;color:#64748b;">{q}</td><td style="padding:11px;text-align:center;color:#64748b;">{p:.0f}</td><td style="padding:11px;text-align:center;font-weight:700;color:#1e293b;">{p*q:.0f}</td></tr>'

    discount_row = ""
    if discount and discount > 0:
        discount_row = f'<div style="display:flex;justify-content:space-between;padding:7px 0;color:#16a34a;font-size:13px;"><span>خصم كوبون</span><span>- {discount:.0f} ر.س</span></div>'

    wa_link = f'https://wa.me/{store_whatsapp.replace("+","").replace(" ","")}' if store_whatsapp else '#'

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>إيصال #{o.id} | {store_name}</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'IBM Plex Sans Arabic',Tahoma,Arial,sans-serif;direction:rtl;background:#f8fafc;min-height:100vh;display:flex;align-items:flex-start;justify-content:center;padding:32px 16px;}}
.page{{width:100%;max-width:620px;}}
.card{{background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);}}

/* HEADER */
.header{{background:linear-gradient(135deg,#d97706 0%,#f59e0b 60%,#fbbf24 100%);padding:32px 28px 24px;position:relative;overflow:hidden;}}
.header::before{{content:'';position:absolute;top:-30px;left:-30px;width:150px;height:150px;border-radius:50%;background:rgba(255,255,255,.08);}}
.header::after{{content:'';position:absolute;bottom:-20px;right:40px;width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,.06);}}
.header-top{{display:flex;justify-content:space-between;align-items:flex-start;position:relative;z-index:1;}}
.store-name{{color:#fff;font-size:26px;font-weight:800;letter-spacing:-.5px;}}
.store-sub{{color:rgba(255,255,255,.85);font-size:12px;margin-top:3px;font-weight:500;}}
.badge{{background:rgba(255,255,255,.2);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.3);color:#fff;padding:6px 14px;border-radius:50px;font-size:12px;font-weight:700;}}
.receipt-title{{color:rgba(255,255,255,.7);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;margin-top:20px;position:relative;z-index:1;}}
.receipt-num{{color:#fff;font-size:32px;font-weight:800;position:relative;z-index:1;line-height:1.1;}}

/* META ROW */
.meta-row{{display:flex;gap:0;border-bottom:1px solid #f1f5f9;}}
.meta-cell{{flex:1;padding:14px 20px;border-left:1px solid #f1f5f9;}}
.meta-cell:last-child{{border-left:none;}}
.meta-label{{font-size:10px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}}
.meta-val{{font-size:13px;color:#1e293b;font-weight:700;}}

/* SECTION */
.section{{padding:20px 24px;border-bottom:1px solid #f8fafc;}}
.section-head{{font-size:11px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;display:flex;align-items:center;gap:8px;}}
.section-head::after{{content:'';flex:1;height:1px;background:#f1f5f9;}}
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
.info-item{{background:#f8fafc;border-radius:12px;padding:12px 14px;}}
.info-item-label{{font-size:10px;color:#94a3b8;font-weight:600;margin-bottom:3px;}}
.info-item-val{{font-size:14px;color:#1e293b;font-weight:700;}}

/* TABLE */
.table-wrap{{overflow:hidden;border-radius:12px;border:1px solid #f1f5f9;}}
table{{width:100%;border-collapse:collapse;font-size:13px;}}
thead tr{{background:#1e293b;}}
thead th{{color:#fff;padding:11px 16px;font-weight:600;font-size:11px;letter-spacing:.3px;}}
thead th:first-child{{text-align:right;}}
thead th:not(:first-child){{text-align:center;}}
tbody tr:last-child td{{border-bottom:none;}}
tbody td{{border-bottom:1px solid #f1f5f9;font-size:13px;}}

/* TOTALS */
.totals{{background:#f8fafc;border-radius:12px;padding:16px 18px;}}
.total-line{{display:flex;justify-content:space-between;padding:6px 0;color:#64748b;font-size:13px;}}
.total-line.main{{border-top:2px solid #e2e8f0;margin-top:8px;padding-top:12px;color:#1e293b;font-size:17px;font-weight:800;}}
.total-line.main span:last-child{{color:#d97706;}}

/* STATUS */
.status-badge{{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:50px;font-size:13px;font-weight:700;background:{s_bg};color:{s_color};}}

/* FOOTER */
.footer{{padding:20px 24px;background:#fafafa;border-top:1px solid #f1f5f9;}}
.footer-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;}}
.footer-item{{display:flex;align-items:center;gap:8px;font-size:12px;color:#64748b;}}
.footer-item strong{{color:#475569;}}
.thanks{{text-align:center;padding:16px;background:linear-gradient(135deg,#fffbeb,#fef3c7);border-radius:12px;}}
.thanks p{{font-size:15px;font-weight:800;color:#92400e;}}
.thanks small{{font-size:11px;color:#b45309;margin-top:4px;display:block;}}

/* PRINT BUTTON */
.print-bar{{text-align:center;padding:24px 0 0;}}
.print-btn{{background:linear-gradient(135deg,#d97706,#f59e0b);color:#fff;border:none;padding:14px 40px;border-radius:50px;font-family:'IBM Plex Sans Arabic',sans-serif;font-size:15px;font-weight:700;cursor:pointer;box-shadow:0 4px 14px rgba(217,119,6,.35);transition:all .2s;}}
.print-btn:hover{{transform:translateY(-1px);box-shadow:0 6px 20px rgba(217,119,6,.4);}}
.close-btn{{background:#f1f5f9;color:#64748b;border:none;padding:14px 28px;border-radius:50px;font-family:'IBM Plex Sans Arabic',sans-serif;font-size:15px;font-weight:600;cursor:pointer;margin-right:10px;transition:all .2s;}}

@media print{{
  body{{background:#fff;padding:0;}}
  .print-bar{{display:none!important;}}
  .card{{box-shadow:none;border-radius:0;}}
  @page{{margin:15mm;size:A4;}}
}}
</style>
</head>
<body>
<div class="page">
  <div class="card">

    <!-- HEADER -->
    <div class="header">
      <div class="header-top">
        <div>
          <div class="store-name">{store_name}</div>
          <div class="store-sub">للخدمات الأكاديمية والطلابية</div>
        </div>
        <div class="badge">إيصال رسمي</div>
      </div>
      <div class="receipt-title">رقم الإيصال</div>
      <div class="receipt-num">#{o.id}</div>
    </div>

    <!-- META -->
    <div class="meta-row">
      <div class="meta-cell">
        <div class="meta-label">التاريخ</div>
        <div class="meta-val">{date_str}</div>
      </div>
      <div class="meta-cell">
        <div class="meta-label">الوقت</div>
        <div class="meta-val">{time_str}</div>
      </div>
      <div class="meta-cell">
        <div class="meta-label">حالة الطلب</div>
        <div class="meta-val"><span class="status-badge">{s_icon} {status}</span></div>
      </div>
    </div>

    <!-- CUSTOMER -->
    <div class="section">
      <div class="section-head">معلومات العميل</div>
      <div class="info-grid">
        <div class="info-item">
          <div class="info-item-label">الاسم الكامل</div>
          <div class="info-item-val">{o.customer_name or '—'}</div>
        </div>
        <div class="info-item">
          <div class="info-item-label">رقم الجوال</div>
          <div class="info-item-val" style="direction:ltr;text-align:right;">{o.customer_phone or '—'}</div>
        </div>
      </div>
    </div>

    <!-- ITEMS -->
    <div class="section">
      <div class="section-head">تفاصيل الخدمات</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>الخدمة</th>
              <th>الكمية</th>
              <th>سعر الوحدة</th>
              <th>الإجمالي</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>

    <!-- TOTALS -->
    <div class="section">
      <div class="totals">
        <div class="total-line"><span>المجموع الفرعي</span><span>{subtotal:.0f} ر.س</span></div>
        {discount_row}
        <div class="total-line main"><span>الإجمالي المستحق</span><span>{total:.0f} ر.س</span></div>
      </div>
    </div>

    <!-- FOOTER -->
    <div class="footer">
      <div class="footer-grid">
        <div class="footer-item"><span>📧</span><span><strong>البريد:</strong> {store_email}</span></div>
        <div class="footer-item"><span>💬</span><span><strong>واتساب:</strong> {store_whatsapp or '—'}</span></div>
      </div>
      <div class="thanks">
        <p>شكراً لثقتك بـ {store_name} 🌟</p>
        <small>هذا الإيصال دليل على إتمام طلبك بنجاح</small>
      </div>
    </div>

  </div>

  <!-- PRINT BAR -->
  <div class="print-bar">
    <button class="close-btn" onclick="window.close()">إغلاق</button>
    <button class="print-btn" onclick="window.print()">🖨️ طباعة / حفظ PDF</button>
  </div>
</div>

<script>
// طباعة تلقائية بعد تحميل الخط
document.fonts.ready.then(function(){{
  // لا تطبع تلقائياً — ينتظر المستخدم يضغط الزر
}});
</script>
</body>
</html>"""
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/api/download_delivery/<int:order_id>')
def download_delivery(order_id):
    """تحميل ملف التسليم - العميل"""
    import sqlite3 as _sq
    _c = _sq.connect(db_path)
    try:
        row = _c.execute('SELECT delivery_file, delivery_filename FROM [order] WHERE id=?', (order_id,)).fetchone()
        _c.close()
        if row and row[0]:
            return jsonify({"status":"success","file":row[0],"filename":row[1] or "delivery"})
    except: pass
    return jsonify({"status":"error","message":"لا يوجد ملف"}), 404


@app.route('/admin/update_status/<int:order_id>', methods=['POST'])
@login_required
def admin_update_status(order_id):
    """تحديث حالة الطلب مع معالجة خاصة لـ إيصال خاطئ"""
    o = Order.query.get(order_id)
    if not o:
        return jsonify({"status":"error"}), 404

    new_status = request.form.get('status') or (request.get_json(silent=True) or {}).get('status')
    if not new_status:
        return jsonify({"status":"error","message":"الحالة مطلوبة"}), 400

    old_status = o.status
    o.status = new_status

    # إذا الحالة الجديدة "إيصال خاطئ" - امسح الإيصال
    if new_status == "إيصال خاطئ":
        import sqlite3 as _sq
        _c = _sq.connect(db_path)
        _c.execute('UPDATE [order] SET receipt_image = NULL WHERE id = ?', (order_id,))
        _c.commit()
        _c.close()
        # غيّر الحالة لـ بانتظار الدفع بعد مسح الإيصال
        o.status = "بانتظار الدفع"

    db.session.commit()

    # إذا الحالة "مكتمل" - إنشاء إيصال الشراء تلقائياً وإرساله بالإيميل
    invoice_link = None
    if new_status == "مكتمل":
        try:
            pdf_data = generate_invoice_pdf(order_id)
            if pdf_data:
                invoice_b64 = "data:application/pdf;base64," + base64.b64encode(pdf_data).decode()
                import sqlite3 as _sq
                _c = _sq.connect(db_path)
                try:
                    _c.execute('ALTER TABLE [order] ADD COLUMN invoice_pdf TEXT')
                    _c.commit()
                except: pass
                _c.execute('UPDATE [order] SET invoice_pdf=? WHERE id=?', (invoice_b64, order_id))
                _c.commit()
                _c.close()
                invoice_link = f"/api/download_invoice/{order_id}"
                # إرسال إيصال الشراء بالإيميل
                try:
                    send_purchase_receipt_email(o, pdf_data)
                except Exception as mail_err:
                    app.logger.warning(f"Receipt email failed: {mail_err}")
        except Exception as e:
            print(f"Error generating receipt: {e}")
    else:
        # إرسال إيميل تحديث الحالة لجميع الحالات الأخرى
        try:
            send_status_update_email(o, new_status)
        except Exception as mail_err:
            app.logger.warning(f"Status update email failed: {mail_err}")

    # إرسال واتساب
    settings = StoreSettings.query.first()
    wa_link = None
    if settings and settings.whatsapp_number and o.customer_phone:
        status_msgs = {
            "جديد": "تم استلام طلبك رقم #{}",
            "جار التجهيز": "طلبك رقم #{} قيد التنفيذ الآن",
            "بانتظار الدفع": "طلبك رقم #{} بانتظار تأكيد الدفع",
            "إيصال خاطئ": "طلبك رقم #{} - الإيصال المرفوع غير واضح أو خاطئ، يُرجى رفع إيصال صحيح من صفحة طلباتك",
            "يتطلب تعديل": "طلبك رقم #{} يتطلب تعديلات",
            "مكتمل": "تم إنجاز طلبك رقم #{}!"
        }
        msg = status_msgs.get(new_status if new_status != "إيصال خاطئ" else "إيصال خاطئ", "تحديث على طلبك #{}").format(order_id)
        wa_link = "https://wa.me/{}?text={}".format(
            o.customer_phone.replace('+','').replace(' ',''),
            urllib.parse.quote(msg))

    return jsonify({"status":"success","wa_link":wa_link,"new_status":o.status})

@app.route('/api/send_wa_status/<int:order_id>', methods=['POST'])
@login_required
def send_wa_status(order_id):
    """إرسال إشعار واتساب للعميل عند تغيير الحالة"""
    o = Order.query.get(order_id)
    if not o: return jsonify({"status":"error"}), 404
    status_msgs = {
        "جديد": "تم استلام طلبك رقم #{} وسيتم البدء قريباً",
        "جار التجهيز": "طلبك رقم #{} قيد التنفيذ الآن",
        "بانتظار الدفع": "طلبك رقم #{} بانتظار تأكيد الدفع",
        "إيصال خاطئ": "طلبك رقم #{} - الإيصال المرفوع غير واضح أو خاطئ، يُرجى رفع إيصال صحيح من صفحة طلباتك",
        "يتطلب تعديل": "طلبك رقم #{} يتطلب بعض التعديلات، تواصل معنا",
        "مكتمل": "تم إنجاز طلبك رقم #{}! شكراً لثقتك بانجازك"
    }
    msg = status_msgs.get(o.status, "تحديث على طلبك رقم #{}").format(o.id)
    wa_link = "https://wa.me/{}?text={}".format(
        o.customer_phone.replace('+','').replace(' ',''),
        urllib.parse.quote(msg))
    return jsonify({"status":"success","wa_link":wa_link})

@app.route('/api/admin_stats')
@login_required
def admin_stats():
    """إحصائيات متقدمة للأدمن"""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    daily_sales = db.session.query(db.func.sum(Order.cart_total)).filter(
        Order.order_date >= today, Order.status == "مكتمل").scalar() or 0
    weekly_sales = db.session.query(db.func.sum(Order.cart_total)).filter(
        Order.order_date >= week_ago, Order.status == "مكتمل").scalar() or 0
    monthly_sales = db.session.query(db.func.sum(Order.cart_total)).filter(
        Order.order_date >= month_ago, Order.status == "مكتمل").scalar() or 0

    total_orders = Order.query.filter(Order.order_date >= month_ago).count()
    completed = Order.query.filter(Order.order_date >= month_ago, Order.status == "مكتمل").count()

    # أكثر خدمة طلباً
    top_product = db.session.query(Order.product_name, db.func.count(Order.id))        .filter(Order.order_date >= month_ago)        .group_by(Order.product_name)        .order_by(db.func.count(Order.id).desc()).first()

    # طلبات قرب الموعد النهائي (خلال 24 ساعة)
    deadline_soon = []
    try:
        import sqlite3 as _sq
        _c = _sq.connect(db_path)
        rows = _c.execute('SELECT id, customer_name, deadline FROM [order] WHERE deadline IS NOT NULL AND status NOT IN ("مكتمل","ملغي")').fetchall()
        _c.close()
        for r in rows:
            if r[2]:
                from datetime import datetime as dt
                try:
                    dl = dt.strptime(r[2], '%Y-%m-%d %H:%M:%S')
                    if dl <= now + timedelta(hours=24):
                        deadline_soon.append({"id":r[0],"name":r[1],"deadline":r[2]})
                except: pass
    except: pass

    return jsonify({
        "daily_sales": round(daily_sales, 0),
        "weekly_sales": round(weekly_sales, 0),
        "monthly_sales": round(monthly_sales, 0),
        "total_orders": total_orders,
        "completed": completed,
        "top_product": {"name": top_product[0], "count": top_product[1]} if top_product else None,
        "deadline_soon": deadline_soon
    })

@app.route('/admin/team', methods=['GET','POST'])
@login_required
def admin_team():
    """إدارة فريق العمل"""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name','').strip()
            role = request.form.get('role','').strip()
            if name:
                db.session.add(TeamMember(name=name, role=role))
                db.session.commit()
        elif action == 'delete':
            m = TeamMember.query.get(int(request.form.get('id',0)))
            if m: db.session.delete(m); db.session.commit()
    try:
        members = TeamMember.query.filter_by(is_active=True).all()
        return jsonify([{"id":m.id,"name":m.name,"role":m.role} for m in members])
    except:
        return jsonify([])

@app.route('/admin/testimonials', methods=['GET','POST'])
@login_required
def admin_testimonials():
    """إدارة شهادات العملاء"""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            db.session.add(Testimonial(
                name=request.form.get('name','').strip(),
                text=request.form.get('text','').strip(),
                rating=int(request.form.get('rating',5)),
                is_approved=True
            ))
            db.session.commit()
        elif action == 'approve':
            t = Testimonial.query.get(int(request.form.get('id',0)))
            if t: t.is_approved = True; db.session.commit()
        elif action == 'delete':
            t = Testimonial.query.get(int(request.form.get('id',0)))
            if t: db.session.delete(t); db.session.commit()
    try:
        tlist = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
        return jsonify([{"id":t.id,"name":t.name,"text":t.text,"rating":t.rating,"approved":t.is_approved} for t in tlist])
    except:
        return jsonify([])

@app.route('/admin/offers', methods=['GET','POST'])
@login_required
def admin_offers():
    """إدارة العروض الموسمية"""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            db.session.add(SeasonalOffer(
                title=request.form.get('title','').strip(),
                discount_percent=float(request.form.get('discount',0) or 0),
                start_date=datetime.strptime(request.form.get('start',''), '%Y-%m-%dT%H:%M') if request.form.get('start') else datetime.now(timezone.utc),
                end_date=datetime.strptime(request.form.get('end',''), '%Y-%m-%dT%H:%M') if request.form.get('end') else datetime.now(timezone.utc),
                banner_text=request.form.get('banner','').strip(),
                is_active=True
            ))
            db.session.commit()
        elif action == 'toggle':
            o = SeasonalOffer.query.get(int(request.form.get('id',0)))
            if o: o.is_active = not o.is_active; db.session.commit()
        elif action == 'delete':
            o = SeasonalOffer.query.get(int(request.form.get('id',0)))
            if o: db.session.delete(o); db.session.commit()
    try:
        offers = SeasonalOffer.query.order_by(SeasonalOffer.id.desc()).all()
        return jsonify([{"id":o.id,"title":o.title,"discount":o.discount_percent,
            "start":o.start_date.strftime('%Y-%m-%d %H:%M') if o.start_date else "",
            "end":o.end_date.strftime('%Y-%m-%d %H:%M') if o.end_date else "",
            "banner":o.banner_text,"active":o.is_active} for o in offers])
    except:
        return jsonify([])

@app.route('/api/weekly_report')
@login_required
def weekly_report():
    """تقرير أسبوعي"""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    orders = Order.query.filter(Order.order_date >= week_ago).all()
    total_sales = sum(o.cart_total or 0 for o in orders if o.status == "مكتمل")
    total_cost = sum(o.cost_price or 0 for o in orders if o.status == "مكتمل")
    profit = total_sales - total_cost
    by_status = {}
    for o in orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1

    settings = StoreSettings.query.first()
    report_text = "تقرير الأسبوع - انجازك\n"
    report_text += "عدد الطلبات: {}\n".format(len(orders))
    report_text += "المبيعات: {} ر.س\n".format(int(total_sales))
    report_text += "التكاليف: {} ر.س\n".format(int(total_cost))
    report_text += "الأرباح: {} ر.س\n".format(int(profit))
    for s,c in by_status.items():
        report_text += "{}: {}\n".format(s, c)

    wa_link = None
    if settings and settings.whatsapp_number:
        wa_link = "https://wa.me/{}?text={}".format(settings.whatsapp_number, urllib.parse.quote(report_text))

    return jsonify({
        "total_orders": len(orders),
        "sales": round(total_sales,0),
        "cost": round(total_cost,0),
        "profit": round(profit,0),
        "by_status": by_status,
        "wa_link": wa_link
    })


# =================== PUSH NOTIFICATIONS ===================

@app.route('/api/push/vapid_public_key')
def vapid_public_key():
    """مفتاح VAPID العام للـ push notifications"""
    return jsonify({"key": os.environ.get('VAPID_PUBLIC_KEY', '')})

@app.route('/api/push/subscribe', methods=['POST'])
def push_subscribe():
    """حفظ اشتراك push notification"""
    data = request.get_json(silent=True) or {}
    # حفظ الاشتراك في session للبساطة
    session['push_subscription'] = json.dumps(data.get('subscription', {}))
    return jsonify({"status": "success"})

@app.route('/api/order_status_check/<int:order_id>')
def order_status_check(order_id):
    """فحص حالة الطلب - للـ polling"""
    o = Order.query.get(order_id)
    if not o:
        return jsonify({"status": "error"}), 404
    return jsonify({
        "status": "success",
        "order_status": o.status,
        "order_id": o.id
    })




@app.route('/api/chatbot', methods=['POST'])
def ai_chatbot():
    """Chatbot مدعوم بـ Claude AI مع fallback ذكي"""
    data = request.get_json(force=True, silent=True) or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({"status": "error", "message": "الرسالة فارغة"}), 400

    # جلب معلومات المتجر
    settings = StoreSettings.query.first()
    products = Product.query.filter_by(is_active=True).all()
    products_list = "\n".join([f"- {p.name}: {p.price} ر.س ({p.category})" for p in products[:20]])

    bank_info = ""
    if settings and settings.bank_name:
        bank_info = f"البنك: {settings.bank_name}، الاسم: {settings.bank_holder}، IBAN: {settings.bank_iban}"

    wa_number = settings.whatsapp_number if settings else '966536602928'

    # ردود محلية ذكية (fallback بدون AI)
    def get_local_reply(msg):
        m = msg.lower().strip()
        if any(k in m for k in ['الأسعار', 'الاسعار', 'سعر', 'كم سعر', 'كم تكلف', 'التكلفة', 'اسعار', '💰']):
            if products:
                prices = '\n'.join([f"• {p.name}: {p.price} ر.س" for p in products[:8]])
                return f"أسعار خدماتنا 💰:\n{prices}\n\nللمزيد تصفح المتجر أو تواصل معنا عبر الواتساب 📲"
            return "يمكنك تصفح الخدمات والأسعار في الصفحة الرئيسية 💰"
        if any(k in m for k in ['خدمات', 'خدمة', 'ماذا تقدم', 'شنو عندكم', '🎓']):
            if products:
                services = '\n'.join([f"• {p.name} ({p.category})" for p in products[:8]])
                return f"خدماتنا المتاحة 🎓:\n{services}\n\nاضغط على أي خدمة للتفاصيل والطلب ✨"
            return "نقدم خدمات أكاديمية متنوعة! تصفح المتجر لمعرفة التفاصيل 🎓"
        if any(k in m for k in ['دفع', 'تحويل', 'بنك', 'طريقة الدفع', '💳']):
            reply = "طريقة الدفع 💳:\nالتحويل البنكي"
            if bank_info:
                reply += f"\n{bank_info}"
            reply += "\n\nبعد التحويل ارفع الإيصال من صفحة الطلب ✅"
            return reply
        if any(k in m for k in ['مدة', 'وقت', 'كم ياخذ', 'متى يجهز', 'تنفيذ', '✈️', '⏱️']):
            return "مدة التنفيذ ⏱️:\nعادةً من 24 إلى 72 ساعة حسب نوع الخدمة.\nالخدمات المستعجلة متاحة برسوم إضافية ⚡"
        if any(k in m for k in ['تعديل', 'تعديلات', 'مراجعة', '🔄']):
            return "التعديلات 🔄:\nنوفر تعديلات مجانية على جميع الخدمات حتى رضاك التام! ✨\nفقط تواصل معنا عبر الواتساب واطلب التعديل."
        if any(k in m for k in ['طلب', 'حالة طلب', 'طلبي', 'طلباتي', '📦']):
            return "يمكنك متابعة طلبك من صفحة 'طلباتي' 📦\nاضغط على أيقونة المستخدم في الأعلى ثم 'طلباتي' 📝"
        if any(k in m for k in ['مرحبا', 'هلا', 'السلام', 'هاي', 'hi', 'hello']):
            return "أهلاً وسهلاً! 👋\nكيف يمكنني مساعدتك اليوم؟\nيمكنك السؤال عن الخدمات، الأسعار، أو طريقة الطلب 😊"
        if any(k in m for k in ['شكر', 'مشكور', 'تسلم', 'يعطيك العافية']):
            return "العفو! نسعد بخدمتك دائماً 🙏\nلا تتردد بالتواصل معنا لأي استفسار ❤️"
        return None

    # محاولة الرد المحلي أولاً
    local_reply = get_local_reply(user_message)

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        # إذا لا يوجد مفتاح API، استخدم الرد المحلي
        if local_reply:
            return jsonify({"status": "success", "reply": local_reply})
        else:
            return jsonify({"status": "success", "reply": f"شكراً لسؤالك! 😊\nللحصول على إجابة دقيقة، تواصل معنا مباشرة عبر الواتساب 📲\nرقمنا: {wa_number}"})

    system_prompt = f"""أنت مساعد ذكي لمتجر انجازك للخدمات الأكاديمية. ردودك باللغة العربية فقط.
اسم المتجر: انجازك للخدمات الأكاديمية
الخدمات المتاحة:
{products_list}

معلومات الدفع: التحويل البنكي. {bank_info}
رقم الواتساب: {wa_number}

قواعد مهمة:
- ردودك قصيرة ومفيدة (3-5 أسطر كحد أقصى)
- استخدم الإيموجي بشكل معتدل
- لا تخترع معلومات غير موجودة
- إذا سأل عن طلب محدد قله يراجع صفحة "طلباتي"
- إذا أراد التواصل المباشر وجّهه للواتساب
- لا تذكر أنك Claude أو AI، قل فقط أنك مساعد متجر انجازك"""

    # بناء تاريخ المحادثة
    messages = []
    for h in history[-6:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({"role": h['role'], "content": h['content']})
    messages.append({"role": "user", "content": user_message})

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": system_prompt,
                "messages": messages
            },
            timeout=15
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get('content') and len(result['content']) > 0:
                reply = result['content'][0]['text']
                return jsonify({"status": "success", "reply": reply})
            else:
                if local_reply:
                    return jsonify({"status": "success", "reply": local_reply})
                return jsonify({"status": "success", "reply": "عذراً، لم أتمكن من الرد. تواصل معنا عبر الواتساب 📲", "show_wa": True, "wa_number": wa_number})
        else:
            # في حالة فشل API، استخدم الرد المحلي
            app.logger.warning(f"Chatbot API returned {resp.status_code}: {resp.text[:200]}")
            if local_reply:
                return jsonify({"status": "success", "reply": local_reply})
            return jsonify({"status": "success", "reply": "شكراً لسؤالك! 😊\nتواصل معنا مباشرة عبر الواتساب للحصول على إجابة فورية 📲", "show_wa": True, "wa_number": wa_number})
    except Exception as e:
        app.logger.error(f"Chatbot error: {e}")
        if local_reply:
            return jsonify({"status": "success", "reply": local_reply})
        return jsonify({"status": "success", "reply": "تعذر الاتصال حالياً. تواصل معنا عبر الواتساب 📲", "show_wa": True, "wa_number": wa_number})



# =================== WHATSAPP BOT ROUTES ===================

# إعدادات واتساب بيزنس (يجب إضافتها في Environment Variables)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "enjazk_secret_token")

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """مسار استقبال رسائل واتساب (Webhook)"""
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid verification token", 403

    if request.method == "POST":
        data = request.get_json(silent=True)
        if data and data.get("object") == "whatsapp_business_account":
            try:
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        if "messages" in value:
                            for msg in value["messages"]:
                                sender = msg["from"]
                                if "text" in msg:
                                    text = msg["text"]["body"]
                                    process_whatsapp_message(sender, text)
            except Exception as e:
                app.logger.error(f"Error processing webhook: {e}")
        return jsonify({"status": "ok"}), 200

def process_whatsapp_message(sender, text):
    """معالجة الرسالة الواردة وإرسال الرد المناسب"""
    text = text.lower().strip()
    reply = ""

    if any(word in text for word in ['سعر', 'تكلفة', 'كم', 'الأسعار', 'اسعار']):
        reply = "أسعارنا تبدأ من *5 ر.س* وتختلف حسب نوع الخدمة وحجمها. 💰\n\nيمكنك مشاهدة أسعار كل خدمة في صفحة المتجر، أو تواصل معنا للحصول على عرض سعر مخصص."
    elif any(word in text for word in ['طلب', 'حالة', 'اين طلبي', 'وين طلبي']):
        reply = "لمتابعة حالة طلبك: 📦\n\nقم بزيارة متجرنا واضغط على 'طلباتي' من القائمة العلوية وأدخل رقم جوالك."
    elif any(word in text for word in ['خدم', 'ماذا تقدمون', 'وش تقدمون', 'خدمات']):
        reply = "نقدم مجموعة متنوعة من الخدمات الأكاديمية: 🎓\n\n📝 *بحوث ورسائل*\n📊 *تقارير ودراسات*\n🎯 *مشاريع تخرج*\n📚 *ملخصات ومراجعات*\n💻 *عروض PowerPoint*\n\nتصفّح المتجر للاطلاع على جميع خياراتنا."
    elif any(word in text for word in ['دفع', 'تحويل', 'ايبان', 'بنك']):
        settings = StoreSettings.query.first()
        bank_info = f"\nالبنك: {settings.bank_name}\nالاسم: {settings.bank_holder}\nالحساب: {settings.bank_account}\nالآيبان: {settings.bank_iban}" if settings and settings.bank_name else ""
        reply = f"طريقة الدفع: 💳\n\nعن طريق *التحويل البنكي*{bank_info}\n\nبعد تأكيد الطلب تستلم بيانات الحساب وترفع إيصال التحويل من صفحة طلباتك."
    elif any(word in text for word in ['مدة', 'وقت', 'متى', 'سرعة', 'كم يوم']):
        reply = "مدة التنفيذ تعتمد على نوع وحجم الطلب: ⏱️\n\n⚡ *الطلبات البسيطة:* 24-48 ساعة\n📄 *البحوث المتوسطة:* 3-5 أيام\n📚 *المشاريع الكبيرة:* يتفق مسبقاً"
    elif any(word in text for word in ['تعديل', 'تغيير', 'تصحيح']):
        reply = "نوفر تعديلات مجانية! 🔄\n\n✅ تعديل مجاني حتى رضاك التام\n✅ سرعة في تنفيذ التعديلات"
    elif any(word in text for word in ['مرحبا', 'اهلا', 'هلا', 'السلام']):
        reply = "أهلاً وسهلاً بك في متجر إنجازك! 😊\n\nكيف يمكنني مساعدتك؟ يمكنك سؤالي عن (الأسعار، الخدمات، حالة طلبك، طرق الدفع)."
    else:
        reply = "عذراً، لم أفهم طلبك بوضوح 😅\n\nيمكنني مساعدتك في الإجابة عن أسئلة بخصوص (الأسعار، الخدمات، حالة طلبك، وطريقة الدفع). سيقوم فريقنا بمراجعة رسالتك والرد عليك قريباً."

    send_whatsapp_message(sender, reply)

def send_whatsapp_message(to, message):
    """إرسال الرسالة عبر API واتساب الرسمي"""
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        return
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        app.logger.error(f"WhatsApp API Error: {e}")


# =================== LOGIN HTML ===================
PRODUCT_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>{{ product.name }} | انجازك</title>
<link rel="icon" type="image/png" href="data:image/png;base64,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">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
{% raw %}<style>
body{font-family:'IBM Plex Sans Arabic',sans-serif;background:#f8fafc;}
.btn-dark{background:#0f172a;color:white;transition:all .25s;}
.btn-dark:hover{background:#1e293b;}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);transition:transform .4s;opacity:0;z-index:9999;}
#toast.show{transform:translateX(-50%) translateY(0);opacity:1;}
.wa-float{position:fixed;bottom:24px;right:24px;z-index:150;width:56px;height:56px;background:#25d366;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:26px;box-shadow:0 6px 20px rgba(37,211,102,.4);transition:all .3s;text-decoration:none;}
.wa-float:hover{transform:scale(1.1);}
</style>{% endraw %}
</head>
<body>

<!-- Header -->
<header class="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100 shadow-sm">
  <div class="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
    <a href="/" class="flex items-center gap-3">
      <img src="data:image/png;base64,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" class="w-10 h-10 rounded-full object-cover shadow-sm" alt="انجازك">
      <div>
        <h1 class="text-xl font-bold leading-tight">انجازك</h1>
        <span class="text-[9px] text-amber-700 font-bold uppercase tracking-widest">للخدمات الاكاديمية</span>
      </div>
    </a>
    <a href="/" class="flex items-center gap-2 text-slate-600 hover:text-slate-900 text-sm font-bold transition-all">
      <i class="fas fa-arrow-right"></i> العودة للمتجر
    </a>
  </div>
</header>

<main class="max-w-5xl mx-auto px-4 py-10">
  <!-- Breadcrumb -->
  <div class="flex items-center gap-2 text-xs text-slate-400 mb-8">
    <a href="/" class="hover:text-amber-600 transition-all">الرئيسية</a>
    <i class="fas fa-chevron-left text-[10px]"></i>
    <span class="text-amber-600 font-bold">{{ product.name }}</span>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-16">
    <!-- Image -->
    <div class="relative">
      <div class="aspect-[4/3] rounded-3xl overflow-hidden bg-slate-100 shadow-xl">
        <img src="{{ product.image_data if product.image_data else 'https://placehold.co/600x450/0f172a/white?text=Enjazk' }}"
          class="w-full h-full object-cover"
          onerror="this.src='https://placehold.co/600x450/0f172a/white?text=Enjazk'">
      </div>
      {% if product.old_price %}
      <div class="absolute top-4 right-4 bg-red-500 text-white text-sm font-black px-3 py-1.5 rounded-full shadow-lg">
        خصم {{ ((product.old_price - product.price) / product.old_price * 100)|int }}%
      </div>
      {% endif %}
      <div class="absolute top-4 left-4 bg-white/90 text-amber-700 text-xs font-bold px-3 py-1.5 rounded-full">
        {{ product.category }}
      </div>
    </div>

    <!-- Details -->
    <div class="flex flex-col justify-between">
      <div>
        <h1 class="text-3xl font-black text-slate-900 mb-4">{{ product.name }}</h1>
        {% if product.old_price %}
        <p class="text-slate-400 line-through text-sm mb-1">{{ product.old_price }} ر.س</p>
        {% endif %}
        <p class="text-4xl font-black text-amber-600 mb-6">{{ product.price }} <span class="text-lg font-normal text-slate-500">ر.س</span></p>

        {% if product.description %}
        <div class="bg-slate-50 rounded-2xl p-5 mb-6">
          <h3 class="font-bold text-slate-700 mb-3 flex items-center gap-2"><i class="fas fa-info-circle text-amber-600"></i> تفاصيل الخدمة</h3>
          <p class="text-slate-600 text-sm leading-relaxed">{{ product.description }}</p>
        </div>
        {% endif %}

        <!-- Features -->
        <div class="space-y-3 mb-6">
          <div class="flex items-center gap-3 text-sm text-slate-600"><div class="w-8 h-8 bg-green-100 rounded-xl flex items-center justify-center"><i class="fas fa-check text-green-600 text-xs"></i></div> جودة عالية ومضمونة</div>
          <div class="flex items-center gap-3 text-sm text-slate-600"><div class="w-8 h-8 bg-blue-100 rounded-xl flex items-center justify-center"><i class="fas fa-clock text-blue-600 text-xs"></i></div> التزام تام بالمواعيد</div>
          <div class="flex items-center gap-3 text-sm text-slate-600"><div class="w-8 h-8 bg-purple-100 rounded-xl flex items-center justify-center"><i class="fas fa-shield-alt text-purple-600 text-xs"></i></div> سرية تامة لبياناتك</div>
          <div class="flex items-center gap-3 text-sm text-slate-600"><div class="w-8 h-8 bg-amber-100 rounded-xl flex items-center justify-center"><i class="fas fa-redo text-amber-600 text-xs"></i></div> تعديلات مجانية</div>
        </div>
      </div>

      <!-- Action Buttons -->
      {% if product.stock != 0 %}
      <div class="space-y-3">
        <button onclick="openOrderModal()" class="w-full btn-dark py-4 rounded-2xl font-black text-lg shadow-xl flex items-center justify-center gap-3">
          <i class="fas fa-paper-plane"></i> اطلب الآن
        </button>
        <button onclick="shareProduct()" class="w-full border-2 border-slate-200 text-slate-600 hover:border-amber-500 hover:text-amber-600 py-4 rounded-2xl font-bold transition-all flex items-center justify-center gap-2">
          <i class="fas fa-share-alt"></i> مشاركة الخدمة
        </button>
        <a href="{{ settings.whatsapp }}?text={{ ('استفسار عن خدمة: ' + product.name)|urlencode }}" target="_blank"
          class="w-full bg-green-500 hover:bg-green-600 text-white py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all">
          <i class="fab fa-whatsapp"></i> استفسر عبر واتساب
        </a>
      </div>
      {% else %}
      <div class="bg-red-50 border border-red-200 rounded-2xl p-4 text-center">
        <p class="text-red-600 font-bold">نفذت الكمية حالياً</p>
        <a href="{{ settings.whatsapp }}" target="_blank" class="text-sm text-green-600 hover:underline mt-1 block">تواصل معنا للاستفسار</a>
      </div>
      {% endif %}
    </div>
  </div>

  <!-- FAQ Section -->
  <div class="bg-white rounded-3xl p-8 shadow-sm mb-10">
    <h2 class="text-2xl font-black text-slate-900 mb-6 flex items-center gap-3"><i class="fas fa-question-circle text-amber-600"></i> أسئلة شائعة</h2>
    <div class="space-y-4" id="faqList">
      <div class="faq-item border border-slate-100 rounded-2xl overflow-hidden">
        <button onclick="toggleFaq(this)" class="w-full flex justify-between items-center p-4 text-right font-bold text-slate-700 hover:bg-slate-50 transition-all">
          <span>كم يستغرق تنفيذ الطلب؟</span><i class="fas fa-chevron-down text-amber-600 transition-transform"></i>
        </button>
        <div class="faq-answer hidden px-4 pb-4 text-sm text-slate-500 leading-relaxed">يتوقف على حجم ومتطلبات الطلب. نحدد الموعد بدقة عند استلام الطلب وتفاصيله.</div>
      </div>
      <div class="faq-item border border-slate-100 rounded-2xl overflow-hidden">
        <button onclick="toggleFaq(this)" class="w-full flex justify-between items-center p-4 text-right font-bold text-slate-700 hover:bg-slate-50 transition-all">
          <span>هل يمكن التعديل بعد التسليم؟</span><i class="fas fa-chevron-down text-amber-600 transition-transform"></i>
        </button>
        <div class="faq-answer hidden px-4 pb-4 text-sm text-slate-500 leading-relaxed">نعم، نوفر تعديلات مجانية لضمان رضاك التام عن العمل المقدم.</div>
      </div>
      <div class="faq-item border border-slate-100 rounded-2xl overflow-hidden">
        <button onclick="toggleFaq(this)" class="w-full flex justify-between items-center p-4 text-right font-bold text-slate-700 hover:bg-slate-50 transition-all">
          <span>كيف يتم الدفع؟</span><i class="fas fa-chevron-down text-amber-600 transition-transform"></i>
        </button>
        <div class="faq-answer hidden px-4 pb-4 text-sm text-slate-500 leading-relaxed">عبر التحويل البنكي بعد تأكيد الطلب، ثم ترفع إيصال التحويل من خلال الموقع.</div>
      </div>
      <div class="faq-item border border-slate-100 rounded-2xl overflow-hidden">
        <button onclick="toggleFaq(this)" class="w-full flex justify-between items-center p-4 text-right font-bold text-slate-700 hover:bg-slate-50 transition-all">
          <span>هل بياناتي سرية؟</span><i class="fas fa-chevron-down text-amber-600 transition-transform"></i>
        </button>
        <div class="faq-answer hidden px-4 pb-4 text-sm text-slate-500 leading-relaxed">نعم بالكامل، جميع بيانات العملاء سرية ولا تُشارك مع أي طرف ثالث.</div>
      </div>
    </div>
  </div>

  <!-- Related Products -->
  {% if related %}
  <div>
    <h2 class="text-2xl font-black text-slate-900 mb-6">خدمات مشابهة</h2>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-5">
      {% for r in related %}
      <a href="/product/{{ r.id }}" class="bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all group">
        <div class="aspect-[4/3] overflow-hidden">
          <img src="{{ r.image_data if r.image_data else 'https://placehold.co/400x300/0f172a/white?text=Enjazk' }}"
            class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onerror="this.src='https://placehold.co/400x300/0f172a/white?text=Enjazk'">
        </div>
        <div class="p-4">
          <h4 class="font-bold text-slate-800 text-sm mb-1 truncate">{{ r.name }}</h4>
          <p class="text-amber-600 font-black">{{ r.price }} ر.س</p>
        </div>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}
</main>

<!-- ORDER MODAL -->
<div id="orderModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[110]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative">
    <button onclick="closeModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <div class="text-center mb-6">
      <p class="text-amber-600 text-xs font-bold uppercase tracking-widest mb-1">طلب خدمة</p>
      <h3 class="text-xl font-black text-slate-900">{{ product.name }}</h3>
      <p class="text-2xl font-black text-amber-600 mt-1" id="modalPrice">{{ product.price }} <span class="text-lg font-normal text-slate-500">ر.س</span></p>
      <p id="couponDiscount" class="text-xs text-green-600 font-bold mt-1 hidden"></p>
    </div>
    <div class="space-y-4">
      <div class="relative"><i class="fas fa-user absolute right-4 top-4 text-slate-300"></i>
        <input id="oName" placeholder="اسمك الكريم *" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div class="relative"><i class="fas fa-phone absolute right-4 top-4 text-slate-300"></i>
        <input id="oPhone" type="tel" placeholder="رقم الجوال *" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div>
        <textarea id="oNotes" placeholder="تفاصيل طلبك (مطلوب) - المستوى الدراسي، التخصص، الموعد النهائي..." class="w-full p-4 bg-amber-50 border-2 border-amber-200 rounded-2xl focus:border-amber-500 outline-none text-sm h-28 resize-none"></textarea>
        <p class="text-[11px] text-amber-600 font-bold mt-1 flex items-center gap-1"><i class="fas fa-exclamation-circle"></i> هذا الحقل مطلوب</p>
      </div>
      <!-- Coupon -->
      <div class="bg-slate-50 rounded-2xl p-3 border border-slate-100">
        <div class="flex gap-2">
          <input id="oCoupon" placeholder="كود الخصم (اختياري)" class="flex-grow p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500" style="text-transform:uppercase">
          <button onclick="applyProductCoupon()" class="bg-amber-100 text-amber-700 px-4 py-3 rounded-xl font-bold text-xs hover:bg-amber-200 transition-all whitespace-nowrap">تطبيق</button>
        </div>
        <p id="oCouponMsg" class="text-xs mt-2 font-bold hidden"></p>
      </div>
      <button onclick="submitOrder()" id="submitBtn" class="w-full btn-dark py-4 rounded-2xl font-black shadow-xl flex items-center justify-center gap-3">
        ارسال الطلب <i class="fas fa-paper-plane"></i>
      </button>
    </div>
  </div>
</div>

<!-- SUCCESS MODAL -->
<div id="successModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[120]">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl text-center">
    <div class="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-check text-green-500 text-3xl"></i></div>
    <h3 class="text-xl font-black mb-2">تم استلام طلبك!</h3>
    <p id="successNum" class="text-amber-600 font-bold text-sm mb-4"></p>
    <div id="bankInfoDiv" style="display:none" class="bg-blue-50 border border-blue-100 rounded-2xl p-4 mb-4 text-right">
      <p class="text-xs font-black text-blue-800 mb-2"><i class="fas fa-university ml-1"></i>بيانات التحويل</p>
      <p class="text-xs text-slate-600 mb-1">البنك: <span id="bName" class="font-bold"></span></p>
      <p class="text-xs text-slate-600 mb-1">الاسم: <span id="bHolder" class="font-bold"></span></p>
      <div class="flex justify-between items-center bg-white rounded-xl p-2 mt-2">
        <span id="bAccount" class="text-xs font-mono font-bold"></span>
        <button onclick="copyEl('bAccount')" class="text-[10px] bg-blue-100 text-blue-700 px-2 py-1 rounded-lg font-bold">نسخ</button>
      </div>
      <div class="flex justify-between items-center bg-white rounded-xl p-2 mt-1">
        <span id="bIban" class="text-xs font-mono font-bold"></span>
        <button onclick="copyEl('bIban')" class="text-[10px] bg-blue-100 text-blue-700 px-2 py-1 rounded-lg font-bold">نسخ</button>
      </div>
    </div>
    <div class="space-y-2">
      <button onclick="document.getElementById('successModal').style.display='none';openReceiptModal();" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-3 rounded-2xl font-bold text-sm transition-all flex items-center justify-center gap-2">
        <i class="fas fa-file-invoice"></i> رفع ايصال التحويل
      </button>
      <a href="/" class="w-full bg-slate-100 text-slate-700 py-3 rounded-2xl font-bold text-sm hover:bg-slate-200 transition-all flex items-center justify-center gap-2 block text-center">العودة للمتجر</a>
    </div>
  </div>
</div>

<!-- RECEIPT MODAL -->
<div id="receiptModal" style="display:none" class="fixed inset-0 bg-slate-900/70 backdrop-blur-md flex items-center justify-center p-4 z-[130]">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl relative">
    <button onclick="document.getElementById('receiptModal').style.display='none'" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500"><i class="fas fa-times"></i></button>
    <div class="text-center mb-5">
      <div class="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-file-invoice text-amber-600 text-2xl"></i></div>
      <h3 class="text-lg font-black">رفع ايصال التحويل</h3>
      <p id="receiptOrderNum" class="text-amber-600 font-bold text-sm mt-1"></p>
    </div>
    <div id="receiptPreviewArea" style="display:none" class="mb-4"><img id="receiptPreview" src="" class="w-full rounded-2xl border max-h-48 object-contain"></div>
    <label class="block cursor-pointer mb-4">
      <div class="border-2 border-dashed border-amber-300 bg-amber-50 rounded-2xl p-5 text-center hover:bg-amber-100 transition-all">
        <i class="fas fa-cloud-upload-alt text-amber-500 text-2xl block mb-2"></i>
        <p class="text-sm font-bold text-amber-700">اضغط لاختيار صورة الايصال</p>
      </div>
      <input type="file" id="receiptFile" accept="image/*" class="hidden" onchange="previewRec(this)">
    </label>
    <button onclick="submitRec()" id="submitRecBtn" disabled class="w-full bg-amber-600 text-white py-4 rounded-2xl font-black text-sm disabled:opacity-40">ارسال الايصال</button>
  </div>
</div>

<!-- TOAST -->
<div id="toast" class="bg-green-500 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 text-sm font-bold"><i class="fas fa-check-circle"></i><span id="toastMsg"></span></div>

<a href="{{ settings.whatsapp }}" target="_blank" class="wa-float"><i class="fab fa-whatsapp"></i></a>

<script>
var productName = {{ product.name|tojson }};
var productPrice = {{ product.price }};
var currentOrderId = null;

// Check session for logged in customer
async function checkSession(){
  try{
    var r=await fetch('/api/customer/me');
    var d=await r.json();
    if(d.status==='logged_in'){
      document.getElementById('oName').value=d.name;
      document.getElementById('oPhone').value=d.phone;
      document.getElementById('oName').readOnly=true;
      document.getElementById('oPhone').readOnly=true;
      document.getElementById('oName').style.background='#f8fafc';
      document.getElementById('oPhone').style.background='#f8fafc';
    }
  }catch(e){}
}

function openOrderModal(){
  fetch('/api/customer/me').then(function(r){return r.json();}).then(function(d){
    if(d.status!=='logged_in'){
      window.location='/?login=1&redirect='+encodeURIComponent(window.location.pathname);
    } else {
      document.getElementById('orderModal').style.display='flex';
      document.body.style.overflow='hidden';
      checkSession();
    }
  });
}
function closeModal(){
  document.getElementById('orderModal').style.display='none';
  document.body.style.overflow='';
}

async function submitOrder(){
  var name=document.getElementById('oName').value.trim();
  var phone=document.getElementById('oPhone').value.trim();
  var notes=document.getElementById('oNotes').value.trim();
  var coupon=document.getElementById('oCoupon').value.trim().toUpperCase();
  var btn=document.getElementById('submitBtn');
  if(!name){document.getElementById('oName').focus();return;}
  if(!phone){document.getElementById('oPhone').focus();return;}
  if(!notes){document.getElementById('oNotes').focus();showToast('يرجى كتابة تفاصيل طلبك',false);return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> جاري الارسال...';
  try{
    var payload={name:name,phone:phone,notes:notes,
      product_name:productName,cart:[{name:productName,price:productPrice,qty:1}]};
    if(coupon) payload.coupon=coupon;
    var r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)});
    var d=await r.json();
    if(d.status==='success'){
      closeModal();
      currentOrderId=d.order_id;
      document.getElementById('successNum').innerText='رقم طلبك: #'+d.order_id;
      document.getElementById('receiptOrderNum').innerText='طلب #'+d.order_id;
      if(d.bank_info&&d.bank_info.bank_name){
        document.getElementById('bName').innerText=d.bank_info.bank_name;
        document.getElementById('bHolder').innerText=d.bank_info.bank_holder;
        document.getElementById('bAccount').innerText=d.bank_info.bank_account;
        document.getElementById('bIban').innerText=d.bank_info.bank_iban;
        document.getElementById('bankInfoDiv').style.display='block';
      }
      document.getElementById('successModal').style.display='flex';
    } else showToast(d.message||'حدث خطأ',false);
  }catch(e){showToast('تعذر الاتصال',false);}
  btn.disabled=false;btn.innerHTML='ارسال الطلب <i class="fas fa-paper-plane"></i>';
}

async function applyProductCoupon(){
  var code=document.getElementById('oCoupon').value.trim().toUpperCase();
  var msg=document.getElementById('oCouponMsg');
  var discountEl=document.getElementById('couponDiscount');
  var priceEl=document.getElementById('modalPrice');
  if(!code){msg.innerText='أدخل كود الخصم';msg.className='text-xs mt-2 font-bold text-red-500';msg.classList.remove('hidden');return;}
  try{
    var r=await fetch('/api/validate_coupon',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:code,total:productPrice})});
    var d=await r.json();
    if(d.status==='success'){
      msg.innerText=d.desc+' - تم خصم '+d.discount+' ر.س';
      msg.className='text-xs mt-2 font-bold text-green-600';
      msg.classList.remove('hidden');
      discountEl.innerText='السعر بعد الخصم: '+(d.new_total||productPrice)+' ر.س';
      discountEl.classList.remove('hidden');
      priceEl.style.textDecoration='line-through';
      priceEl.style.color='#94a3b8';
      priceEl.style.fontSize='1.25rem';
      productPrice=d.new_total||productPrice;
    } else {
      msg.innerText=d.message||'كود غير صحيح';
      msg.className='text-xs mt-2 font-bold text-red-500';
      msg.classList.remove('hidden');
    }
  }catch(e){msg.innerText='تعذر التحقق';msg.className='text-xs mt-2 font-bold text-red-500';msg.classList.remove('hidden');}
}

function openReceiptModal(){
  document.getElementById('receiptModal').style.display='flex';
}

function previewRec(input){
  if(!input.files||!input.files[0])return;
  var reader=new FileReader();
  reader.onload=function(e){
    document.getElementById('receiptPreview').src=e.target.result;
    document.getElementById('receiptPreviewArea').style.display='block';
    document.getElementById('submitRecBtn').disabled=false;
  };
  reader.readAsDataURL(input.files[0]);
}

async function submitRec(){
  if(!currentOrderId)return;
  var file=document.getElementById('receiptFile').files[0];
  if(!file)return;
  var btn=document.getElementById('submitRecBtn');
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  var fd=new FormData();fd.append('receipt',file);
  try{
    var r=await fetch('/api/upload_receipt/'+currentOrderId,{method:'POST',body:fd});
    var d=await r.json();
    if(d.status==='success'){
      document.getElementById('receiptModal').style.display='none';
      showToast('تم رفع الايصال بنجاح!',true);
    }
  }catch(e){}
  btn.disabled=false;btn.innerHTML='ارسال الايصال';
}

function copyEl(id){
  var el=document.getElementById(id);
  navigator.clipboard.writeText(el.innerText).then(function(){showToast('تم النسخ!',true);});
}

function shareProduct(){
  var url=window.location.href;
  var text=productName+' - '+productPrice+' ر.س - انجازك للخدمات الاكاديمية - '+url;
  if(navigator.share)navigator.share({title:productName,text:text,url:url});
  else window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank');
}

function toggleFaq(btn){
  var answer=btn.nextElementSibling;
  var icon=btn.querySelector('i');
  var isOpen=!answer.classList.contains('hidden');
  document.querySelectorAll('.faq-answer').forEach(function(a){a.classList.add('hidden');});
  document.querySelectorAll('.faq-item i').forEach(function(i){i.style.transform='';});
  if(!isOpen){answer.classList.remove('hidden');icon.style.transform='rotate(180deg)';}
}

function showToast(msg,ok){
  var t=document.getElementById('toast');
  document.getElementById('toastMsg').innerText=msg;
  t.className=(ok?'bg-green-500':'bg-red-500')+' text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 text-sm font-bold';
  t.classList.add('show');
  setTimeout(function(){t.classList.remove('show');},4000);
}

document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
</script>
</body></html>"""


CUSTOMERS_INVOICES_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>العملاء وإيصالات الشراء | إنجازك</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
{% raw %}<style>
body{font-family:'IBM Plex Sans Arabic',sans-serif;background:#f8fafc;}
.tab.active{background:#0f172a;color:#fff;}
tbody tr.hide{display:none;}
</style>{% endraw %}
</head>
<body class="min-h-screen text-slate-900">
<nav class="bg-white border-b border-slate-200 sticky top-0 z-30">
  <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
    <div class="flex items-center gap-3 min-w-0">
      <div class="w-10 h-10 bg-slate-900 text-white rounded-xl flex items-center justify-center"><i class="fas fa-address-book"></i></div>
      <div class="min-w-0">
        <h1 class="font-black text-base truncate">إدارة العملاء وإيصالات الشراء</h1>
        <p class="text-[11px] text-slate-500">واجهة مستقلة لمراجعة العملاء وإيصالات الشراء</p>
      </div>
    </div>
    <div class="flex gap-2 flex-wrap justify-end">
      <a href="/cp" class="text-xs bg-slate-100 hover:bg-slate-200 px-3 py-2 rounded-xl font-bold"><i class="fas fa-gauge ml-1"></i>لوحة التحكم</a>
      <a href="/admin/export_invoices" class="text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-700 px-3 py-2 rounded-xl font-bold"><i class="fas fa-file-csv ml-1"></i>تصدير CSV</a>
      <a href="/logout" class="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-2 rounded-xl font-bold"><i class="fas fa-sign-out-alt ml-1"></i>خروج</a>
    </div>
  </div>
</nav>

<main class="max-w-7xl mx-auto px-4 py-6 space-y-6">
  <section class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <div class="bg-white border border-slate-200 rounded-2xl p-5">
      <p class="text-xs text-slate-500 font-bold">عدد العملاء</p>
      <p class="text-3xl font-black mt-1">{{ customers_count }}</p>
    </div>
    <div class="bg-white border border-slate-200 rounded-2xl p-5">
      <p class="text-xs text-slate-500 font-bold">عدد إيصالات الشراء</p>
      <p class="text-3xl font-black mt-1">{{ invoices_count }}</p>
    </div>
    <div class="bg-white border border-slate-200 rounded-2xl p-5">
      <p class="text-xs text-slate-500 font-bold">مبيعات مكتملة</p>
      <p class="text-3xl font-black mt-1 text-emerald-600">{{ "%.0f"|format(completed_sales) }} ر.س</p>
    </div>
  </section>

  <section class="bg-white border border-slate-200 rounded-2xl p-4">
    <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-4">
      <div class="flex bg-slate-100 rounded-xl p-1 w-fit">
        <button id="tabCustomers" onclick="showPanel('customers')" class="tab active px-4 py-2 rounded-lg text-xs font-black">بيانات العملاء</button>
        <button id="tabInvoices" onclick="showPanel('invoices')" class="tab px-4 py-2 rounded-lg text-xs font-black">إيصالات الشراء</button>
        <button id="tabReviews" onclick="showPanel('reviews')" class="tab px-4 py-2 rounded-lg text-xs font-black">تقييمات العملاء</button>
      </div>
      <div class="relative w-full lg:w-96">
        <i class="fas fa-search absolute right-3 top-3 text-slate-400 text-xs"></i>
        <input id="searchBox" oninput="filterRows()" placeholder="بحث بالاسم، الجوال، رقم الطلب..." class="w-full pr-9 pl-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-slate-900">
      </div>
    </div>

    <div id="panelCustomers" class="overflow-x-auto">
      <table class="w-full text-right min-w-[820px]">
        <thead>
          <tr class="border-b border-slate-200 text-[11px] text-slate-500">
            <th class="py-3">العميل</th><th>الجوال</th><th>البريد</th><th>عدد الطلبات</th><th>إجمالي مكتمل</th><th>آخر طلب</th><th>تاريخ التسجيل</th>
          </tr>
        </thead>
        <tbody id="customersRows">
          {% for c in customers %}
          <tr class="border-b border-slate-100 hover:bg-slate-50" data-search="{{ c.name }} {{ c.phone }} {{ c.email }}">
            <td class="py-3 font-bold">{{ c.name }}</td>
            <td class="font-mono text-xs"><a class="text-blue-600 hover:underline" href="tel:{{ c.phone }}">{{ c.phone }}</a></td>
            <td class="text-xs text-slate-500">{{ c.email or '-' }}</td>
            <td><span class="bg-blue-50 text-blue-700 text-xs font-bold px-2 py-1 rounded-lg">{{ c.orders_count }}</span></td>
            <td class="font-black text-emerald-600">{{ "%.0f"|format(c.total_spent) }} ر.س</td>
            <td class="text-xs text-slate-500">{{ c.last_order or '-' }}</td>
            <td class="text-xs text-slate-500">{{ c.created_at or '-' }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% if not customers %}<p class="text-center text-slate-400 text-sm py-12">لا يوجد عملاء مسجلون</p>{% endif %}
    </div>

    <div id="panelInvoices" class="overflow-x-auto hidden">
      <table class="w-full text-right min-w-[920px]">
        <thead>
          <tr class="border-b border-slate-200 text-[11px] text-slate-500">
            <th class="py-3">رقم الإيصال</th><th>العميل</th><th>الجوال</th><th>الخدمة</th><th>التاريخ</th><th>الحالة</th><th>الإجمالي</th><th class="text-center">الإجراءات</th>
          </tr>
        </thead>
        <tbody id="invoicesRows">
          {% for inv in invoices %}
          <tr class="border-b border-slate-100 hover:bg-slate-50" data-search="{{ inv.id }} {{ inv.customer_name }} {{ inv.customer_phone }} {{ inv.status }} {{ inv.product }}">
            <td class="py-3 font-black">#{{ inv.id }}</td>
            <td class="font-bold">{{ inv.customer_name }}</td>
            <td class="font-mono text-xs">{{ inv.customer_phone }}</td>
            <td class="text-xs text-slate-500 max-w-[180px] truncate">{{ inv.product or '-' }}</td>
            <td class="text-xs text-slate-500">{{ inv.date }}</td>
            <td><span class="text-[11px] px-2 py-1 rounded-lg font-bold {% if inv.status == 'مكتمل' %}bg-emerald-50 text-emerald-700{% else %}bg-slate-100 text-slate-600{% endif %}">{{ inv.status }}</span></td>
            <td class="font-black text-emerald-600">{{ "%.0f"|format(inv.total) }} ر.س</td>
            <td>
              <div class="flex justify-center gap-2">
                <button onclick="downloadInvoice({{ inv.id }})" class="text-[11px] bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded-lg font-bold hover:bg-indigo-100"><i class="fas fa-download ml-1"></i>PDF</button>
                <button onclick="sendInvoice({{ inv.id }})" class="text-[11px] bg-green-50 text-green-700 px-3 py-1.5 rounded-lg font-bold hover:bg-green-100"><i class="fab fa-whatsapp ml-1"></i>واتساب</button>
              </div>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% if not invoices %}<p class="text-center text-slate-400 text-sm py-12">لا توجد إيصالات شراء</p>{% endif %}
    </div>

    <div id="panelReviews" class="overflow-x-auto hidden">
      <table class="w-full text-right min-w-[700px]">
        <thead>
          <tr class="border-b border-slate-200 text-[11px] text-slate-500">
            <th class="py-3">العميل</th><th>رقم الطلب</th><th>التقييم</th><th>التعليق</th><th>التاريخ</th>
          </tr>
        </thead>
        <tbody id="reviewsRows">
          {% for r in reviews %}
          <tr class="border-b border-slate-100 hover:bg-slate-50" data-search="{{ r.customer_name }} {{ r.order_id }} {{ r.comment }}">
            <td class="py-3 font-bold">{{ r.customer_name or 'عميل' }}</td>
            <td class="font-mono text-xs">#{{ r.order_id }}</td>
            <td>
              <div class="flex gap-0.5">
                {% for i in range(5) %}
                <i class="fas fa-star text-[10px] {{ 'text-amber-400' if i < r.rating else 'text-slate-200' }}"></i>
                {% endfor %}
              </div>
            </td>
            <td class="text-xs text-slate-500 max-w-[300px] truncate">{{ r.comment or '-' }}</td>
            <td class="text-xs text-slate-500">{{ r.created_at }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% if not reviews %}<p class="text-center text-slate-400 text-sm py-12">لا توجد تقييمات بعد</p>{% endif %}
    </div>
  </section>
</main>

<script>
var activePanel='customers';
function showPanel(panel){
  activePanel=panel;
  document.getElementById('panelCustomers').classList.toggle('hidden',panel!=='customers');
  document.getElementById('panelInvoices').classList.toggle('hidden',panel!=='invoices');
  document.getElementById('panelReviews').classList.toggle('hidden',panel!=='reviews');
  document.getElementById('tabCustomers').classList.toggle('active',panel==='customers');
  document.getElementById('tabInvoices').classList.toggle('active',panel==='invoices');
  document.getElementById('tabReviews').classList.toggle('active',panel==='reviews');
  filterRows();
}
function filterRows(){
  var q=document.getElementById('searchBox').value.trim().toLowerCase();
  var selector;
  if(activePanel==='customers') selector='#customersRows tr';
  else if(activePanel==='invoices') selector='#invoicesRows tr';
  else selector='#reviewsRows tr';
  document.querySelectorAll(selector).forEach(function(row){
    row.classList.toggle('hide', q && !row.dataset.search.toLowerCase().includes(q));
  });
}
function downloadInvoice(id){
  window.open('/api/download_invoice/'+id,'_blank');
}
async function sendInvoice(id){
  try{
    var r=await fetch('/api/send_invoice_wa/'+id);
    var d=await r.json();
    if(d.wa_link)window.open(d.wa_link,'_blank');
  }catch(e){
    alert('تعذر إنشاء رابط واتساب');
  }
}
</script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>تسجيل الدخول | انجازك</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{font-family:'IBM Plex Sans Arabic',sans-serif;}</style>
</head>
<body class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
<div class="w-full max-w-md">
  <div class="text-center mb-10">
    <div class="w-20 h-20 bg-amber-600 rounded-3xl flex items-center justify-center text-white mx-auto mb-4 shadow-2xl"><i class="fas fa-graduation-cap text-3xl"></i></div>
    <h1 class="text-3xl font-black text-white">انجازك</h1>
    <p class="text-slate-400 text-sm mt-1">لوحة ادارة المتجر</p>
  </div>
  <div class="bg-white/5 backdrop-blur border border-white/10 rounded-3xl p-8 shadow-2xl">
    {% if error %}<div class="bg-red-500/10 border border-red-500/30 text-red-400 rounded-2xl p-4 mb-6 text-sm flex items-center gap-3"><i class="fas fa-exclamation-circle"></i> {{ error }}</div>{% endif %}
    <form method="POST" class="space-y-5">
      <div>
        <label class="block text-xs font-bold text-slate-400 mb-2">اسم المستخدم</label>
        <div class="relative"><i class="fas fa-user absolute right-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
        <input name="username" type="text" autocomplete="username" placeholder="admin" required
          class="w-full bg-white/5 border border-white/10 text-white rounded-2xl py-4 pr-12 pl-4 text-sm outline-none focus:border-amber-500 transition-all"></div>
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-400 mb-2">كلمة المرور</label>
        <div class="relative"><i class="fas fa-lock absolute right-4 top-1/2 -translate-y-1/2 text-slate-500"></i>
        <input name="password" id="pf" type="password" autocomplete="current-password" placeholder="admin123" required
          class="w-full bg-white/5 border border-white/10 text-white rounded-2xl py-4 pr-12 pl-12 text-sm outline-none focus:border-amber-500 transition-all">
        <button type="button" onclick="var f=document.getElementById('pf');f.type=f.type=='password'?'text':'password';" class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"><i class="fas fa-eye"></i></button>
        </div>
      </div>
      <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 text-white font-black py-4 rounded-2xl transition-all flex items-center justify-center gap-2">
        <i class="fas fa-sign-in-alt"></i> دخول للوحة الادارة
      </button>
    </form>
  </div>
  <p class="text-center text-slate-600 text-xs mt-6">كلمة المرور الافتراضية: admin123</p>
</div>
</body></html>"""

STORE_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>متجر انجازك الاكاديمي</title>
<link rel="icon" type="image/png" href="data:image/png;base64,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">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
{% raw %}<style>
body{font-family:'IBM Plex Sans Arabic',sans-serif;background:#f8fafc;}
.hero-bg{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);}
.moving-banner{background:#b45309;color:#fff;padding:6px 0;overflow:hidden;}
.marquee{display:inline-block;white-space:nowrap;animation:marquee 30s linear infinite;font-size:.8rem;font-weight:500;}
@keyframes marquee{0%{transform:translateX(100%)}100%{transform:translateX(-100%)}}
.card{background:rgba(255,255,255,.95);border:1px solid rgba(255,255,255,.4);box-shadow:0 10px 30px -10px rgba(0,0,0,.06);transition:all .3s;}
.card:hover{transform:translateY(-4px);box-shadow:0 20px 40px -15px rgba(180,83,9,.15);}
.btn-dark{background:#0f172a;color:white;transition:all .25s;}
.btn-dark:hover{background:#1e293b;}
.cat-btn{transition:all .2s;border:2px solid #e2e8f0;}
.cat-btn.active{border-color:#b45309;background:rgba(180,83,9,.08);color:#b45309;}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);transition:transform .4s cubic-bezier(.34,1.56,.64,1);opacity:0;z-index:9999;min-width:280px;}
#toast.show{transform:translateX(-50%) translateY(0);opacity:1;}
.cart-sidebar{transition:transform .35s cubic-bezier(.4,0,.2,1);}
.cart-sidebar.open{transform:translateX(0) !important;}
.qty-btn{width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;cursor:pointer;transition:all .15s;}
.qty-btn:hover{background:#e2e8f0;}
.rf{border-color:#f59e0b !important;background:#fffbeb !important;}
.notes-req{border:2px solid #fcd34d;background:#fffbeb;}
.wa-float{position:fixed;bottom:24px;right:24px;z-index:150;width:56px;height:56px;background:#25d366;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:26px;box-shadow:0 6px 20px rgba(37,211,102,.4);transition:all .3s;text-decoration:none;}
.wa-float:hover{transform:scale(1.1);}
.status-new{background:#dbeafe;color:#1d4ed8;}
.status-proc{background:#fef3c7;color:#b45309;}
.status-pay{background:#dcfce7;color:#15803d;}
.status-edit{background:#f3e8ff;color:#7c3aed;}
.status-cancel{background:#fee2e2;color:#dc2626;}
.status-done{background:#d1fae5;color:#065f46;}
@keyframes popIn{0%{transform:scale(.6);opacity:0}100%{transform:scale(1);opacity:1}}
.pop-in{animation:popIn .35s cubic-bezier(.34,1.56,.64,1);}
/* ===== DARK MODE ===== */
html.dark body{background:#0f172a;color:#e2e8f0;}
html.dark header{background:rgba(15,23,42,.95) !important;border-color:#1e293b !important;}
html.dark .bg-white{background:#1e293b !important;}
html.dark .bg-slate-50{background:#0f172a !important;}
html.dark .bg-slate-100{background:#1e293b !important;}
html.dark .text-slate-900{color:#f1f5f9 !important;}
html.dark .text-slate-800{color:#e2e8f0 !important;}
html.dark .text-slate-700{color:#cbd5e1 !important;}
html.dark .text-slate-600{color:#94a3b8 !important;}
html.dark .text-slate-500{color:#64748b !important;}
html.dark .border-slate-100{border-color:#1e293b !important;}
html.dark .border-slate-200{border-color:#334155 !important;}
html.dark .product-card{background:#1e293b !important;}
html.dark .moving-banner{background:#1a1200 !important;}
html.dark footer{background:#020617 !important;}
html.dark input,html.dark textarea{background:#0f172a !important;color:#e2e8f0 !important;border-color:#334155 !important;}
html.dark .btn-dark{background:#d4af37 !important;color:#000 !important;}
/* progress bar */
.order-progress-step{height:6px;flex:1;border-radius:3px;transition:background .4s;}
.order-progress-step.done{background:#f59e0b;}
.order-progress-step.active{background:#10b981;}
.order-progress-step.pending{background:#e2e8f0;}
</style>{% endraw %}
</head>
<body class="flex flex-col min-h-screen">

<div class="moving-banner"><div class="marquee">{{ settings.moving_text }}</div></div>

<header class="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100 shadow-sm">
  <div class="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <img src="data:image/png;base64,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" class="w-10 h-10 rounded-full object-cover shadow-sm" alt="انجازك">
      <div>
        <h1 class="text-xl font-bold leading-tight">انجازك</h1>
        <span class="text-[9px] text-amber-700 font-bold uppercase tracking-widest">للخدمات الاكاديمية</span>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <div id="guestBtn">
        <button onclick="openAuthModal('login')" class="flex items-center gap-1.5 border border-slate-200 text-slate-600 px-3 py-2 rounded-full text-xs font-bold hover:bg-slate-50 transition-all">
          <i class="fas fa-user-circle text-slate-500"></i>
          <span class="hidden sm:inline">دخول</span>
        </button>
      </div>
      <div id="loggedInBtn" style="display:none" class="relative">
        <button onclick="toggleUserMenu()" class="flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-700 px-3 py-2 rounded-full text-xs font-bold hover:bg-amber-100 transition-all">
          <i class="fas fa-user-check text-amber-600"></i>
          <span id="headerUserName" class="hidden sm:inline max-w-[70px] truncate"></span>
        </button>
        <div id="userMenu" style="display:none" class="absolute left-0 top-11 bg-white border border-slate-200 rounded-2xl shadow-xl p-3 w-44 z-50">
          <p id="menuUserName" class="text-xs font-bold text-slate-800 mb-0.5 truncate"></p>
          <p id="menuUserPhone" class="text-[10px] text-slate-400 mb-3 font-mono"></p>
          <button onclick="closeUserMenu();openProfileModal();" class="w-full text-right text-xs py-2 px-3 rounded-xl hover:bg-slate-50 text-slate-600 font-bold flex items-center gap-2">
            <i class="fas fa-id-card text-amber-600"></i> الملف الشخصي
          </button>
          <button onclick="closeUserMenu();openMyOrders();" class="w-full text-right text-xs py-2 px-3 rounded-xl hover:bg-slate-50 text-slate-600 font-bold flex items-center gap-2">
            <i class="fas fa-receipt text-amber-600"></i> طلباتي
          </button>
          <button onclick="doCustomerLogout()" class="w-full text-right text-xs py-2 px-3 rounded-xl hover:bg-red-50 text-red-500 font-bold flex items-center gap-2 mt-1">
            <i class="fas fa-sign-out-alt"></i> تسجيل خروج
          </button>
        </div>
      </div>
      <button onclick="openCart()" class="relative flex items-center gap-2 bg-slate-900 text-white px-4 py-2 rounded-full text-sm font-bold hover:bg-slate-700 transition-all">
        <i class="fas fa-shopping-cart"></i>
        <span class="hidden sm:inline">السلة</span>
        <span id="cartBadge" style="display:none" class="absolute -top-1 -left-1 w-5 h-5 bg-amber-500 text-white rounded-full text-[10px] font-black flex items-center justify-center">0</span>
      </button>
      <button onclick="toggleDarkMode()" id="darkModeBtn" class="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200 transition-all" title="وضع مظلم">
        <i class="fas fa-moon text-sm" id="darkModeIcon"></i>
      </button>
    </div>
  </div>
</header>

<!-- بانر العرض الموسمي -->
<div id="offerBanner" style="display:none" class="bg-gradient-to-r from-red-600 to-amber-500 text-white py-3 px-4 text-center cursor-pointer" onclick="this.style.display='none'">
  <p id="offerBannerText" class="text-sm font-black flex items-center justify-center gap-2"><i class="fas fa-gift"></i> <span></span> <i class="fas fa-times text-xs opacity-60 mr-4"></i></p>
</div>

<section class="hero-bg text-white py-14 sm:py-20 px-4 text-center">
  <div class="max-w-3xl mx-auto">
    <h2 class="text-3xl sm:text-5xl font-black mb-4 leading-tight">شريكك الموثوق للتميز في بحوثك ودراستك</h2>
    <p class="text-slate-300 text-sm sm:text-lg mb-8">نقدم لك نخبة من الخدمات التعليمية باعلى معايير الجودة</p>
    <div class="flex flex-wrap justify-center gap-3">
      <div class="flex items-center gap-2 text-xs bg-white/10 px-4 py-2 rounded-full border border-white/10"><i class="fas fa-check-circle text-amber-400"></i> خبير متخصص لكل مجال</div>
      <div class="flex items-center gap-2 text-xs bg-white/10 px-4 py-2 rounded-full border border-white/10"><i class="fas fa-clock text-amber-400"></i> التزام بالمواعيد</div>
      <div class="flex items-center gap-2 text-xs bg-white/10 px-4 py-2 rounded-full border border-white/10"><i class="fas fa-shield-alt text-amber-400"></i> سرية تامة</div>
    </div>
  </div>
</section>

<!-- عداد الطلبات -->
<div class="bg-white border-b border-slate-100 py-5 px-4">
  <div class="max-w-6xl mx-auto flex flex-wrap justify-center gap-10 text-center">
    <div><p id="statCompleted" class="text-3xl font-black text-amber-600">...</p><p class="text-xs text-slate-500 mt-1 font-bold">طلب مكتمل</p></div>
    <div><p id="statProducts" class="text-3xl font-black text-amber-600">...</p><p class="text-xs text-slate-500 mt-1 font-bold">خدمة متاحة</p></div>
    <div><p class="text-3xl font-black text-amber-600">100%</p><p class="text-xs text-slate-500 mt-1 font-bold">رضا العملاء</p></div>
  </div>
</div>

<main class="max-w-6xl mx-auto px-4 py-12 flex-grow">
  <div class="mb-8 flex flex-col sm:flex-row gap-4 items-center justify-between">
    <h3 class="text-2xl font-bold border-r-4 border-amber-600 pr-3">خدماتنا المتميزة</h3>
    <div class="relative w-full sm:w-72">
      <i class="fas fa-search absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm"></i>
      <input id="searchInput" oninput="filterProducts()" placeholder="ابحث عن خدمة..."
        class="w-full bg-white border border-slate-200 rounded-2xl py-3 pr-11 pl-4 text-sm outline-none focus:border-amber-500 shadow-sm">
    </div>
  </div>
  {% if categories %}
  <div class="flex flex-wrap gap-2 mb-8">
    <button onclick="filterByCategory('all')" class="cat-btn active px-4 py-2 rounded-full text-xs font-bold bg-white" id="cat-all">الكل</button>
    {% for cat in categories %}<button onclick="filterByCategory({{ cat|tojson }})" class="cat-btn px-4 py-2 rounded-full text-xs font-bold bg-white">{{ cat }}</button>{% endfor %}
  </div>
  {% endif %}
  <div id="productsGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
    {% for p in products %}
    <div class="card rounded-3xl overflow-hidden flex flex-col group product-card"
      data-name="{{ p.name|lower }}" data-desc="{{ (p.description or '')|lower }}" data-category="{{ p.category }}">
      <a href="/product/{{ p.id }}" class="relative aspect-[4/3] overflow-hidden block">
        <img src="{{ p.image_data if p.image_data else 'https://placehold.co/600x450/0f172a/white?text=Enjazk' }}"
          class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy"
          onerror="this.src='https://placehold.co/600x450/0f172a/white?text=Enjazk'">
        {% if p.old_price %}<div class="absolute top-3 left-3 bg-red-500 text-white text-[10px] font-black px-2 py-1 rounded-full">خصم {{ ((p.old_price - p.price) / p.old_price * 100)|int }}%</div>{% endif %}
        <div class="absolute top-3 right-3 bg-white/90 text-amber-700 text-[10px] font-bold px-2 py-1 rounded-full">{{ p.category }}</div>
        {% if p.stock is not none and p.stock < 5 and p.stock > 0 %}<div class="absolute bottom-3 left-3 bg-orange-500 text-white text-[10px] font-bold px-2 py-1 rounded-full">متبقي {{ p.stock }}</div>{% endif %}
        {% if p.stock == 0 %}<div class="absolute inset-0 bg-black/60 flex items-center justify-center"><span class="text-white font-black text-xl">غير متاح حاليا</span></div>{% endif %}
      </a>
      <div class="p-6 flex flex-col flex-grow">
        <a href="/product/{{ p.id }}" class="block mb-2"><h4 class="text-lg font-bold text-slate-800 hover:text-amber-600 transition-colors">{{ p.name }}</h4></a>
        <p class="text-slate-500 text-xs leading-relaxed mb-5 flex-grow">{{ p.description }}</p>
        <div class="flex items-center justify-between gap-3 mt-auto">
          <div>
            {% if p.old_price %}<span class="text-[10px] text-slate-400 line-through block">{{ p.old_price }} ر.س</span>{% endif %}
            <span class="text-2xl font-black text-slate-900">{{ p.price }} <small class="text-xs font-normal">ر.س</small></span>
          </div>
          {% if p.stock != 0 %}
          <div class="flex gap-2">
            <button onclick="addToCart({{ p.name|tojson }}, {{ p.price }}); return false;" class="border-2 border-amber-600 text-amber-700 hover:bg-amber-600 hover:text-white px-3 py-2 rounded-xl text-xs font-bold transition-all"><i class="fas fa-cart-plus"></i></button>
            <a href="/product/{{ p.id }}" class="btn-dark px-4 py-2 rounded-xl text-xs font-bold shadow-sm text-center flex items-center justify-center">اطلب الان</a>
            <button onclick="shareService({{ p.name|tojson }}, {{ p.price }}); return false;" class="border border-slate-200 text-slate-400 hover:text-amber-600 hover:border-amber-300 px-2 py-2 rounded-xl text-xs transition-all" title="مشاركة"><i class="fas fa-share-alt"></i></button>
          </div>
          {% else %}<span class="text-xs text-red-400 font-bold bg-red-50 px-3 py-2 rounded-xl">نفذت الكمية</span>{% endif %}
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  <div id="emptyState" class="hidden text-center py-20 text-slate-300"><i class="fas fa-search text-5xl mb-4 block"></i><p class="text-lg font-bold">لا توجد نتائج مطابقة</p></div>
</main>

<!-- شهادات العملاء -->
<section class="bg-slate-50 py-14 px-4">
  <div class="max-w-6xl mx-auto">
    <h3 class="text-2xl font-black text-center mb-8 text-slate-900">ماذا يقول عملاؤنا</h3>
    <div id="testimonialsList" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      <div class="text-center py-8 text-slate-300 col-span-full"><i class="fas fa-spinner fa-spin text-xl"></i></div>
    </div>
  </div>
</section>

<footer class="bg-slate-950 text-white pt-14 pb-8 px-4">
  <div class="max-w-4xl mx-auto">

    <!-- روابط تهمك -->
    <div class="mb-12">
      <h4 class="text-center text-xl font-black mb-1">روابط <span class="text-amber-500 underline decoration-amber-500/60">تهمك</span></h4>
      <p class="text-center text-slate-500 text-xs mb-8">كل ما تحتاج معرفته في مكان واحد</p>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <button onclick="openInfoModal('about')" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-info-circle"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">عننا</span>
        </button>
        <button onclick="openInfoModal('trust')" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-shield-alt"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">كيف تثق بنا؟</span>
        </button>
        <button onclick="openInfoModal('solutions')" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-book-open"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">حلول وشروحات</span>
        </button>
        <button onclick="openInfoModal('warranty')" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-undo-alt"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">سياسة الضمان</span>
        </button>
        <button onclick="openInfoModal('trends')" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-fire"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">أحدث الترندات</span>
        </button>
        <button onclick="openInfoModal('terms')" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-file-contract"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">الشروط والأحكام</span>
        </button>
        <button onclick="openLiveChat()" class="group flex items-center gap-3 bg-white/5 hover:bg-amber-600/20 border border-white/8 hover:border-amber-500/40 rounded-2xl px-4 py-3.5 transition-all duration-300 text-right w-full md:col-start-2">
          <span class="w-8 h-8 bg-amber-500/15 group-hover:bg-amber-500/25 rounded-xl flex items-center justify-center text-amber-400 text-sm transition-all"><i class="fas fa-headset"></i></span>
          <span class="text-sm font-bold text-slate-200 group-hover:text-white">مساعدة فورية</span>
        </button>
      </div>
    </div>

    <!-- خط فاصل -->
    <div class="border-t border-white/5 mb-8"></div>

    <!-- خدمة العملاء + سوشيال -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">

      <!-- خدمة العملاء -->
      <div>
        <h5 class="text-amber-500 font-bold text-xs uppercase tracking-widest mb-4">خدمة العملاء</h5>
        <div class="space-y-2">
          <a href="{{ settings.whatsapp }}" target="_blank" class="flex items-center gap-3 bg-white/5 hover:bg-green-500/15 border border-white/8 hover:border-green-500/30 rounded-2xl px-4 py-3 transition-all group">
            <span class="w-9 h-9 bg-green-500/15 rounded-xl flex items-center justify-center"><i class="fab fa-whatsapp text-green-400 text-lg"></i></span>
            <div><p class="text-xs font-bold text-white">واتساب</p><p class="text-[10px] text-slate-500">رد فوري خلال دقائق</p></div>
            <i class="fas fa-arrow-left text-slate-600 group-hover:text-green-400 text-xs mr-auto transition-all"></i>
          </a>
          <button onclick="openLiveChat()" class="w-full flex items-center gap-3 bg-white/5 hover:bg-amber-500/15 border border-white/8 hover:border-amber-500/30 rounded-2xl px-4 py-3 transition-all group text-right">
            <span class="w-9 h-9 bg-amber-500/15 rounded-xl flex items-center justify-center"><i class="fas fa-comments text-amber-400 text-base"></i></span>
            <div><p class="text-xs font-bold text-white">محادثة مباشرة</p><p class="text-[10px] text-slate-500">تواصل معنا من الموقع</p></div>
            <span id="liveChatDot" class="w-2 h-2 bg-green-400 rounded-full mr-auto animate-pulse"></span>
          </button>
          <a href="mailto:{{ settings.email }}" class="flex items-center gap-3 bg-white/5 hover:bg-blue-500/15 border border-white/8 hover:border-blue-500/30 rounded-2xl px-4 py-3 transition-all group">
            <span class="w-9 h-9 bg-blue-500/15 rounded-xl flex items-center justify-center"><i class="fas fa-envelope text-blue-400 text-base"></i></span>
            <div><p class="text-xs font-bold text-white">البريد الإلكتروني</p><p class="text-[10px] text-slate-500">{{ settings.email }}</p></div>
            <i class="fas fa-arrow-left text-slate-600 group-hover:text-blue-400 text-xs mr-auto transition-all"></i>
          </a>
        </div>
      </div>

      <!-- سوشيال ميديا -->
      <div>
        <h5 class="text-amber-500 font-bold text-xs uppercase tracking-widest mb-4">تابعنا</h5>
        <div class="grid grid-cols-2 gap-2">
          {% if settings.instagram %}
          <a href="{{ settings.instagram }}" target="_blank" class="group flex items-center gap-2.5 bg-white/5 hover:bg-pink-500/15 border border-white/8 hover:border-pink-500/30 rounded-2xl px-3 py-3 transition-all">
            <span class="w-8 h-8 rounded-xl flex items-center justify-center" style="background:linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);"><i class="fab fa-instagram text-white text-sm"></i></span>
            <span class="text-xs font-bold text-slate-300 group-hover:text-white">انستغرام</span>
          </a>
          {% endif %}
          {% if settings.tiktok %}
          <a href="{{ settings.tiktok }}" target="_blank" class="group flex items-center gap-2.5 bg-white/5 hover:bg-slate-700/50 border border-white/8 hover:border-white/20 rounded-2xl px-3 py-3 transition-all">
            <span class="w-8 h-8 bg-black rounded-xl flex items-center justify-center"><i class="fab fa-tiktok text-white text-sm"></i></span>
            <span class="text-xs font-bold text-slate-300 group-hover:text-white">تيك توك</span>
          </a>
          {% endif %}
          {% if settings.snapchat %}
          <a href="{{ settings.snapchat }}" target="_blank" class="group flex items-center gap-2.5 bg-white/5 hover:bg-yellow-400/15 border border-white/8 hover:border-yellow-400/30 rounded-2xl px-3 py-3 transition-all">
            <span class="w-8 h-8 bg-yellow-400 rounded-xl flex items-center justify-center"><i class="fab fa-snapchat text-black text-sm"></i></span>
            <span class="text-xs font-bold text-slate-300 group-hover:text-white">سناب شات</span>
          </a>
          {% endif %}
          {% if settings.twitter %}
          <a href="{{ settings.twitter }}" target="_blank" class="group flex items-center gap-2.5 bg-white/5 hover:bg-slate-700/50 border border-white/8 hover:border-white/20 rounded-2xl px-3 py-3 transition-all">
            <span class="w-8 h-8 bg-black rounded-xl flex items-center justify-center"><i class="fab fa-x-twitter text-white text-sm"></i></span>
            <span class="text-xs font-bold text-slate-300 group-hover:text-white">تويتر / X</span>
          </a>
          {% endif %}
          <a href="{{ settings.whatsapp }}" target="_blank" class="group flex items-center gap-2.5 bg-white/5 hover:bg-green-500/15 border border-white/8 hover:border-green-500/30 rounded-2xl px-3 py-3 transition-all">
            <span class="w-8 h-8 bg-green-500 rounded-xl flex items-center justify-center"><i class="fab fa-whatsapp text-white text-sm"></i></span>
            <span class="text-xs font-bold text-slate-300 group-hover:text-white">واتساب</span>
          </a>
        </div>
      </div>
    </div>

    <!-- Copyright -->
    <div class="border-t border-white/5 pt-6 flex flex-col md:flex-row items-center justify-between gap-2">
      <div class="flex items-center gap-2"><div class="w-6 h-6 bg-amber-600 rounded-lg flex items-center justify-center"><i class="fas fa-graduation-cap text-[10px]"></i></div><span class="text-slate-500 text-xs font-bold">انجازك للخدمات الأكاديمية</span></div>
      <p class="text-slate-600 text-[10px]">&copy; 2025 جميع الحقوق محفوظة</p>
    </div>
  </div>
</footer>

<!-- INFO MODAL - روابط تهمك -->
<div id="infoModal" style="display:none" class="fixed inset-0 bg-slate-900/70 backdrop-blur-md flex items-center justify-center p-4 z-[116]">
  <div class="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden pop-in" style="max-height:85vh;display:flex;flex-direction:column;">
    <div id="infoModalHeader" class="px-6 py-4 flex items-center gap-3 flex-shrink-0">
      <div id="infoModalIcon" class="w-10 h-10 rounded-2xl flex items-center justify-center text-white text-base flex-shrink-0"></div>
      <h3 id="infoModalTitle" class="font-black text-white text-base flex-1"></h3>
      <button onclick="closeInfoModal()" class="w-8 h-8 bg-white/20 rounded-xl flex items-center justify-center text-white hover:bg-white/30 transition-all flex-shrink-0"><i class="fas fa-times text-xs"></i></button>
    </div>
    <div id="infoModalBody" class="overflow-y-auto p-6 flex-1 text-sm text-slate-700 leading-relaxed space-y-3"></div>
    <div class="p-4 border-t border-slate-100 flex-shrink-0">
      <button onclick="closeInfoModal()" class="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-2xl font-bold text-sm transition-all">إغلاق</button>
    </div>
  </div>
</div>

<script>
var infoContent = {
  about: {
    title: 'عننا',
    icon: 'fa-graduation-cap',
    color: 'from-amber-500 to-amber-600',
    body: `<div class="text-center py-4">
      <div class="w-20 h-20 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-5"><i class="fas fa-graduation-cap text-amber-500 text-4xl"></i></div>
      <p class="font-black text-slate-800 text-lg mb-4">تسوّق أفضل متجر للخدمات الأكاديمية.</p>
      <p class="text-slate-600 leading-loose text-sm">في متجر انجازك، نقدم لك تجربة خدمية مميزة مع مكتبة خدمات واسعة، أصيلة وحصرية، بأسعار منافسة وجودة مضمونة. ودعم سريع على مدار الساعة. استمتع بتجربة طلب بسيطة وآمنة من أول خطوة حتى تسليم الخدمة.</p>
    </div>`
  },
  trust: {
    title: 'كيف تثق بنا؟',
    icon: 'fa-shield-alt',
    color: 'from-blue-500 to-blue-600',
    body: `<div class="space-y-3">
    <div class="flex gap-3 bg-blue-50 rounded-2xl p-4"><div class="w-9 h-9 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0"><i class="fas fa-lock text-blue-600 text-sm"></i></div><div><p class="font-bold text-sm text-slate-800">دفع آمن بعد التسليم</p><p class="text-xs text-slate-500 mt-0.5">ندعم الدفع بعد مراجعة العمل وتأكيد جودته.</p></div></div>
    <div class="flex gap-3 bg-green-50 rounded-2xl p-4"><div class="w-9 h-9 bg-green-100 rounded-xl flex items-center justify-center flex-shrink-0"><i class="fas fa-redo text-green-600 text-sm"></i></div><div><p class="font-bold text-sm text-slate-800">تعديلات مجانية غير محدودة</p><p class="text-xs text-slate-500 mt-0.5">نعدّل حتى تصل إلى رضاك الكامل بدون أي تكلفة إضافية.</p></div></div>
    <div class="flex gap-3 bg-amber-50 rounded-2xl p-4"><div class="w-9 h-9 bg-amber-100 rounded-xl flex items-center justify-center flex-shrink-0"><i class="fas fa-star text-amber-600 text-sm"></i></div><div><p class="font-bold text-sm text-slate-800">تقييمات حقيقية من عملائنا</p><p class="text-xs text-slate-500 mt-0.5">كل التقييمات المعروضة من عملاء حقيقيين يمكنك التحقق منها.</p></div></div>
    <div class="flex gap-3 bg-purple-50 rounded-2xl p-4"><div class="w-9 h-9 bg-purple-100 rounded-xl flex items-center justify-center flex-shrink-0"><i class="fas fa-user-shield text-purple-600 text-sm"></i></div><div><p class="font-bold text-sm text-slate-800">خصوصية تامة</p><p class="text-xs text-slate-500 mt-0.5">بياناتك ومعلوماتك محفوظة بسرية تامة ولا تُشارك مع أي طرف.</p></div></div>
    </div>`
  },
  solutions: {
    title: 'حلول وشروحات',
    icon: 'fa-book-open',
    color: 'from-green-500 to-green-600',
    body: `<p class="mb-3">نقدم مجموعة شاملة من الحلول والشروحات الأكاديمية في مختلف المجالات:</p>
    <div class="space-y-2">
      <div class="flex items-center gap-2 bg-slate-50 rounded-xl p-3"><i class="fas fa-calculator text-green-600 w-5 text-center text-sm"></i><span class="text-sm font-bold">الرياضيات والإحصاء</span></div>
      <div class="flex items-center gap-2 bg-slate-50 rounded-xl p-3"><i class="fas fa-flask text-blue-600 w-5 text-center text-sm"></i><span class="text-sm font-bold">العلوم والفيزياء والكيمياء</span></div>
      <div class="flex items-center gap-2 bg-slate-50 rounded-xl p-3"><i class="fas fa-laptop-code text-purple-600 w-5 text-center text-sm"></i><span class="text-sm font-bold">البرمجة وتقنية المعلومات</span></div>
      <div class="flex items-center gap-2 bg-slate-50 rounded-xl p-3"><i class="fas fa-pen-nib text-amber-600 w-5 text-center text-sm"></i><span class="text-sm font-bold">الكتابة الأكاديمية والتقارير</span></div>
      <div class="flex items-center gap-2 bg-slate-50 rounded-xl p-3"><i class="fas fa-chart-bar text-red-600 w-5 text-center text-sm"></i><span class="text-sm font-bold">تحليل البيانات وSPSS</span></div>
      <div class="flex items-center gap-2 bg-slate-50 rounded-xl p-3"><i class="fas fa-language text-teal-600 w-5 text-center text-sm"></i><span class="text-sm font-bold">الترجمة واللغة الإنجليزية</span></div>
    </div>
    <div class="bg-amber-50 rounded-2xl p-3 mt-3 text-xs text-amber-700"><i class="fas fa-lightbulb ml-1"></i>لديك مادة مختلفة؟ تواصل معنا وسنجد لك الحل!</div>`
  },
  warranty: {
    title: 'سياسة الضمان والاسترجاع',
    icon: 'fa-undo-alt',
    color: 'from-purple-500 to-purple-600',
    body: `<div class="space-y-3">
    <div class="bg-green-50 border border-green-200 rounded-2xl p-4"><p class="font-black text-green-700 text-sm mb-2">✅ ضمان الجودة</p><p class="text-xs text-green-600">نضمن جودة جميع خدماتنا. إذا لم تكن راضياً عن النتيجة، نعيد العمل مجاناً حتى تصل لرضاك الكامل.</p></div>
    <div class="bg-blue-50 border border-blue-200 rounded-2xl p-4"><p class="font-black text-blue-700 text-sm mb-2">🔄 التعديلات المجانية</p><p class="text-xs text-blue-600">جميع الخدمات تشمل تعديلات مجانية خلال 7 أيام من تاريخ التسليم.</p></div>
    <div class="bg-amber-50 border border-amber-200 rounded-2xl p-4"><p class="font-black text-amber-700 text-sm mb-2">💰 سياسة الاسترداد</p><ul class="text-xs text-amber-600 space-y-1 list-disc list-inside"><li>استرداد كامل قبل بدء التنفيذ</li><li>استرداد جزئي بعد بدء التنفيذ</li><li>لا يمكن الاسترداد بعد التسليم النهائي</li></ul></div>
    <div class="bg-red-50 border border-red-200 rounded-2xl p-4"><p class="font-black text-red-700 text-sm mb-2">⚠️ ملاحظة مهمة</p><p class="text-xs text-red-600">يُرجى التأكد من تفاصيل الطلب قبل التأكيد. طلبات الاسترداد تُدرس خلال 48 ساعة.</p></div>
    </div>`
  },
  trends: {
    title: 'أحدث الترندات والأخبار',
    icon: 'fa-fire',
    color: 'from-orange-500 to-red-500',
    body: `<div class="bg-orange-50 rounded-2xl p-3 mb-4 flex items-center gap-2"><i class="fas fa-fire text-orange-500"></i><p class="text-xs font-bold text-orange-700">أكثر الخدمات طلباً الآن</p></div>
    <div class="space-y-2">
      <div class="flex items-center justify-between bg-slate-50 rounded-xl p-3"><div class="flex items-center gap-2"><span class="w-6 h-6 bg-red-100 rounded-lg flex items-center justify-center text-[10px] font-black text-red-600">1</span><span class="text-sm font-bold">حل واجبات الرياضيات</span></div><span class="text-[10px] bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-bold">🔥 رائج</span></div>
      <div class="flex items-center justify-between bg-slate-50 rounded-xl p-3"><div class="flex items-center gap-2"><span class="w-6 h-6 bg-orange-100 rounded-lg flex items-center justify-center text-[10px] font-black text-orange-600">2</span><span class="text-sm font-bold">تقارير وبحوث أكاديمية</span></div><span class="text-[10px] bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full font-bold">⬆️ ارتفع</span></div>
      <div class="flex items-center justify-between bg-slate-50 rounded-xl p-3"><div class="flex items-center gap-2"><span class="w-6 h-6 bg-amber-100 rounded-lg flex items-center justify-center text-[10px] font-black text-amber-600">3</span><span class="text-sm font-bold">مشاريع البرمجة</span></div><span class="text-[10px] bg-amber-100 text-amber-600 px-2 py-0.5 rounded-full font-bold">🆕 جديد</span></div>
      <div class="flex items-center justify-between bg-slate-50 rounded-xl p-3"><div class="flex items-center gap-2"><span class="w-6 h-6 bg-blue-100 rounded-lg flex items-center justify-center text-[10px] font-black text-blue-600">4</span><span class="text-sm font-bold">تحليل إحصائي SPSS</span></div><span class="text-[10px] bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full font-bold">📈 مميز</span></div>
    </div>
    <div class="bg-slate-50 rounded-2xl p-3 mt-3 text-center"><p class="text-xs text-slate-500">يتم تحديث الترندات يومياً بناءً على طلبات العملاء 📊</p></div>`
  },
  terms: {
    title: 'الشروط والأحكام',
    icon: 'fa-file-contract',
    color: 'from-slate-600 to-slate-700',
    body: `<div class="space-y-3 text-xs text-slate-600">
    <div class="bg-slate-50 rounded-2xl p-4"><p class="font-black text-slate-800 text-sm mb-2">📋 شروط الاستخدام</p><ul class="space-y-1.5 list-disc list-inside"><li>الخدمات مخصصة للاستخدام الشخصي والتعليمي فقط</li><li>يُحظر إعادة بيع أو توزيع الخدمات المقدمة</li><li>يتحمل العميل مسؤولية استخدام الخدمات بشكل أخلاقي</li></ul></div>
    <div class="bg-blue-50 rounded-2xl p-4"><p class="font-black text-blue-800 text-sm mb-2">🔒 سياسة الخصوصية</p><ul class="space-y-1.5 list-disc list-inside text-blue-700"><li>لا نشارك بياناتك مع أطراف ثالثة</li><li>معلوماتك محفوظة بتشفير آمن</li><li>يمكنك طلب حذف بياناتك في أي وقت</li></ul></div>
    <div class="bg-amber-50 rounded-2xl p-4"><p class="font-black text-amber-800 text-sm mb-2">💳 شروط الدفع</p><ul class="space-y-1.5 list-disc list-inside text-amber-700"><li>الدفع عبر التحويل البنكي فقط</li><li>يُرفق إيصال التحويل لتأكيد الطلب</li><li>الأسعار تشمل الضريبة إن وجدت</li></ul></div>
    <p class="text-center text-slate-400 text-[10px] pt-2">آخر تحديث: يونيو 2025 | جميع الحقوق محفوظة لمتجر انجازك</p>
    </div>`
  }
};

function openInfoModal(key){
  var info = infoContent[key];
  if(!info) return;
  var hdr = document.getElementById('infoModalHeader');
  hdr.className = 'px-6 py-4 flex items-center gap-3 flex-shrink-0 bg-gradient-to-r ' + info.color;
  document.getElementById('infoModalIcon').innerHTML = '<i class="fas '+info.icon+'"></i>';
  document.getElementById('infoModalTitle').innerText = info.title;
  document.getElementById('infoModalBody').innerHTML = info.body;
  document.getElementById('infoModal').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
function closeInfoModal(){
  document.getElementById('infoModal').style.display = 'none';
  document.body.style.overflow = '';
}
</script>

<!-- LIVE CHAT MODAL -->
<div id="liveChatModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-end justify-center p-4 z-[115] md:items-center">
  <div class="bg-white rounded-3xl w-full max-w-sm shadow-2xl overflow-hidden pop-in flex flex-col" style="max-height:85vh">
    <!-- Chat Header -->
    <div class="bg-gradient-to-r from-amber-600 to-amber-500 px-5 py-4 flex items-center gap-3">
      <div class="w-10 h-10 bg-white/20 rounded-2xl flex items-center justify-center"><i class="fas fa-headset text-white text-base"></i></div>
      <div class="flex-1">
        <p class="text-white font-black text-sm">خدمة عملاء انجازك</p>
        <p class="text-white/75 text-[10px] flex items-center gap-1"><span class="w-1.5 h-1.5 bg-green-300 rounded-full inline-block animate-pulse"></span> متاحون الآن</p>
      </div>
      <button onclick="closeLiveChat()" class="w-8 h-8 bg-white/20 rounded-xl flex items-center justify-center text-white hover:bg-white/30 transition-all"><i class="fas fa-times text-xs"></i></button>
    </div>
    <!-- Chat Messages -->
    <div id="chatMessages" class="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50" style="min-height:220px;max-height:340px;">
      <div class="flex gap-2 items-end">
        <div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0"><i class="fas fa-graduation-cap text-amber-600 text-[10px]"></i></div>
        <div class="bg-white rounded-2xl rounded-br-md px-4 py-2.5 shadow-sm max-w-[80%]">
          <p class="text-xs text-slate-700 font-medium leading-relaxed">مرحباً! 👋 كيف نقدر نساعدك اليوم؟</p>
          <p class="text-[9px] text-slate-400 mt-1">الآن</p>
        </div>
      </div>
    </div>
    <!-- Quick Replies -->
    <div id="quickReplies" class="px-4 py-2 flex gap-2 overflow-x-auto border-t border-slate-100 bg-white">
      <button onclick="sendQuickReply('استفسار عن سعر خدمة')" class="flex-shrink-0 text-[10px] bg-amber-50 text-amber-700 border border-amber-200 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">💰 استفسار عن السعر</button>
      <button onclick="sendQuickReply('متى يكتمل طلبي؟')" class="flex-shrink-0 text-[10px] bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1.5 rounded-full font-bold hover:bg-blue-100 transition-all">📦 حالة الطلب</button>
      <button onclick="sendQuickReply('أريد التحدث مع موظف')" class="flex-shrink-0 text-[10px] bg-green-50 text-green-700 border border-green-200 px-3 py-1.5 rounded-full font-bold hover:bg-green-100 transition-all">🎧 موظف بشري</button>
    </div>
    <!-- Input -->
    <div class="p-3 border-t border-slate-100 bg-white flex gap-2">
      <input id="chatInput" type="text" placeholder="اكتب رسالتك..." class="flex-1 bg-slate-50 border border-slate-200 rounded-2xl px-4 py-2.5 text-sm outline-none focus:border-amber-400 transition-all" onkeydown="if(event.key==='Enter')sendChatMsg()">
      <button onclick="sendChatMsg()" class="w-10 h-10 bg-amber-600 hover:bg-amber-500 text-white rounded-2xl flex items-center justify-center transition-all flex-shrink-0"><i class="fas fa-paper-plane text-xs"></i></button>
    </div>
  </div>
</div>

<script>
// ============ LIVE CHAT ============
var chatHistory = [];
var chatOpen = false;
function openLiveChat(){
  document.getElementById('liveChatModal').style.display='flex';
  document.body.style.overflow='hidden';
  chatOpen=true;
  setTimeout(function(){document.getElementById('chatInput').focus();},300);
}
function closeLiveChat(){
  document.getElementById('liveChatModal').style.display='none';
  document.body.style.overflow='';
  chatOpen=false;
}
function sendQuickReply(msg){
  document.getElementById('chatInput').value=msg;
  sendChatMsg();
}
function appendMsg(text, isUser){
  var box=document.getElementById('chatMessages');
  var d=document.createElement('div');
  d.className='flex gap-2 items-end '+(isUser?'flex-row-reverse':'');
  var now=new Date().toLocaleTimeString('ar',{hour:'2-digit',minute:'2-digit'});
  if(isUser){
    d.innerHTML='<div class="bg-amber-600 text-white rounded-2xl rounded-bl-md px-4 py-2.5 max-w-[80%]"><p class="text-xs font-medium leading-relaxed">'+text+'</p><p class="text-[9px] text-white/60 mt-1 text-left">'+now+'</p></div>';
  } else {
    d.innerHTML='<div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0"><i class="fas fa-graduation-cap text-amber-600 text-[10px]"></i></div><div class="bg-white rounded-2xl rounded-br-md px-4 py-2.5 shadow-sm max-w-[80%]"><p class="text-xs text-slate-700 font-medium leading-relaxed">'+text+'</p><p class="text-[9px] text-slate-400 mt-1">'+now+'</p></div>';
  }
  box.appendChild(d);
  box.scrollTop=box.scrollHeight;
}
function showTyping(){
  var box=document.getElementById('chatMessages');
  var d=document.createElement('div');
  d.id='typingIndicator';d.className='flex gap-2 items-end';
  d.innerHTML='<div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0"><i class="fas fa-graduation-cap text-amber-600 text-[10px]"></i></div><div class="bg-white rounded-2xl rounded-br-md px-4 py-3 shadow-sm"><div class="flex gap-1">'+'<span style="width:6px;height:6px;background:#d97706;border-radius:50%;animation:bounce 1s infinite 0s"></span>'.repeat(3)+'</div></div>';
  box.appendChild(d);box.scrollTop=box.scrollHeight;
}
function removeTyping(){var t=document.getElementById('typingIndicator');if(t)t.remove();}
async function sendChatMsg(){
  var inp=document.getElementById('chatInput');
  var msg=(inp.value||'').trim();
  if(!msg)return;
  inp.value='';
  document.getElementById('quickReplies').style.display='none';
  appendMsg(msg,true);
  chatHistory.push({role:'user',content:msg});
  showTyping();
  try{
    var r=await fetch('/api/chatbot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,history:chatHistory})});
    var d=await r.json();
    removeTyping();
    var reply=d.reply||'شكراً على تواصلك! سنرد عليك قريباً.';
    appendMsg(reply,false);
    chatHistory.push({role:'assistant',content:reply});
    // زر واتساب لو show_wa أو طلب موظف
    var needWa = d.show_wa || msg.includes('موظف') || msg.includes('بشري') || msg.includes('مباشر');
    if(needWa){
      setTimeout(function(){
        var box=document.getElementById('chatMessages');
        var btn=document.createElement('div');
        btn.className='flex justify-center mt-1';
        btn.innerHTML='<a href="{{ settings.whatsapp }}" target="_blank" class="inline-flex items-center gap-2 bg-green-500 text-white text-xs font-bold px-4 py-2 rounded-full hover:bg-green-600 transition-all"><i class="fab fa-whatsapp"></i> تواصل واتساب</a>';
        box.appendChild(btn);box.scrollTop=box.scrollHeight;
      },400);
    }
  }catch(e){removeTyping();appendMsg('عذراً، حدث خطأ. حاول مجدداً.',false);}
}
</script>

<a href="{{ settings.whatsapp }}" target="_blank" class="wa-float" title="واتساب"><i class="fab fa-whatsapp"></i></a>

<!-- CART SIDEBAR -->
<div id="cartOverlay" onclick="closeCart()" style="display:none" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-[90]"></div>
<div id="cartSidebar" class="cart-sidebar fixed top-0 left-0 h-full w-full max-w-sm bg-white z-[100] shadow-2xl flex flex-col" style="transform:translateX(-100%)">
  <div class="flex items-center justify-between p-6 border-b border-slate-100">
    <h2 class="text-xl font-black flex items-center gap-2"><i class="fas fa-shopping-cart text-amber-600"></i> سلة الطلبات</h2>
    <button onclick="closeCart()" class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
  </div>
  <div id="cartItems" class="flex-grow overflow-y-auto p-6 space-y-4">
    <div id="emptyCartMsg" class="text-center py-16 text-slate-300"><i class="fas fa-shopping-bag text-5xl mb-4 block"></i><p class="text-sm font-bold">السلة فارغة</p><p class="text-xs mt-1">اضف خدمات لتبدا طلبك</p></div>
  </div>
  <div class="border-t border-slate-100 p-6 space-y-4">
    <div class="flex justify-between text-lg font-black"><span>الاجمالي:</span><span id="cartTotal" class="text-amber-600">0 ر.س</span></div>
    <button onclick="openCheckout()" id="checkoutBtn" disabled class="w-full bg-slate-900 text-white py-4 rounded-2xl font-black text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 transition-all flex items-center justify-center gap-2"><i class="fas fa-lock text-xs"></i> اتمام الطلب</button>
  </div>
</div>

<!-- CHECKOUT MODAL -->
<div id="checkoutModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[110]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative max-h-[92vh] overflow-y-auto">
    <button onclick="closeCheckout()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <div class="mb-6">
      <p class="text-amber-600 text-xs font-bold uppercase tracking-widest mb-1">ملخص الطلب</p>
      <h3 class="text-2xl font-black text-slate-900 mb-4">اتمام الطلب</h3>
      <div id="checkoutSummary" class="bg-slate-50 rounded-2xl p-4 space-y-3 text-sm text-slate-600 mb-3"></div>
      <div class="flex justify-between font-black text-base border-t border-slate-200 pt-3"><span>الاجمالي</span><span id="checkoutTotal" class="text-amber-600"></span></div>
    </div>
    <div class="space-y-4">
      <div class="relative"><i class="fas fa-user absolute right-4 top-4 text-slate-300"></i><input id="coName" placeholder="اسمك الكريم *" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div class="relative"><i class="fas fa-phone absolute right-4 top-4 text-slate-300"></i><input id="coPhone" type="tel" placeholder="رقم الجوال *" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div class="bg-slate-50 rounded-2xl p-3 border border-slate-100">
        <div class="flex gap-2">
          <input id="couponCode" placeholder="كود الخصم (اختياري)" class="flex-grow p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500" style="text-transform:uppercase">
          <button onclick="applyCoupon()" class="bg-amber-100 text-amber-700 px-4 py-3 rounded-xl font-bold text-xs hover:bg-amber-200 transition-all whitespace-nowrap">تطبيق</button>
        </div>
        <p id="couponMsg" class="text-xs mt-2 font-bold hidden"></p>
      </div>
      <button onclick="submitCartOrder()" id="submitCartBtn" class="w-full bg-slate-900 hover:bg-slate-700 text-white py-4 rounded-2xl font-black shadow-xl flex items-center justify-center gap-3 transition-all">تاكيد وارسال الطلب <i class="fas fa-paper-plane"></i></button>
    </div>
  </div>
</div>

<!-- SINGLE ORDER MODAL -->
<div id="orderModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[110]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative">
    <button onclick="closeOrderModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <div class="mb-6 text-center"><p class="text-amber-600 text-xs font-bold uppercase tracking-widest mb-1">طلب خدمة</p><h3 id="orderModalTitle" class="text-xl font-black text-slate-900"></h3></div>
    <div class="space-y-4">
      <div class="relative"><i class="fas fa-user absolute right-4 top-4 text-slate-300"></i><input id="sName" placeholder="اسمك الكريم *" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div class="relative"><i class="fas fa-phone absolute right-4 top-4 text-slate-300"></i><input id="sPhone" type="tel" placeholder="رقم الجوال *" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div>
        <textarea id="sNotes" placeholder="تفاصيل طلبك (مطلوب) - المستوى الدراسي، التخصص، الموعد النهائي... *" class="notes-req w-full p-4 rounded-2xl focus:border-amber-500 outline-none text-sm h-28 resize-none"></textarea>
        <p class="text-[11px] text-amber-600 font-bold mt-1 flex items-center gap-1"><i class="fas fa-exclamation-circle"></i> هذا الحقل مطلوب</p>
      </div>
      <div class="bg-slate-50 rounded-2xl p-3 border border-slate-100">
        <div class="flex gap-2">
          <input id="couponCodeSingle" placeholder="كود الخصم (اختياري)" class="flex-grow p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500" style="text-transform:uppercase">
          <button onclick="applyCouponSingle()" class="bg-amber-100 text-amber-700 px-4 py-3 rounded-xl font-bold text-xs hover:bg-amber-200 transition-all whitespace-nowrap">تطبيق</button>
        </div>
        <p id="couponMsgSingle" class="text-xs mt-2 font-bold hidden"></p>
      </div>
      <button onclick="submitSingleOrder()" id="submitSingleBtn" class="w-full bg-slate-900 hover:bg-slate-700 text-white py-4 rounded-2xl font-black shadow-xl flex items-center justify-center gap-3 transition-all">ارسال الطلب الان <i class="fas fa-paper-plane"></i></button>
    </div>
  </div>
</div>

<!-- SUCCESS MODAL -->
<div id="successModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[120]">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl text-center pop-in">
    <div class="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-check text-green-500 text-3xl"></i></div>
    <h3 class="text-xl font-black text-slate-900 mb-2">تم استلام طلبك!</h3>
    <p id="successOrderNum" class="text-amber-600 font-bold text-sm mb-1"></p>
    <p id="successEstDays" class="text-slate-500 text-xs mb-3 font-bold"></p>

    <!-- بيانات البنك - تظهر فقط إذا متوفرة -->
    <div id="successBankInfo" style="display:none" class="bg-blue-50 border-2 border-blue-200 rounded-2xl p-4 mb-4 text-right">
      <p class="text-xs font-black text-blue-800 mb-3 flex items-center gap-2"><i class="fas fa-university text-blue-600"></i> بيانات التحويل البنكي</p>
      <div class="space-y-2">
        <div class="flex justify-between items-center text-xs"><span class="text-slate-500">البنك</span><span id="sBankName" class="font-bold text-slate-800"></span></div>
        <div class="flex justify-between items-center text-xs"><span class="text-slate-500">اسم الحساب</span><span id="sBankHolder" class="font-bold text-slate-800"></span></div>
        <div class="bg-white rounded-xl p-2.5 flex justify-between items-center gap-2">
          <div><p class="text-[9px] text-slate-400 mb-0.5">رقم الحساب</p><p id="sBankAccount" class="text-xs font-mono font-black text-slate-800"></p></div>
          <button onclick="copyBankField('sBankAccount')" class="text-[10px] bg-blue-100 text-blue-700 px-2 py-1 rounded-lg font-bold whitespace-nowrap hover:bg-blue-200 transition-all"><i class="fas fa-copy ml-1"></i>نسخ</button>
        </div>
        <div class="bg-white rounded-xl p-2.5 flex justify-between items-center gap-2">
          <div><p class="text-[9px] text-slate-400 mb-0.5">رقم الآيبان</p><p id="sBankIban" class="text-xs font-mono font-black text-slate-800"></p></div>
          <button onclick="copyBankField('sBankIban')" class="text-[10px] bg-blue-100 text-blue-700 px-2 py-1 rounded-lg font-bold whitespace-nowrap hover:bg-blue-200 transition-all"><i class="fas fa-copy ml-1"></i>نسخ</button>
        </div>
      </div>
      <p class="text-[10px] text-blue-600 font-bold mt-3 flex items-center gap-1"><i class="fas fa-exclamation-circle"></i> بعد التحويل ارفع صورة الإيصال من الزر أدناه</p>
    </div>

    <div class="flex gap-3 mb-3">
      <a id="successTrackLink" href="#" class="flex-1 bg-slate-100 text-slate-700 py-3 rounded-2xl font-bold text-sm hover:bg-slate-200 transition-all flex items-center justify-center gap-1.5"><i class="fas fa-location-arrow text-xs"></i>تتبع</a>
      <a id="successWaLink" href="#" target="_blank" class="flex-1 bg-green-500 text-white py-3 rounded-2xl font-bold text-sm hover:bg-green-600 transition-all flex items-center justify-center gap-2"><i class="fab fa-whatsapp"></i> تأكيد</a>
    </div>
    <button onclick="closeSuccessModal();openReceiptModal(successOrderId);" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-3 rounded-2xl font-bold text-sm transition-all flex items-center justify-center gap-2">
      <i class="fas fa-file-invoice"></i> رفع ايصال التحويل البنكي
    </button>
  </div>
</div>

<!-- AUTH MODAL -->
<div id="authModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[120]">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl relative">
    <button onclick="closeAuthModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <div class="flex bg-slate-100 rounded-2xl p-1 mb-6">
      <button onclick="switchAuthTab('login')" id="auth-tab-login" class="flex-1 py-2.5 rounded-xl text-xs font-black transition-all bg-slate-900 text-white">تسجيل الدخول</button>
      <button onclick="switchAuthTab('register')" id="auth-tab-register" class="flex-1 py-2.5 rounded-xl text-xs font-black transition-all text-slate-500">حساب جديد</button>
    </div>
    <div id="auth-login">
      <div class="text-center mb-5"><div class="w-14 h-14 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-user text-slate-600 text-xl"></i></div><h3 class="text-lg font-black text-slate-900">مرحباً بك</h3><p class="text-slate-500 text-xs mt-1">سجّل دخولك لتسريع طلباتك</p></div>
      <div class="space-y-3">
        <div class="relative"><i class="fas fa-phone absolute right-4 top-4 text-slate-300"></i><input id="loginPhone" type="tel" placeholder="رقم الجوال" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <div class="relative"><i class="fas fa-lock absolute right-4 top-4 text-slate-300"></i><input id="loginPwd" type="password" placeholder="كلمة المرور" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <button type="button" onclick="switchAuthTab('forgot')" class="w-full text-amber-600 text-xs font-bold hover:text-amber-500">نسيت كلمة المرور؟</button>
        <button onclick="doLogin()" id="loginBtn" class="w-full bg-slate-900 hover:bg-slate-700 text-white py-4 rounded-2xl font-black text-sm transition-all flex items-center justify-center gap-2"><i class="fas fa-sign-in-alt"></i> دخول</button>
        <p id="loginError" class="text-red-500 text-xs text-center hidden mt-1"></p>
      </div>
    </div>
    <div id="auth-forgot" style="display:none">
      <div class="text-center mb-5"><div class="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-key text-amber-600 text-xl"></i></div><h3 class="text-lg font-black text-slate-900">استعادة كلمة المرور</h3><p class="text-slate-500 text-xs mt-1">سنرسل رابط إعادة التعيين إلى بريدك الإلكتروني</p></div>
      <div class="space-y-3">
        <div class="relative"><i class="fas fa-envelope absolute right-4 top-4 text-slate-300"></i><input id="forgotEmail" type="email" placeholder="البريد الإلكتروني" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <button onclick="doForgotPassword()" id="forgotBtn" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-4 rounded-2xl font-black text-sm transition-all flex items-center justify-center gap-2"><i class="fas fa-paper-plane"></i> إرسال الرابط</button>
        <p id="forgotMsg" class="text-xs text-center hidden mt-1"></p>
      </div>
    </div>
    <div id="auth-register" style="display:none">
      <div class="text-center mb-5"><div class="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-user-plus text-amber-600 text-xl"></i></div><h3 class="text-lg font-black text-slate-900">حساب جديد</h3><p class="text-slate-500 text-xs mt-1">سجّل مرة واحدة وطلّب بسهولة دائماً</p></div>
      <div class="space-y-3">
        <div class="relative"><i class="fas fa-user absolute right-4 top-4 text-slate-300"></i><input id="regName" type="text" placeholder="اسمك الكريم" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <div class="relative"><i class="fas fa-phone absolute right-4 top-4 text-slate-300"></i><input id="regPhone" type="tel" placeholder="رقم الجوال" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <div class="relative"><i class="fas fa-envelope absolute right-4 top-4 text-slate-300"></i><input id="regEmail" type="email" placeholder="البريد الإلكتروني" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <div class="relative"><i class="fas fa-lock absolute right-4 top-4 text-slate-300"></i><input id="regPwd" type="password" placeholder="كلمة مرور (6 احرف على الاقل)" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
        <button onclick="doRegister()" id="registerBtn" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-4 rounded-2xl font-black text-sm transition-all flex items-center justify-center gap-2"><i class="fas fa-user-plus"></i> انشاء الحساب</button>
        <p id="registerError" class="text-red-500 text-xs text-center hidden mt-1"></p>
      </div>
    </div>
  </div>
</div>

<!-- PROFILE MODAL -->
<div id="profileModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[115]">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl relative">
    <button onclick="closeProfileModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <div class="text-center mb-5">
      <div class="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-id-card text-amber-600 text-xl"></i></div>
      <h3 class="text-lg font-black text-slate-900">الملف الشخصي</h3>
      <p class="text-slate-500 text-xs mt-1">أضف بريدك لتقدر تستعيد كلمة المرور لاحقا</p>
    </div>
    <div class="space-y-3">
      <div class="relative"><i class="fas fa-user absolute right-4 top-4 text-slate-300"></i><input id="profileName" type="text" placeholder="الاسم" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <div class="relative"><i class="fas fa-phone absolute right-4 top-4 text-slate-300"></i><input id="profilePhone" type="tel" readonly placeholder="رقم الجوال" class="w-full pr-12 pl-4 py-4 bg-slate-100 text-slate-500 rounded-2xl border-2 border-slate-200 outline-none text-sm"></div>
      <div class="relative"><i class="fas fa-envelope absolute right-4 top-4 text-slate-300"></i><input id="profileEmail" type="email" placeholder="البريد الإلكتروني" class="w-full pr-12 pl-4 py-4 bg-slate-50 rounded-2xl border-2 border-slate-200 focus:border-amber-500 outline-none text-sm"></div>
      <button onclick="saveProfile()" id="profileBtn" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-4 rounded-2xl font-black text-sm transition-all flex items-center justify-center gap-2"><i class="fas fa-save"></i> حفظ البيانات</button>
      <p id="profileMsg" class="text-xs text-center hidden mt-1"></p>
    </div>
  </div>
</div>

<!-- MY ORDERS MODAL -->
<div id="myOrdersModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[110]">
  <div class="bg-white rounded-3xl w-full max-w-lg shadow-2xl relative max-h-[90vh] flex flex-col overflow-hidden">
    <div class="flex items-center justify-between p-6 border-b border-slate-100 flex-shrink-0">
      <div><h3 class="text-xl font-black text-slate-900 flex items-center gap-2"><i class="fas fa-receipt text-amber-600"></i> طلباتي</h3><p id="myOrdersSubtitle" class="text-slate-400 text-xs mt-0.5"></p></div>
      <button onclick="closeMyOrders()" class="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    </div>
    <div id="myOrdersPhoneArea" class="px-6 pt-4 flex-shrink-0" style="display:none">
      <div class="flex gap-2">
        <div class="relative flex-grow"><i class="fas fa-phone absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm"></i><input id="myOrdersPhone" type="tel" placeholder="رقم الجوال" class="w-full pr-10 pl-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500"></div>
        <button onclick="loadMyOrders()" class="bg-slate-900 text-white px-5 py-3 rounded-2xl font-bold text-sm hover:bg-slate-700 transition-all">بحث</button>
      </div>
    </div>
    <div id="myOrdersResult" class="overflow-y-auto p-6 space-y-3 flex-grow"></div>
  </div>
</div>

<!-- RECEIPT UPLOAD MODAL -->
<div id="receiptModal" style="display:none" class="fixed inset-0 bg-slate-900/70 backdrop-blur-md flex items-center justify-center p-4 z-[130]">
  <div class="bg-white rounded-3xl w-full max-w-sm p-8 shadow-2xl relative">
    <button onclick="closeReceiptModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <div class="text-center mb-5">
      <div class="w-16 h-16 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fas fa-file-invoice text-amber-600 text-2xl"></i></div>
      <h3 class="text-lg font-black text-slate-900">رفع ايصال التحويل</h3>
      <p class="text-slate-500 text-xs mt-1">ارفع صورة الايصال لتاكيد طلبك</p>
      <p id="receiptOrderNum" class="text-amber-600 font-bold text-sm mt-1"></p>
    </div>
    <div id="receiptPreviewArea" style="display:none" class="mb-4"><img id="receiptPreview" src="" alt="معاينة" class="w-full rounded-2xl border border-slate-200 max-h-52 object-contain"></div>
    <label class="block cursor-pointer mb-4">
      <div class="border-2 border-dashed border-amber-300 bg-amber-50 rounded-2xl p-6 text-center hover:bg-amber-100 transition-all">
        <i class="fas fa-cloud-upload-alt text-amber-500 text-2xl block mb-2"></i>
        <p class="text-sm font-bold text-amber-700">اضغط لاختيار صورة الايصال</p>
        <p class="text-xs text-amber-500 mt-1">JPG, PNG, HEIC</p>
      </div>
      <input type="file" id="receiptFile" accept="image/*" class="hidden" onchange="previewReceipt(this)">
    </label>
    <button onclick="submitReceipt()" id="submitReceiptBtn" disabled class="w-full bg-amber-600 hover:bg-amber-500 text-white py-4 rounded-2xl font-black text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"><i class="fas fa-paper-plane"></i> ارسال الايصال</button>
    <p id="receiptError" class="text-red-500 text-xs text-center mt-2 hidden"></p>
  </div>
</div>

<!-- REVIEW MODAL -->
<div id="reviewModal" style="display:none" class="fixed inset-0 bg-slate-900/70 backdrop-blur-md flex items-center justify-center p-4 z-[130]">
  <div class="bg-white rounded-3xl w-full max-w-md p-8 shadow-2xl relative">
    <button onclick="closeReviewModal()" class="absolute top-5 left-5 w-10 h-10 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-600 transition-all"><i class="fas fa-times"></i></button>

    <div class="text-center mb-6">
      <div class="w-16 h-16 bg-gradient-to-br from-amber-400 to-orange-500 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
        <i class="fas fa-star text-white text-2xl"></i>
      </div>
      <h3 class="text-2xl font-black text-slate-800 mb-1">كيف كانت تجربتك؟</h3>
      <p id="reviewOrderNum" class="text-amber-600 font-bold text-sm"></p>
    </div>

    <!-- اختيارات التقييم -->
    <div class="space-y-3 mb-6">
      <button onclick="setRatingChoice(5, 'ممتاز - أفوق التوقعات')" class="rating-choice w-full p-4 bg-slate-50 hover:bg-gradient-to-r hover:from-green-50 hover:to-emerald-50 border-2 border-slate-200 hover:border-green-400 rounded-2xl text-right font-bold text-slate-700 hover:text-green-700 transition-all duration-300 flex items-center gap-3">
        <span class="text-2xl">😍</span>
        <span>ممتاز - فوق التوقعات</span>
      </button>

      <button onclick="setRatingChoice(4, 'جيد جداً - راضي تماماً')" class="rating-choice w-full p-4 bg-slate-50 hover:bg-gradient-to-r hover:from-blue-50 hover:to-cyan-50 border-2 border-slate-200 hover:border-blue-400 rounded-2xl text-right font-bold text-slate-700 hover:text-blue-700 transition-all duration-300 flex items-center gap-3">
        <span class="text-2xl">😊</span>
        <span>جيد جداً - راضي تماماً</span>
      </button>

      <button onclick="setRatingChoice(3, 'جيد - يحتاج تحسين')" class="rating-choice w-full p-4 bg-slate-50 hover:bg-gradient-to-r hover:from-yellow-50 hover:to-amber-50 border-2 border-slate-200 hover:border-yellow-400 rounded-2xl text-right font-bold text-slate-700 hover:text-yellow-700 transition-all duration-300 flex items-center gap-3">
        <span class="text-2xl">🙂</span>
        <span>جيد - يحتاج تحسين</span>
      </button>

      <button onclick="setRatingChoice(2, 'مقبول - أقل من المتوقع')" class="rating-choice w-full p-4 bg-slate-50 hover:bg-gradient-to-r hover:from-orange-50 hover:to-red-50 border-2 border-slate-200 hover:border-orange-400 rounded-2xl text-right font-bold text-slate-700 hover:text-orange-700 transition-all duration-300 flex items-center gap-3">
        <span class="text-2xl">😐</span>
        <span>مقبول - أقل من المتوقع</span>
      </button>

      <button onclick="setRatingChoice(1, 'سيء - غير راضي')" class="rating-choice w-full p-4 bg-slate-50 hover:bg-gradient-to-r hover:from-red-50 hover:to-pink-50 border-2 border-slate-200 hover:border-red-400 rounded-2xl text-right font-bold text-slate-700 hover:text-red-700 transition-all duration-300 flex items-center gap-3">
        <span class="text-2xl">😞</span>
        <span>سيء - غير راضي</span>
      </button>
    </div>

    <textarea id="reviewComment" placeholder="أخبرنا المزيد عن تجربتك... (اختياري)" class="w-full p-4 bg-slate-50 border-2 border-slate-200 rounded-2xl text-sm resize-none outline-none focus:border-amber-400 focus:bg-white transition-all mb-4" rows="3" style="display:none"></textarea>

    <button onclick="submitReview()" id="submitReviewBtn" disabled class="w-full bg-slate-200 text-slate-400 py-4 rounded-2xl font-black text-base cursor-not-allowed transition-all duration-300">
      اختر تقييمك
    </button>
  </div>
</div>


<!-- TOAST -->
<div id="toast" class="bg-green-500 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 text-sm font-bold"><i class="fas fa-check-circle text-lg"></i><span id="toastMsg"></span></div>

<script>
var cart=[],spn='',spp=0,currentUser=null,successOrderId=null,currentReceiptOrderId=null,pendingAction=null;

// ============ CART ============
function addToCart(n,p){var f=false;for(var i=0;i<cart.length;i++){if(cart[i].name===n){cart[i].qty++;f=true;break;}}if(!f)cart.push({name:n,price:p,qty:1});renderCart();updateCartBadge();showToast('تمت اضافة "'+n+'" للسلة',true);}
function removeFromCart(i){cart.splice(i,1);renderCart();}
function changeQty(i,d){cart[i].qty=Math.max(1,cart[i].qty+d);renderCart();}
function renderCart(){
  var c=document.getElementById('cartItems'),em=document.getElementById('emptyCartMsg'),badge=document.getElementById('cartBadge'),btn=document.getElementById('checkoutBtn'),tot=0,cnt=0;
  for(var i=0;i<cart.length;i++){tot+=cart[i].price*cart[i].qty;cnt+=cart[i].qty;}
  document.getElementById('cartTotal').innerText=tot.toFixed(0)+' ر.س';
  badge.style.display=cnt>0?'flex':'none';badge.innerText=cnt;
  btn.disabled=cart.length===0;
  var ex=c.querySelectorAll('.ci');for(var j=0;j<ex.length;j++)ex[j].remove();
  em.style.display=cart.length?'none':'block';
  for(var k=0;k<cart.length;k++){(function(item,idx){var d=document.createElement('div');d.className='ci flex items-center gap-3 bg-slate-50 rounded-2xl p-3';
  d.innerHTML='<div class="flex-grow min-w-0"><p class="font-bold text-sm text-slate-800 truncate">'+item.name+'</p><p class="text-amber-600 font-black text-sm">'+(item.price*item.qty).toFixed(0)+' ر.س</p></div>'+
  '<div class="flex items-center gap-1 bg-white border border-slate-200 rounded-xl px-1"><button class="qty-btn text-slate-500" onclick="changeQty('+idx+',-1)">−</button><span class="w-7 text-center font-bold text-sm">'+item.qty+'</span><button class="qty-btn text-slate-500" onclick="changeQty('+idx+',1)">+</button></div>'+
  '<button onclick="removeFromCart('+idx+')" class="w-8 h-8 rounded-xl bg-red-50 text-red-400 hover:bg-red-500 hover:text-white transition-all flex items-center justify-center"><i class="fas fa-trash text-xs"></i></button>';
  c.appendChild(d);})(cart[k],k);}
}
function openCart(){document.getElementById('cartSidebar').classList.add('open');document.getElementById('cartOverlay').style.display='block';document.body.style.overflow='hidden';}
function closeCart(){document.getElementById('cartSidebar').classList.remove('open');document.getElementById('cartOverlay').style.display='none';document.body.style.overflow='';}
function openCheckout(){
  if(!currentUser){pendingAction=openCheckout;openAuthModal('login');showToast('سجّل دخولك أولاً لإتمام الطلب',false);return;}
  closeCart();var html='',tot=0;
  for(var i=0;i<cart.length;i++){var s=cart[i].price*cart[i].qty;tot+=s;html+='<div class="flex justify-between"><span>'+cart[i].name+' x'+cart[i].qty+'</span><span class="font-bold">'+s.toFixed(0)+' ر.س</span></div>';}
  document.getElementById('checkoutSummary').innerHTML=html;document.getElementById('checkoutTotal').innerText=tot.toFixed(0)+' ر.س';
  // Apply seasonal discount
  fetch('/api/active_offer').then(function(r){return r.json();}).then(function(d){
    if(d.status==='success'&&d.discount>0){
      var totalEl=document.getElementById('checkoutTotal');
      if(totalEl){
        var currentTotal=tot;
        var discountAmount=currentTotal*(d.discount/100);
        var finalTotal=currentTotal-discountAmount;
        var summary=document.getElementById('checkoutSummary');
        summary.insertAdjacentHTML('afterbegin','<div class="bg-green-50 border border-green-200 rounded-xl p-2 mb-3 text-center"><i class="fas fa-gift text-green-600 ml-1"></i><span class="text-green-700 font-bold text-xs">'+d.banner+' - خصم '+d.discount+'%</span></div>');
        summary.insertAdjacentHTML('beforeend','<div class="flex justify-between mt-2 text-green-600"><span class="text-sm font-bold">الخصم الموسمي</span><span class="font-black">-'+discountAmount.toFixed(0)+' ر.س</span></div>');
        totalEl.innerText=finalTotal.toFixed(0)+' ر.س';
        window.checkoutFinalTotal=finalTotal;
        window.seasonalDiscount=d.discount;
        window.seasonalDiscountAmount=discountAmount;
      }
    }
  }).catch(function(){});
  document.getElementById('checkoutModal').style.display='flex';document.body.style.overflow='hidden';fillUserFields();
}
function closeCheckout(){document.getElementById('checkoutModal').style.display='none';document.body.style.overflow='';}

async function submitCartOrder(){
  var name=document.getElementById('coName').value.trim(),phone=document.getElementById('coPhone').value.trim(),notes=document.getElementById('coNotes').value.trim(),btn=document.getElementById('submitCartBtn');
  if(!name){pulse('coName');showToast('يرجى ادخال اسمك',false);return;}
  if(!phone||!/^[0-9+]{7,15}$/.test(phone)){pulse('coPhone');showToast('رقم الجوال غير صحيح',false);return;}
  if(!notes){pulse('coNotes');showToast('يرجى كتابة تفاصيل طلبك',false);return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> جاري الارسال...';
  try{var r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      name:name,
      phone:phone,
      notes:notes,
      cart:cart,
      coupon_code:window.appliedCoupon||'',
      seasonal_discount:window.seasonalDiscount||0,
      final_total:window.checkoutFinalTotal||(function(){
        var t=0;
        for(var i=0;i<cart.length;i++) t+=cart[i].price*cart[i].qty;
        return t;
      })()
    })});
  var d=await r.json();
  if(r.ok&&d.status==='success'){closeCheckout();cart=[];renderCart();document.getElementById('coNotes').value='';showSuccessModal(d.order_id,d.customer_wa_link,d.estimated_days||'',d.bank_info||null);}
  else showToast(d.message||'حدث خطا',false);}catch(e){showToast('تعذر الاتصال',false);}
  btn.disabled=false;btn.innerHTML='تاكيد وارسال الطلب <i class="fas fa-paper-plane"></i>';
}

function openSingleOrder(n,p){
  if(!currentUser){pendingAction=function(){openSingleOrder(n,p);};openAuthModal('login');showToast('سجّل دخولك أولاً لإتمام الطلب',false);return;}
  spn=n;spp=p;document.getElementById('orderModalTitle').innerText=n;
  document.getElementById('orderModal').style.display='flex';document.body.style.overflow='hidden';fillUserFields();
}
function closeOrderModal(){document.getElementById('orderModal').style.display='none';document.body.style.overflow='';}

async function submitSingleOrder(){
  var name=document.getElementById('sName').value.trim(),phone=document.getElementById('sPhone').value.trim(),notes=document.getElementById('sNotes').value.trim(),btn=document.getElementById('submitSingleBtn');
  if(!name){pulse('sName');showToast('يرجى ادخال اسمك',false);return;}
  if(!phone||!/^[0-9+]{7,15}$/.test(phone)){pulse('sPhone');showToast('رقم الجوال غير صحيح',false);return;}
  if(!notes){pulse('sNotes');showToast('يرجى كتابة تفاصيل طلبك',false);return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> جاري الارسال...';
  try{var r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,phone:phone,notes:notes,product_name:spn,cart:[{name:spn,price:spp,qty:1}]})});
  var d=await r.json();
  if(r.ok&&d.status==='success'){closeOrderModal();document.getElementById('sNotes').value='';showSuccessModal(d.order_id,d.customer_wa_link,d.estimated_days||'',d.bank_info||null);}
  else showToast(d.message||'حدث خطا',false);}catch(e){showToast('تعذر الاتصال',false);}
  btn.disabled=false;btn.innerHTML='ارسال الطلب الان <i class="fas fa-paper-plane"></i>';
}

function showSuccessModal(orderId,waLink,estimatedDays,bankInfo){
  successOrderId=orderId;
  document.getElementById('successOrderNum').innerText='رقم طلبك: #'+orderId;
  var estEl=document.getElementById('successEstDays');
  if(estEl){estEl.innerText=estimatedDays?'⏱️ وقت التسليم المتوقع: '+estimatedDays:'';}
  var wa=document.getElementById('successWaLink');
  if(waLink){wa.href=waLink;wa.style.display='flex';}else wa.style.display='none';
  // رابط تتبع الطلب
  var trackEl=document.getElementById('successTrackLink');
  if(trackEl){trackEl.href='/order/'+orderId;}
  // بيانات البنك
  var bankDiv=document.getElementById('successBankInfo');
  if(bankInfo&&bankInfo.bank_name&&bankDiv){
    document.getElementById('sBankName').innerText=bankInfo.bank_name||'';
    document.getElementById('sBankHolder').innerText=bankInfo.bank_holder||'';
    document.getElementById('sBankAccount').innerText=bankInfo.bank_account||'';
    document.getElementById('sBankIban').innerText=bankInfo.bank_iban||'';
    bankDiv.style.display='block';
  } else if(bankDiv){ bankDiv.style.display='none'; }
  document.getElementById('successModal').style.display='flex';
  // بدأ polling لتتبع حالة الطلب
  startOrderPolling(orderId);
  requestNotificationPermission();
}
function closeSuccessModal(){document.getElementById('successModal').style.display='none';}

// ============ DARK MODE ============
function toggleDarkMode(){
  var html=document.documentElement;
  var isDark=html.classList.toggle('dark');
  var icon=document.getElementById('darkModeIcon');
  if(icon){icon.className=isDark?'fas fa-sun text-sm text-amber-400':'fas fa-moon text-sm';}
  try{localStorage.setItem('darkMode',isDark?'1':'0');}catch(e){}
}
// تطبيق dark mode المحفوظ
(function(){
  try{
    var saved=localStorage.getItem('darkMode');
    if(saved==='1'){
      document.documentElement.classList.add('dark');
      setTimeout(function(){
        var icon=document.getElementById('darkModeIcon');
        if(icon)icon.className='fas fa-sun text-sm text-amber-400';
      },100);
    }
  }catch(e){}
})();

// ============ PUSH NOTIFICATIONS (Polling) ============
var activeOrderIds=[];
var pollInterval=null;
function startOrderPolling(orderId){
  if(activeOrderIds.indexOf(orderId)===-1) activeOrderIds.push(orderId);
  if(!pollInterval){
    pollInterval=setInterval(function(){
      activeOrderIds.forEach(function(id){
        fetch('/api/order_status_check/'+id)
          .then(function(r){return r.json();})
          .then(function(d){
            if(d.status==='success'){
              var key='order_status_'+id;
              var prev=sessionStorage.getItem(key);
              if(prev && prev!==d.order_status){
                showPushNotification('تحديث طلبك #'+id,'حالة طلبك الآن: '+d.order_status);
                sessionStorage.setItem(key,d.order_status);
              } else if(!prev){
                sessionStorage.setItem(key,d.order_status);
              }
            }
          }).catch(function(){});
      });
    },30000); // كل 30 ثانية
  }
}
function showPushNotification(title,body){
  if('Notification' in window && Notification.permission==='granted'){
    new Notification(title,{body:body,icon:'/favicon.ico'});
  } else {
    showToast(title+' - '+body,true);
  }
}
function requestNotificationPermission(){
  if('Notification' in window && Notification.permission==='default'){
    Notification.requestPermission();
  }
}


async function checkSession(){
  try{var r=await fetch('/api/customer/me');var d=await r.json();if(d.status==='logged_in')setLoggedIn(d.name,d.phone,d.email||'');}catch(e){}
}
checkSession();

function setLoggedIn(name,phone,email){
  currentUser={name:name,phone:phone,email:email||''};
  document.getElementById('guestBtn').style.display='none';
  document.getElementById('loggedInBtn').style.display='block';
  document.getElementById('headerUserName').innerText=name;
  document.getElementById('menuUserName').innerText=name;
  document.getElementById('menuUserPhone').innerText=phone;
  fillUserFields();
}
function fillUserFields(){
  if(!currentUser)return;
  var fields=[['coName','coPhone'],['sName','sPhone']];
  fields.forEach(function(p){
    var n=document.getElementById(p[0]),ph=document.getElementById(p[1]);
    if(n){n.value=currentUser.name;n.style.background='#f8fafc';n.style.color='#64748b';n.readOnly=true;}
    if(ph){ph.value=currentUser.phone;ph.style.background='#f8fafc';ph.style.color='#64748b';ph.readOnly=true;}
  });
}
function setGuest(){
  currentUser=null;
  document.getElementById('guestBtn').style.display='block';
  document.getElementById('loggedInBtn').style.display='none';
  ['coName','coPhone','sName','sPhone'].forEach(function(id){var el=document.getElementById(id);if(el){el.readOnly=false;el.style.background='';el.style.color='';el.value='';}});
}
function toggleUserMenu(){var m=document.getElementById('userMenu');m.style.display=m.style.display==='none'?'block':'none';}
function closeUserMenu(){document.getElementById('userMenu').style.display='none';}
document.addEventListener('click',function(e){var b=document.getElementById('loggedInBtn');if(b&&!b.contains(e.target))closeUserMenu();});
async function doCustomerLogout(){closeUserMenu();try{await fetch('/api/customer/logout',{method:'POST'});}catch(e){}setGuest();showToast('تم تسجيل الخروج',true);}
function openProfileModal(){
  if(!currentUser){openAuthModal('login');return;}
  document.getElementById('profileName').value=currentUser.name||'';
  document.getElementById('profilePhone').value=currentUser.phone||'';
  document.getElementById('profileEmail').value=currentUser.email||'';
  document.getElementById('profileMsg').className='text-xs text-center hidden mt-1';
  document.getElementById('profileModal').style.display='flex';
  document.body.style.overflow='hidden';
}
function closeProfileModal(){document.getElementById('profileModal').style.display='none';document.body.style.overflow='';}
async function saveProfile(){
  var name=document.getElementById('profileName').value.trim(),email=document.getElementById('profileEmail').value.trim(),btn=document.getElementById('profileBtn'),msg=document.getElementById('profileMsg');
  msg.className='text-xs text-center hidden mt-1';
  if(!name||!email){msg.innerText='الاسم والبريد الإلكتروني مطلوبان';msg.className='text-red-500 text-xs text-center mt-1';return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  try{
    var r=await fetch('/api/customer/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,email:email})});
    var d=await r.json();
    msg.innerText=d.message||'';
    msg.className=(r.ok?'text-green-600':'text-red-500')+' text-xs text-center mt-1';
    if(r.ok){setLoggedIn(d.name,d.phone,d.email||'');setTimeout(closeProfileModal,700);}
  }catch(e){msg.innerText='تعذر الاتصال';msg.className='text-red-500 text-xs text-center mt-1';}
  btn.disabled=false;btn.innerHTML='<i class="fas fa-save"></i> حفظ البيانات';
}
function openAuthModal(tab){switchAuthTab(tab||'login');document.getElementById('authModal').style.display='flex';document.body.style.overflow='hidden';}
function closeAuthModal(){document.getElementById('authModal').style.display='none';document.body.style.overflow='';}
function switchAuthTab(tab){
  document.getElementById('auth-login').style.display=tab==='login'?'block':'none';
  document.getElementById('auth-register').style.display=tab==='register'?'block':'none';
  document.getElementById('auth-forgot').style.display=tab==='forgot'?'block':'none';
  var base='flex-1 py-2.5 rounded-xl text-xs font-black transition-all ';
  document.getElementById('auth-tab-login').className=base+(tab==='login'?'bg-slate-900 text-white':'text-slate-500');
  document.getElementById('auth-tab-register').className=base+(tab==='register'?'bg-amber-600 text-white':'text-slate-500');
}
async function doLogin(){
  var phone=document.getElementById('loginPhone').value.trim(),pwd=document.getElementById('loginPwd').value.trim(),btn=document.getElementById('loginBtn'),err=document.getElementById('loginError');
  err.classList.add('hidden');if(!phone||!pwd){err.innerText='ادخل الجوال وكلمة المرور';err.classList.remove('hidden');return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  try{var r=await fetch('/api/customer/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:phone,password:pwd})});var d=await r.json();
  if(r.ok&&d.status==='success'){setLoggedIn(d.name,d.phone,d.email||'');closeAuthModal();document.getElementById('loginPhone').value='';document.getElementById('loginPwd').value='';showToast('مرحباً '+d.name+'!',true);if(pendingAction){var fn=pendingAction;pendingAction=null;setTimeout(fn,400);}}
  else{err.innerText=d.message||'بيانات غير صحيحة';err.classList.remove('hidden');}}catch(e){err.innerText='تعذر الاتصال';err.classList.remove('hidden');}
  btn.disabled=false;btn.innerHTML='<i class="fas fa-sign-in-alt"></i> دخول';
}
async function doForgotPassword(){
  var email=document.getElementById('forgotEmail').value.trim(),btn=document.getElementById('forgotBtn'),msg=document.getElementById('forgotMsg');
  msg.className='text-xs text-center hidden mt-1';
  if(!email){msg.innerText='أدخل البريد الإلكتروني';msg.className='text-red-500 text-xs text-center mt-1';return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  try{
    var r=await fetch('/api/customer/forgot-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email})});
    var d=await r.json();
    msg.innerText=d.message||'تم إرسال رابط إعادة التعيين';
    msg.className=(r.ok?'text-green-600':'text-red-500')+' text-xs text-center mt-1';
  }catch(e){msg.innerText='تعذر الاتصال';msg.className='text-red-500 text-xs text-center mt-1';}
  btn.disabled=false;btn.innerHTML='<i class="fas fa-paper-plane"></i> إرسال الرابط';
}
async function doRegister(){
  var name=document.getElementById('regName').value.trim(),phone=document.getElementById('regPhone').value.trim(),email=document.getElementById('regEmail').value.trim(),pwd=document.getElementById('regPwd').value.trim(),btn=document.getElementById('registerBtn'),err=document.getElementById('registerError');
  err.classList.add('hidden');if(!name||!phone||!email||!pwd){err.innerText='جميع الحقول مطلوبة';err.classList.remove('hidden');return;}
  if(pwd.length<6){err.innerText='كلمة المرور 6 احرف على الاقل';err.classList.remove('hidden');return;}
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  try{var r=await fetch('/api/customer/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,phone:phone,email:email,password:pwd})});var d=await r.json();
  if(r.ok&&d.status==='success'){setLoggedIn(d.name,d.phone,d.email||'');closeAuthModal();document.getElementById('regName').value='';document.getElementById('regPhone').value='';document.getElementById('regEmail').value='';document.getElementById('regPwd').value='';showToast('تم انشاء حسابك! مرحباً '+d.name,true);if(pendingAction){var fn=pendingAction;pendingAction=null;setTimeout(fn,400);}}
  else{err.innerText=d.message||'خطا في التسجيل';err.classList.remove('hidden');}}catch(e){err.innerText='تعذر الاتصال';err.classList.remove('hidden');}
  btn.disabled=false;btn.innerHTML='<i class="fas fa-user-plus"></i> انشاء الحساب';
}

// ============ MY ORDERS ============
function openMyOrders(){
  document.getElementById('myOrdersModal').style.display='flex';
  document.body.style.overflow='hidden';
  document.getElementById('myOrdersResult').innerHTML='';
  if(currentUser){
    document.getElementById('myOrdersPhoneArea').style.display='none';
    document.getElementById('myOrdersSubtitle').innerText='طلبات '+currentUser.name;
    loadMyOrders();
  }else{
    document.getElementById('myOrdersPhoneArea').style.display='block';
    document.getElementById('myOrdersSubtitle').innerText='ادخل رقم جوالك لعرض طلباتك';
  }
}
function closeMyOrders(){document.getElementById('myOrdersModal').style.display='none';document.body.style.overflow='';}

async function loadMyOrders(){
  var result=document.getElementById('myOrdersResult');
  result.innerHTML='<div class="text-center py-8 text-amber-600"><i class="fas fa-spinner fa-spin text-2xl block mb-2"></i><p class="text-xs">جاري البحث...</p></div>';
  var body={};
  if(!currentUser){
    var phone=document.getElementById('myOrdersPhone').value.trim();
    if(!phone){result.innerHTML='<p class="text-slate-400 text-sm text-center py-6">ادخل رقم جوالك للبحث</p>';return;}
    body={phone:phone};
  }
  try{
    var r=await fetch('/api/my_orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var d=await r.json();
    if(d.orders&&d.orders.length>0){
      var sm={'جديد':'bg-blue-100 text-blue-700','جار التجهيز':'bg-amber-100 text-amber-700','بانتظار الدفع':'bg-green-100 text-green-700','يتطلب تعديل':'bg-purple-100 text-purple-700','ملغي':'bg-red-100 text-red-700','مكتمل':'bg-emerald-100 text-emerald-700'};
      result.innerHTML=d.orders.map(function(o){
        var sc=sm[o.status]||'bg-slate-100 text-slate-700';
        var items=o.items.map(function(i){return'<span>'+i.name+' x'+i.qty+'</span>';}).join(' • ');
        var receiptBtn='';
        if(o.status==='بانتظار الدفع'&&o.receipt_rejected){
          receiptBtn='<div class="bg-red-50 border-2 border-red-200 rounded-xl p-3 mt-2"><p class="text-xs text-red-700 font-bold mb-2"><i class="fas fa-exclamation-triangle ml-1"></i>الإيصال المرفوع غير صحيح</p>'+
            '<button onclick="uploadNewReceipt('+o.id+')" class="w-full text-xs bg-red-600 text-white px-3 py-2 rounded-lg font-bold hover:bg-red-500"><i class="fas fa-upload ml-1"></i>رفع إيصال جديد</button></div>';
        }
        if(o.status==='مكتمل'){
          receiptBtn='<div class="flex gap-2 mt-2 flex-wrap">'+
            '<button onclick="downloadDelivery('+o.id+')" class="text-[10px] bg-green-50 border border-green-200 text-green-700 px-3 py-1.5 rounded-xl font-bold hover:bg-green-100 transition-all flex items-center gap-1"><i class="fas fa-download"></i>تحميل الملف</button>'+
            '<button onclick="downloadInvoicePDF('+o.id+')" class="text-[10px] bg-indigo-50 border border-indigo-200 text-indigo-700 px-3 py-1.5 rounded-xl font-bold hover:bg-indigo-100 transition-all flex items-center gap-1"><i class="fas fa-file-invoice"></i>إيصال الشراء</button>'+
            '<button onclick="openReviewModal('+o.id+')" class="text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-xl font-bold hover:bg-amber-100 transition-all flex items-center gap-1"><i class="fas fa-star text-amber-400"></i>قيّم</button>'+
          '</div>';
        }else if(o.status!=='ملغي'){
          var rIcon=o.has_receipt?'check-circle text-green-500':'file-invoice text-amber-600';
          var rLabel=o.has_receipt?'تم رفع الايصال - رفع مجدداً':'رفع ايصال التحويل';
          receiptBtn='<button onclick="openReceiptModal('+o.id+')" class="mt-2 text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-xl font-bold hover:bg-amber-100 transition-all flex items-center gap-1.5"><i class="fas fa-'+rIcon+'"></i>'+rLabel+'</button>';
        }
        return '<div class="border border-slate-100 rounded-2xl p-4 bg-slate-50 hover:bg-white transition-all">'+
          '<div class="flex justify-between items-start mb-2"><div><span class="font-black text-slate-800">#'+o.id+'</span><span class="text-[10px] text-slate-400 mr-2">'+o.date+'</span></div><span class="text-[10px] px-2 py-1 rounded-full font-bold '+sc+'">'+o.status+'</span></div>'+
          '<div class="flex gap-1 mb-2">'+
            '<div class="h-1.5 flex-1 rounded-full '+(["جديد","جار التجهيز","بانتظار الدفع","مكتمل"].indexOf(o.status)>=0?"bg-amber-400":"bg-slate-200")+'"></div>'+
            '<div class="h-1.5 flex-1 rounded-full '+(["جار التجهيز","بانتظار الدفع","مكتمل"].indexOf(o.status)>=0?"bg-amber-400":"bg-slate-200")+'"></div>'+
            '<div class="h-1.5 flex-1 rounded-full '+(["بانتظار الدفع","مكتمل"].indexOf(o.status)>=0?"bg-amber-400":"bg-slate-200")+'"></div>'+
            '<div class="h-1.5 flex-1 rounded-full '+(o.status==="مكتمل"?"bg-green-500":"bg-slate-200")+'"></div>'+
          '</div>'+
          '<p class="text-xs text-slate-500 mb-1">'+items+'</p>'+
          '<div class="flex items-center justify-between"><p class="font-black text-amber-600">'+o.total.toFixed(0)+' ر.س</p>'+receiptBtn+'</div>'+
        '</div>';
      }).join('');
    }else{
      result.innerHTML='<div class="text-center py-10 text-slate-300"><i class="fas fa-box-open text-4xl mb-3 block"></i><p class="text-sm font-bold">لا توجد طلبات</p></div>';
    }
  }catch(e){result.innerHTML='<p class="text-red-500 text-sm text-center py-4">تعذر البحث</p>';}
}

// ============ RECEIPT ============
function openReceiptModal(orderId){
  currentReceiptOrderId=orderId;
  document.getElementById('receiptOrderNum').innerText='طلب رقم #'+orderId;
  document.getElementById('receiptPreviewArea').style.display='none';
  document.getElementById('receiptFile').value='';
  document.getElementById('submitReceiptBtn').disabled=true;
  document.getElementById('receiptError').classList.add('hidden');
  document.getElementById('receiptModal').style.display='flex';
}
function closeReceiptModal(){document.getElementById('receiptModal').style.display='none';}
function previewReceipt(input){
  if(!input.files||!input.files[0])return;
  var reader=new FileReader();
  reader.onload=function(e){document.getElementById('receiptPreview').src=e.target.result;document.getElementById('receiptPreviewArea').style.display='block';document.getElementById('submitReceiptBtn').disabled=false;};
  reader.readAsDataURL(input.files[0]);
}
async function submitReceipt(){
  if(!currentReceiptOrderId)return;
  var file=document.getElementById('receiptFile').files[0];
  if(!file){document.getElementById('receiptError').innerText='اختر صورة الايصال';document.getElementById('receiptError').classList.remove('hidden');return;}
  var btn=document.getElementById('submitReceiptBtn');
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> جاري الرفع...';
  var fd=new FormData();fd.append('receipt',file);
  try{
    var r=await fetch('/api/upload_receipt/'+currentReceiptOrderId,{method:'POST',body:fd});
    var d=await r.json();
    if(r.ok&&d.status==='success'){closeReceiptModal();showToast('تم رفع الايصال بنجاح!',true);if(document.getElementById('myOrdersModal').style.display!=='none')loadMyOrders();}
    else{document.getElementById('receiptError').innerText=d.message||'خطا في الرفع';document.getElementById('receiptError').classList.remove('hidden');}
  }catch(e){document.getElementById('receiptError').innerText='تعذر الرفع';document.getElementById('receiptError').classList.remove('hidden');}
  btn.disabled=false;btn.innerHTML='<i class="fas fa-paper-plane"></i> ارسال الايصال';
}

// ============ HELPERS ============
function copyBankField(id){var el=document.getElementById(id);if(!el)return;navigator.clipboard.writeText(el.innerText).then(function(){showToast('تم نسخ '+el.innerText,true);}).catch(function(){});}
function pulse(id){var el=document.getElementById(id);el.classList.add('rf');el.focus();setTimeout(function(){el.classList.remove('rf');},2500);}
function showToast(msg,ok){var t=document.getElementById('toast');document.getElementById('toastMsg').innerText=msg;t.className=(ok!==false?'bg-green-500':'bg-red-500')+' text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 text-sm font-bold';t.classList.add('show');setTimeout(function(){t.classList.remove('show');},4500);}
var ac='all';
function filterProducts(){var q=document.getElementById('searchInput').value.toLowerCase(),cards=document.querySelectorAll('.product-card'),v=0;cards.forEach(function(c){var ok=(!q||c.dataset.name.includes(q)||c.dataset.desc.includes(q))&&(ac==='all'||c.dataset.category===ac);c.style.display=ok?'':'none';if(ok)v++;});document.getElementById('emptyState').classList.toggle('hidden',v>0);}
function filterByCategory(cat){ac=cat;document.querySelectorAll('.cat-btn').forEach(function(b){b.classList.toggle('active',b.textContent.trim()===(cat==='all'?'الكل':cat));});filterProducts();}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeCheckout();closeOrderModal();closeCart();closeMyOrders();closeSuccessModal();closeAuthModal();closeReceiptModal();closeReviewModal();}});

// ===== SEASONAL OFFER BANNER =====
async function loadOfferBanner(){
  try{
    var r=await fetch('/api/active_offer');var d=await r.json();
    if(d.status==='success'){
      document.getElementById('offerBannerText').querySelector('span').innerText=d.banner||d.title+' - خصم '+d.discount+'%';
      document.getElementById('offerBanner').style.display='block';
    }
  }catch(e){}
}
loadOfferBanner();

// ===== TESTIMONIALS =====
async function loadTestimonials(){
  try{
    var r=await fetch('/api/testimonials');var list=await r.json();
    var el=document.getElementById('testimonialsList');
    if(!list.length){el.innerHTML='<p class="text-center text-slate-400 text-sm col-span-full py-6">لا توجد تقييمات حالياً</p>';return;}
    el.innerHTML=list.map(function(t){
      var stars='';for(var i=0;i<5;i++)stars+='<span class="'+(i<t.rating?'text-amber-400':'text-slate-300')+'">★</span>';
      return '<div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100">'+
        '<div class="flex items-center gap-2 mb-3"><div class="w-9 h-9 bg-amber-100 rounded-full flex items-center justify-center font-black text-amber-700 text-sm">'+t.name.charAt(0)+'</div>'+
        '<div><p class="font-bold text-sm text-slate-800">'+t.name+'</p><div class="text-sm">'+stars+'</div></div></div>'+
        '<p class="text-slate-600 text-xs leading-relaxed">'+t.text+'</p></div>';
    }).join('');
  }catch(e){}
}
loadTestimonials();

// ===== DOWNLOAD DELIVERY FILE =====
async function downloadDelivery(orderId){
  try{
    var r=await fetch('/api/download_delivery/'+orderId);
    var d=await r.json();
    if(d.status==='success'&&d.file){
      var a=document.createElement('a');
      a.href=d.file;a.download=d.filename||'delivery';
      document.body.appendChild(a);a.click();a.remove();
      showToast('جاري تحميل الملف...',true);
    }else{showToast('لم يتم تسليم الملف بعد',false);}
  }catch(e){showToast('تعذر التحميل',false);}
}

// ===== REFERRAL =====
async function showReferralCode(){
  try{
    var r=await fetch('/api/generate_referral');var d=await r.json();
    if(d.status==='success'){
      showToast('كود الإحالة: '+d.code+' - شاركه مع أصدقائك!',true);
      navigator.clipboard.writeText(d.code);
    }
  }catch(e){}
}

// ===== STATS =====
async function loadStats(){
  try{
    var r=await fetch('/api/stats_public');var d=await r.json();
    if(d.completed!==undefined){animateNum('statCompleted',d.completed);animateNum('statProducts',d.products);}
  }catch(e){}
}
function animateNum(id,target){
  var el=document.getElementById(id);if(!el)return;
  var n=0,step=Math.max(1,Math.ceil(target/40));
  var t=setInterval(function(){n=Math.min(n+step,target);el.innerText=n+'+';if(n>=target)clearInterval(t);},25);
}
loadStats();
// Auto-open auth if redirected from product page
if(window.location.search.includes('login=1')){
  setTimeout(function(){openAuthModal('login');showToast('سجّل دخولك لإتمام الطلب',false);},500);
}

// ===== COUPON =====
var appliedCoupon=null;
async function applyCoupon(){
  var code=document.getElementById('couponCode').value.trim().toUpperCase();
  var msg=document.getElementById('couponMsg');
  if(!code)return;

  // Use price after seasonal discount if applied
  var baseTotal=0;
  for(var i=0;i<cart.length;i++) baseTotal+=cart[i].price*cart[i].qty;

  // Apply seasonal discount first
  var totalAfterSeasonal = window.checkoutFinalTotal || baseTotal;

  try{
    var r=await fetch('/api/validate_coupon',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({code:code,total:totalAfterSeasonal})
    });
    var d=await r.json();
    if(d.status==='success'){
      appliedCoupon=d;
      window.appliedCoupon=code;
      window.checkoutFinalTotal=d.new_total;

      msg.innerText='✓ '+d.desc+' - الإجمالي: '+d.new_total.toFixed(0)+' ر.س';
      msg.className='text-xs mt-2 font-bold text-green-600';
      msg.classList.remove('hidden');
      document.getElementById('checkoutTotal').innerText=d.new_total.toFixed(0)+' ر.س';
    }else{
      appliedCoupon=null;
      window.appliedCoupon='';
      msg.innerText='✗ '+d.message;
      msg.className='text-xs mt-2 font-bold text-red-500';
      msg.classList.remove('hidden');
    }
  }catch(e){}
}

// ===== COUPON SINGLE =====
var appliedCouponSingle=null;
async function applyCouponSingle(){
  var code=document.getElementById('couponCodeSingle').value.trim().toUpperCase();
  var msg=document.getElementById('couponMsgSingle');
  if(!code)return;
  try{
    var r=await fetch('/api/validate_coupon',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({code:code,total:spp})});
    var d=await r.json();
    if(d.status==='success'){
      appliedCouponSingle=d;
      msg.innerText='✓ '+d.desc+' - السعر: '+d.new_total.toFixed(0)+' ر.س';
      msg.className='text-xs mt-2 font-bold text-green-600';msg.classList.remove('hidden');
    }else{
      appliedCouponSingle=null;
      msg.innerText='✗ '+d.message;
      msg.className='text-xs mt-2 font-bold text-red-500';msg.classList.remove('hidden');
    }
  }catch(e){}
}

// ===== SHARE =====
function shareService(name,price){
  var url=window.location.href;
    var text='خدمة '+name+' - '+price+' ر.س - متجر انجازك - '+url;
  if(navigator.share){navigator.share({title:'انجازك - '+name,text:text,url:url});}
  else{window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank');}
}

// ===== REVIEW =====
var reviewOrderId=null,reviewRating=0;
function openReviewModal(orderId){
  reviewOrderId=orderId;reviewRating=0;
  document.getElementById('reviewOrderNum').innerText='طلب #'+orderId;
  document.getElementById('reviewComment').value='';
  document.getElementById('submitReviewBtn').disabled=true;
  document.querySelectorAll('.star-btn').forEach(function(b){b.style.color='#cbd5e1';});
  document.getElementById('reviewModal').style.display='flex';
}
function closeReviewModal(){document.getElementById('reviewModal').style.display='none';}
function setRating(val){
  reviewRating=val;
  document.querySelectorAll('.star-btn').forEach(function(b){b.style.color=parseInt(b.dataset.val)<=val?'#f59e0b':'#cbd5e1';});
  document.getElementById('submitReviewBtn').disabled=false;document.getElementById('submitReviewBtn').className='relative z-10 w-full bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 text-white py-5 rounded-2xl font-black text-base hover:from-amber-600 hover:via-orange-600 hover:to-red-600 shadow-2xl hover:shadow-amber-500/50 transition-all duration-300 transform hover:scale-105 cursor-pointer';document.getElementById('submitReviewBtn').innerHTML='<span class="relative z-10 flex items-center justify-center gap-3"><i class="fas fa-paper-plane text-lg"></i>إرسال التقييم</span>';
}

function setRatingChoice(rating, label){
  reviewRating=rating;
  document.querySelectorAll('.rating-choice').forEach(function(btn){
    btn.classList.remove('bg-gradient-to-r','from-amber-400','to-orange-500','border-amber-500','text-white','scale-105','shadow-lg');
    btn.classList.add('bg-slate-50','border-slate-200');
  });
  event.target.closest('.rating-choice').classList.remove('bg-slate-50','border-slate-200');
  event.target.closest('.rating-choice').classList.add('bg-gradient-to-r','from-amber-400','to-orange-500','border-amber-500','text-white','scale-105','shadow-lg');
  document.getElementById('reviewComment').style.display='block';
  document.getElementById('submitReviewBtn').disabled=false;
  document.getElementById('submitReviewBtn').className='w-full bg-gradient-to-r from-amber-500 to-orange-600 text-white py-4 rounded-2xl font-black text-base hover:from-amber-600 hover:to-orange-700 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105 cursor-pointer';
  document.getElementById('submitReviewBtn').innerHTML='<span class="flex items-center justify-center gap-2"><i class="fas fa-paper-plane"></i>إرسال التقييم</span>';
}
async function submitReview(){
  if(!reviewRating||!reviewOrderId)return;
  var btn=document.getElementById('submitReviewBtn');
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>';
  try{
    var r=await fetch('/api/submit_review',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({order_id:reviewOrderId,rating:reviewRating,comment:document.getElementById('reviewComment').value.trim()})});
    var d=await r.json();
    if(d.status==='success'){closeReviewModal();showToast('شكراً على تقييمك!',true);}
    else showToast('حدث خطأ',false);
  }catch(e){showToast('تعذر الإرسال',false);}
  btn.disabled=false;btn.innerHTML='ارسال التقييم';
}

// Add review button in my orders
var _origLoadMyOrders=loadMyOrders;
loadMyOrders=async function(){
  await _origLoadMyOrders();
  // review buttons already handled in loadMyOrders render
};

function downloadInvoicePDF(orderId){
  window.open('/api/download_invoice/'+orderId,'_blank');
}
</script>

<!-- ===== CHATBOT ===== -->
<div id="chatbotBtn" onclick="toggleChatbot()" class="fixed bottom-24 left-6 z-50 w-14 h-14 bg-gradient-to-br from-amber-500 to-amber-700 text-white rounded-full shadow-2xl flex items-center justify-center cursor-pointer hover:scale-110 transition-all" title="مساعد انجازك">
  <i class="fas fa-robot text-xl" id="chatbotIcon"></i>
  <span id="chatbotBadge" class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[9px] font-black rounded-full items-center justify-center hidden">1</span>
</div>

<div id="chatbotWindow" style="display:none;max-height:500px" class="fixed bottom-44 left-6 z-50 w-80 bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-100">
  <!-- Header -->
  <div class="bg-gradient-to-l from-amber-600 to-amber-800 px-4 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
        <i class="fas fa-robot text-white text-lg"></i>
      </div>
      <div>
        <p class="text-white font-black text-sm">مساعد انجازك</p>
        <div class="flex items-center gap-1"><div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div><p class="text-white/80 text-[10px]">متاح دائماً</p></div>
      </div>
    </div>
    <button onclick="toggleChatbot()" class="text-white/70 hover:text-white"><i class="fas fa-times"></i></button>
  </div>

  <!-- Messages -->
  <div id="chatMessages" class="overflow-y-auto p-4 space-y-3 bg-slate-50" style="height:320px">
    <div class="flex gap-2">
      <div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center shrink-0 mt-1"><i class="fas fa-robot text-amber-600 text-xs"></i></div>
      <div class="bg-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm max-w-[85%]">
        <p class="text-xs text-slate-700 leading-relaxed">مرحباً! 👋 أنا مساعد متجر انجازك. كيف يمكنني مساعدتك اليوم؟</p>
      </div>
    </div>
    <div class="flex flex-wrap gap-2 pr-9">
      <button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">💰 الأسعار</button>
      <button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">📦 حالة طلبي</button>
      <button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">🎓 الخدمات</button>
      <button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">💳 طريقة الدفع</button>
      <button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">⏱️ مدة التنفيذ</button>
      <button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1.5 rounded-full font-bold hover:bg-amber-100 transition-all">🔄 التعديلات</button>
    </div>
  </div>

  <!-- Input -->
  <div class="border-t border-slate-100 p-3 bg-white flex gap-2">
    <input id="chatInput" type="text" placeholder="اكتب سؤالك..." onkeydown="if(event.key==='Enter')sendChatMsg()" class="flex-1 text-xs bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 outline-none focus:border-amber-400">
    <button onclick="sendChatMsg()" class="w-10 h-10 bg-amber-600 text-white rounded-full flex items-center justify-center hover:bg-amber-500 transition-all shrink-0"><i class="fas fa-paper-plane text-xs"></i></button>
  </div>
</div>

<script>
// ===== CHATBOT LOGIC =====
var chatbotOpen = false;
var chatGreeted = false;

function toggleChatbot(){
  chatbotOpen = !chatbotOpen;
  var win = document.getElementById('chatbotWindow');
  var badge = document.getElementById('chatbotBadge');
  win.style.display = chatbotOpen ? 'block' : 'none';
  badge.classList.add('hidden');
  if(chatbotOpen){
    scrollChatToBottom();
    if(!chatGreeted){
      chatGreeted = true;
      setTimeout(function(){
        addBotMsg('كيف يمكنني مساعدتك؟ اختر من الأزرار أعلاه أو اكتب سؤالك 😊');
      }, 800);
    }
  }
}

function sendQuickMsg(btn){
  var text = btn.innerText;
  addUserMsg(text);
  btn.parentElement.style.display = 'none';
  setTimeout(function(){ getBotReply(text); }, 400);
}

function sendChatMsg(){
  var input = document.getElementById('chatInput');
  var msg = input.value.trim();
  if(!msg) return;
  input.value = '';
  addUserMsg(msg);
  setTimeout(function(){ getBotReply(msg); }, 500);
}

function addUserMsg(text){
  var msgs = document.getElementById('chatMessages');
  var div = document.createElement('div');
  div.className = 'flex justify-start flex-row-reverse gap-2';
  div.innerHTML = '<div class="w-7 h-7 bg-slate-200 rounded-full flex items-center justify-center shrink-0 mt-1"><i class="fas fa-user text-slate-500 text-xs"></i></div>'+
    '<div class="bg-amber-600 text-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm max-w-[85%]"><p class="text-xs leading-relaxed">'+escapeHtmlChat(text)+'</p></div>';
  msgs.appendChild(div);
  scrollChatToBottom();
}

function addBotMsg(text, withButtons){
  var msgs = document.getElementById('chatMessages');
  var typing = document.createElement('div');
  typing.className = 'flex gap-2';
  typing.id = 'chatTyping';
  typing.innerHTML = '<div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center shrink-0 mt-1"><i class="fas fa-robot text-amber-600 text-xs"></i></div>'+
    '<div class="bg-white rounded-2xl px-4 py-3 shadow-sm"><div class="flex gap-1 items-center"><span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce"></span><span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:.15s"></span><span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:.3s"></span></div></div>';
  msgs.appendChild(typing);
  scrollChatToBottom();
  setTimeout(function(){
    var t = document.getElementById('chatTyping');
    if(t) t.remove();
    var div = document.createElement('div');
    div.className = 'flex gap-2';
    var btnsHtml = '';
    if(withButtons){
      btnsHtml = '<div class="flex flex-wrap gap-1.5 mt-2">'+withButtons.map(function(b){
        return '<button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-2 py-1 rounded-full font-bold hover:bg-amber-100 transition-all">'+b+'</button>';
      }).join('')+'</div>';
    }
    div.innerHTML = '<div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center shrink-0 mt-1"><i class="fas fa-robot text-amber-600 text-xs"></i></div>'+
      '<div class="bg-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm max-w-[85%]"><p class="text-xs text-slate-700 leading-relaxed">'+text+'</p>'+btnsHtml+'</div>';
    msgs.appendChild(div);
    scrollChatToBottom();
  }, 900);
}

// تاريخ المحادثة للسياق
var chatHistory = [];

async function getBotReply(msg){
  // معالجة خاصة للأزرار السريعة بدون AI
  var m = msg.toLowerCase().trim();

  if(m.includes('📋 طلباتي')||m.includes('طلباتي')){
    addBotMsg('سأفتح لك صفحة طلباتك الآن! 📋');
    setTimeout(function(){
      document.getElementById('chatbotWindow').style.display='none';
      chatbotOpen=false;
      openMyOrders();
    }, 1000);
    return;
  }

  if(m.includes('📋 عرض الخدمات')){
    addBotMsg('سأعيدك لصفحة الخدمات الآن! 🎓');
    setTimeout(function(){
      document.getElementById('chatbotWindow').style.display='none';
      chatbotOpen=false;
      window.scrollTo({top:document.getElementById('productsGrid').offsetTop-80,behavior:'smooth'});
    }, 1000);
    return;
  }

  if(m.includes('💬 تواصل واتساب')||m.includes('واتساب')||m.includes('whatsapp')){
    var waLink = document.querySelector('.wa-float');
    var href = waLink ? waLink.href : '#';
    addBotMsg('سأفتح لك واتساب الآن! 💬');
    setTimeout(function(){window.open(href,'_blank');}, 800);
    return;
  }

  // إضافة رسالة المستخدم للتاريخ
  chatHistory.push({role:'user', content: msg});

  // إظهار typing indicator
  var msgs = document.getElementById('chatMessages');
  var typing = document.createElement('div');
  typing.className = 'flex gap-2';
  typing.id = 'chatTyping';
  typing.innerHTML = '<div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center shrink-0 mt-1"><i class="fas fa-robot text-amber-600 text-xs"></i></div>'+
    '<div class="bg-white rounded-2xl px-4 py-3 shadow-sm"><div class="flex gap-1 items-center"><span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce"></span><span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:.15s"></span><span class="w-2 h-2 bg-amber-400 rounded-full animate-bounce" style="animation-delay:.3s"></span></div></div>';
  msgs.appendChild(typing);
  scrollChatToBottom();

  try{
    var r = await fetch('/api/chatbot', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, history: chatHistory.slice(-6)})
    });
    var d = await r.json();
    var t = document.getElementById('chatTyping');
    if(t) t.remove();

    var reply = d.reply || 'عذراً، حدث خطأ. حاول مرة أخرى.';
    // إضافة رد البوت للتاريخ
    chatHistory.push({role:'assistant', content: reply});
    // تحديد الأزرار السريعة المناسبة
    var quickBtns = null;
    var rl = reply.toLowerCase();
    if(rl.includes('طلبات')||rl.includes('طلبك')) quickBtns = ['📋 طلباتي'];
    else if(rl.includes('واتساب')||rl.includes('تواصل')) quickBtns = ['💬 تواصل واتساب'];
    else if(rl.includes('خدمات')||rl.includes('خدمة')) quickBtns = ['📋 عرض الخدمات','💬 تواصل واتساب'];

    // عرض الرد
    var div = document.createElement('div');
    div.className = 'flex gap-2';
    var btnsHtml = '';
    if(quickBtns){
      btnsHtml = '<div class="flex flex-wrap gap-1.5 mt-2">'+quickBtns.map(function(b){
        return '<button onclick="sendQuickMsg(this)" class="chatQuick text-[10px] bg-amber-50 border border-amber-200 text-amber-700 px-2 py-1 rounded-full font-bold hover:bg-amber-100 transition-all">'+b+'</button>';
      }).join('')+'</div>';
    }
    div.innerHTML = '<div class="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center shrink-0 mt-1"><i class="fas fa-robot text-amber-600 text-xs"></i></div>'+
      '<div class="bg-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm max-w-[85%]"><p class="text-xs text-slate-700 leading-relaxed">'+escapeHtmlChat(reply)+'</p>'+btnsHtml+'</div>';
    msgs.appendChild(div);
    scrollChatToBottom();
  }catch(e){
    var t2 = document.getElementById('chatTyping');
    if(t2) t2.remove();
    addBotMsg('تعذر الاتصال، حاول مرة أخرى. 😓');
  }
}

function scrollChatToBottom(){
  var msgs = document.getElementById('chatMessages');
  if(msgs) msgs.scrollTop = msgs.scrollHeight;
}

function escapeHtmlChat(str){
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Show badge after 5 seconds
setTimeout(function(){
  if(!chatbotOpen){
    var badge = document.getElementById('chatbotBadge');
    badge.style.display = 'flex';
  }
}, 5000);
</script>

</body></html>"""

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>لوحة الادارة | انجازك</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
{% raw %}<style>
body{font-family:'IBM Plex Sans Arabic',sans-serif;background:#f1f5f9;}
.cs{box-shadow:0 4px 6px -1px rgb(0 0 0/.08);}
.scr::-webkit-scrollbar{width:4px;height:4px}.scr::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:10px}
.tab{transition:all .2s;border-bottom:3px solid transparent;white-space:nowrap;padding-bottom:10px;font-size:11px;cursor:pointer;}
.tab.active{border-color:#b45309;color:#b45309;font-weight:700;}
.oc{transition:all .2s;}.oc:hover{transform:translateY(-1px);box-shadow:0 6px 16px -4px rgba(0,0,0,.1);}
.stab{cursor:pointer;padding:6px 12px;border-radius:8px;font-size:11px;font-weight:700;transition:all .2s;}
.stab.active{background:#0f172a;color:white;}
.stab:not(.active){color:#64748b;}.stab:not(.active):hover{background:#f1f5f9;}
</style>{% endraw %}

<script>
// Modal functions - defined early in head

function filterOrderCards(){
  var q=(document.getElementById('orderSearchInput').value||'').toLowerCase().trim();
  var cards=document.querySelectorAll('.order-card');
  cards.forEach(function(c){
    var match=!q||c.dataset.search.toLowerCase().includes(q);
    c.style.display=match?'':'none';
  });
}
function openCouponModal(){document.getElementById('couponModal').style.display='flex';loadCoupons();}
function closeCouponModal(){document.getElementById('couponModal').style.display='none';}
function openTeamModal(){document.getElementById('teamModal').style.display='flex';loadTeam();}
function closeTeamModal(){document.getElementById('teamModal').style.display='none';}
function openOffersModal(){document.getElementById('offersModal').style.display='flex';loadOffers();}
function closeOffersModal(){document.getElementById('offersModal').style.display='none';}
function openTestimonialsModal(){document.getElementById('testimonialsModal').style.display='flex';loadAdminTestimonials();}
function closeTestimonialsModal(){document.getElementById('testimonialsModal').style.display='none';}
function openStatsModal(){document.getElementById('statsModal').style.display='flex';loadAdminStats();}
function closeStatsModal(){document.getElementById('statsModal').style.display='none';}

// ===== إيصالات الشراء =====
function openInvoicesModal(){
  document.getElementById('invoicesModal').style.display='flex';
  document.body.style.overflow='hidden';
  loadAllInvoices();
}

function closeInvoicesModal(){
  document.getElementById('invoicesModal').style.display='none';
  document.body.style.overflow='';
}

async function loadAllInvoices(){
  var list=document.getElementById('invoicesList');
  if(!list){console.error('invoicesList not found');return;}
  try{
    var r=await fetch('/api/admin/invoices');
    var data=await r.json();
    if(!data.invoices||!data.invoices.length){
      list.innerHTML='<p class="text-center text-slate-400 text-sm py-8">لا توجد إيصالات شراء</p>';
      return;
    }
    list.innerHTML=data.invoices.map(function(inv){
      var statusColor=inv.status==='مكتمل'?'green':'slate';
      return '<div class="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-md transition-all">'+
        '<div class="flex justify-between items-start mb-2">'+
          '<div><p class="font-bold text-sm">إيصال شراء #'+inv.order_id+'</p>'+
          '<p class="text-xs text-slate-500">'+inv.customer_name+' | '+inv.date+'</p></div>'+
          '<span class="text-xs px-2 py-1 rounded-full bg-'+statusColor+'-100 text-'+statusColor+'-700 font-bold">'+inv.status+'</span>'+
        '</div>'+
        '<div class="flex justify-between items-center mt-3">'+
          '<p class="font-black text-indigo-600">'+inv.total+' ر.س</p>'+
          '<div class="flex gap-2">'+
            '<button onclick="downloadInvoice('+inv.order_id+')" class="text-xs bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-lg font-bold hover:bg-indigo-100"><i class="fas fa-download ml-1"></i>تحميل</button>'+
            '<button onclick="sendInvoiceWA('+inv.order_id+')" class="text-xs bg-green-50 text-green-600 px-3 py-1.5 rounded-lg font-bold hover:bg-green-100"><i class="fab fa-whatsapp ml-1"></i>إرسال</button>'+
          '</div>'+
        '</div>'+
      '</div>';
    }).join('');
  }catch(e){console.error(e);list.innerHTML='<p class="text-red-500 text-xs text-center">تعذر التحميل</p>';}
}

function downloadInvoice(orderId){window.open('/api/download_invoice/'+orderId,'_blank');}

async function sendInvoiceWA(orderId){
  try{
    var r=await fetch('/api/send_invoice_wa/'+orderId);
    var d=await r.json();
    if(d.wa_link)window.open(d.wa_link,'_blank');
  }catch(e){showAdminToast('فشل الإرسال');}
}

async function searchInvoice(){
  var orderId=document.getElementById('invoiceSearchOrder').value;
  if(!orderId)return loadAllInvoices();
  loadAllInvoices();
}

// ===== إدارة العملاء =====
function openCustomersModal(){
  document.getElementById('customersModal').style.display='flex';
  document.body.style.overflow='hidden';
  loadAllCustomers();
}

function closeCustomersModal(){
  document.getElementById('customersModal').style.display='none';
  document.body.style.overflow='';
}

async function loadAllCustomers(){
  var list=document.getElementById('customersList');
  if(!list){console.error('customersList not found');return;}
  try{
    var r=await fetch('/api/admin/customers');
    var data=await r.json();
    if(!data.customers||!data.customers.length){
      list.innerHTML='<p class="text-center text-slate-400 text-sm py-8">لا يوجد عملاء مسجلين</p>';
      return;
    }
    list.innerHTML=data.customers.map(function(c){
      var ordersText=c.orders_count+' '+(c.orders_count===1?'طلب':'طلبات');
      return '<div class="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-md transition-all">'+
        '<div class="flex justify-between items-start">'+
          '<div class="flex-1"><p class="font-bold text-sm mb-1">'+c.name+'</p>'+
          '<p class="text-xs text-slate-500 mb-1"><i class="fas fa-phone ml-1"></i>'+c.phone+'</p>'+
          (c.email?'<p class="text-xs text-slate-500"><i class="fas fa-envelope ml-1"></i>'+c.email+'</p>':'')+'</div>'+
          '<div class="text-left"><span class="text-xs px-2 py-1 rounded-full bg-cyan-100 text-cyan-700 font-bold">'+ordersText+'</span></div>'+
        '</div>'+
        '<div class="flex gap-2 mt-3">'+
          '<button onclick="editCustomer('+c.id+')" class="text-xs bg-cyan-50 text-cyan-600 px-3 py-1.5 rounded-lg font-bold hover:bg-cyan-100 flex-1"><i class="fas fa-edit ml-1"></i>تعديل</button>'+
          '<button onclick="deleteCustomer('+c.id+')" class="text-xs bg-red-50 text-red-600 px-3 py-1.5 rounded-lg font-bold hover:bg-red-100"><i class="fas fa-trash ml-1"></i>حذف</button>'+
        '</div>'+
      '</div>';
    }).join('');
  }catch(e){console.error(e);list.innerHTML='<p class="text-red-500 text-xs text-center">تعذر التحميل</p>';}
}

async function searchCustomers(){
  var query=document.getElementById('customerSearchInput').value;
  if(!query)return loadAllCustomers();
  loadAllCustomers();
}

async function editCustomer(id){
  try{
    var r=await fetch('/api/admin/customer/'+id);
    var c=await r.json();
    document.getElementById('editCustomerId').value=c.id;
    document.getElementById('editCustomerName').value=c.name||'';
    document.getElementById('editCustomerPhone').value=c.phone||'';
    document.getElementById('editCustomerEmail').value=c.email||'';
    document.getElementById('editCustomerModal').style.display='flex';
  }catch(e){showAdminToast('فشل تحميل البيانات');}
}

function closeEditCustomer(){document.getElementById('editCustomerModal').style.display='none';}

async function saveCustomerEdit(){
  var id=document.getElementById('editCustomerId').value;
  var name=document.getElementById('editCustomerName').value;
  var phone=document.getElementById('editCustomerPhone').value;
  var email=document.getElementById('editCustomerEmail').value;
  if(!name||!phone){showAdminToast('الاسم والجوال مطلوبان');return;}
  try{
    var r=await fetch('/api/admin/customer/'+id,{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:name,phone:phone,email:email})
    });
    var d=await r.json();
    if(d.status==='success'){
      showAdminToast('تم حفظ التعديلات');
      closeEditCustomer();
      loadAllCustomers();
    }
  }catch(e){showAdminToast('فشل الحفظ');}
}

async function deleteCustomer(id){
  if(!confirm('هل أنت متأكد من حذف هذا العميل؟'))return;
  try{
    var r=await fetch('/api/admin/customer/'+id,{method:'DELETE'});
    var d=await r.json();
    if(d.status==='success'){
      showAdminToast('تم الحذف');
      loadAllCustomers();
    }
  }catch(e){showAdminToast('فشل الحذف');}
}




</script>
</head>
<body class="min-h-screen pb-20">

<nav class="bg-white border-b border-slate-200 px-4 py-3 sticky top-0 z-40 shadow-sm">
  <div class="max-w-7xl mx-auto flex justify-between items-center flex-wrap gap-2">
    <div class="flex items-center gap-3">
      <div class="w-10 h-10 bg-amber-600 rounded-lg flex items-center justify-center text-white"><i class="fas fa-lock text-sm"></i></div>
      <div><h1 class="text-base font-bold text-slate-800">انجازك | لوحة الادارة</h1><p class="text-[10px] text-slate-400">تحكم كامل في المتجر والطلبات</p></div>
    </div>
    <div class="flex gap-2 items-center flex-wrap">
      <div class="flex gap-1 bg-slate-100 rounded-xl p-1">
        <a href="/cp?period=today" class="text-[10px] px-2 py-1 rounded-lg font-bold transition-all {% if filter_period=='today' %}bg-white shadow text-amber-600{% else %}text-slate-500 hover:text-slate-800{% endif %}">اليوم</a>
        <a href="/cp?period=week" class="text-[10px] px-2 py-1 rounded-lg font-bold transition-all {% if filter_period=='week' %}bg-white shadow text-amber-600{% else %}text-slate-500 hover:text-slate-800{% endif %}">الاسبوع</a>
        <a href="/cp?period=month" class="text-[10px] px-2 py-1 rounded-lg font-bold transition-all {% if filter_period=='month' %}bg-white shadow text-amber-600{% else %}text-slate-500 hover:text-slate-800{% endif %}">الشهر</a>
        <a href="/cp?period=all" class="text-[10px] px-2 py-1 rounded-lg font-bold transition-all {% if filter_period=='all' %}bg-white shadow text-amber-600{% else %}text-slate-500 hover:text-slate-800{% endif %}">الكل</a>
      </div>
      <button onclick="openCouponModal()" class="text-xs bg-amber-50 px-3 py-2 rounded-lg font-bold text-amber-600 hover:bg-amber-100 transition-all"><i class="fas fa-tag ml-1"></i>الكوبونات</button>
      <button onclick="openTeamModal()" class="text-xs bg-blue-50 px-3 py-2 rounded-lg font-bold text-blue-600 hover:bg-blue-100 transition-all"><i class="fas fa-users ml-1"></i>الفريق</button>
      <button onclick="openOffersModal()" class="text-xs bg-red-50 px-3 py-2 rounded-lg font-bold text-red-600 hover:bg-red-100 transition-all"><i class="fas fa-gift ml-1"></i>العروض</button>
      <button onclick="openTestimonialsModal()" class="text-xs bg-green-50 px-3 py-2 rounded-lg font-bold text-green-600 hover:bg-green-100 transition-all"><i class="fas fa-star ml-1"></i>الشهادات</button>
      <button onclick="openStatsModal()" class="text-xs bg-purple-50 px-3 py-2 rounded-lg font-bold text-purple-600 hover:bg-purple-100 transition-all"><i class="fas fa-chart-bar ml-1"></i>التقارير</button>
      <a href="/admin/customers_invoices" class="text-xs bg-cyan-50 px-3 py-2 rounded-lg font-bold text-cyan-700 hover:bg-cyan-100 transition-all"><i class="fas fa-address-book ml-1"></i>العملاء وإيصالات الشراء</a>
      <a href="/" class="text-xs bg-slate-100 px-3 py-2 rounded-lg font-bold text-slate-600 hover:bg-slate-200"><i class="fas fa-store ml-1"></i>المتجر</a>
      <a href="/logout" class="text-xs bg-red-50 px-3 py-2 rounded-lg font-bold text-red-500 hover:bg-red-100"><i class="fas fa-sign-out-alt ml-1"></i>خروج</a>
    </div>
  </div>
</nav>

<div class="max-w-7xl mx-auto px-4 py-8 space-y-8">
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="bg-white p-5 rounded-2xl cs border-r-4 border-amber-500"><p class="text-slate-400 text-[11px] font-bold mb-1">اجمالي المبيعات</p><p class="text-2xl font-black">{{ "%.0f"|format(total_sales) }} ر.س</p></div>
    <div class="bg-white p-5 rounded-2xl cs border-r-4 border-blue-500"><p class="text-slate-400 text-[11px] font-bold mb-1">طلبات جديدة</p><p class="text-2xl font-black text-blue-600">{{ total_new }}</p></div>
    <div class="bg-white p-5 rounded-2xl cs border-r-4 border-amber-400"><p class="text-slate-400 text-[11px] font-bold mb-1">جار التجهيز</p><p class="text-2xl font-black text-amber-600">{{ total_processing }}</p></div>
    <div class="bg-white p-5 rounded-2xl cs border-r-4 border-green-500"><p class="text-slate-400 text-[11px] font-bold mb-1">مكتملة</p><p class="text-2xl font-black text-green-600">{{ orders_by_status['مكتمل']|length }}</p></div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
    <!-- Settings -->
    <div id="settings" class="bg-white p-6 rounded-3xl cs h-fit">
      <h3 class="font-bold text-slate-800 mb-4 flex items-center gap-2 text-base"><i class="fas fa-cog text-amber-600"></i> الاعدادات</h3>
      <div class="flex gap-1 bg-slate-100 rounded-xl p-1 mb-5">
        <button onclick="switchST('contact')" id="st-contact" class="stab active flex-1 text-center">التواصل</button>
        <button onclick="switchST('bank')" id="st-bank" class="stab flex-1 text-center">البنك</button>
      </div>
      <form id="form-contact" action="/admin/update_settings" method="POST" class="space-y-3">
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">رابط واتساب (للزوار)</label><input name="whatsapp" value="{{ settings.whatsapp }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">رقم الواتساب للاشعارات (966XXXXXXXXX)</label><input name="whatsapp_number" value="{{ settings.whatsapp_number }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500"></div>
        <div class="grid grid-cols-2 gap-2">
          <div><label class="text-[10px] font-bold text-slate-400 block mb-1">انستغرام</label><input name="instagram" value="{{ settings.instagram }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs"></div>
          <div><label class="text-[10px] font-bold text-slate-400 block mb-1">تيك توك</label><input name="tiktok" value="{{ settings.tiktok }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs"></div>
          <div><label class="text-[10px] font-bold text-slate-400 block mb-1">سناب شات</label><input name="snapchat" value="{{ settings.snapchat or '' }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs" placeholder="https://snapchat.com/add/..."></div>
          <div><label class="text-[10px] font-bold text-slate-400 block mb-1">تويتر / X</label><input name="twitter" value="{{ settings.twitter or '' }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs" placeholder="https://x.com/..."></div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div><label class="text-[10px] font-bold text-slate-400 block mb-1">الهاتف</label><input name="phone" value="{{ settings.phone }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs"></div>
          <div><label class="text-[10px] font-bold text-slate-400 block mb-1">البريد</label><input name="email" value="{{ settings.email }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs"></div>
        </div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">شريط الاعلانات</label><textarea name="moving_text" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs h-16">{{ settings.moving_text }}</textarea></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">نص الفوتر</label><textarea name="footer_text" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs h-14">{{ settings.footer_text }}</textarea></div>
        <input type="hidden" name="bank_name" value="{{ settings.bank_name or '' }}">
        <input type="hidden" name="bank_account" value="{{ settings.bank_account or '' }}">
        <input type="hidden" name="bank_iban" value="{{ settings.bank_iban or '' }}">
        <input type="hidden" name="bank_holder" value="{{ settings.bank_holder or '' }}">
        <button type="submit" class="w-full bg-slate-900 text-white py-3 rounded-xl font-bold text-xs hover:bg-slate-800 transition-all"><i class="fas fa-save ml-1"></i> حفظ الاعدادات</button>
      </form>
      <form id="form-bank" action="/admin/update_settings" method="POST" class="space-y-3 hidden">
        <div class="bg-blue-50 border border-blue-100 rounded-xl p-3"><p class="text-[11px] text-blue-700 font-bold flex items-center gap-1"><i class="fas fa-university"></i> بيانات الحساب البنكي</p></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">اسم البنك</label><input name="bank_name" value="{{ settings.bank_name or '' }}" placeholder="مثال: بنك الراجحي" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">اسم صاحب الحساب</label><input name="bank_holder" value="{{ settings.bank_holder or '' }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">رقم الحساب</label><input name="bank_account" value="{{ settings.bank_account or '' }}" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">رقم الايبان</label><input name="bank_iban" value="{{ settings.bank_iban or '' }}" placeholder="SA..." class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500"></div>
        <input type="hidden" name="whatsapp" value="{{ settings.whatsapp }}">
        <input type="hidden" name="whatsapp_number" value="{{ settings.whatsapp_number }}">
        <input type="hidden" name="instagram" value="{{ settings.instagram }}">
        <input type="hidden" name="tiktok" value="{{ settings.tiktok }}">
        <input type="hidden" name="phone" value="{{ settings.phone }}">
        <input type="hidden" name="email" value="{{ settings.email }}">
        <input type="hidden" name="moving_text" value="{{ settings.moving_text }}">
        <input type="hidden" name="footer_text" value="{{ settings.footer_text }}">
        <button type="submit" class="w-full bg-slate-900 text-white py-3 rounded-xl font-bold text-xs hover:bg-slate-800"><i class="fas fa-save ml-1"></i> حفظ بيانات البنك</button>
        {% if settings.bank_name %}<div class="bg-green-50 border border-green-200 rounded-xl p-3 text-[10px] text-green-700 space-y-0.5"><p class="font-bold">البيانات المحفوظة:</p><p>البنك: {{ settings.bank_name }}</p><p>الاسم: {{ settings.bank_holder }}</p><p>الحساب: {{ settings.bank_account }}</p><p>الايبان: {{ settings.bank_iban }}</p></div>{% endif %}
      </form>
    </div>

    <!-- Orders -->
    <div class="lg:col-span-2 bg-white p-6 rounded-3xl cs">
      <div class="flex items-center justify-between mb-5">
        <h3 class="font-bold text-slate-800 flex items-center gap-2 text-base"><i class="fas fa-list text-blue-600"></i> الطلبات</h3>
        <a href="/admin/export_orders" class="text-[10px] bg-green-50 text-green-600 border border-green-200 px-3 py-2 rounded-xl font-bold hover:bg-green-100"><i class="fas fa-file-csv ml-1"></i> تصدير CSV</a>
      </div>
      <!-- فلتر بحث الطلبات -->
      <div class="flex gap-2 mb-4">
        <div class="relative flex-grow">
          <i class="fas fa-search absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
          <input id="orderSearchInput" oninput="filterOrderCards()" placeholder="بحث بالاسم أو الجوال أو رقم الطلب..." class="w-full pr-9 pl-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:border-amber-500">
        </div>
        <button onclick="document.getElementById('orderSearchInput').value='';filterOrderCards();" class="text-[10px] bg-slate-100 text-slate-500 px-3 py-2 rounded-xl font-bold hover:bg-slate-200">مسح</button>
      </div>
      <div class="flex gap-3 border-b border-slate-100 mb-5 overflow-x-auto pb-px">
        {% for s in ORDER_STATUSES %}
        <button onclick="showOTab('{{ loop.index }}')" id="otab-{{ loop.index }}" class="tab {% if loop.first %}active{% endif %}">
          {% if s=='جديد' %}🔵{% elif s=='جار التجهيز' %}🟡{% elif s=='بانتظار الدفع' %}💰{% elif s=='يتطلب تعديل' %}🔄{% elif s=='ملغي' %}🔴{% else %}🟢{% endif %}
          {{ s }} ({{ orders_by_status[s]|length }})
        </button>
        {% endfor %}
      </div>

      {% set cmap = {'جديد':'blue','جار التجهيز':'amber','بانتظار الدفع':'green','يتطلب تعديل':'purple','ملغي':'red','مكتمل':'emerald'} %}
      {% for s in ORDER_STATUSES %}{% set idx=loop.index %}{% set col=cmap.get(s,'slate') %}
      <div id="opanel-{{ idx }}" class="space-y-3 min-h-20 {% if not loop.first %}hidden{% endif %}">
        {% for o in orders_by_status[s] %}
        <div class="oc bg-{{ col }}-50 border border-{{ col }}-100 rounded-2xl p-4 order-card" data-search="{{ o.id }} {{ o.customer_name or '' }} {{ o.customer_phone or '' }} {{ o.product_name or '' }}">
          <div class="flex gap-3 items-start">
            <div class="flex-grow min-w-0">
              <div class="flex gap-2 items-center mb-1 flex-wrap">
                <span class="bg-{{ col }}-100 text-{{ col }}-700 text-[10px] font-black px-2 py-0.5 rounded-full">#{{ o.id }}</span>
                <span class="text-slate-400 text-[10px]">{{ o.order_date.strftime('%Y/%m/%d %H:%M') }}</span>
                {% if o.receipt_image %}<span class="bg-green-100 text-green-700 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1"><i class="fas fa-file-invoice"></i> يوجد ايصال</span>{% endif %}
              </div>
              <p class="font-bold text-slate-800">{{ o.customer_name }}</p>
              <a href="tel:{{ o.customer_phone }}" class="text-xs text-amber-600 font-mono hover:underline">{{ o.customer_phone }}</a>
              <div class="mt-1 space-y-0.5">
                {% if o.parsed_cart %}{% for item in o.parsed_cart %}<p class="text-[11px] text-slate-600">• {{ item.name }} &times;{{ item.qty }}</p>{% endfor %}
                {% else %}<p class="text-[11px] text-slate-600">• {{ o.product_name }}</p>{% endif %}
                {% if o.cart_total and o.cart_total > 0 %}<p class="text-sm font-black text-green-700">{{ "%.0f"|format(o.cart_total) }} ر.س</p>{% endif %}
              </div>
              {% if o.customer_notes %}<div class="mt-2 bg-white rounded-xl px-3 py-2"><p class="text-[10px] text-slate-500 font-bold mb-0.5">ملاحظات:</p><p class="text-[11px] text-slate-700">{{ o.customer_notes }}</p></div>{% endif %}
            </div>
            <div class="flex flex-col gap-1.5 shrink-0" style="min-width:100px">
              <select onchange="if(this.value){updateOrderStatus({{ o.id }},this.value);}" class="text-[9px] bg-white border border-slate-200 rounded-xl px-2 py-1.5 font-bold text-slate-600 outline-none cursor-pointer w-full">
                <option value="">تغيير الحالة</option>
                {% for st in ORDER_STATUSES %}{% if st != o.status %}<option value="{{ st }}">{{ st }}</option>{% endif %}{% endfor %}
              </select>
              {% if o.receipt_image %}
              <a href="/admin/view_receipt/{{ o.id }}" target="_blank" class="text-[10px] bg-amber-500 text-white px-2 py-1.5 rounded-xl font-bold text-center hover:bg-amber-600 transition-all"><i class="fas fa-file-invoice ml-1"></i>عرض الايصال</a>
              {% endif %}
              <button onclick="openOrderDetail({{ o.id }})" class="text-[10px] bg-blue-50 text-blue-600 border border-blue-200 px-2 py-1.5 rounded-xl font-bold text-center hover:bg-blue-100 transition-all"><i class="fas fa-eye ml-1"></i>التفاصيل</button>
              <a href="/order/{{ o.id }}" target="_blank" class="text-[10px] bg-slate-50 text-slate-600 border border-slate-200 px-2 py-1.5 rounded-xl font-bold text-center hover:bg-slate-100 transition-all"><i class="fas fa-location-arrow ml-1"></i>تتبع</a>
              <a href="https://wa.me/{{ o.customer_phone|replace(' ','')|replace('+','') }}" target="_blank" class="text-[10px] bg-green-50 text-green-700 border border-green-200 px-2 py-1.5 rounded-xl font-bold text-center hover:bg-green-100 transition-all"><i class="fab fa-whatsapp ml-1"></i>واتساب</a>
              <a href="/admin/delete_order/{{ o.id }}" onclick="return confirm('حذف الطلب نهائياً؟')" class="text-[10px] bg-red-50 text-red-500 px-2 py-1.5 rounded-xl font-bold text-center hover:bg-red-500 hover:text-white transition-all"><i class="fas fa-trash ml-1"></i>حذف</a>
            </div>
          </div>
        </div>
        {% endfor %}
        {% if not orders_by_status[s] %}<div class="py-14 text-center text-slate-300 text-xs"><i class="fas fa-inbox text-3xl block mb-3"></i>لا توجد طلبات في هذه الحالة</div>{% endif %}
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- Add Service -->
  <div id="services" class="bg-slate-900 rounded-3xl p-8 text-white shadow-2xl">
    <h3 class="text-xl font-bold mb-6 flex items-center gap-3"><i class="fas fa-plus-circle text-amber-500"></i> اضافة خدمة جديدة</h3>
    <form method="POST" enctype="multipart/form-data" class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="space-y-4">
        <input name="name" placeholder="عنوان الخدمة *" required class="w-full p-4 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-amber-500 text-sm">
        <div class="grid grid-cols-4 gap-2">
          <input name="price" type="number" step="0.01" placeholder="السعر" class="p-3 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-amber-500 text-sm">
          <input name="old_price" type="number" step="0.01" placeholder="القديم" class="p-3 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-amber-500 text-sm">
          <input name="category" placeholder="التصنيف" class="p-3 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-amber-500 text-sm">
          <input name="stock" type="number" placeholder="الكمية" value="999" title="999=غير محدود" class="p-3 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-amber-500 text-sm">
        </div>
        <div class="p-4 bg-white/5 border border-dashed border-white/20 rounded-2xl">
          <label class="text-[10px] text-slate-400 font-bold block mb-2">صورة الخدمة</label>
          <input type="file" name="product_file" accept="image/*" class="text-xs text-slate-400 w-full cursor-pointer">
        </div>
      </div>
      <div class="flex flex-col gap-4">
        <textarea name="description" placeholder="وصف الخدمة..." class="flex-grow p-4 bg-white/5 border border-white/10 rounded-2xl outline-none focus:border-amber-500 text-sm min-h-[130px]"></textarea>
        <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 py-4 rounded-2xl font-black text-sm transition-all"><i class="fas fa-cloud-upload-alt ml-2"></i> نشر الخدمة</button>
      </div>
    </form>
  </div>

  <!-- Manage Products -->
  <div class="bg-white p-6 rounded-3xl cs">
    <h3 class="text-lg font-bold text-slate-800 mb-6 flex items-center gap-3"><i class="fas fa-boxes text-amber-600"></i> ادارة الخدمات الحالية</h3>
    <div class="overflow-x-auto scr">
      <table class="w-full text-right min-w-[700px]">
        <thead><tr class="text-[10px] text-slate-400 border-b-2 border-slate-100 uppercase tracking-widest">
          <th class="pb-4 pr-3">#</th><th class="pb-4">الخدمة</th><th class="pb-4">السعر</th><th class="pb-4">الكمية</th><th class="pb-4">التصنيف</th><th class="pb-4 text-center">الحالة</th><th class="pb-4 text-center">الاجراءات</th>
        </tr></thead>
        <tbody class="text-xs">
        {% for p in products %}
        <tr class="hover:bg-slate-50 border-b border-slate-50 {% if not p.is_active %}opacity-50{% endif %}">
          <td class="py-4 pr-3 text-slate-400">{{ p.id }}</td>
          <td class="py-4 font-bold text-slate-700 max-w-[180px]"><div class="truncate">{{ p.name }}</div><div class="text-[10px] text-slate-400 font-normal truncate">{{ (p.description or '')[:45] }}</div></td>
          <td class="py-4"><span class="font-black">{{ p.price }} ر.س</span>{% if p.old_price %}<span class="text-[10px] text-slate-400 line-through block">{{ p.old_price }}</span>{% endif %}</td>
          <td class="py-4">{% if p.stock is none or p.stock >= 999 %}<span class="text-slate-400 text-[10px]">غير محدود</span>{% elif p.stock == 0 %}<span class="text-red-500 font-bold text-[10px]">نفذت</span>{% elif p.stock < 5 %}<span class="text-orange-500 font-bold text-[10px]">{{ p.stock }} فقط</span>{% else %}<span class="text-slate-600 text-[10px]">{{ p.stock }}</span>{% endif %}</td>
          <td class="py-4"><span class="bg-amber-50 text-amber-700 px-2 py-1 rounded-full text-[10px] font-bold">{{ p.category }}</span></td>
          <td class="py-4 text-center">
            <a href="/admin/toggle_product/{{ p.id }}" class="text-[10px] px-3 py-1.5 rounded-full font-bold transition-all {% if p.is_active %}bg-green-100 text-green-700 hover:bg-green-200{% else %}bg-slate-100 text-slate-500{% endif %}">
              {% if p.is_active %}<i class="fas fa-eye ml-1"></i>مرئي{% else %}<i class="fas fa-eye-slash ml-1"></i>مخفي{% endif %}
            </a>
          </td>
          <td class="py-4"><div class="flex justify-center gap-2">
            <button onclick='openEdit({{ p.id }}, {{ p.name|tojson }}, {{ p.price }}, {{ p.old_price if p.old_price else "null" }}, {{ p.category|tojson }}, {{ (p.description or "")|tojson }}, {{ p.stock if p.stock is not none else 999 }})' class="w-8 h-8 bg-blue-50 text-blue-600 rounded-lg flex items-center justify-center hover:bg-blue-600 hover:text-white transition-all"><i class="fas fa-edit text-xs"></i></button>
            <a href="/admin/delete_product/{{ p.id }}" onclick="return confirm('حذف الخدمة؟')" class="w-8 h-8 bg-red-50 text-red-500 rounded-lg flex items-center justify-center hover:bg-red-600 hover:text-white transition-all"><i class="fas fa-trash text-xs"></i></a>
          </div></td>
        </tr>
        {% endfor %}
        {% if not products %}<tr><td colspan="7" class="py-14 text-center text-slate-300">لا توجد خدمات مضافة بعد.</td></tr>{% endif %}
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- Team Modal -->
<div id="teamModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-md p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeTeamModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-5"><i class="fas fa-users text-blue-600 ml-2"></i>إدارة فريق العمل</h3>
    <div class="flex gap-2 mb-5">
      <input id="teamName" placeholder="اسم العضو" class="flex-grow p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-blue-500">
      <input id="teamRole" placeholder="الدور" class="w-32 p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-blue-500">
      <button onclick="addTeamMember()" class="bg-blue-600 text-white px-4 rounded-xl font-bold text-sm hover:bg-blue-500">+</button>
    </div>
    <div id="teamList" class="space-y-2"></div>
  </div>
</div>

<!-- Offers Modal -->
<div id="offersModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeOffersModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-5"><i class="fas fa-gift text-red-600 ml-2"></i>العروض الموسمية</h3>
    <div class="bg-slate-50 rounded-2xl p-4 mb-5 space-y-3">
      <div class="grid grid-cols-2 gap-3">
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">عنوان العرض</label><input id="offerTitle" placeholder="خصم نهاية الفصل" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">نسبة الخصم %</label><input id="offerDiscount" type="number" placeholder="15" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm"></div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">تاريخ البداية</label><input id="offerStart" type="datetime-local" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">تاريخ الانتهاء</label><input id="offerEnd" type="datetime-local" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm"></div>
      </div>
      <div><label class="text-[10px] font-bold text-slate-400 block mb-1">نص البانر</label><input id="offerBannerInput" placeholder="خصم 15% على جميع الخدمات حتى نهاية الشهر!" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm"></div>
      <button onclick="addOffer()" class="w-full bg-red-600 text-white py-3 rounded-xl font-bold text-sm hover:bg-red-500"><i class="fas fa-plus ml-1"></i>إضافة العرض</button>
    </div>
    <div id="offersList" class="space-y-2"></div>
  </div>
</div>

<!-- Testimonials Modal -->
<div id="testimonialsModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeTestimonialsModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-5"><i class="fas fa-star text-amber-500 ml-2"></i>شهادات العملاء</h3>
    <div class="bg-slate-50 rounded-2xl p-4 mb-5 space-y-3">
      <div class="grid grid-cols-2 gap-3">
        <input id="testName" placeholder="اسم العميل" class="p-3 bg-white border border-slate-200 rounded-xl text-sm">
        <select id="testRating" class="p-3 bg-white border border-slate-200 rounded-xl text-sm"><option value="5">5 نجوم</option><option value="4">4 نجوم</option><option value="3">3 نجوم</option></select>
      </div>
      <textarea id="testText" placeholder="نص الشهادة..." class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm h-20 resize-none"></textarea>
      <button onclick="addTestimonial()" class="w-full bg-amber-600 text-white py-3 rounded-xl font-bold text-sm hover:bg-amber-500"><i class="fas fa-plus ml-1"></i>إضافة شهادة</button>
    </div>
    <div id="testimonialAdminList" class="space-y-2"></div>
  </div>
</div>

<!-- Stats Modal -->
<div id="statsModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeStatsModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-5"><i class="fas fa-chart-bar text-purple-600 ml-2"></i>التقارير والإحصائيات</h3>
    <div id="statsContent"><p class="text-center py-8 text-slate-400"><i class="fas fa-spinner fa-spin text-xl"></i></p></div>
  </div>
</div>

<!-- Coupon Modal -->
<div id="couponModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeCouponModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-6 flex items-center gap-2"><i class="fas fa-tag text-amber-600"></i> إدارة كوبونات الخصم</h3>
    <div class="bg-slate-50 rounded-2xl p-4 mb-5 space-y-3">
      <div class="grid grid-cols-2 gap-3">
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">كود الخصم</label>
          <input id="newCouponCode" placeholder="SAVE20" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500" style="text-transform:uppercase"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">نوع الخصم</label>
          <select id="newCouponType" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm">
            <option value="percent">نسبة مئوية %</option>
            <option value="fixed">مبلغ ثابت ر.س</option>
          </select></div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">قيمة الخصم</label>
          <input id="newCouponValue" type="number" placeholder="20" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500"></div>
        <div><label class="text-[10px] font-bold text-slate-400 block mb-1">عدد الاستخدامات (0=بلا حد)</label>
          <input id="newCouponMax" type="number" value="0" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500"></div>
      </div>
      <div><label class="text-[10px] font-bold text-slate-400 block mb-1">تاريخ انتهاء الصلاحية (اختياري)</label>
        <input id="newCouponExpiry" type="datetime-local" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-amber-500"></div>
      <button onclick="addCoupon()" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-3 rounded-xl font-bold text-sm transition-all"><i class="fas fa-plus ml-1"></i> إضافة الكوبون</button>
    </div>
    <div id="couponList" class="space-y-2 text-sm"><p class="text-center text-slate-400 text-xs py-4">جاري التحميل...</p></div>
  </div>
</div>

<!-- Edit Modal -->
<div id="editModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-lg p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeEdit()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-6 flex items-center gap-2"><i class="fas fa-edit text-amber-600"></i> تعديل الخدمة</h3>
    <form id="editForm" method="POST" enctype="multipart/form-data" class="space-y-4">
      <input name="name" id="eName" placeholder="اسم الخدمة" class="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500">
      <div class="grid grid-cols-4 gap-2">
        <input name="price" id="ePrice" type="number" step="0.01" placeholder="السعر" class="p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500">
        <input name="old_price" id="eOldPrice" type="number" step="0.01" placeholder="القديم" class="p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500">
        <input name="category" id="eCategory" placeholder="التصنيف" class="p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500">
        <input name="stock" id="eStock" type="number" placeholder="الكمية" title="999=غير محدود" class="p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500">
      </div>
      <textarea name="description" id="eDesc" placeholder="الوصف" class="w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm outline-none focus:border-amber-500 h-28 resize-none"></textarea>
      <div class="p-3 bg-slate-50 border border-dashed border-slate-200 rounded-2xl"><label class="text-[10px] font-bold text-slate-400 block mb-1">تغيير الصورة (اختياري)</label><input type="file" name="product_file" accept="image/*" class="text-xs text-slate-500 w-full"></div>
      <button type="submit" class="w-full bg-amber-600 hover:bg-amber-500 text-white py-4 rounded-2xl font-black text-sm transition-all">حفظ التعديلات</button>
    </form>
  </div>
</div>

<!-- Order Detail Modal -->
<div id="orderDetailModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-lg shadow-2xl relative max-h-[90vh] flex flex-col overflow-hidden">
    <div class="flex items-center justify-between p-6 border-b border-slate-100">
      <h3 class="text-lg font-black text-slate-800 flex items-center gap-2"><i class="fas fa-file-alt text-blue-600"></i> تفاصيل الطلب</h3>
      <button onclick="closeOrderDetail()" class="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    </div>
    <div id="orderDetailContent" class="overflow-y-auto p-6 space-y-4 flex-grow">
      <div class="text-center py-8 text-slate-300"><i class="fas fa-spinner fa-spin text-2xl"></i></div>
    </div>
  </div>
</div>

<script>
function showOTab(t){
  document.querySelectorAll('[id^="opanel-"]').forEach(function(el){el.classList.add('hidden');});
  document.querySelectorAll('[id^="otab-"]').forEach(function(el){el.classList.remove('active');});
  var p=document.getElementById('opanel-'+t);var b=document.getElementById('otab-'+t);
  if(p)p.classList.remove('hidden');if(b)b.classList.add('active');
}
function switchST(tab){
  document.getElementById('form-contact').classList.add('hidden');document.getElementById('form-bank').classList.add('hidden');
  document.getElementById('st-contact').classList.remove('active');document.getElementById('st-bank').classList.remove('active');
  document.getElementById('form-'+tab).classList.remove('hidden');document.getElementById('st-'+tab).classList.add('active');
}
function openEdit(id,name,price,oldPrice,category,desc,stock){
  document.getElementById('editForm').action='/admin/edit_product/'+id;
  document.getElementById('eName').value=name;document.getElementById('ePrice').value=price;
  document.getElementById('eOldPrice').value=oldPrice||'';document.getElementById('eCategory').value=category;
  document.getElementById('eDesc').value=desc;document.getElementById('eStock').value=stock||999;
  document.getElementById('editModal').style.display='flex';document.body.style.overflow='hidden';
}
function closeEdit(){document.getElementById('editModal').style.display='none';document.body.style.overflow='';}

async function openOrderDetail(orderId){
  document.getElementById('orderDetailModal').style.display='flex';
  document.body.style.overflow='hidden';
  var content=document.getElementById('orderDetailContent');
  content.innerHTML='<div class="text-center py-8 text-slate-300"><i class="fas fa-spinner fa-spin text-2xl"></i></div>';
  try{
    var r=await fetch('/api/order_detail/'+orderId);
    var d=await r.json();
    if(d.status==='success'){
      var statusColors={'جديد':'bg-blue-100 text-blue-700','جار التجهيز':'bg-amber-100 text-amber-700','بانتظار الدفع':'bg-green-100 text-green-700','يتطلب تعديل':'bg-purple-100 text-purple-700','ملغي':'bg-red-100 text-red-700','مكتمل':'bg-emerald-100 text-emerald-700'};
      var sc=statusColors[d.status_val]||'bg-slate-100 text-slate-600';
      var items=d.items.map(function(i){return'<div class="flex justify-between py-1 border-b border-slate-50"><span class="text-slate-700">'+i.name+' x'+i.qty+'</span><span class="font-bold">'+( parseFloat(i.price)*i.qty).toFixed(0)+' ر.س</span></div>';}).join('');
      var receiptHtml=d.has_receipt?'<a href="/admin/view_receipt/'+orderId+'" target="_blank" class="w-full mt-2 bg-amber-500 hover:bg-amber-600 text-white py-3 rounded-2xl font-bold text-sm text-center flex items-center justify-center gap-2 transition-all"><i class="fas fa-file-invoice"></i> عرض ايصال التحويل</a>':'<p class="text-center text-slate-400 text-xs py-2">لم يتم رفع ايصال بعد</p>';
      content.innerHTML=
        '<div class="flex justify-between items-start"><div><p class="text-2xl font-black text-slate-900">#'+d.id+'</p><p class="text-slate-400 text-xs">'+d.date+'</p></div><span class="text-xs px-3 py-1.5 rounded-full font-bold '+sc+'">'+d.status_val+'</span></div>'+
        '<div class="bg-slate-50 rounded-2xl p-4"><p class="text-xs font-bold text-slate-500 mb-2">بيانات العميل</p><p class="font-bold text-slate-800">'+d.customer_name+'</p><a href="tel:'+d.customer_phone+'" class="text-sm text-amber-600 font-mono hover:underline">'+d.customer_phone+'</a></div>'+
        '<div class="bg-slate-50 rounded-2xl p-4"><p class="text-xs font-bold text-slate-500 mb-2">الخدمات المطلوبة</p>'+items+'<div class="flex justify-between pt-2 font-black"><span>الاجمالي</span><span class="text-green-700">'+d.total.toFixed(0)+' ر.س</span></div></div>'+
        (d.customer_notes?'<div class="bg-amber-50 border border-amber-100 rounded-2xl p-4"><p class="text-xs font-bold text-amber-700 mb-1">ملاحظات العميل</p><p class="text-sm text-slate-700">'+d.customer_notes+'</p></div>':'')+
        '<div class="bg-slate-50 rounded-2xl p-4"><p class="text-xs font-bold text-slate-500 mb-2">ايصال التحويل</p>'+receiptHtml+'</div>'+
        '<div class="bg-slate-50 rounded-2xl p-4"><p class="text-xs font-bold text-slate-500 mb-2">ملاحظة داخلية (للإدارة فقط)</p><textarea id="adminNoteInput" class="w-full p-3 bg-white border border-slate-200 rounded-xl text-xs outline-none h-16 resize-none" placeholder="ملاحظتك...">'+d.admin_notes+'</textarea><button onclick="saveAdminNote('+orderId+')" class="mt-2 text-[10px] bg-slate-900 text-white px-4 py-2 rounded-xl font-bold hover:bg-slate-700 transition-all">حفظ الملاحظة</button></div>'+
        '<div class="flex gap-2 mb-3">'+
          '<button onclick="uploadDeliveryFile('+orderId+')" class="flex-1 bg-slate-900 text-white py-2.5 rounded-xl font-bold text-xs hover:bg-slate-700 transition-all flex items-center justify-center gap-1"><i class="fas fa-upload"></i>تسليم ملف</button>'+
          '<button onclick="assignOrder('+orderId+')" class="flex-1 bg-blue-50 text-blue-600 border border-blue-200 py-2.5 rounded-xl font-bold text-xs hover:bg-blue-100 transition-all flex items-center justify-center gap-1"><i class="fas fa-user-cog"></i>تعيين</button>'+
          '<button onclick="sendWaStatus('+orderId+')" class="flex-1 bg-green-50 text-green-600 border border-green-200 py-2.5 rounded-xl font-bold text-xs hover:bg-green-100 transition-all flex items-center justify-center gap-1"><i class="fab fa-whatsapp"></i>إشعار</button>'+
        '</div>'+
        '<div class="grid grid-cols-3 gap-2">'+
          '<a href="/admin/set_order_status/'+orderId+'/مكتمل" class="bg-green-500 hover:bg-green-600 text-white py-3 rounded-2xl font-bold text-xs text-center transition-all"><i class="fas fa-check ml-1"></i>مكتمل</a>'+
          '<a href="/admin/set_order_status/'+orderId+'/جار التجهيز" class="bg-amber-500 hover:bg-amber-600 text-white py-3 rounded-2xl font-bold text-xs text-center transition-all"><i class="fas fa-cog ml-1"></i>تجهيز</a>'+
          '<a href="/admin/set_order_status/'+orderId+'/ملغي" onclick="return true" class="bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-200 py-3 rounded-2xl font-bold text-xs text-center transition-all"><i class="fas fa-ban ml-1"></i>إلغاء</a>'+
        '</div>';
    }else{content.innerHTML='<p class="text-red-500 text-center py-6">تعذر تحميل التفاصيل</p>';}
  }catch(e){content.innerHTML='<p class="text-red-500 text-center py-6">تعذر الاتصال</p>';}
}
function closeOrderDetail(){document.getElementById('orderDetailModal').style.display='none';document.body.style.overflow='';}
async function sendWaStatus(orderId){
  try{var r=await fetch('/api/send_wa_status/'+orderId,{method:'POST'});
  var d=await r.json();
  if(d.wa_link)window.open(d.wa_link,'_blank');
  }catch(e){}
}

window.addEventListener('click',function(e){
  if(e.target===document.getElementById('editModal'))closeEdit();
  if(e.target===document.getElementById('orderDetailModal'))closeOrderDetail();
  if(e.target===document.getElementById('couponModal'))closeCouponModal();
});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeEdit();closeOrderDetail();closeCouponModal();}});

// ===== إشعار صوتي =====
var _lastNewCount={{ total_new }};
function playBeep(){
  try{var ctx=new(window.AudioContext||window.webkitAudioContext)();
  var o=ctx.createOscillator();var g=ctx.createGain();o.connect(g);g.connect(ctx.destination);
  o.frequency.setValueAtTime(880,ctx.currentTime);o.frequency.setValueAtTime(660,ctx.currentTime+0.15);
  g.gain.setValueAtTime(0.3,ctx.currentTime);g.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.5);
  o.start();o.stop(ctx.currentTime+0.5);}catch(e){}
}
setInterval(async function(){
  try{var r=await fetch('/api/stats_public');var d=await r.json();
  if(d.completed!==undefined){var newCount=d.completed;if(newCount>_lastNewCount){playBeep();_lastNewCount=newCount;}}}
  catch(e){}
},20000);

// ===== كوبونات =====


async function addCoupon(){
  var code=document.getElementById('newCouponCode');
  var type=document.getElementById('newCouponType');
  var value=document.getElementById('newCouponValue');
  var maxUses=document.getElementById('newCouponMax');
  var expiry=document.getElementById('newCouponExpiry');
  if(!code||!value){showAdminToast('خطأ في النموذج');return;}
  if(!code.value||!value.value){showAdminToast('أدخل الكود وقيمة الخصم');return;}
  var fd=new FormData();
  fd.append('action','add');
  fd.append('code',code.value.toUpperCase());
  fd.append('discount_type',type?type.value:'percent');
  fd.append('discount_value',value.value);
  fd.append('max_uses',maxUses?maxUses.value:'0');
  if(expiry&&expiry.value) fd.append('expires_at',expiry.value);
  try{
    await fetch('/admin/coupons',{method:'POST',body:fd});
    showAdminToast('تم إضافة الكوبون ✅');
    code.value='';value.value='';if(maxUses)maxUses.value='0';if(expiry)expiry.value='';
    loadCoupons();
  }catch(e){showAdminToast('فشل الإضافة');}
}

async function deleteCoupon(id){
  if(!confirm('حذف الكوبون؟'))return;
  var fd=new FormData();fd.append('action','delete');fd.append('id',id);
  try{
    await fetch('/admin/coupons',{method:'POST',body:fd});
    showAdminToast('تم الحذف');loadCoupons();
  }catch(e){showAdminToast('فشل الحذف');}
}

async function loadCoupons(){
  var list=document.getElementById('couponList');
  try{
    var r=await fetch('/admin/coupons');var coupons=await r.json();
    if(!coupons.length){list.innerHTML='<p class="text-center text-slate-400 text-xs py-6">لا توجد كوبونات. أضف أول كوبون!</p>';return;}
    var now=new Date();
    list.innerHTML=coupons.map(function(c){
      var typeLabel=c.type==='percent'?c.value+'%':c.value+' ر.س';
      var expiryHtml='';
      if(c.expires_at){
        var expDate=new Date(c.expires_at);
        var isExpired=expDate<now;
        expiryHtml='<span class="text-[9px] '+(isExpired?'text-red-500 font-bold':'text-slate-400')+'"> | ينتهي: '+expDate.toLocaleDateString('ar-SA')+(isExpired?' (منتهي)':'')+'</span>';
      }
      return '<div class="flex items-center justify-between bg-slate-50 rounded-xl p-3">'+
        '<div><p class="font-black text-sm">'+c.code+'</p><p class="text-[10px] text-slate-500">خصم '+typeLabel+' | استخدم '+c.used+' مرة'+expiryHtml+'</p></div>'+
        '<div class="flex gap-1">'+
        '<form method="POST" action="/admin/coupons" class="inline"><input type="hidden" name="action" value="toggle"><input type="hidden" name="id" value="'+c.id+'"><button type="submit" class="text-[10px] px-2 py-1 rounded-lg font-bold '+( c.active?'bg-green-100 text-green-700':'bg-slate-200 text-slate-500')+'">'+( c.active?'فعال':'معطل')+'</button></form> '+
        '<button onclick="deleteCoupon('+c.id+')" class="text-[10px] px-2 py-1 rounded-lg bg-red-50 text-red-500 font-bold">حذف</button>'+
        '</div></div>';
    }).join('');
  }catch(e){list.innerHTML='<p class="text-red-500 text-xs text-center">تعذر التحميل</p>';}
}

// ===== فريق العمل =====
async function loadTeam(){
  var list=document.getElementById('teamList');
  if(!list)return;
  list.innerHTML='<p class="text-center py-4 text-slate-400"><i class="fas fa-spinner fa-spin"></i></p>';
  try{
    var r=await fetch('/admin/team');
    var team=await r.json();
    if(!team.length){list.innerHTML='<p class="text-center text-slate-400 text-xs py-4">لا يوجد أعضاء فريق</p>';return;}
    list.innerHTML=team.map(function(m){
      return '<div class="bg-slate-50 rounded-xl p-3 flex justify-between items-center gap-3">'+
        '<div class="min-w-0"><p class="font-bold text-sm">'+escapeHtml(m.name)+'</p>'+
        '<p class="text-xs text-slate-500">'+escapeHtml(m.role||'')+'</p></div>'+
        '<button onclick="deleteTeamMember('+m.id+')" class="text-[10px] bg-red-50 text-red-500 px-2 py-1 rounded-lg font-bold shrink-0">حذف</button>'+
      '</div>';
    }).join('');
  }catch(e){list.innerHTML='<p class="text-red-500 text-xs text-center py-4">تعذر تحميل الفريق</p>';}
}

async function addTeamMember(){
  var name=document.getElementById('teamName').value.trim();
  var role=document.getElementById('teamRole').value.trim();
  if(!name){showAdminToast('اسم العضو مطلوب');return;}
  var fd=new FormData();fd.append('action','add');fd.append('name',name);fd.append('role',role);
  try{
    await fetch('/admin/team',{method:'POST',body:fd});
    document.getElementById('teamName').value='';
    document.getElementById('teamRole').value='';
    loadTeam();
  }catch(e){showAdminToast('فشل إضافة العضو');}
}

async function deleteTeamMember(id){
  if(!confirm('حذف عضو الفريق؟'))return;
  var fd=new FormData();fd.append('action','delete');fd.append('id',id);
  try{await fetch('/admin/team',{method:'POST',body:fd});loadTeam();}
  catch(e){showAdminToast('فشل حذف العضو');}
}

// ===== العروض الموسمية =====
async function loadOffers(){
  var list=document.getElementById('offersList');
  if(!list)return;
  list.innerHTML='<p class="text-center py-4 text-slate-400"><i class="fas fa-spinner fa-spin"></i></p>';
  try{
    var r=await fetch('/admin/offers');
    var offers=await r.json();
    if(!offers.length){list.innerHTML='<p class="text-center text-slate-400 text-xs py-4">لا توجد عروض</p>';return;}
    list.innerHTML=offers.map(function(o){
      return '<div class="bg-slate-50 rounded-xl p-3">'+
        '<div class="flex justify-between items-start gap-3">'+
          '<div class="min-w-0"><p class="font-bold text-sm">'+escapeHtml(o.title)+' <span class="text-red-600">'+o.discount+'%</span></p>'+
          '<p class="text-[10px] text-slate-500">'+escapeHtml(o.start||'')+' - '+escapeHtml(o.end||'')+'</p>'+
          '<p class="text-xs text-slate-600 truncate">'+escapeHtml(o.banner||'')+'</p></div>'+
          '<span class="text-[10px] px-2 py-1 rounded-lg font-bold '+(o.active?'bg-green-100 text-green-700':'bg-slate-200 text-slate-500')+'">'+(o.active?'فعال':'معطل')+'</span>'+
        '</div>'+
        '<div class="flex gap-2 mt-3">'+
          '<button onclick="toggleOffer('+o.id+')" class="flex-1 text-[10px] bg-amber-50 text-amber-600 px-2 py-1.5 rounded-lg font-bold">تبديل الحالة</button>'+
          '<button onclick="deleteOffer('+o.id+')" class="text-[10px] bg-red-50 text-red-500 px-2 py-1.5 rounded-lg font-bold">حذف</button>'+
        '</div>'+
      '</div>';
    }).join('');
  }catch(e){list.innerHTML='<p class="text-red-500 text-xs text-center py-4">تعذر تحميل العروض</p>';}
}

async function addOffer(){
  var title=document.getElementById('offerTitle').value.trim();
  var discount=document.getElementById('offerDiscount').value;
  if(!title||!discount){showAdminToast('عنوان العرض ونسبة الخصم مطلوبة');return;}
  var fd=new FormData();fd.append('action','add');
  fd.append('title',title);fd.append('discount',discount);
  fd.append('start',document.getElementById('offerStart').value);
  fd.append('end',document.getElementById('offerEnd').value);
  fd.append('banner',document.getElementById('offerBannerInput').value);
  try{
    await fetch('/admin/offers',{method:'POST',body:fd});
    ['offerTitle','offerDiscount','offerStart','offerEnd','offerBannerInput'].forEach(function(id){document.getElementById(id).value='';});
    loadOffers();
  }catch(e){showAdminToast('فشل إضافة العرض');}
}

async function toggleOffer(id){
  var fd=new FormData();fd.append('action','toggle');fd.append('id',id);
  try{await fetch('/admin/offers',{method:'POST',body:fd});loadOffers();}
  catch(e){showAdminToast('فشل تحديث العرض');}
}

async function deleteOffer(id){
  if(!confirm('حذف العرض؟'))return;
  var fd=new FormData();fd.append('action','delete');fd.append('id',id);
  try{await fetch('/admin/offers',{method:'POST',body:fd});loadOffers();}
  catch(e){showAdminToast('فشل حذف العرض');}
}

// ===== شهادات العملاء =====
function openTestimonialsModal(){document.getElementById('testimonialsModal').style.display='flex';loadAdminTestimonials();}
function closeTestimonialsModal(){document.getElementById('testimonialsModal').style.display='none';}
async function addTestimonial(){
  var fd=new FormData();fd.append('action','add');
  fd.append('name',document.getElementById('testName').value);
  fd.append('text',document.getElementById('testText').value);
  fd.append('rating',document.getElementById('testRating').value);
  await fetch('/admin/testimonials',{method:'POST',body:fd});
  document.getElementById('testName').value='';document.getElementById('testText').value='';loadAdminTestimonials();
}
async function loadAdminTestimonials(){
  var list=document.getElementById('testimonialAdminList');
  try{var r=await fetch('/admin/testimonials');var data=await r.json();
  if(!data.length){list.innerHTML='<p class="text-center text-slate-400 text-xs py-4">لا توجد شهادات</p>';return;}
  list.innerHTML=data.map(function(t){
    return '<div class="bg-slate-50 rounded-xl p-3 flex justify-between items-start"><div class="min-w-0"><p class="font-bold text-sm">'+t.name+' - '+t.rating+' نجوم</p>'+
    '<p class="text-xs text-slate-500 truncate">'+t.text+'</p></div>'+
    '<button onclick="deleteTestimonial('+t.id+')" class="text-[10px] bg-red-50 text-red-500 px-2 py-1 rounded-lg font-bold shrink-0">حذف</button></div>';
  }).join('');}catch(e){}
}
async function deleteTestimonial(id){var fd=new FormData();fd.append('action','delete');fd.append('id',id);await fetch('/admin/testimonials',{method:'POST',body:fd});loadAdminTestimonials();}

// ===== التقارير =====
async function loadAdminStats(){
  var box=document.getElementById('statsContent');
  if(!box)return;
  box.innerHTML='<p class="text-center py-8 text-slate-400"><i class="fas fa-spinner fa-spin text-xl"></i></p>';
  try{
    var r=await fetch('/api/admin_stats');
    var s=await r.json();
    var top=s.top_product?escapeHtml(s.top_product.name||'')+' ('+s.top_product.count+')':'لا يوجد';
    var deadline=(s.deadline_soon||[]).length?(s.deadline_soon||[]).map(function(o){
      return '<div class="bg-red-50 text-red-700 rounded-xl p-3 text-xs font-bold">#'+o.id+' - '+escapeHtml(o.name||'')+'<br><span class="font-normal">'+escapeHtml(o.deadline||'')+'</span></div>';
    }).join(''):'<p class="text-xs text-slate-400 text-center py-3">لا توجد طلبات قريبة الموعد</p>';
    box.innerHTML=
      '<div class="grid grid-cols-2 gap-3 mb-5">'+
        '<div class="bg-purple-50 rounded-2xl p-4"><p class="text-[10px] text-purple-500 font-bold">مبيعات اليوم</p><p class="text-2xl font-black text-purple-700">'+s.daily_sales+' ر.س</p></div>'+
        '<div class="bg-blue-50 rounded-2xl p-4"><p class="text-[10px] text-blue-500 font-bold">مبيعات الأسبوع</p><p class="text-2xl font-black text-blue-700">'+s.weekly_sales+' ر.س</p></div>'+
        '<div class="bg-green-50 rounded-2xl p-4"><p class="text-[10px] text-green-500 font-bold">مبيعات الشهر</p><p class="text-2xl font-black text-green-700">'+s.monthly_sales+' ر.س</p></div>'+
        '<div class="bg-slate-50 rounded-2xl p-4"><p class="text-[10px] text-slate-500 font-bold">طلبات الشهر</p><p class="text-2xl font-black text-slate-800">'+s.total_orders+'</p></div>'+
      '</div>'+
      '<div class="bg-slate-50 rounded-2xl p-4 mb-4"><p class="text-xs text-slate-500 font-bold mb-1">أكثر خدمة طلباً</p><p class="font-black text-slate-800">'+top+'</p></div>'+
      '<div><p class="text-xs text-slate-500 font-bold mb-2">طلبات قريبة الموعد</p><div class="space-y-2">'+deadline+'</div></div>'+
      '<button onclick="loadWeeklyReport()" class="w-full mt-5 bg-purple-600 text-white py-3 rounded-xl font-bold text-sm hover:bg-purple-500">تقرير واتساب أسبوعي</button>';
  }catch(e){box.innerHTML='<p class="text-red-500 text-xs text-center py-8">تعذر تحميل الإحصائيات</p>';}
}

async function loadWeeklyReport(){
  try{
    var r=await fetch('/api/weekly_report');
    var d=await r.json();
    if(d.wa_link)window.open(d.wa_link,'_blank');
  }catch(e){showAdminToast('فشل تحميل التقرير');}
}

function escapeHtml(value){
  return String(value==null?'':value).replace(/[&<>"']/g,function(ch){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
  });
}

// ===== تسليم ملف للعميل =====
async function uploadDeliveryFile(orderId){
  var input=document.createElement('input');
  input.type='file';input.accept='.pdf,.doc,.docx,.pptx,.xlsx,.zip,.rar';
  input.onchange=async function(){
    if(!input.files[0])return;
    var fd=new FormData();fd.append('file',input.files[0]);
    try{
      var r=await fetch('/api/upload_delivery/'+orderId,{method:'POST',body:fd});
      var d=await r.json();
      if(d.status==='success'){
        showAdminToast('تم رفع الملف وتحديث الحالة لمكتمل ✅');
        setTimeout(function(){location.reload();},1500);
      }
    }catch(e){showAdminToast('فشل الرفع');}
  };
  input.click();
}

// ===== تعيين موظف =====
async function assignOrder(orderId){
  try{var r=await fetch('/admin/team');var team=await r.json();
  if(!team.length){showAdminToast('أضف أعضاء فريق أولاً');return;}
  var names=team.map(function(m,i){return(i+1)+'. '+m.name;}).join('\n');
  var choice=prompt('اختر رقم العضو:\n'+names);
  if(!choice)return;
  var idx=parseInt(choice)-1;
  if(idx>=0&&idx<team.length){
    await fetch('/admin/save_note/'+orderId,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({note:'تم تعيين: '+team[idx].name})});
    showAdminToast('تم تعيين '+team[idx].name);
  }}catch(e){}
}

// ===== ملاحظة داخلية =====
async function updateOrderStatus(orderId,newStatus){
  fetch('/admin/update_status/'+orderId,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({status:newStatus})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.status==='success'){
      showAdminToast('تم تحديث الحالة');
      if(d.wa_link)window.open(d.wa_link,'_blank');
      if(d.new_status)showAdminToast('الحالة: '+d.new_status);
      setTimeout(function(){location.reload();},1500);
    }
  }).catch(function(){showAdminToast('فشل التحديث');});
}


function showAdminToast(msg){
  var t=document.createElement('div');
  t.className='fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-900 text-white px-6 py-3 rounded-2xl font-bold text-sm shadow-2xl z-[999]';
  t.innerText=msg;
  document.body.appendChild(t);
  setTimeout(function(){t.remove();},2500);
}

async function saveAdminNote(orderId){
  var note=document.getElementById('adminNoteInput').value;
  try{await fetch('/admin/save_note/'+orderId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:note})});
  var t=document.createElement('div');t.className='fixed bottom-6 left-1/2 -translate-x-1/2 bg-green-500 text-white px-5 py-3 rounded-2xl font-bold text-sm shadow-xl z-[999]';
  t.innerText='تم حفظ الملاحظة';document.body.appendChild(t);setTimeout(function(){t.remove();},2500);}catch(e){}
}
</script>

<!-- Customers Modal -->
<div id="customersModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-5xl p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeCustomersModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-5"><i class="fas fa-users text-cyan-600 ml-2"></i>إدارة العملاء</h3>
    <div class="bg-slate-50 rounded-2xl p-4 mb-4">
      <div class="flex gap-3">
        <input id="customerSearchInput" type="text" placeholder="بحث بالاسم أو الجوال" class="flex-1 p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-cyan-500">
        <button onclick="searchCustomers()" class="bg-cyan-600 text-white px-6 rounded-xl font-bold text-sm hover:bg-cyan-500"><i class="fas fa-search ml-1"></i>بحث</button>
      </div>
    </div>
    <div id="customersList" class="space-y-3">
      <div class="text-center py-8 text-slate-400"><i class="fas fa-spinner fa-spin text-xl"></i></div>
    </div>
  </div>
</div>

<!-- Edit Customer Modal -->
<div id="editCustomerModal" style="display:none" class="fixed inset-0 bg-slate-900/70 backdrop-blur-md flex items-center justify-center p-4 z-[110]">
  <div class="bg-white rounded-3xl w-full max-w-md p-8 shadow-2xl relative">
    <button onclick="closeEditCustomer()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <h3 class="text-lg font-black mb-5"><i class="fas fa-user-edit text-cyan-600 ml-2"></i>تعديل بيانات العميل</h3>
    <div class="space-y-3">
      <input id="editCustomerId" type="hidden">
      <div>
        <label class="text-xs font-bold text-slate-600 mb-1 block">الاسم</label>
        <input id="editCustomerName" type="text" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-cyan-500">
      </div>
      <div>
        <label class="text-xs font-bold text-slate-600 mb-1 block">الجوال</label>
        <input id="editCustomerPhone" type="text" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-cyan-500">
      </div>
      <div>
        <label class="text-xs font-bold text-slate-600 mb-1 block">البريد الإلكتروني</label>
        <input id="editCustomerEmail" type="email" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-cyan-500">
      </div>
      <button onclick="saveCustomerEdit()" class="w-full bg-cyan-600 text-white py-3 rounded-xl font-bold hover:bg-cyan-500 mt-4">
        <i class="fas fa-save ml-2"></i>حفظ التعديلات
      </button>
    </div>
  </div>
</div>


<!-- Invoices Modal -->
<div id="invoicesModal" style="display:none" class="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
  <div class="bg-white rounded-3xl w-full max-w-4xl p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
    <button onclick="closeInvoicesModal()" class="absolute top-5 left-5 w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200"><i class="fas fa-times"></i></button>
    <h3 class="text-xl font-black mb-5"><i class="fas fa-file-invoice text-indigo-600 ml-2"></i>إيصالات الشراء</h3>
    <div class="bg-slate-50 rounded-2xl p-4 mb-4">
      <div class="flex gap-3">
        <input id="invoiceSearchOrder" type="number" placeholder="رقم الطلب" class="flex-1 p-3 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-indigo-500">
        <button onclick="searchInvoice()" class="bg-indigo-600 text-white px-6 rounded-xl font-bold text-sm hover:bg-indigo-500"><i class="fas fa-search ml-1"></i>بحث</button>
      </div>
    </div>
    <div id="invoicesList" class="space-y-3">
      <div class="text-center py-8 text-slate-400"><i class="fas fa-spinner fa-spin text-xl"></i></div>
    </div>
  </div>
</div>

</body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)