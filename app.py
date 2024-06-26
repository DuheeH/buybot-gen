from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import login_required, getTable, randomWait

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Connect SQLite database
db = SQL("sqlite:///buybot.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    user_id = session['user_id']
    if request.method == "POST":
        user_id = session["user_id"]
        urls = request.form.getlist('url')
        date_time = datetime.now()
        
        wd = webdriver.Chrome()
        profile = getTable('profiles')
        profile_columns = ['firstName', 'lastName', 'email', 'address', 'address2', 'city', 'state', 'zip', 'phone']
        card_columns = ['ccName', 'ccNumber', 'ccExpiration', 'ccSecurity']
        
        # The two dicitonaries below can be edited in order for code to work for other websites as well
        xpath_dict = {
            'addCart' : '//*[@id="product-root"]/div/div[2]/div[2]/form/div[2]/div/div[4]/div[2]/div[2]/div[3]/div[1]/input',
            'price' : '//*[@id="product-root"]/div/div[2]/div[2]/form/div[2]/div/div[4]/div[1]/div[2]',
            'checkout' : '//*[@id="product-root"]/div/div[1]/div/div/div/a[2]',
        }
        id_dict = {
            'processPayment': 'checkout-pay-button',
            'firstName': 'TextField0',
            'lastName': 'TextField1',
            'email': 'email',
            'address': 'shipping-address1',
            'address2': 'TextField2',
            'city': 'TextField3',
            'state': 'Select1',
            'zip': 'TextField4',
            'phone': 'TextField5',
            'ccName': 'name',
            'ccNumber': 'number',
            'ccExpiration': 'expiry',
            'ccSecurity': 'verification_value'
        }

        # The for loop below adds the provided urls to the cart and also webscraps the cost of the item and saves it
        prices = []
        for index, url in enumerate(urls):
            wd.get(url)
            # Add items to cart
            wd.find_element(By.XPATH, xpath_dict['addCart']).click()
            # Add price to prices list
            price = (wd.find_element(By.XPATH, xpath_dict['price']).text)
            prices.append(price)
        time.sleep(1.5)

        # Go to checkout
        wd.find_element(By.XPATH, xpath_dict['checkout']).click()
        randomWait()

        # Fill in checkout info, two for loops as results were more consistent
        for column in profile_columns:
            value = str(profile[column])
            id = id_dict[column]
            element = wd.find_element(By.ID, id)
            element.send_keys(value)
        for column in card_columns:
            value = str(profile[column])
            id = id_dict[column]
            element = wd.find_element(By.ID, id)
            element.click()
            element.send_keys(Keys.BACKSPACE * 5 + value)

        # Keep uncommented to double check the autofilled information
        time.sleep(5)

        # Process Payment: CONSIDER THIS THE SAFETY SWITCH OF THE WEBAPP
        # If the line below is not commented out, the payment will be processed
        #wd.find_element(By.XPATH, xpath_dict['processPayment']).click()
        wd.quit

        # Enters the data into the transactions table
        for index, url in enumerate(urls):
            db.execute("""
                INSERT INTO transactions
                (url, price, datetime, user_id)
                VALUES(?,?,?,?)
            """, url, prices[index], date_time, user_id)
        flash("Purchase Successful!")

        # Redirects to table of transactions
        return redirect("/")
    
    # If not submitting form, tests to see whether there is a profile and redirects/renders accordingly
            # Creates table for transactions if not already existing
    profile = getTable('profiles')
    if len(profile)>1:
        return render_template("buy.html")
    flash("| Profile Required Prior to Purchase |")
    return redirect("/profile")

@app.route("/")
@login_required
def index():
    # Will either display the table or redirect to buy, as there are no transactions
    try:
        transactions = getTable('transactions')
    except:
        transactions = []
    if len(transactions)==0:
        flash("| No Transactions | ")
        return redirect("/buy")
    return render_template("index.html",transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Invalid Username/Password", "error")
            return redirect("/login")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Invalid Username/Password", "error")
            return redirect("/login")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            flash("Invalid Username/Password", "error")
            return redirect("/login")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


# registers the user
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if len(username) == 0:
            flash("Invalid Username", "error")
            return redirect("/register")
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username does not already exist
        if len(rows) != 0:
            flash("Invalid Username", "error")
            return redirect("/register")

        # Ensure password exists
        if len(password) == 0:
            flash("Invalid Password", "error")
            return redirect("/register")

        # Ensure password and confirmation match
        if password != confirmation:
            flash("Passwords Must Match", "error")
            return redirect("/register")

        # Input username and password hash into user table in database
        db.execute(
            "INSERT INTO users (username, hash) VALUES(?, ?)",
            username,
            generate_password_hash(password),
        )
        # redirects user to the homepage
        return redirect("/")
    # if GET method, renders the register.html
    return render_template("register.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    if request.method == "POST":
        # Grabs info from the form as a dictionary
        profile = dict(request.form.items())

        # Changing the expiration month/year so that it successfully inputs into the checkout form and database
        profile['ccExpiration'] = profile['ccExpirationM'] + '               ' + profile['ccExpirationY']
        del profile["ccExpirationM"]
        del profile["ccExpirationY"]

        # Tests to see whether there is a profile already for the user logged in
        test = getTable('profiles')
        if not test:
            db.execute("""
                INSERT INTO profiles (user_id)
                VALUES (?)
                """, user_id)
        
        # Adds in the submitted profile info into the database
        for key,value in profile.items():
            db.execute("""
                UPDATE profiles
                SET ?=?
                WHERE user_id=?
                """, key, value, user_id)
        
        # Grabs the most up to date profile info
        profile_recent = getTable('profiles')
        flash("Profile Updated")
        return render_template("profile.html", profile_recent=profile_recent)
    # Renders the profile info with the info in the table if any exists
    profile_recent = getTable('profiles')
    return render_template("profile.html", profile_recent=profile_recent)


@app.route("/changepass", methods=["GET", "POST"])
@login_required
def changepass():
    # Changes password
    if request.method == "POST":
        userid = session["user_id"]
        password = request.form.get("password")
        newpassword = request.form.get("newpassword")
        confirmation = request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE id = ?", userid)
        # Checks previous password
        if len(password) == 0 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid Password", "error")
            return redirect("/changepass")

        # Checks new password
        if len(newpassword) == 0:
            flash("Must Provide New Password", "error")
            return redirect("/changepass")

        # Ensure password and confirmation match
        if newpassword != confirmation:
            flash("New Passwords Must Match", "error")
            return redirect("/changepass")

        # Checks new vs previous password
        if password == newpassword:
            flash("Provide New Password")
            return redirect("/changepass")

        # Update passwords
        db.execute(
            "UPDATE users SET hash=? WHERE id=?",
            generate_password_hash(newpassword),
            userid,
        )
        # redirects user to the homepage
        flash("Password Updated")
        return redirect("/")

    # if GET method, renders the changepass.html
    return render_template("changepass.html")