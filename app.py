from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient, ReturnDocument
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime
import razorpay
import base64
import random
import string
from dotenv import load_dotenv
import os
import logging

load_dotenv()
class App:
    def __init__(self):
        self.g_total_price = 0
        self.g_cart1 = []
        self.g_total = 0
        self.g_sharing_people = 4
        self.g_code = None
        self.g_referral_code = None
        self.g_sharing_price = 500

    def get_g_total_price(self):
        return self.g_total_price
    def get_g_cart1(self):
        return self.g_cart1
    def get_g_total(self):
        return self.g_total
    def get_g_sharing_people(self):
        return self.g_sharing_people
    def get_g_code(self):
        return self.g_code
    def get_g_referral_code(self):
        return self.g_referral_code
    def get_g_sharing_price(self):
        return self.g_sharing_price
    

    def set_g_total_price(self, total_price):
        self.g_total_price = total_price
    def set_g_cart1(self, cart1):
        self.g_cart1 = cart1
    def set_g_total(self, total):
        self.g_total = total
    def set_g_sharing_people(self, sharing_people):
        self.g_sharing_people = sharing_people
    def set_g_code(self, code):
        self.g_code = code
    def set_g_referral_code(self, referral_code):
        self.g_referral_code = referral_code
    def set_g_sharing_price(self,sharing_price):
        self.g_sharing_price=sharing_price

    
def generate_code(length=5):
      """Generates a unique code of specified length."""
      code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
      # Ensure uniqueness
      generated_codes = db.referal_code_table.find()
      while True:
        is_duplicate = False
        for existing_code in generated_codes:
          if code == existing_code.get('code'):
            is_duplicate = True
            break
        if not is_duplicate:
          break
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
      
      return code    

app = Flask(__name__)
app.secret_key = "your_secret_key"
# MongoDB connection
url=os.getenv("mongo_url")
client = MongoClient(url)
db = client["clikkart"]
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
v=App()


# Counters collection for user IDs
if not db.counters.find_one({"_id": "user_id"}):
    db.counters.insert_one({"_id": "user_id", "seq": 0})

if not db.counters.find_one({"_id": "p_id"}):
    db.counters.insert_one({"_id": "p_id", "seq": 0})

def get_next_sequence(name):
    counter = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        return_document=ReturnDocument.AFTER
    )
    return counter["seq"]


@app.route("/")
@app.route("/<code>")
def home(code=None):
    referral_code=code
    referral = db.referal_code_table.find_one({"code": referral_code})
    if referral and referral.get("is_valid", False):
        v.set_g_referral_code(referral_code)
        v.set_g_sharing_price(referral['sharing_price']) 
    total_docs = db.product_list.count_documents({})
    products=db.product_list.aggregate([{"$sample": {"size": total_docs}}])
    return render_template("index.html",products=products)

    
@app.route("/check-referral", methods=["POST"])
def check_referral():
    data = request.json
    referral_code = data.get("referral_code")

    if not referral_code:
        return jsonify({"valid": False, "message": "Referral code cannot be empty"}), 400
    check=db.completed_orders.find_one({'code':referral_code})
    if check and check.get("pending")== 0:
        return jsonify({"valid": False, "message": "Invalid referral code."}), 400

    referral = db.referal_code_table.find_one({"code": referral_code})
    if referral and referral.get("is_valid", False):
        
        v.set_g_referral_code(referral_code)
        v.set_g_sharing_price(referral['sharing_price'])
        
        return jsonify({
            "valid": True,
            "message": f"Referral code {referral_code} is valid!",
            "message2": f" your minimun buying price is :{referral['sharing_price']}",
        })
    else:
        return jsonify({"valid": False, "message": "Invalid referral code."}), 400

@app.route("/signup")
def signup_form():
    return render_template("signup.html")


@app.route("/si", methods=["POST"])
def signup():
    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    mobile_no = request.form["mobile_no"]
    password = request.form["password"]

    if db.users.find_one({"mobile_no": mobile_no}):
        return render_template("signup.html", message="Mobile number already exists.")

    user_id = get_next_sequence("user_id")
   
    user = {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "mobile_no": mobile_no,
        "password": password,
    }
    db.users.insert_one(user)
    return render_template("login.html")


@app.route("/login", methods=["GET"])
def login_form():
    next_url = request.args.get("next")  # Get the 'next' parameter if present
    return render_template("login.html", next=next_url)



@app.route("/login1", methods=["POST"])
def login():
    mobile = request.form.get("mobile")
    password = request.form.get("password")

    user = db.users.find_one({"mobile_no": mobile})
    if user and user["password"]== password:
        session["user_id"] = user["user_id"]
        flash("Login successful!", "success")
        return redirect(url_for("home"))
    else:
        flash("Invalid mobile number or password.", "danger")
        return redirect(url_for("login_form"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))


@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Please log in to add items to the cart."}), 401

    data = request.get_json()
    producturl = data.get("producturl")
    product_name = data.get("productName")
    price = data.get("price")

    if product_name and price:
        db.cart.update_one(
            {"user_id": session["user_id"]},
            {"$push": {"items": {"producturl":producturl, "product_name": product_name, "price": price}}},
            upsert=True
        )
            
        
        
        return jsonify({"status": "success", "message": f"{product_name} added to cart successfully!"}), 200
    else:
        return jsonify({"status": "error", "message": "Invalid product details."}), 400


@app.route("/cart", methods=["GET"])
def view_cart():
    if "user_id" not in session:
        flash("Please log in to view your cart.", "warning")
        return redirect(url_for("login_form", next = request.url))

    cart_list = db.cart.find({"user_id": session["user_id"]})
    
    g_cart1=[]
    total_price=0
    for i in cart_list:
        for n in range(0,len(i['items'])):
            g_cart1.append([i['items'][n]['producturl'],i['items'][n]['product_name'],i['items'][n]['price']])
            total_price +=i['items'][n]['price']
    v.set_g_cart1(g_cart1)
    # global g_total_price,g_sharing_people,g_total
    g_total_price = total_price
    v.set_g_total_price(g_total_price)
    v.set_g_total(g_total_price//(v.get_g_sharing_people()-1))
    return render_template("cart1.html", cart=v.get_g_cart1() ,total_price1=v.get_g_total_price()//3,total_price=v.get_g_total_price() ,share_with_people=4,referral_code=v.get_g_referral_code(),s_price=v.get_g_sharing_price())

@app.route("/cart_summary", methods=["GET", "POST"])
def cart_summary():
    if request.method == "POST":
        # global g_sharing_people
        v.set_g_sharing_people(int(request.form['category']))
        # global g_total_price, g_total, g_cart1
        v.set_g_total(v.get_g_total_price() // (v.get_g_sharing_people() - 1))
        return render_template("cart1.html", cart=v.get_g_cart1(), total_price1=v.get_g_total(), total_price=v.get_g_total_price(), share_with_people=v.get_g_sharing_people(), referral_code=v.get_g_referral_code(), s_price=v.get_g_sharing_price())
    else:
        # Handle GET request if needed
        return redirect(url_for('view_cart2'))

@app.route("/view_cart2", methods=["GET"])
def view_cart2():
    if "user_id" not in session:
        flash("Please log in to view your cart.", "warning")
        return redirect(url_for("login_form",next=request.url))

    cart_list = db.cart.find({"user_id": session["user_id"]})
    # global g_cart1
    g_cart1 = []
    total_price = 0
    for i in cart_list:
        for n in range(len(i['items'])):
            g_cart1.append([i['items'][n]['producturl'], i['items'][n]['product_name'], i['items'][n]['price']])
            total_price += i['items'][n]['price']
    # global g_total_price, g_sharing_people, g_total
    v.set_g_total_price(total_price)
    v.set_g_total(v.get_g_total_price() // (v.get_g_sharing_people() - 1)) 
    return render_template("cart1.html", cart=g_cart1, total_price1=v.get_g_total_price() // 3, total_price=v.get_g_total_price(), share_with_people=4, referral_code=v.get_g_referral_code(), s_price=v.get_g_sharing_price())



@app.route("/remove-item", methods=["POST"])
def remove_item():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Please log in."}), 401

    data = request.get_json()
    product_name = data.get("product_name")
    user_id = session["user_id"]

    # Remove the item from the user's cart
    db.cart.update_one(
        {"user_id": user_id},
        {"$pull": {"items": {"product_name": product_name}}}
    )

    return jsonify({"status": "success", "message": "Item removed successfully."}), 200


@app.route("/checkout")
def checkout():
    completed_order = {
            "user_id": session["user_id"],
            "items": v.get_g_cart1(),
            "total_price": v.get_g_total_price(),
            'code':v.get_g_code(),
            'sharing_price':v.get_g_total(),
            'sharing_people':v.get_g_sharing_people(),
            "use_code":v.get_g_referral_code(),
            "minumum_buying_price":v.get_g_sharing_price(),
            "payment_status": "success",
            "pending":v.get_g_sharing_people(),
              # Store additional payment details if available
            "order_date": datetime.utcnow()
        }

    
    
    
    db.completed_orders.insert_one(completed_order)
    filter = {"code":v.get_g_referral_code()}
    document = db.completed_orders.find_one(filter)
    if document:
        # Get the current value of sharing_people
        current_pending = document.get("pending", 0)
        updated_pending = current_pending - 1
        update = {"$set": {"pending": updated_pending}}
        result = db.completed_orders.update_one(filter, update)

    
    
    db.cart.update_one({"user_id":session["user_id"]}, {"$set": {"items": []}})
    
    return render_template("orderplace.html" ,code=v.get_g_code(),no_of_people=v.get_g_sharing_people(),sharing_price=v.get_g_total(),cart=v.get_g_cart1())
   
    
@app.route('/payment/callback', methods=['POST'])   
def payment_callback():
    """Verify Razorpay payment."""
    try:
        data = request.json
       
        payment_id = data['payment_id']
        order_id = data['order_id']
        signature = data['signature']
        fname=data['first_name']
        lname=data['last_name']
        email=data['email']
        mobile=data['mobile']
        address1=data['address1']
        address2=data['address2']
        city=data['city']
        state=data['state']
        zip=data['zip']

        # Verify payment signature
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)

         # Store user and payment details in MongoDB
        
        payment_data = {
            "user_id": session["user_id"],
            "code":g_code,
            
            "cart": v.get_g_cart1(),
            "payment_id": payment_id,
            "order_id": order_id,
            "first_name": fname,
            "last_name": lname,
            "email": email,
            "mobile": mobile,
            "address1": address1,
            "address2": address2,
            "city": city,
            "state": state,
            "zip": zip,
            "status": "success"
        }
        db.address.insert_one(payment_data)
        db.referal_code_table.insert_one({
             "profile_id": session["user_id"],
             "product_id": v.get_g_cart1(),
             "code": v.get_g_code(),
             "sharing_price": v.get_g_total(),
             "no_of_people": v.get_g_sharing_people(),
             "original_price": v.get_g_total_price(),
             "use_code":v.get_g_referral_code(),
             "is_valid": True})  # Store the referral code in the database

        # Verification successful
        return jsonify({"status": "success"})
    except razorpay.errors.SignatureVerificationError as e:
        # Verification failed
        return jsonify({"status": "failure", "error": str(e)})
    except Exception as e:
        # Handle other exceptions
        return jsonify({"status": "failure", "error": str(e)})
    

    
    
    


     

        # Empty the user's cart
    

    # return jsonify({"status": "success", "message": "Payment successful. Order placed!","code":code,"no_of_people":g_sharing_people,"sharing_price":g_total,"oder":g_cart1}), 200
    


# @app.route("/pay-now", methods=["POST"])
# def pay_now():
#     if "user_id" not in session:
#         flash("Please log in to proceed with payment.", "warning")
#         return redirect(url_for("login_form"))

#     # Clear the cart after payment
#     db.cart.delete_many({"user_id": session["user_id"]})
#     flash("Payment successful! Your cart has been cleared.", "success")
#     return redirect(url_for("home"))

@app.route("/proceed_to_checkout")
def proceed_to_checkout():
    # global g_cart1,g_sharing_people,g_total_price,g_total
    if v.get_g_total()>=v.get_g_sharing_price() and v.get_g_total()>=500:
        try:
            global g_code
            g_code=generate_code()
            v.set_g_code(g_code)
            # Create Razorpay order
            # Amount in paise (100 paise = 1 INR)
            order_currency = 'INR'
            order_receipt = 'order_rcptid_11'
            payment_order = razorpay_client.order.create({
                'amount':2*100,
                'currency': order_currency,
                'receipt': order_receipt,
                'payment_capture': 1
            })
            return render_template("checkout.html", cart=v.get_g_cart1(), total=v.get_g_total(), sharing_people=v.get_g_sharing_people(),total_price=v.get_g_total_price(),key_id=RAZORPAY_KEY_ID,order_id=payment_order['id'])
        except Exception as e:
            logging.error(f"Error in checkout: {e}")
            return "Error in creating order", 500
    elif v.get_g_total() < v.get_g_sharing_price():
        flash(f"your total is less than {session['g_sharing_price']}")
        return render_template("cart1.html",  cart=v.get_g_cart1() ,total_price1=v.get_g_total(),total_price=v.get_g_total_price() ,share_with_people=v.get_g_sharing_people()-1,referral_code=v.get_g_referral_code(),s_price=v.get_g_sharing_price())


# @app.route("/success", methods=["POST"])
# def success():
#     payment_id = request.form["razorpay_payment_id"]
#     order_id = request.form["razorpay_order_id"]
#     signature = request.form["razorpay_signature"]

#     # Verify the payment signature
#     try:
#         razorpay_client.utility.verify_payment_signature({
#             "razorpay_order_id": order_id,
#             "razorpay_payment_id": payment_id,
#             "razorpay_signature": signature
#         })
#         db.payment_collection.insert_one({
            
#             "payment_id": payment_id,
#             "order_id": order_id,
#             "signature": signature,
#             "status": "success"
#         })
#         code=generate_code()  # Generate a unique referral code
#         db.referal_code_table.insert_one({
#             "profile_id": session["user_id"],
#             "product_id": g_cart1,
#             "code": code,
#             "sharing_price": g_sharing_price,
#             "no_of_people": g_sharing_people,
#             "original_price": g_total_price,
#             "is_valid": True})  # Store the referral code in the database
#         db.billing_table.insert_one({
#             "profile_id": session["user_id"],
#             "product_id": g_cart1,
#             "total_price": g_total_price,
#             "sharing_price": g_sharing_price,
#             "no_of_people": g_sharing_people,
#             "order_id": order_id,
#             "payment_id": payment_id,
#             "signature": signature,
#             "code": code,
#             })  # Store the billing details in the database

#          # Clear the cart after successful payment
#         return render_template("success.html", payment_id=payment_id,code=code)
#     except razorpay.errors.SignatureVerificationError:
#         return "Payment verification failed!", 400
@app.route("/order")
def order():
    if "user_id" not in session:
        flash("Please log in to view your orders.", "warning")
        return redirect(url_for("login_form"))
    order1=db.completed_orders.find({"user_id": session["user_id"]})
    profile=db.users.find_one({"user_id": session["user_id"]})
    return render_template("order.html",order1=order1,profile=profile)

@app.route("/order_details/<code>")
def order_details(code):
    order1=db.completed_orders.find_one({"code": code,"user_id": session["user_id"]})
    return render_template("order_details.html",order1=order1)


if __name__ == "__main__":
    app.run(debug=True)
