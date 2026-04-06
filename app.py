from flask import Flask, render_template, request, redirect, send_file, session
from models import User, db, Product, Sale
from sqlalchemy import func
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os
from collections import Counter
from functools import wraps
from datetime import datetime, timedelta
from reportlab.platypus import Image

app = Flask(__name__)
app.secret_key = "supersecretkey"

db_url = os.environ.get("DATABASE_URL")

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///database.db'

db.init_app(app)

with app.app_context():
    db.create_all()

# ================= LOGIN REQUIRED =================
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect('/login')
        return func(*args, **kwargs)
    return wrapper


# ================= DASHBOARD =================
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')

    products = Product.query.filter_by(user_id=user_id).all()
    sales = Sale.query.filter_by(user_id=user_id).all()

    total_sales = sum(s.total_price for s in sales)
    total_profit = sum(s.profit for s in sales)

    # 📊 DAILY SALES (BAR CHART)
    daily_sales = {}
    for s in sales:
        day = s.date.strftime("%Y-%m-%d")
        daily_sales[day] = daily_sales.get(day, 0) + s.total_price

    sorted_sales = sorted(daily_sales.items())

    dates = [d[0] for d in sorted_sales]
    sales_data = [d[1] for d in sorted_sales]

    # 📉 LOW STOCK
    low_stock = len([p for p in products if p.quantity <= p.min_stock])

    # 🔥 BEST SELLER
    product_sales = {}
    for s in sales:
        product = db.session.get(Product, s.product_id)
        if product:
            product_sales[product.name] = product_sales.get(product.name, 0) + s.quantity_sold

    best_product = max(product_sales, key=product_sales.get) if product_sales else "N/A"

    # 📆 WEEKLY COMPARISON
    today = datetime.now()
    last_7_days = today - timedelta(days=7)
    prev_7_days = today - timedelta(days=14)

    current_week_sales = sum(s.total_price for s in sales if s.date >= last_7_days)
    previous_week_sales = sum(s.total_price for s in sales if prev_7_days <= s.date < last_7_days)

    # 🧠 SMART INSIGHTS
    insight = "📊 Keep pushing sales!"
    if current_week_sales > previous_week_sales:
        insight = "🔥 Sales increased this week!"
    elif current_week_sales < previous_week_sales:
        insight = "⚠️ Sales dropped this week"

    if total_profit > 100:
        insight += " 💰 Strong profit growth!"
    elif total_profit < 20:
        insight += " ⚠️ Low profit margins"

    return render_template(
        "dashboard.html",
        total_sales=total_sales,
        total_profit=total_profit,
        dates=dates,
        sales_data=sales_data,
        low_stock=low_stock,
        best_product=best_product,
        insight=insight,
        products=products
    )


# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(
            username=request.form['username'],
            password=request.form['password']
        ).first()

        if user:
            session['user_id'] = user.id
            return redirect('/dashboard')

    return render_template("login.html")


# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(
            username=request.form['username'],
            password=request.form['password']
        )
        db.session.add(user)
        db.session.commit()
        return redirect('/login')

    return render_template("register.html")


# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ================= STOCK =================
@app.route('/stock')
@login_required
def stock():
    user_id = session.get('user_id')
    products = Product.query.filter_by(user_id=user_id).all()
    return render_template("stock.html", products=products)


# ================= SALES =================
@app.route('/sales')
@login_required
def sales_page():
    user_id = session.get('user_id')
    products = Product.query.filter_by(user_id=user_id).all()
    return render_template("sales.html", products=products)


# ================= REPORTS =================
@app.route('/reports')
@login_required
def reports():
    return render_template("reports.html")


# ================= ADD PRODUCT =================
@app.route('/add_product', methods=['POST'])
@login_required
def add_product():
    user_id = session.get('user_id')

    name = request.form['name']
    buying_price = float(request.form['buying_price'])
    selling_price = float(request.form['selling_price'])
    quantity = int(request.form['quantity'])
    min_stock = int(request.form['min_stock'])

    existing = Product.query.filter_by(name=name, user_id=user_id).first()

    if existing:
        existing.quantity += quantity
    else:
        product = Product(
            name=name,
            buying_price=buying_price,
            selling_price=selling_price,
            quantity=quantity,
            min_stock=min_stock,
            user_id=user_id
        )
        db.session.add(product)

    db.session.commit()
    return redirect('/stock')


# ================= SELL =================
@app.route('/sell/<int:id>', methods=['POST'])
@login_required
def sell(id):
    product = Product.query.get(id)
    qty = int(request.form['quantity'])

    if product and product.quantity >= qty:
        product.quantity -= qty

        total = qty * product.selling_price
        profit = qty * (product.selling_price - product.buying_price)

        sale = Sale(
            product_id=id,
            quantity_sold=qty,
            total_price=total,
            profit=profit,
            user_id=session.get('user_id')
        )

        db.session.add(sale)
        db.session.commit()

    return redirect('/sales')


# ================= RESTOCK =================
@app.route('/restock/<int:id>', methods=['POST'])
@login_required
def restock(id):
    product = Product.query.get(id)
    qty = int(request.form['quantity'])

    if product:
        product.quantity += qty
        db.session.commit()

    return redirect('/stock')


# ================= DELETE =================
@app.route('/delete/<int:id>')
@login_required
def delete(id):
    product = Product.query.get(id)
    if product:
        db.session.delete(product)
        db.session.commit()
    return redirect('/stock')


# ================= PDF REPORT =================
@app.route('/report')
@login_required
def report():
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elements = []

    user_id = session.get('user_id')
    user = User.query.get(user_id)

    sales = Sale.query.filter_by(user_id=user_id).all()
    products = Product.query.filter_by(user_id=user_id).all()

    total_sales = sum(s.total_price for s in sales)
    total_profit = sum(s.profit for s in sales)

    # ================= HEADER =================`
    logo = "static/logo.png"
    elements.append(Image(logo, width=80, height=40))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("MktIntel Business Report", styles['Title']))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph(
        f"User: <b>{user.username}</b>",
        styles['Normal']
    ))

    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles['Normal']
    ))

    elements.append(Spacer(1, 12))

    # ================= SUMMARY =================
    elements.append(Paragraph("Financial Summary", styles['Heading2']))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph(
        f"Total Sales: <b>${total_sales}</b>",
        styles['Normal']
    ))

    elements.append(Paragraph(
        f"Total Profit: <b>${total_profit}</b>",
        styles['Normal']
    ))

    elements.append(Spacer(1, 12))

    # ================= SALES =================
    elements.append(Paragraph("Sales History", styles['Heading2']))
    elements.append(Spacer(1, 6))

    if not sales:
        elements.append(Paragraph("No sales recorded", styles['Normal']))
    else:
        for s in sales:
            product = Product.query.get(s.product_id)
            name = product.name if product else "Deleted Product"

            elements.append(Paragraph(
                f"{s.date.strftime('%Y-%m-%d')} | "
                f"{name} | "
                f"Qty: {s.quantity_sold} | "
                f"Sales: ${s.total_price} | "
                f"Profit: ${s.profit}",
                styles['Normal']
            ))

    elements.append(Spacer(1, 12))

    # ================= STOCK =================
    elements.append(Paragraph("Stock Summary", styles['Heading2']))
    elements.append(Spacer(1, 6))

    for p in products:
        status = "LOW STOCK" if p.quantity <= p.min_stock else "OK"

        elements.append(Paragraph(
            f"{p.name} — {p.quantity} units "
            f"(Min: {p.min_stock}) — {status}",
            styles['Normal']
        ))

    elements.append(Spacer(1, 12))

    # ================= INSIGHTS =================
    elements.append(Paragraph("Business Insights", styles['Heading2']))
    elements.append(Spacer(1, 6))

    if total_profit > 100:
        insight = "Strong profitability"
    elif total_profit < 20:
        insight = "Low profit margin"
    else:
        insight = "Stable performance"

    elements.append(Paragraph(insight, styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="MktIntel_Report.pdf"
    )


if __name__ == "__main__":
    app.run(debug=True)