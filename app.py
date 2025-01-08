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

load_dotenv()
class admin:
    def __init(self):
        self.url = "mongodb+srv://vishal:12345@sharemart.qwglm.mongodb.net/?retryWrites=true&w=majority&appName=sharemart"
        self.client = MongoClient(url)
        self.db = client["clikkart"]
        
    def admin_login(self,userid,password):
        login=db.adminlogin.find_one()
        if login['userid']==userid and login['password']==password:
            return True
        else:
            return False
    
        
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
v=admin()
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

g_referral_code = None
g_sharing_price = 500
g_total_price = 0
g_cart1=[]
g_total=0
g_sharing_people=4

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
def home():
    products=db.product_list.find()
    return render_template("index.html",products=products)

@app.route('/adminlogin')
def adminpage():
    return render_template('adminlogin.html')

@app.route('/adminpanel',methods=['POST'])
def adminvsk():
    userid1= request.form["userid"]
    password1= request.form["password"]
    if v.admin_login(userid1,password1)==True:
        return render_template('/adminpanel.html')
    else:
        return False
@app.route('/product_add',methods=['POST'])
def product_add():
    p_name=request.form['product_name']
    p_url=request.form['image_url']
    p_price=request.form['price']
    p_cat=request.form['category']
    p_id = get_next_sequence("p_id")
    db.product_list.insert_one({'product_id':p_id,
                                'product_name':p_name,
                                'product_url':p_url,
                                'product_price':p_price,
                                'product_cat':p_cat})
    flash("product add succefully",'danger')
    return render_template('adminpanel.html')

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
        return jsonify({"status": "error", "message": "Mobile number already registered."})

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


@app.route("/login")
def login_form():
    return render_template("login.html")


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
        return redirect(url_for("login_form"))

    cart_list = db.cart.find({"user_id": session["user_id"]})
    global g_cart1
    g_cart1=[]
    total_price=0
    for i in cart_list:
        for n in range(0,len(i['items'])):
            g_cart1.append([i['items'][n]['producturl'],i['items'][n]['product_name'],i['items'][n]['price']])
            total_price +=i['items'][n]['price']
    global g_total_price,g_sharing_people,g_total
    g_total_price = total_price
    g_total=g_total_price//(g_sharing_people-1)
    return render_template("cart1.html", cart=g_cart1 ,total_price1=g_total_price//3,total_price=g_total_price ,share_with_people=4,referral_code=g_referral_code,s_price=g_sharing_price)

@app.route("/cart_summary", methods=["GET", "POST"])
def cart_summary():
    if request.method == "POST":
        global g_sharing_people
        g_sharing_people = int(request.form['category'])
        global g_total_price, g_sharing_price, g_referral_code, g_total, g_cart1
        g_total = g_total_price // (g_sharing_people - 1)
        return render_template("cart1.html", cart=g_cart1, total_price1=g_total, total_price=g_total_price, share_with_people=g_sharing_people, referral_code=g_referral_code, s_price=g_sharing_price)
    else:
        # Handle GET request if needed
        return redirect(url_for('view_cart2'))

@app.route("/view_cart2", methods=["GET"])
def view_cart2():
    if "user_id" not in session:
        flash("Please log in to view your cart.", "warning")
        return redirect(url_for("login_form"))

    cart_list = db.cart.find({"user_id": session["user_id"]})
    global g_cart1
    g_cart1 = []
    total_price = 0
    for i in cart_list:
        for n in range(len(i['items'])):
            g_cart1.append([i['items'][n]['producturl'], i['items'][n]['product_name'], i['items'][n]['price']])
            total_price += i['items'][n]['price']
    global g_total_price, g_sharing_people, g_total
    g_total_price = total_price
    g_total = g_total_price // (g_sharing_people - 1)
    return render_template("cart1.html", cart=g_cart1, total_price1=g_total_price // 3, total_price=g_total_price, share_with_people=4, referral_code=g_referral_code, s_price=g_sharing_price)



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


@app.route("/checkout", methods=["POST"])
def checkout():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Please log in to complete the payment."}), 401
    fname=request.form['fname']
    lname=request.form['lname']
    email=request.form['email']
    mobile=request.form['mobile']
    address1=request.form['address1']
    address2=request.form['address2']
    city=request.form['city']
    state=request.form['state']
    zip=request.form['zip']

    # Mock payment verification logic (replace with actual payment gateway integration)
    # Retrieve the cart items for the user
    user_id = session["user_id"]
    user_cart = db.cart.find_one({"user_id": user_id})

    if not user_cart or not user_cart.get("items"):
        return jsonify({"status": "error", "message": "Cart is empty. Add items to checkout."}), 400

    # Move cart items to the completed_orders collection
    code=generate_code()  # Generate a unique referral code
    
    completed_order = {
            "user_id": user_id,
            "items": g_cart1,
            "total_price": g_total_price,
            'code':code,
            'sharing_price':g_total,
            'sharing_people':g_sharing_people,
            "use_code":g_referral_code,
            "minumum_buying_price":g_sharing_price,
            "payment_status": "success",
            "pending":g_sharing_people,
              # Store additional payment details if available
            "order_date": datetime.utcnow()
        }
    
    db.completed_orders.insert_one(completed_order)

    filter = {"code":g_referral_code}
    document = db.completed_orders.find_one(filter)
    if document:
        # Get the current value of sharing_people
        current_pending = document.get("pending", 0)
        updated_pending = current_pending - 1
        update = {"$set": {"pending": updated_pending}}
        result = db.completed_orders.update_one(filter, update)


    db.referal_code_table.insert_one({
             "profile_id": session["user_id"],
             "product_id": g_cart1,
             "code": code,
             "sharing_price": g_total,
             "no_of_people": g_sharing_people,
             "original_price": g_total_price,
             "use_code":g_referral_code,
             "is_valid": True}) 

        # Empty the user's cart
    db.cart.update_one({"user_id": user_id}, {"$set": {"items": []}})
    db.address.insert_one({
        
        "user_id":user_id,
        "code":code,
        "cart":g_cart1,
        "fname":fname,
        "lname":lname,
        "email":email,
        "mobile":mobile,
        "address1":address1,
        "address2":address2,
        "city":city,
        "state":state,
        "zip":zip
    })

    # return jsonify({"status": "success", "message": "Payment successful. Order placed!","code":code,"no_of_people":g_sharing_people,"sharing_price":g_total,"oder":g_cart1}), 200
    return render_template("orderplace.html" ,code=code,no_of_people=g_sharing_people,sharing_price=g_total,cart=g_cart1)


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
        global g_referral_code, g_sharing_price
        g_referral_code = referral_code
        g_sharing_price = referral['sharing_price']
        
        return jsonify({
            "valid": True,
            "message": f"Referral code {g_referral_code} is valid!",
            "message2": f" your minimun buying price is :{g_sharing_price}",
        })
    else:
        return jsonify({"valid": False, "message": "Invalid referral code."}), 400


@app.route("/pay-now", methods=["POST"])
def pay_now():
    if "user_id" not in session:
        flash("Please log in to proceed with payment.", "warning")
        return redirect(url_for("login_form"))

    # Clear the cart after payment
    db.cart.delete_many({"user_id": session["user_id"]})
    flash("Payment successful! Your cart has been cleared.", "success")
    return redirect(url_for("home"))

@app.route("/proceed_to_checkout")
def proceed_to_checkout():
    global g_sharing_price,g_cart1,g_sharing_people,g_total_price,g_total
    if g_total>=g_sharing_price and g_total>=500:
        return render_template("checkout.html", cart=g_cart1, total=g_total, sharing_people=g_sharing_people,total_price=g_total_price,key_id=RAZORPAY_KEY_ID)
    elif g_total<g_sharing_price:
        flash(f"your total is less than {g_sharing_price}")
        return render_template("cart1.html",  cart=g_cart1 ,total_price1=g_total,total_price=g_total_price ,share_with_people=g_sharing_people-1,referral_code=g_referral_code,s_price=g_sharing_price)


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
    return render_template("order.html",order1=order1)

if __name__ == "__main__":
    app.run(debug=True)
