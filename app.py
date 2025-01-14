from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
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

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

    
@app.route("/")
@app.route("/<code>")
def home(code=None):
    if code == "favicon.ico":
        return "", 204  # Respond with no content
    
    r_code=code
    session["g_referral_code"] = None
    session["g_sharing_price"] = 500
    session["g_cart1"] = []
    session["g_total_price"] = 0
    session["g_total"] = 0
    session["g_sharing_people"] = 4
    session["g_code"] = None
    

    
   
    referral = db.referal_code_table.find_one({"code":r_code})
    if referral and referral.get("is_valid", False):
        session['g_referral_code'] = r_code
        session['g_sharing_price'] = referral['sharing_price']
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
       
            
        session['g_referral_code'] = referral_code
        session['g_sharing_price'] = referral['sharing_price']
        
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
    next_url = request.args.get("next", "")  # Get the 'next' parameter if present
    return render_template("login.html", next=next_url)



@app.route("/login1", methods=["POST"])
def login():
    mobile = request.form.get("mobile")
    password = request.form.get("password")
    next_url = request.form.get("next")

    user = db.users.find_one({"mobile_no": mobile})
    if user and user["password"]== password:
        session["user_id"] = user["user_id"]
        flash("Login successful!", "success")
        return redirect(next_url or url_for("home"))
    else:
        flash("Invalid mobile number or password.", "danger")
        return redirect(url_for("login_form"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("g_referral_code", None)
    session.pop("g_sharing_price", None)
    session.pop("g_cart1", None)
    session.pop("g_total_price", None)
    session.pop("g_total", None)
    session.pop("g_sharing_people", None)
    session.pop("g_code", None)
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
        return redirect(url_for("login_form", next=request.url))

    cart_list = db.cart.find({"user_id": session["user_id"]})
    # global g_cart1
    g_cart1=[]
    total_price=0
    for i in cart_list:
        for n in range(0,len(i['items'])):
            g_cart1.append([i['items'][n]['producturl'],i['items'][n]['product_name'],i['items'][n]['price']])
            total_price +=i['items'][n]['price']
    session['g_cart1']=g_cart1
    session['g_total_price'] = total_price
    session['g_total']=session['g_total_price']//(session['g_sharing_people']-1)
    return render_template("cart1.html", cart=g_cart1 ,total_price1=session['g_total_price']//3,total_price=session['g_total_price'] ,share_with_people=4,referral_code=session['g_referral_code'],s_price=session['g_sharing_price'])

@app.route("/cart_summary", methods=["GET", "POST"])
def cart_summary():
    if request.method == "POST":
        
        session['g_sharing_people'] = int(request.form['category'])
        
        session['g_total'] = session['g_total_price'] // (session['g_sharing_people'] - 1)
        return render_template("cart1.html", cart=session['g_cart1'], total_price1=session['g_total'], total_price=session['g_total_price'], share_with_people=session['g_sharing_people'], referral_code=session['g_referral_code'], s_price=session['g_sharing_price'])
    else:
        # Handle GET request if needed
        return redirect(url_for('view_cart2'))

@app.route("/view_cart2", methods=["GET"])
def view_cart2():
    if "user_id" not in session:
        flash("Please log in to view your cart.", "warning")
        return redirect(url_for("login_form",next=request.url))

    cart_list = db.cart.find({"user_id": session["user_id"]})
    
    g_cart1 = []
    total_price = 0
    for i in cart_list:
        for n in range(len(i['items'])):
            g_cart1.append([i['items'][n]['producturl'], i['items'][n]['product_name'], i['items'][n]['price']])
            total_price += i['items'][n]['price']
    session['g_cart1']=g_cart1
    
    session['g_total_price'] = total_price
    session['g_total'] = session['g_total_price'] // (session['g_sharing_people'] - 1)
    return render_template("cart1.html", cart=session['g_cart1'], total_price1=session['g_total_price'] // 3, total_price=session['g_total_price'], share_with_people=4, referral_code=session['g_referral_code'], s_price=session['g_sharing_price'])



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
            "items": session['g_cart1'],
            "total_price": session['g_total_price'],
            'code':session['g_code'],
            'sharing_price':session['g_total'],
            'sharing_people':session['g_sharing_people'],
            "use_code":session['g_referral_code'],
            "minumum_buying_price":session['g_sharing_price'],
            "payment_status": "success",
            "pending":session['g_sharing_people'],
              # Store additional payment details if available
            "order_date": datetime.utcnow()
        }

    
    
    
    db.completed_orders.insert_one(completed_order)
    filter = {"code":session['g_referral_code']}
    document = db.completed_orders.find_one(filter)
    if document:
        # Get the current value of sharing_people
        current_pending = document.get("pending", 0)
        updated_pending = current_pending - 1
        update = {"$set": {"pending": updated_pending}}
        result = db.completed_orders.update_one(filter, update)

    
    
    db.cart.update_one({"user_id":session["user_id"]}, {"$set": {"items": []}})
    
    return render_template("orderplace.html" ,code=session['g_code'],no_of_people=session['g_sharing_people'],sharing_price=session['g_total'],cart=session['g_cart1'])
   
    
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
            "code":session['g_code'],
            
            "cart": session['g_cart1'],
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
             "product_id": session['g_cart1'],
             "code": session['g_code'],
             "sharing_price": session['g_total'],
             "no_of_people": session['g_sharing_people'],
             "original_price": session['g_total_price'],
             "use_code":session['g_referral_code'],
             "is_valid": True})  # Store the referral code in the database

        # Verification successful
        return jsonify({"status": "success"})
    except razorpay.errors.SignatureVerificationError as e:
        # Verification failed
        return jsonify({"status": "failure", "error": str(e)})
    except Exception as e:
        # Handle other exceptions
        return jsonify({"status": "failure", "error": str(e)})
    

@app.route("/proceed_to_checkout")
def proceed_to_checkout():
    if session['g_total']>=session['g_sharing_price'] and session['g_total']>=500:
        try:
            g_code=generate_code()
            session['g_code']=g_code
            # Create Razorpay order
            # Amount in paise (100 paise = 1 INR)
            order_currency = 'INR'
            order_receipt = 'order_rcptid_11'
            payment_order = razorpay_client.order.create({
                'amount':session['g_total']*100,
                'currency': order_currency,
                'receipt': order_receipt,
                'payment_capture': 1
            })
            


            return render_template("checkout.html", cart=session['g_cart1'], total=session['g_total'], sharing_people=session['g_sharing_people'],total_price=session['g_total_price'],key_id=RAZORPAY_KEY_ID,order_id=payment_order['id'],ref_code=session['g_referral_code'])
        except Exception as e:
            logging.error(f"Error in checkout: {e}")
            return "Error in creating order", 500
    elif session['g_total']<session['g_sharing_price']:
        flash(f"your total is less than {session['g_sharing_price']}")
        return render_template("cart1.html",  cart=session['g_cart1'] ,total_price1=session['g_total'],total_price=session['g_total_price'] ,share_with_people=session['g_sharing_people']-1,referral_code=session['g_referral_code'],s_price=session['g_sharing_price'])


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
@app.route("/order", methods=["GET"])
def order():
    if "user_id" not in session:
        flash("Please log in to view your orders.", "warning")
        return redirect(url_for("login_form", next=request.url))
    order1=db.completed_orders.find({"user_id": session["user_id"]})
    profile=db.users.find_one({"user_id": session["user_id"]})
    return render_template("order.html",order1=order1,profile=profile)

@app.route("/order_details/<code>")
def order_details(code):
    order1=db.completed_orders.find_one({"code": code,"user_id": session["user_id"]})
    payment_id=db.address.find_one({"code": code,"user_id": session["user_id"]})
    return render_template("order_details.html",order1=order1,payment_id=payment_id)
@app.route("/tc")
def tc():
    return render_template("tc.html")

@app.route("/reset")
def reset_password():
    return render_template("reset.html")

@app.route('/reset_password',methods=['POST'])
def reset_password1():
    mobile_no = request.form['mobile_no']
    password = request.form['password']
    user = db.users.find_one({"mobile_no": mobile_no})
    if user:
        db.users.update_one({"mobile_no": mobile_no}, {"$set": {"password": password}})
        return render_template("login.html")
    else:
        return render_template("reset.html", message="Mobile number not found. please signup")

if __name__ == "__main__":
    app.run(debug=True)
