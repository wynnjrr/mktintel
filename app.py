from flask import Flask, render_template, request, redirect, send_file, session
from models import User, db, Product, Sale
from sqlalchemy import func
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os
from collections import Counter
from functools import wraps

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

    dates = [s.date.strftime("%Y-%m-%d") for s in sales]
    sales_data = [s.total_price for s in sales]

    low_stock = len([p for p in products if p.quantity <= p.min_stock])

    # BEST SELLER
    product_sales = Counter()
    for s in sales:
        product = Product.query.get(s.product_id)
        if product:
            product_sales[product.name] += s.quantity_sold

    best_product = max(product_sales, key=product_sales.get) if product_sales else "N/A"

    # INSIGHT
    insight = "Good performance"
    if total_profit > 100:
        insight = "🔥 Strong profit growth!"
    elif total_profit < 20:
        insight = "⚠️ Profit is low, increase sales"

    return render_template(
        "dashboard.html",
        total_sales=total_sales,
        total_profit=total_profit,
        dates=dates,
        sales_data=sales_data,
        low_stock=low_stock,
        products=products,
        best_product=best_product,
        insight=insight
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
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("MktIntel Financial Report", styles['Title']))
    elements.append(Spacer(1, 10))

    user_id = session.get('user_id')
    sales = Sale.query.filter_by(user_id=user_id).all()

    total_sales = sum(s.total_price for s in sales)
    total_profit = sum(s.profit for s in sales)

    elements.append(Paragraph(f"Total Sales: ${total_sales}", styles['Normal']))
    elements.append(Paragraph(f"Total Profit: ${total_profit}", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="report.pdf")


if __name__ == "__main__":
    app.run(debug=True)