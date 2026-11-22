from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(100))
    pack = db.Column(db.String(50))
    hsn = db.Column(db.String(10))
    gst_percent = db.Column(db.Numeric(4, 2), nullable=False)
    mrp = db.Column(db.Numeric(10, 2), nullable=False)


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    gstin = db.Column(db.String(15))
    drug_licence_no = db.Column(db.String(50))


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    gstin = db.Column(db.String(15))
    drug_licence_no = db.Column(db.String(50))
    phone = db.Column(db.String(15))


class Purchase(db.Model):
    __tablename__ = "purchases"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    bill_no = db.Column(db.String(50))
    bill_date = db.Column(db.Date, nullable=False)
    supplier = db.relationship("Supplier")
    batches = db.relationship("Batch", backref="purchase")


class Batch(db.Model):
    __tablename__ = "batches"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=False)
    batch_no = db.Column(db.String(50), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    purchase_rate = db.Column(db.Numeric(10, 2), nullable=False)
    sale_rate = db.Column(db.Numeric(10, 2), nullable=False)
    qty_received = db.Column(db.Integer, nullable=False)
    qty_available = db.Column(db.Integer, nullable=False)
    product = db.relationship("Product")

class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(20), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    gst_total = db.Column(db.Numeric(12, 2), nullable=False)
    round_off = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    grand_total = db.Column(db.Numeric(12, 2), nullable=False)
    customer = db.relationship("Customer")
    items = db.relationship("SaleItem", backref="sale")


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    gst_percent = db.Column(db.Numeric(4, 2), nullable=False)
    taxable_amount = db.Column(db.Numeric(12, 2), nullable=False)
    gst_amount = db.Column(db.Numeric(12, 2), nullable=False)
    batch = db.relationship("Batch")
    product = db.relationship("Product")

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    reference = db.Column(db.String(100))
    customer = db.relationship("Customer")

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="staff")
    active = db.Column(db.Boolean, nullable=False, default=True)

class SaleReturn(db.Model):
    __tablename__ = "sale_returns"
    id = db.Column(db.Integer, primary_key=True)
    credit_note_no = db.Column(db.String(20), nullable=False, unique=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    gst_total = db.Column(db.Numeric(12, 2), nullable=False)
    round_off = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    grand_total = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(100))
    sale = db.relationship("Sale")
    customer = db.relationship("Customer")
    items = db.relationship("SaleReturnItem", backref="sale_return")


class SaleReturnItem(db.Model):
    __tablename__ = "sale_return_items"
    id = db.Column(db.Integer, primary_key=True)
    sale_return_id = db.Column(db.Integer, db.ForeignKey("sale_returns.id"), nullable=False)
    sale_item_id = db.Column(db.Integer, db.ForeignKey("sale_items.id"), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    gst_percent = db.Column(db.Numeric(4, 2), nullable=False)
    taxable_amount = db.Column(db.Numeric(12, 2), nullable=False)
    gst_amount = db.Column(db.Numeric(12, 2), nullable=False)
    restocked = db.Column(db.Boolean, nullable=False, default=False)
    sale_item = db.relationship("SaleItem")
    batch = db.relationship("Batch")
    product = db.relationship("Product")


class PurchaseReturn(db.Model):
    __tablename__ = "purchase_returns"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    batch = db.relationship("Batch")
    supplier = db.relationship("Supplier")

class SupplierPayment(db.Model):
    __tablename__ = "supplier_payments"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    reference = db.Column(db.String(100))
    supplier = db.relationship("Supplier")