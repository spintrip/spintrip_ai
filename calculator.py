import os
import sqlite3
from flask import Flask, request, render_template, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Database setup
DATABASE = 'bookings.db'

def init_db():
    """Initialize the SQLite database and update schema if necessary."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Create table for storing booking details with delivery field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT UNIQUE,
            user_amount REAL,
            host_amount REAL,
            platform_profit REAL,
            insurance REAL,
            gst REAL,
            delivery TEXT DEFAULT 'No'
        )
    ''')
    # Ensure delivery column exists
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'delivery' not in columns:
        cursor.execute("ALTER TABLE bookings ADD COLUMN delivery TEXT DEFAULT 'No'")
    conn.commit()
    conn.close()

def save_to_db(booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery):
    """Save booking details to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO bookings (booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery))
        conn.commit()
        return {"message": "Data saved successfully!"}
    except sqlite3.IntegrityError:
        return {"error": "Booking ID already exists. Please use a unique Booking ID."}
    finally:
        conn.close()

def update_db(booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery):
    """Update booking details in the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE bookings
            SET user_amount = ?, host_amount = ?, platform_profit = ?, insurance = ?, gst = ?, delivery = ?
            WHERE booking_id = ?
        ''', (user_amount, host_amount, platform_profit, insurance, gst, delivery, booking_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {"error": "No booking found with the provided Booking ID."}
        return {"message": "Data updated successfully!"}
    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()

def fetch_all_data():
    """Fetch all saved booking details from the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery FROM bookings')
    rows = cursor.fetchall()
    conn.close()
    return rows

def calculate_totals():
    """Calculate total platform profit, total host amount, total insurance amount, total sales, profit percentage, and EBITDA."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(platform_profit), SUM(host_amount), SUM(insurance), SUM(user_amount) FROM bookings')
    total_profit, total_host_amount, total_insurance, total_sales = cursor.fetchone()
    conn.close()

    # Ensure values are not None
    total_profit = total_profit or 0
    total_sales = total_sales or 0
    total_host_amount = total_host_amount or 0
    total_insurance = total_insurance or 0
    
    # Calculate profit percentage
    profit_percentage = (total_profit / total_sales * 100) if total_sales > 0 else 0

    # Calculate EBITDA
    ebitda = total_profit + total_insurance  # Adjust this calculation based on your specific EBITDA definition

    # Calculate EBITDA percentage
    ebitda_percentage = (ebitda / total_sales * 100) if total_sales > 0 else 0

    return {
        'total_profit': total_profit,
        'total_host_amount': total_host_amount,
        'total_insurance': total_insurance,
        'total_sales': total_sales,
        'profit_percentage': round(profit_percentage, 2),
        'ebitda': round(ebitda, 2),
        'ebitda_percentage': round(ebitda_percentage, 2)  # Add EBITDA percentage
    }


@app.route('/')
def index():
    data = fetch_all_data()
    totals = calculate_totals()  # Calculate totals
    return render_template('index.html', bookings=data, totals=totals)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    user_amount = data.get('user_amount', 0)  # Default to 0 if not provided
    host_amount = data.get('host_amount', 0)
    platform_profit = data.get('platform_profit', 0)
    delivery_charge = 800 if data.get('delivery') else 0
    gst_rate = 0.18
    insurance_rate = 0.14
    insurance = 0
    gst = 0

    try:
        # Adjust the user amount by subtracting the delivery charge if applicable
        adjusted_user_amount = user_amount - delivery_charge if user_amount is not None else 0

        # Ensure all values sum up correctly
        if adjusted_user_amount is not None and host_amount is not None:
            platform_profit = adjusted_user_amount - host_amount
            gst = platform_profit * gst_rate
            insurance = (host_amount + platform_profit) * insurance_rate
            platform_profit = adjusted_user_amount - host_amount - gst - insurance

        elif adjusted_user_amount is not None and platform_profit is not None:
            host_amount = adjusted_user_amount - platform_profit
            gst = platform_profit * gst_rate
            insurance = (host_amount + platform_profit) * insurance_rate
            platform_profit = adjusted_user_amount - host_amount - gst - insurance

        elif host_amount is not None and platform_profit is not None:
            adjusted_user_amount = host_amount + platform_profit
            user_amount = adjusted_user_amount + delivery_charge
            gst = platform_profit * gst_rate
            insurance = (host_amount + platform_profit) * insurance_rate
            platform_profit = adjusted_user_amount - host_amount - gst - insurance

        else:
            return jsonify({"error": "Please provide any two values."}), 400

        return jsonify({
            "user_amount": round(user_amount or 0, 2),  # Default to 0 if None
            "host_amount": round(host_amount or 0, 2),
            "platform_profit": round(platform_profit or 0, 2),
            "insurance": round(insurance or 0, 2),
            "gst": round(gst or 0, 2)
        })

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid input values. Please enter numerical values."}), 400

@app.route('/save', methods=['POST'])
def save_data():
    data = request.json
    booking_id = data.get('booking_id')
    user_amount = data.get('user_amount', 0)
    host_amount = data.get('host_amount', 0)
    platform_profit = data.get('platform_profit', 0)
    insurance = data.get('insurance', 0)
    gst = data.get('gst', 0)
    delivery = 'Yes' if data.get('delivery') else 'No'

    response = save_to_db(booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery)
    return jsonify(response)

def balance_payments():
    """Balance all payments in the database to ensure net funds equal zero."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_amount, host_amount, platform_profit, insurance, gst, delivery FROM bookings')
    rows = cursor.fetchall()

    for row in rows:
        id, user_amount, host_amount, platform_profit, insurance, gst, delivery = row
        delivery_charge = 800 if delivery == 'Yes' else 0
        adjusted_user_amount = user_amount - delivery_charge

        # Recalculate platform profit
        platform_profit = adjusted_user_amount - (host_amount + insurance + gst)

        # Update the record with balanced values
        cursor.execute('''
            UPDATE bookings
            SET platform_profit = ?
            WHERE id = ?
        ''', (round(platform_profit, 2), id))

    conn.commit()
    conn.close()
    return {"message": "All payments balanced successfully!"}
@app.route('/update', methods=['POST'])
def update_data():
    data = request.json
    booking_id = data.get('booking_id')
    user_amount = data.get('user_amount', 0)
    host_amount = data.get('host_amount', 0)
    platform_profit = data.get('platform_profit', 0)
    insurance = data.get('insurance', 0)
    gst = data.get('gst', 0)
    delivery = 'Yes' if data.get('delivery') else 'No'

    response = update_db(booking_id, user_amount, host_amount, platform_profit, insurance, gst, delivery)
    return jsonify(response)

@app.route('/balance', methods=['POST'])
def balance_data():
    response = balance_payments()
    return jsonify(response)

if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(debug=True, threaded=True)
