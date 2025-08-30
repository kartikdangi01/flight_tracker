import os
import psycopg2
from fast_flights import FlightData, Passengers, Result, get_flights
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# Email config
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# Database config
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Connect to DB
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

# Create table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS lowest_prices (
    date TEXT PRIMARY KEY,
    price INTEGER
)
""")
conn.commit()

def send_price_drop_email(price_drops):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = "🔥 Flight Price Drop Alert - BLR to UDR"
        body = "Flight Price Drops Detected!\n\n"
        for date, info in price_drops.items():
            body += f"Date: {date}\nPrevious Price: ₹{info['old_price']:,}\nNew Price: ₹{info['new_price']:,}\nSavings: ₹{info['old_price'] - info['new_price']:,}\n{'-'*30}\n"
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("📧 Price drop email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def get_lowest_price(date):
    cursor.execute("SELECT price FROM lowest_prices WHERE date=%s", (date,))
    result = cursor.fetchone()
    return result[0] if result else None

def set_lowest_price(date, price):
    cursor.execute("""
    INSERT INTO lowest_prices(date, price) VALUES (%s, %s)
    ON CONFLICT(date) DO UPDATE SET price=EXCLUDED.price
    """, (date, price))
    conn.commit()

def check_flights():
    print(f"\nFlight Search - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start_date = datetime(2025, 10, 10)
    end_date = datetime(2025, 10, 17)
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end_date-start_date).days + 1)]

    all_flights_data = []

    for date in dates:
        try:
            result: Result = get_flights(
                flight_data=[FlightData(date=date, from_airport="BLR", to_airport="UDR")],
                trip="one-way",
                seat="economy",
                passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
                fetch_mode="fallback",
            )
            for flight in result.flights:
                if flight.price != 'Price unavailable':
                    price_str = flight.price.strip()
                    numeric_str = price_str[1:].replace(',', '').strip()
                    price_num = int(numeric_str) * 85
                    all_flights_data.append({
                        'date': date,
                        'price_num': price_num,
                        'departure': flight.departure,
                        'arrival': flight.arrival,
                        'stops': flight.stops,
                        'price': price_num
                    })
        except Exception as e:
            print(f"Error fetching flights for {date}: {e}")

    from collections import defaultdict
    flights_by_date = defaultdict(list)
    for flight in all_flights_data:
        flights_by_date[flight['date']].append(flight)

    email_price_drops = {}

    for date in sorted(flights_by_date.keys()):
        flights = sorted(flights_by_date[date], key=lambda x: x['price_num'])[:5]
        if flights:
            current_lowest = flights[0]['price_num']
            previous_lowest = get_lowest_price(date)

            if previous_lowest is None:
                print(f"📊 Initial tracking for {date}, price: ₹{current_lowest:,}")
            elif current_lowest < previous_lowest:
                print(f"🔥 PRICE DROP for {date}! Old: ₹{previous_lowest:,} → New: ₹{current_lowest:,}")
                email_price_drops[date] = {'old_price': previous_lowest, 'new_price': current_lowest}

            set_lowest_price(date, current_lowest)

    if email_price_drops:
        send_price_drop_email(email_price_drops)

if __name__ == "__main__":
    print("🚀 Flight Price Monitor Started!")
    check_flights()
    cursor.close()
    conn.close()
