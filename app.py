
import sqlite3
from flask import Flask, redirect, render_template, request, session, send_from_directory
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import atexit
from fpdf import FPDF
import os

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Initialize connection to SQLite database
con = None
try:
    con = sqlite3.connect("invoices.db", check_same_thread=False)
except FileExistsError as e:
    print(e)

cur = con.cursor()

# Close connection to Database on app termination
def exit_handler():
    cur.close()
    con.close()
    print("Connection to invoices.db was closed.")

atexit.register(exit_handler)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
@login_required
def index():

    # Render home page
    if request.method == "GET":

        # Render homepage
        user = cur.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        invoices_count = cur.execute("SELECT COUNT(*) FROM invoices").fetchone()
        print(invoices_count)

        return render_template("home.html", username=user[1], invoices_count=invoices_count[0], active_home=True)

    return render_template("Something went wrong")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get username and password from submitted form
        username, password = request.form.get("username"), request.form.get("password")

        # Ensure username and password were submitted
        if not username or not password:
            return render_template("login.html", blank_credentials=True)

        # Query database for username
        user = cur.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        # Ensure username exists and password is correct
        if user is None or not check_password_hash(user[2], password):
            return render_template("login.html", invalid=True)
        
        # Remember which user has logged in
        session["user_id"] = user[0]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/create-account", methods=["GET", "POST"])
def create_account():
    """Create account"""

    if request.method == "POST":
        
        # Get username and both passwords from submitted form
        username, password, confirm_password = request.form.get("username"), request.form.get("password"), request.form.get("confirm-password")
        
        # Ensure username and password were submitted
        if not username or not password or not confirm_password:
            return render_template("create-account.html", blank_credentials = True)

        # Query database for username
        user = cur.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        # Ensure username doesn't exist already
        if user is not None:
            return render_template("create-account.html", already_exist = True, username = username)

        # Ensure passwords are identical
        if password != confirm_password:
            return render_template("create-account.html", identical = True)

        # Hash the submitted password
        hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (username, hash,))
        
        # Save user to database
        con.commit()

        # Render that the user was successfully created
        return render_template("create-account.html", created=True)
    else:
        # Render template for create account
        return render_template("create-account.html")


@app.route("/create-invoice", methods=["GET", "POST"])
@login_required
def create_invoice():
    """Create invoice"""

    if request.method == "POST":
        
        # Get form data  
        invoice_num, issue_date = request.form.get("invoice-number"), request.form.get("invoice-date")
        company_name, company_website, company_address = request.form.get("company-name"), request.form.get("company-website"), request.form.get("company-address")
        billed_name, billed_address = request.form.get("billed-name"), request.form.get("billed-address")
        descriptions, costs, quantities = request.form.getlist("description"), request.form.getlist("cost"), request.form.getlist("quantity")

        # Save data to invoices.db
        cur.execute("INSERT INTO invoices (invoice_id, invoice_number, company_name, company_address, company_website, billed_company, billed_company_address, issue_date) VALUES(?, ?, ?, ?, ?, ?, ?, ?)", 
                    (session["user_id"], invoice_num, company_name, company_address, company_website, billed_name, billed_address, issue_date,))
        
        for (d, c, q) in zip(descriptions, costs, quantities):
            cur.execute("INSERT INTO products (product_id, description, unit_cost, quantity) VALUES(?, ?, ?, ?)", (invoice_num, d, c, q,)) 
        
        # Save invoice data to database
        con.commit()

        return render_template("create-invoice.html", created=True)
    else:
        return render_template("create-invoice.html", active_create=True)


@app.route("/search-invoice", methods=["GET", "POST"])
@login_required
def search_invoice():
    """Search invoice"""

    # Fetch all invoices from invoices.db
    invoices = cur.execute("SELECT * FROM invoices JOIN users ON users.id = invoices.invoice_id").fetchall()

    if request.method == "POST":

        # Get selected invoice ID for export
        invoice_num = request.form.get('export-number')

        # Get invoice data from invoices.db
        invoice = cur.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_num,)).fetchone()
        invoice_products = cur.execute("SELECT description, unit_cost, quantity FROM products WHERE product_id = ?", (invoice_num,)).fetchall()
        invoice_products.insert(0, ('Description','Unit Cost','Quantity', 'Amount'))

        company_name, company_address, company_website = invoice[2], invoice[3], invoice[4]
        billed_company, billed_address = invoice[5], invoice[6]
        issue_date = invoice[7]
        

        # Create PDF Object
        pdf = FPDF()
        pdf.add_page()
        # Add Image and font
        pdf.image("static/img/invoice-green_97x76.png", x=20, y=10)

        # Invoice ID and Date of issue
        pdf.set_font('Courier', size=14)
        pdf.set_text_color(113, 121, 126) 
        pdf.text(txt=f'Invoice Number: ', x=120, y=43) 
        pdf.text(txt=f'Date of Issue: ', x=120, y=37)
        pdf.set_text_color(0) 
        pdf.set_font(style="B")
        pdf.text(txt=f'#{invoice_num}', x=167, y=43) 
        pdf.text(txt=issue_date, x=167, y=37)

        # Company name, address and website
        pdf.text(txt=company_name, x=20, y=70)
        pdf.set_font('Courier', size=12)
        pdf.text(txt=company_address, x=20, y=82)
        pdf.set_text_color(0,0,255)    
        pdf.text(txt=company_website, x=20, y=88)

        # Billed To
        pdf.set_font('Courier', size=14)
        pdf.set_text_color(113, 121, 126)    
        pdf.text(txt='Billed To', x=120, y=70)
        pdf.set_font('Courier', size=12)
        pdf.set_text_color(0) 
        pdf.text(txt=billed_company, x=120, y=82)
        pdf.text(txt=billed_address, x=120, y=88)

        # Invoice products as table
        pdf.set_margins(left=20, top=110)
        subtotal = 0
        platinum = 229, 228, 226
        with pdf.table(cell_fill_color=platinum, cell_fill_mode='ROWS', text_align='CENTER',) as table:
            for p in invoice_products:
                row = table.row()
                # Add every column from current product
                for i, col in enumerate(p):
                
                    # If column is quantity 
                    if i == 2 and isinstance(col, int):
                        row.cell(str(col))
                        # Calc unit cost * quantity as Amount
                        amount = int(p[i]) * int(p[i-1])
                        row.cell(f'${amount:.2f}')

                        # Calc Subtotal
                        subtotal += amount

                    # If column is Unit Cost -> format .00
                    elif i == 1 and isinstance(col, int):
                        row.cell(f'${col:.2f}')
                    else:
                        row.cell(str(col))

        # Calc table size
        table_size = len(invoice_products) * 10
        # Initialize starting position for Y
        pos_y = 125 + table_size
        # Add page if products are too many
        if table_size > 130:
            pdf.add_page()
            pos_y = 10
            table_size = 0


        # Calculate and add Subtotal, Tax Rate and Tax
        pdf.text(txt='Subtotal ', x=124, y=pos_y)
        pdf.text(txt=f'${subtotal:.2f}', x=164, y=pos_y)

        pdf.text(txt='Tax Rate', x=124, y=pos_y + 9)
        pdf.text(txt='20%', x=164, y=pos_y + 9)

        pdf.text(txt='Tax', x=124, y=pos_y + 18)
        pdf.text(txt=f'${subtotal * 0.2:.2f}', x=164, y=pos_y + 18)

        # Create line separator for total
        pdf.line(124, pos_y + 27, 190, pos_y + 27)

        # Calculate and add Invoice Total
        pdf.set_font(style="B")
        pdf.text(txt='Total', x=124, y=pos_y + 36)
        pdf.text(txt=f'${(subtotal * 0.2) + subtotal:.2f}', x=164, y=pos_y + 36)

        # Write PDF
        pdf.output(f'exported/invoice_{invoice_num}.pdf')


        return render_template("search-invoice.html", exported=True, invoices=invoices, invoice_id=invoice_num)
    else:
        return render_template("search-invoice.html", invoices=invoices)


@app.route("/exported", methods=["GET", "POST"])
@login_required
def show_pdf():
    """Show exported PDF"""

    # Fetch all invoices from invoices.db
    invoices = cur.execute("SELECT * FROM invoices JOIN users ON users.id = invoices.invoice_id").fetchall()

    # Get PDF filename
    file = request.form.get("exported_invoice")
    # If none render invoices table
    if file is None:
        return render_template("search-invoice.html", invoices=invoices)
    # Get current project directory
    workingdir = os.path.abspath(os.getcwd())
    filepath = workingdir + '/exported/'
    return send_from_directory(filepath, file)



@app.route("/edit-invoice", methods=["GET", "POST"])
@login_required
def edit_invoice():
    """Edit or Delete invoice"""

    if request.method == "POST":
        
        # Get user inputted Invoice ID
        invoice_id = request.form.get("invoice-number")

        # Check if edit button is clicked
        if request.form.get("edit") is not None:
            
            
            invoice = cur.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_id,)).fetchone()
            products = cur.execute("SELECT * FROM products WHERE product_id = ?", (invoice_id,)).fetchall()
            
            if invoice is None:
                return render_template("edit-invoice.html", not_found=True, invoice_id=invoice_id)

            return render_template("edit-invoice.html", invoice=invoice, products=products, query=True)

        elif request.form.get("update") is not None:
            print(invoice_id)
            cur.execute("UPDATE invoices SET company_name=?, company_address=?, company_website=?, billed_company=?, billed_company_address=?, issue_date=? WHERE invoice_number=?", 
                    (request.form.get("company-name"), request.form.get("company-address"), request.form.get("company-website"), request.form.get("billed-name"), request.form.get("billed-address"), request.form.get("invoice-date"), invoice_id,))
            
            
            descriptions, costs, quantities = request.form.getlist("description"), request.form.getlist("cost"), request.form.getlist("quantity")
            for (d, c, q) in zip(descriptions, costs, quantities):
                cur.execute("UPDATE products SET description=?, unit_cost=?, quantity=? WHERE product_id=?", (d, c, q, invoice_id,)) 
        
            # Update invoice data
            con.commit()
            
            return render_template("edit-invoice.html", edited=True, invoice_id=invoice_id)
        
        # Check if user confirmed delete invoice
        elif request.form.get("confirm") is not None:
            
            # Delete invoice based on invoice number
            cur.execute("DELETE FROM invoices WHERE invoice_number = ?", (invoice_id,))
            # Delete invoice products
            cur.execute("DELETE FROM products WHERE product_id = ?", (invoice_id,))
            # Update tables
            con.commit()

            return render_template("edit-invoice.html", deleted=True, invoice_id=invoice_id)
        
    else:
        return render_template("edit-invoice.html")