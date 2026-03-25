from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import io
from flask import Flask, render_template, request, redirect
from models import db, Product, Sale
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db.init_app(app)

with app.app_context():
    db.create_all()

# Home Page
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

# Add Product
@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    buying_price = float(request.form['buying_price'])
    selling_price = float(request.form['selling_price'])
    quantity = int(request.form['quantity'])
    min_stock = int(request.form['min_stock'])

    # Check if product already exists
    existing_product = Product.query.filter_by(name=name).first()

    if existing_product:
        # Restock instead of creating new
        existing_product.quantity += quantity
        existing_product.buying_price = buying_price
        existing_product.selling_price = selling_price
    else:
        # Create new product
        product = Product(
            name=name,
            buying_price=buying_price,
            selling_price=selling_price,
            quantity=quantity,
            min_stock=min_stock
        )
        db.session.add(product)

    db.session.commit()
    return redirect('/')

# Record Sale
@app.route('/sell/<int:id>', methods=['POST'])
def sell(id):
    product = Product.query.get(id)
    qty = int(request.form['quantity'])

    if product.quantity >= qty:
        product.quantity -= qty

        total = qty * product.selling_price
        profit = qty * (product.selling_price - product.buying_price)

        sale = Sale(
            product_id=id,
            quantity_sold=qty,
            total_price=total,
            profit=profit
        )

        db.session.add(sale)
        db.session.commit()

    return redirect('/')

# Dashboard
@app.route('/dashboard')
def dashboard():
    sales = Sale.query.all()

    total_sales = sum(s.total_price for s in sales)
    total_profit = sum(s.profit for s in sales)

    # Chart data
    dates = [s.date.strftime("%Y-%m-%d") for s in sales]
    sales_data = [s.total_price for s in sales]
    profit_data = [s.profit for s in sales]

    # Best-selling products
    best_products = db.session.query(
        Product.name,
        func.sum(Sale.quantity_sold)
    ).join(Sale).group_by(Product.name).all()

    return render_template(
        'dashboard.html',
        total_sales=total_sales,
        total_profit=total_profit,
        dates=dates,
        sales_data=sales_data,
        profit_data=profit_data,
        best_products=best_products
    )

#Restock    
@app.route('/restock/<int:id>', methods=['POST'])
def restock(id):
    product = Product.query.get(id)
    qty = int(request.form['quantity'])

    product.quantity += qty
    db.session.commit()

    return redirect('/')

#Delete
@app.route('/delete/<int:id>')
def delete(id):
    product = Product.query.get(id)
    db.session.delete(product)
    db.session.commit()
    return redirect('/')

#Report
@app.route('/report')
def generate_report():
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("MktIntel Financial Report", styles['Title']))
    elements.append(Spacer(1, 10))

    sales = Sale.query.all()

    total_sales = sum(s.total_price for s in sales)
    total_profit = sum(s.profit for s in sales)

    elements.append(Paragraph(f"Total Sales: ${total_sales}", styles['Normal']))
    elements.append(Paragraph(f"Total Profit: ${total_profit}", styles['Normal']))

    doc.build(elements)

    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="report.pdf")

if __name__ == "__main__":
    app.run()