from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session,send_file)
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, and_
from werkzeug.security import check_password_hash

from models import (db, Product, Supplier, Customer, Purchase, Batch,
                    Sale, SaleItem, Payment, User,
                    SaleReturn, SaleReturnItem, PurchaseReturn, SupplierPayment)
app = Flask(__name__)
app.config.from_object("config.Config")
db.init_app(app)

@app.before_request
def require_login():
    if request.endpoint in ("login", "static"):
        return
    if "user_id" not in session:
        return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        user = User.query.filter_by(username=username, active=True).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            nxt = request.args.get("next", "")
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = url_for("home")
            return redirect(nxt)
        flash("Wrong username or password", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    return redirect(url_for("dashboard"))


# ---------- Products ----------
@app.route("/products")
def products():
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        query = query.filter(Product.name.like(f"%{q}%"))
    items = query.order_by(Product.name).all()
    return render_template("products.html", items=items, q=q)


@app.route("/products/new", methods=["GET", "POST"])
@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def product_form(pid=None):
    product = db.get_or_404(Product, pid) if pid else Product()
    if request.method == "POST":
        f = request.form
        product.name = f["name"].strip()
        product.company = f["company"].strip()
        product.pack = f["pack"].strip()
        product.hsn = f["hsn"].strip()
        product.gst_percent = f["gst_percent"]
        product.mrp = f["mrp"]
        db.session.add(product)
        db.session.commit()
        flash("Product saved")
        return redirect(url_for("products"))
    return render_template("product_form.html", p=product)


# ---------- Suppliers ----------
@app.route("/suppliers")
def suppliers():
    items = Supplier.query.order_by(Supplier.name).all()
    return render_template("suppliers.html", items=items)


@app.route("/suppliers/new", methods=["GET", "POST"])
@app.route("/suppliers/<int:sid>/edit", methods=["GET", "POST"])
def supplier_form(sid=None):
    s = db.get_or_404(Supplier, sid) if sid else Supplier()
    if request.method == "POST":
        f = request.form
        s.name = f["name"].strip()
        s.gstin = f["gstin"].strip()
        s.drug_licence_no = f["drug_licence_no"].strip()
        db.session.add(s)
        db.session.commit()
        flash("Supplier saved")
        return redirect(url_for("suppliers"))
    return render_template("supplier_form.html", s=s)


# ---------- Customers ----------
@app.route("/customers")
def customers():
    items = Customer.query.order_by(Customer.name).all()
    return render_template("customers.html", items=items)


@app.route("/customers/new", methods=["GET", "POST"])
@app.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
def customer_form(cid=None):
    c = db.get_or_404(Customer, cid) if cid else Customer()
    if request.method == "POST":
        f = request.form
        c.name = f["name"].strip()
        c.gstin = f["gstin"].strip()
        c.drug_licence_no = f["drug_licence_no"].strip()
        c.phone = f["phone"].strip()
        db.session.add(c)
        db.session.commit()
        flash("Customer saved")
        return redirect(url_for("customers"))
    return render_template("customer_form.html", c=c)

# ---------- Purchases ----------
@app.route("/purchases")
def purchases():
    items = Purchase.query.order_by(Purchase.bill_date.desc(), Purchase.id.desc()).all()
    return render_template("purchases.html", items=items)


@app.route("/purchases/<int:pid>")
def purchase_detail(pid):
    p = db.get_or_404(Purchase, pid)
    return render_template("purchase_detail.html", p=p)


@app.route("/purchases/new", methods=["GET", "POST"])
def purchase_new():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    products = Product.query.order_by(Product.name).all()
    if request.method == "POST":
        f = request.form
        try:
            purchase = Purchase(
                supplier_id=int(f["supplier_id"]),
                bill_no=f["bill_no"].strip(),
                bill_date=datetime.strptime(f["bill_date"], "%Y-%m-%d").date(),
            )
            db.session.add(purchase)
            db.session.flush()  # purchase.id मिळवण्यासाठी

            rows = zip(
                f.getlist("product_id"), f.getlist("batch_no"),
                f.getlist("expiry_date"), f.getlist("purchase_rate"),
                f.getlist("sale_rate"), f.getlist("qty"),
            )
            count = 0
            for prod_id, batch_no, expiry, p_rate, s_rate, qty in rows:
                if not prod_id:
                    continue
                q = int(qty)
                if q <= 0:
                    raise ValueError("Quantity must be more than 0")
                db.session.add(Batch(
                    product_id=int(prod_id),
                    purchase_id=purchase.id,
                    batch_no=batch_no.strip(),
                    expiry_date=datetime.strptime(expiry, "%Y-%m-%d").date(),
                    purchase_rate=Decimal(p_rate),
                    sale_rate=Decimal(s_rate),
                    qty_received=q,
                    qty_available=q,
                ))
                count += 1
            if count == 0:
                raise ValueError("Add at least one product row")

            db.session.commit()
            flash(f"Purchase saved with {count} item(s). Stock updated.")
            return redirect(url_for("purchase_detail", pid=purchase.id))
        except (ValueError, KeyError, InvalidOperation) as e:
            db.session.rollback()
            flash(f"Could not save: {e}", "error")
    return render_template("purchase_form.html", suppliers=suppliers,
                           products=products, today=date.today().isoformat())

# ---------- Stock ----------
LOW_STOCK = 20          # यापेक्षा कमी qty असेल तर "Low" दिसेल
EXPIRY_ALERT_DAYS = 90  # इतक्या दिवसांत expire होणारा माल पिवळा दिसेल


@app.route("/stock")
def stock():
    q = request.args.get("q", "").strip()
    today = date.today()
    soon = today + timedelta(days=EXPIRY_ALERT_DAYS)

    # product नुसार एकूण विकण्यायोग्य stock (expire न झालेला)
    totals = (
        db.session.query(Product, func.coalesce(func.sum(Batch.qty_available), 0))
        .outerjoin(Batch, and_(Batch.product_id == Product.id,
                               Batch.expiry_date >= today))
        .group_by(Product.id)
        .order_by(Product.name)
    )
    if q:
        totals = totals.filter(Product.name.like(f"%{q}%"))
    totals = totals.all()

    # batch नुसार यादी (आधी expire होणारा वर)
    batches = Batch.query.join(Product).filter(Batch.qty_available > 0)
    if q:
        batches = batches.filter(Product.name.like(f"%{q}%"))
    batches = batches.order_by(Batch.expiry_date).all()

    return render_template("stock.html", totals=totals, batches=batches,
                           today=today, soon=soon, low=LOW_STOCK, q=q)


# ---------- Sales / Billing ----------
def money(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@app.route("/sales")
def sales():
    items = Sale.query.order_by(Sale.invoice_date.desc(), Sale.id.desc()).all()
    return render_template("sales.html", items=items)


@app.route("/sales/<int:sid>")
def sale_detail(sid):
    s = db.get_or_404(Sale, sid)
    return render_template("sale_detail.html", s=s)


@app.route("/sales/new", methods=["GET", "POST"])
def sale_new():
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.order_by(Product.name).all()
    today = date.today()
    avail = dict(
        db.session.query(Batch.product_id, func.sum(Batch.qty_available))
        .filter(Batch.expiry_date >= today)
        .group_by(Batch.product_id).all()
    )
    if request.method == "POST":
        f = request.form
        try:
            invoice_date = datetime.strptime(f["invoice_date"], "%Y-%m-%d").date()
            last_id = db.session.query(func.max(Sale.id)).scalar() or 0
            sale = Sale(
                invoice_no=f"INV-{last_id + 1:05d}",
                customer_id=int(f["customer_id"]),
                invoice_date=invoice_date,
                subtotal=0, gst_total=0, round_off=0, grand_total=0,
            )
            db.session.add(sale)
            db.session.flush()

            subtotal = Decimal("0")
            gst_total = Decimal("0")
            lines = 0
            for prod_id, qty in zip(f.getlist("product_id"), f.getlist("qty")):
                if not prod_id:
                    continue
                need = int(qty)
                if need <= 0:
                    raise ValueError("Quantity must be more than 0")
                product = db.session.get(Product, int(prod_id))
                batches = (
                    Batch.query.filter(
                        Batch.product_id == product.id,
                        Batch.qty_available > 0,
                        Batch.expiry_date >= invoice_date,
                    )
                    .order_by(Batch.expiry_date, Batch.id)
                    .with_for_update()
                    .all()
                )
                if sum(b.qty_available for b in batches) < need:
                    raise ValueError(f"Not enough stock for {product.name}")
                for b in batches:
                    if need == 0:
                        break
                    take = min(need, b.qty_available)
                    taxable = money(b.sale_rate * take)
                    gst = money(taxable * product.gst_percent / 100)
                    b.qty_available -= take
                    need -= take
                    db.session.add(SaleItem(
                        sale_id=sale.id, batch_id=b.id, product_id=product.id,
                        qty=take, rate=b.sale_rate,
                        gst_percent=product.gst_percent,
                        taxable_amount=taxable, gst_amount=gst,
                    ))
                    subtotal += taxable
                    gst_total += gst
                lines += 1
            if lines == 0:
                raise ValueError("Add at least one product row")

            raw = subtotal + gst_total
            grand = raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            sale.subtotal = subtotal
            sale.gst_total = gst_total
            sale.round_off = grand - raw
            sale.grand_total = grand
            db.session.commit()
            flash(f"Invoice {sale.invoice_no} created. Stock updated.")
            return redirect(url_for("sale_detail", sid=sale.id))
        except (ValueError, KeyError, InvalidOperation) as e:
            db.session.rollback()
            flash(f"Could not save: {e}", "error")
    return render_template("sale_form.html", customers=customers,
                           products=products, avail=avail,
                           today=today.isoformat())

# ---------- Payments / Outstanding ----------
@app.route("/payments")
def payments():
    items = Payment.query.order_by(Payment.payment_date.desc(), Payment.id.desc()).all()
    return render_template("payments.html", items=items)


@app.route("/payments/new", methods=["GET", "POST"])
def payment_new():
    customers = Customer.query.order_by(Customer.name).all()
    if request.method == "POST":
        f = request.form
        try:
            amount = Decimal(f["amount"])
            if amount <= 0:
                raise ValueError("Amount must be more than 0")
            p = Payment(
                customer_id=int(f["customer_id"]),
                payment_date=datetime.strptime(f["payment_date"], "%Y-%m-%d").date(),
                amount=amount,
                mode=f["mode"],
                reference=f["reference"].strip(),
            )
            db.session.add(p)
            db.session.commit()
            flash("Payment saved")
            return redirect(url_for("ledger", cid=p.customer_id))
        except (ValueError, KeyError, InvalidOperation) as e:
            db.session.rollback()
            flash(f"Could not save: {e}", "error")
    return render_template("payment_form.html", customers=customers,
                           today=date.today().isoformat(),
                           selected=request.args.get("customer_id", type=int))

@app.route("/outstanding")
def outstanding():
    billed = dict(db.session.query(Sale.customer_id, func.sum(Sale.grand_total))
                  .group_by(Sale.customer_id).all())
    returned = dict(db.session.query(SaleReturn.customer_id, func.sum(SaleReturn.grand_total))
                    .group_by(SaleReturn.customer_id).all())
    paid = dict(db.session.query(Payment.customer_id, func.sum(Payment.amount))
                .group_by(Payment.customer_id).all())
    rows = []
    for c in Customer.query.order_by(Customer.name).all():
        b = billed.get(c.id, Decimal("0")) - returned.get(c.id, Decimal("0"))
        p = paid.get(c.id, Decimal("0"))
        rows.append((c, b, p, b - p))
    rows.sort(key=lambda r: r[3], reverse=True)
    total = sum((r[3] for r in rows), Decimal("0"))
    return render_template("outstanding.html", rows=rows, total=total)

@app.route("/customers/<int:cid>/ledger")
def ledger(cid):
    c = db.get_or_404(Customer, cid)
    entries = []
    for s in Sale.query.filter_by(customer_id=cid):
        entries.append((s.invoice_date, 0, f"Invoice {s.invoice_no}",
                        s.grand_total, Decimal("0")))
    for p in Payment.query.filter_by(customer_id=cid):
        desc = f"Payment ({p.mode})" + (f" - {p.reference}" if p.reference else "")
        entries.append((p.payment_date, 1, desc, Decimal("0"), p.amount))
    for r in SaleReturn.query.filter_by(customer_id=cid):
        entries.append((r.return_date, 2, f"Credit note {r.credit_note_no}",
                        Decimal("0"), r.grand_total))
    entries.sort(key=lambda e: (e[0], e[1]))
    balance = Decimal("0")
    rows = []
    for d, _, desc, debit, credit in entries:
        balance += debit - credit
        rows.append((d, desc, debit, credit, balance))
    return render_template("ledger.html", c=c, rows=rows, balance=balance)

# ---------- Returns ----------
@app.route("/returns")
def returns():
    credit_notes = SaleReturn.query.order_by(
        SaleReturn.return_date.desc(), SaleReturn.id.desc()).all()
    supplier_returns = PurchaseReturn.query.order_by(
        PurchaseReturn.return_date.desc(), PurchaseReturn.id.desc()).all()
    return render_template("returns.html", credit_notes=credit_notes,
                           supplier_returns=supplier_returns)


@app.route("/credit-notes/<int:rid>")
def credit_note(rid):
    r = db.get_or_404(SaleReturn, rid)
    return render_template("credit_note.html", r=r)


@app.route("/sales/<int:sid>/return", methods=["GET", "POST"])
def sale_return(sid):
    sale = db.get_or_404(Sale, sid)
    returned = dict(
        db.session.query(SaleReturnItem.sale_item_id, func.sum(SaleReturnItem.qty))
        .join(SaleReturn, SaleReturn.id == SaleReturnItem.sale_return_id)
        .filter(SaleReturn.sale_id == sid)
        .group_by(SaleReturnItem.sale_item_id).all()
    )
    lines = [(i, int(returned.get(i.id, 0))) for i in sale.items]

    if request.method == "POST":
        f = request.form
        try:
            return_date = datetime.strptime(f["return_date"], "%Y-%m-%d").date()
            restock = f.get("restock") == "yes"
            last_id = db.session.query(func.max(SaleReturn.id)).scalar() or 0
            sr = SaleReturn(
                credit_note_no=f"CN-{last_id + 1:05d}",
                sale_id=sale.id, customer_id=sale.customer_id,
                return_date=return_date, reason=f["reason"].strip(),
                subtotal=0, gst_total=0, round_off=0, grand_total=0,
            )
            db.session.add(sr)
            db.session.flush()

            subtotal = Decimal("0")
            gst_total = Decimal("0")
            count = 0
            for item, already in lines:
                raw = f.get(f"qty_{item.id}", "").strip()
                q = int(raw) if raw else 0
                if q == 0:
                    continue
                if q < 0 or q > item.qty - already:
                    raise ValueError(f"Return qty is too high for {item.product.name}")
                taxable = money(item.rate * q)
                gst = money(taxable * item.gst_percent / 100)
                back = restock and item.batch.expiry_date >= return_date
                if back:
                    item.batch.qty_available += q
                db.session.add(SaleReturnItem(
                    sale_return_id=sr.id, sale_item_id=item.id,
                    batch_id=item.batch_id, product_id=item.product_id,
                    qty=q, rate=item.rate, gst_percent=item.gst_percent,
                    taxable_amount=taxable, gst_amount=gst, restocked=back,
                ))
                subtotal += taxable
                gst_total += gst
                count += 1
            if count == 0:
                raise ValueError("Enter return qty for at least one item")

            raw_total = subtotal + gst_total
            grand = raw_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            sr.subtotal = subtotal
            sr.gst_total = gst_total
            sr.round_off = grand - raw_total
            sr.grand_total = grand
            db.session.commit()
            flash(f"Credit note {sr.credit_note_no} created.")
            return redirect(url_for("credit_note", rid=sr.id))
        except (ValueError, KeyError, InvalidOperation) as e:
            db.session.rollback()
            flash(f"Could not save: {e}", "error")
    return render_template("sale_return_form.html", sale=sale, lines=lines,
                           today=date.today().isoformat())


@app.route("/batches/<int:bid>/return", methods=["GET", "POST"])
def purchase_return_new(bid):
    batch = db.get_or_404(Batch, bid)
    if request.method == "POST":
        try:
            q = int(request.form["qty"])
            if q <= 0 or q > batch.qty_available:
                raise ValueError(f"Qty must be between 1 and {batch.qty_available}")
            db.session.add(PurchaseReturn(
                batch_id=batch.id,
                supplier_id=batch.purchase.supplier_id,
                return_date=datetime.strptime(request.form["return_date"], "%Y-%m-%d").date(),
                qty=q, rate=batch.purchase_rate,
                reason=request.form["reason"],
            ))
            batch.qty_available -= q
            db.session.commit()
            flash("Return to supplier saved. Stock reduced.")
            return redirect(url_for("returns"))
        except (ValueError, KeyError, InvalidOperation) as e:
            db.session.rollback()
            flash(f"Could not save: {e}", "error")
    return render_template("purchase_return_form.html", b=batch,
                           today=date.today().isoformat())

# ---------- Dashboard ----------
@app.route("/dashboard")
def dashboard():
    today = date.today()
    soon = today + timedelta(days=EXPIRY_ALERT_DAYS)
    month_start = today.replace(day=1)

    def net_sales(start, end):
        s = (db.session.query(func.coalesce(func.sum(Sale.grand_total), 0))
             .filter(Sale.invoice_date >= start, Sale.invoice_date <= end).scalar())
        r = (db.session.query(func.coalesce(func.sum(SaleReturn.grand_total), 0))
             .filter(SaleReturn.return_date >= start, SaleReturn.return_date <= end).scalar())
        return s - r

    today_sales = net_sales(today, today)
    month_sales = net_sales(month_start, today)

    # customer नुसार बाकी (उधारी)
    billed = dict(db.session.query(Sale.customer_id, func.sum(Sale.grand_total))
                  .group_by(Sale.customer_id).all())
    returned = dict(db.session.query(SaleReturn.customer_id, func.sum(SaleReturn.grand_total))
                    .group_by(SaleReturn.customer_id).all())
    paid = dict(db.session.query(Payment.customer_id, func.sum(Payment.amount))
                .group_by(Payment.customer_id).all())
    balances = []
    for c in Customer.query.all():
        bal = (billed.get(c.id, Decimal("0")) - returned.get(c.id, Decimal("0"))
               - paid.get(c.id, Decimal("0")))
        if bal > 0:
            balances.append((c, bal))
    balances.sort(key=lambda x: x[1], reverse=True)
    total_outstanding = sum((b for _, b in balances), Decimal("0"))

    # product नुसार उपलब्ध stock (expire न झालेला)
    stock_rows = (
        db.session.query(Product, func.coalesce(func.sum(Batch.qty_available), 0))
        .outerjoin(Batch, and_(Batch.product_id == Product.id,
                               Batch.expiry_date >= today))
        .group_by(Product.id).all()
    )
    low_all = sorted([(p, q) for p, q in stock_rows if q < LOW_STOCK],
                     key=lambda x: x[1])

    expiring_q = Batch.query.filter(Batch.qty_available > 0,
                                    Batch.expiry_date >= today,
                                    Batch.expiry_date <= soon)
    expiring_count = expiring_q.count()
    expiring = expiring_q.order_by(Batch.expiry_date).limit(8).all()

    expired_q = Batch.query.filter(Batch.qty_available > 0, Batch.expiry_date < today)
    expired_count = expired_q.count()
    expired_value = (db.session.query(
        func.coalesce(func.sum(Batch.qty_available * Batch.purchase_rate), 0))
        .filter(Batch.qty_available > 0, Batch.expiry_date < today).scalar())

    recent_sales = Sale.query.order_by(Sale.invoice_date.desc(), Sale.id.desc()).limit(5).all()

    return render_template(
        "dashboard.html", today=today, today_sales=today_sales,
        month_sales=month_sales, total_outstanding=total_outstanding,
        top_due=balances[:5], low_count=len(low_all), low_items=low_all[:8],
        expiring_count=expiring_count, expiring=expiring,
        expired_count=expired_count, expired_value=expired_value,
        recent_sales=recent_sales, low=LOW_STOCK, days=EXPIRY_ALERT_DAYS,
    )

# ---------- Supplier ledger / payables ----------
def supplier_entries(sid):
    entries = []
    for p in Purchase.query.filter_by(supplier_id=sid):
        total = sum(
            (money(b.purchase_rate * b.qty_received * (1 + b.product.gst_percent / 100))
             for b in p.batches), Decimal("0"))
        entries.append((p.bill_date, 0, f"Purchase bill {p.bill_no}",
                        total, Decimal("0")))
    for pay in SupplierPayment.query.filter_by(supplier_id=sid):
        desc = f"Payment ({pay.mode})" + (f" - {pay.reference}" if pay.reference else "")
        entries.append((pay.payment_date, 1, desc, Decimal("0"), pay.amount))
    for r in PurchaseReturn.query.filter_by(supplier_id=sid):
        val = money(r.rate * r.qty * (1 + r.batch.product.gst_percent / 100))
        entries.append((r.return_date, 2,
                        f"Return: {r.batch.product.name} ({r.reason})",
                        Decimal("0"), val))
    entries.sort(key=lambda e: (e[0], e[1]))
    return entries


@app.route("/payables")
def supplier_payables():
    rows = []
    for s in Supplier.query.order_by(Supplier.name).all():
        entries = supplier_entries(s.id)
        bought = sum((e[3] for e in entries), Decimal("0"))
        reduced = sum((e[4] for e in entries), Decimal("0"))
        rows.append((s, bought, reduced, bought - reduced))
    rows.sort(key=lambda r: r[3], reverse=True)
    total = sum((r[3] for r in rows), Decimal("0"))
    return render_template("supplier_payables.html", rows=rows, total=total)


@app.route("/suppliers/<int:sid>/ledger")
def supplier_ledger(sid):
    s = db.get_or_404(Supplier, sid)
    balance = Decimal("0")
    rows = []
    for d, _, desc, add, less in supplier_entries(sid):
        balance += add - less
        rows.append((d, desc, add, less, balance))
    return render_template("supplier_ledger.html", s=s, rows=rows, balance=balance)


@app.route("/supplier-payments")
def supplier_payments():
    items = SupplierPayment.query.order_by(
        SupplierPayment.payment_date.desc(), SupplierPayment.id.desc()).all()
    return render_template("supplier_payments.html", items=items)


@app.route("/supplier-payments/new", methods=["GET", "POST"])
def supplier_payment_new():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    if request.method == "POST":
        f = request.form
        try:
            amount = Decimal(f["amount"])
            if amount <= 0:
                raise ValueError("Amount must be more than 0")
            p = SupplierPayment(
                supplier_id=int(f["supplier_id"]),
                payment_date=datetime.strptime(f["payment_date"], "%Y-%m-%d").date(),
                amount=amount, mode=f["mode"], reference=f["reference"].strip(),
            )
            db.session.add(p)
            db.session.commit()
            flash("Supplier payment saved")
            return redirect(url_for("supplier_ledger", sid=p.supplier_id))
        except (ValueError, KeyError, InvalidOperation) as e:
            db.session.rollback()
            flash(f"Could not save: {e}", "error")
    return render_template("supplier_payment_form.html", suppliers=suppliers,
                           today=date.today().isoformat(),
                           selected=request.args.get("supplier_id", type=int))
# ---------- Reports ----------
def parse_range():
    today = date.today()
    try:
        start = datetime.strptime(request.args.get("from", ""), "%Y-%m-%d").date()
    except ValueError:
        start = today.replace(day=1)
    try:
        end = datetime.strptime(request.args.get("to", ""), "%Y-%m-%d").date()
    except ValueError:
        end = today
    return start, end


GST_KEYS = ["sales_t", "sales_g", "ret_t", "ret_g",
            "pur_t", "pur_g", "pret_t", "pret_g"]


def gst_summary(start, end):
    data = {}

    def add(rate, tkey, gkey, taxable, gst):
        row = data.setdefault(Decimal(rate), {k: Decimal("0") for k in GST_KEYS})
        row[tkey] += taxable
        row[gkey] += gst

    for i in (SaleItem.query.join(Sale)
              .filter(Sale.invoice_date >= start, Sale.invoice_date <= end)):
        add(i.gst_percent, "sales_t", "sales_g", i.taxable_amount, i.gst_amount)

    for i in (SaleReturnItem.query
              .join(SaleReturn, SaleReturn.id == SaleReturnItem.sale_return_id)
              .filter(SaleReturn.return_date >= start, SaleReturn.return_date <= end)):
        add(i.gst_percent, "ret_t", "ret_g", i.taxable_amount, i.gst_amount)

    for b in (Batch.query
              .join(Purchase, Purchase.id == Batch.purchase_id)
              .filter(Purchase.bill_date >= start, Purchase.bill_date <= end)):
        t = money(b.purchase_rate * b.qty_received)
        g = money(t * b.product.gst_percent / 100)
        add(b.product.gst_percent, "pur_t", "pur_g", t, g)

    for r in PurchaseReturn.query.filter(PurchaseReturn.return_date >= start,
                                         PurchaseReturn.return_date <= end):
        t = money(r.rate * r.qty)
        g = money(t * r.batch.product.gst_percent / 100)
        add(r.batch.product.gst_percent, "pret_t", "pret_g", t, g)

    rows = sorted(data.items())
    totals = {k: sum((v[k] for _, v in rows), Decimal("0")) for k in GST_KEYS}
    return rows, totals


def excel_response(filename, sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for title, headers, rows in sheets:
        ws = wb.create_sheet(title[:31])
        ws.append(headers)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append([float(x) if isinstance(x, Decimal) else x for x in r])
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, date):
                    cell.number_format = "DD-MM-YYYY"
                elif isinstance(cell.value, str) and cell.value[:1] in "=+-@":
                    cell.data_type = "s"   # नावातील = वगैरे formula म्हणून चालू नये
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 40)
        ws.freeze_panes = "A2"
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/reports")
def reports():
    start, end = parse_range()
    rows, t = gst_summary(start, end)
    output_gst = t["sales_g"] - t["ret_g"]
    input_gst = t["pur_g"] - t["pret_g"]
    return render_template(
        "reports.html", start=start, end=end, rows=rows, t=t,
        output_gst=output_gst, input_gst=input_gst, net=output_gst - input_gst,
        net_sales=(t["sales_t"] - t["ret_t"]), net_purchases=(t["pur_t"] - t["pret_t"]))


@app.route("/reports/export/<kind>")
def report_export(kind):
    start, end = parse_range()
    tag = f"{start:%d%m%Y}_{end:%d%m%Y}"

    if kind == "sales":
        sales_rows = []
        for s in (Sale.query.filter(Sale.invoice_date >= start, Sale.invoice_date <= end)
                  .order_by(Sale.invoice_date, Sale.id)):
            sales_rows.append([s.invoice_date, s.invoice_no, s.customer.name,
                               s.customer.gstin or "", s.subtotal, s.gst_total,
                               s.round_off, s.grand_total])
        cn_rows = []
        for r in (SaleReturn.query.filter(SaleReturn.return_date >= start,
                                          SaleReturn.return_date <= end)
                  .order_by(SaleReturn.return_date, SaleReturn.id)):
            cn_rows.append([r.return_date, r.credit_note_no, r.sale.invoice_no,
                            r.customer.name, r.customer.gstin or "", r.subtotal,
                            r.gst_total, r.round_off, r.grand_total, r.reason or ""])
        return excel_response(f"sales_{tag}.xlsx", [
            ("Sales", ["Date", "Invoice", "Customer", "GSTIN", "Taxable",
                       "GST", "Round off", "Total"], sales_rows),
            ("Credit notes", ["Date", "Credit note", "Against invoice", "Customer",
                              "GSTIN", "Taxable", "GST", "Round off", "Total",
                              "Reason"], cn_rows),
        ])

    if kind == "purchases":
        rows = []
        for p in (Purchase.query.filter(Purchase.bill_date >= start,
                                        Purchase.bill_date <= end)
                  .order_by(Purchase.bill_date, Purchase.id)):
            taxable = sum((money(b.purchase_rate * b.qty_received) for b in p.batches),
                          Decimal("0"))
            gst = sum((money(money(b.purchase_rate * b.qty_received)
                             * b.product.gst_percent / 100) for b in p.batches),
                      Decimal("0"))
            rows.append([p.bill_date, p.bill_no, p.supplier.name,
                         p.supplier.gstin or "", taxable, gst, taxable + gst])
        ret_rows = []
        for r in (PurchaseReturn.query.filter(PurchaseReturn.return_date >= start,
                                              PurchaseReturn.return_date <= end)
                  .order_by(PurchaseReturn.return_date)):
            t = money(r.rate * r.qty)
            g = money(t * r.batch.product.gst_percent / 100)
            ret_rows.append([r.return_date, r.supplier.name, r.batch.product.name,
                             r.batch.batch_no, r.qty, t, g, t + g, r.reason])
        return excel_response(f"purchases_{tag}.xlsx", [
            ("Purchases", ["Date", "Bill no", "Supplier", "GSTIN", "Taxable",
                           "GST", "Total"], rows),
            ("Supplier returns", ["Date", "Supplier", "Product", "Batch", "Qty",
                                  "Taxable", "GST", "Total", "Reason"], ret_rows),
        ])

    if kind == "stock":
        today = date.today()
        rows = []
        for b in (Batch.query.join(Product).filter(Batch.qty_available > 0)
                  .order_by(Product.name, Batch.expiry_date)):
            rows.append([b.product.name, b.product.company or "", b.product.pack or "",
                         b.batch_no, b.expiry_date, b.qty_available,
                         b.purchase_rate, b.sale_rate,
                         b.purchase_rate * b.qty_available,
                         "Expired" if b.expiry_date < today else ""])
        return excel_response(f"stock_{today:%d%m%Y}.xlsx", [
            ("Stock", ["Product", "Company", "Pack", "Batch", "Expiry", "Qty",
                       "Purchase rate", "Sale rate", "Stock value (purchase)",
                       "Status"], rows),
        ])

    if kind == "gst":
        rows, t = gst_summary(start, end)
        out = [[float(r), v["sales_t"], v["sales_g"], v["ret_t"], v["ret_g"],
                v["pur_t"], v["pur_g"], v["pret_t"], v["pret_g"]] for r, v in rows]
        out.append(["Total", t["sales_t"], t["sales_g"], t["ret_t"], t["ret_g"],
                    t["pur_t"], t["pur_g"], t["pret_t"], t["pret_g"]])
        output_gst = t["sales_g"] - t["ret_g"]
        input_gst = t["pur_g"] - t["pret_g"]
        out += [[], ["Output GST (sales - credit notes)", output_gst],
                ["Input GST (purchases - supplier returns)", input_gst],
                ["Net (output - input)", output_gst - input_gst]]
        return excel_response(f"gst_summary_{tag}.xlsx", [
            ("GST summary", ["GST %", "Sales taxable", "Sales GST", "Credit note taxable",
                             "Credit note GST", "Purchase taxable", "Purchase GST",
                             "Supplier return taxable", "Supplier return GST"], out),
        ])

    if kind == "outstanding":
        billed = dict(db.session.query(Sale.customer_id, func.sum(Sale.grand_total))
                      .group_by(Sale.customer_id).all())
        returned = dict(db.session.query(SaleReturn.customer_id,
                                         func.sum(SaleReturn.grand_total))
                        .group_by(SaleReturn.customer_id).all())
        paid = dict(db.session.query(Payment.customer_id, func.sum(Payment.amount))
                    .group_by(Payment.customer_id).all())
        rows = []
        for c in Customer.query.order_by(Customer.name).all():
            b = billed.get(c.id, Decimal("0")) - returned.get(c.id, Decimal("0"))
            p = paid.get(c.id, Decimal("0"))
            if b or p:
                rows.append([c.name, c.phone or "", b, p, b - p])
        return excel_response(f"outstanding_{date.today():%d%m%Y}.xlsx", [
            ("Outstanding", ["Customer", "Phone", "Billed (after returns)", "Paid",
                             "Outstanding"], rows),
        ])

    flash("Unknown report", "error")
    return redirect(url_for("reports"))

if __name__ == "__main__":
    app.run(debug=True)