import os
import json
from fast_flights import FlightData, Passengers, Result, get_flights
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# JSON file to persist lowest prices
DATA_FILE = "lowest_prices.json"

# Load previous lowest prices
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        lowest_prices = json.load(f)
else:
    lowest_prices = {}

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")


def send_price_drop_email(price_drops):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = "🔥 Flight Price Drop Alert - BLR to UDR"

        body = "Flight Price Drops Detected!\n\n"
        for date, info in price_drops.items():
            body += f"Date: {date}\n"
            body += f"Previous Price: ₹{info['old_price']:,}\n"
            body += f"New Price: ₹{info['new_price']:,}\n"
            body += f"Savings: ₹{info['old_price'] - info['new_price']:,}\n"
            body += "-" * 30 + "\n"

        body += "\nCheck your flight search for more details!"
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()

        print("📧 Price drop email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def check_flights():
    print(f"\n{'='*60}")
    print(f"Flight Search - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Dates to check
    start_date = datetime(2025, 10, 10)
    end_date = datetime(2025, 10, 17)
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end_date-start_date).days + 1)]

    all_flights_data = []

    # Search flights
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
                    price_num = int(flight.price.replace('₹', '').replace(',', ''))
                    all_flights_data.append({
                        'date': date,
                        'departure': flight.departure,
                        'arrival': flight.arrival,
                        'stops': flight.stops,
                        'price': flight.price,
                        'price_num': price_num
                    })
        except Exception as e:
            print(f"Error searching flights for {date}: {e}")

    # Group flights by date and get top 5
    from collections import defaultdict
    flights_by_date = defaultdict(list)
    for flight in all_flights_data:
        flights_by_date[flight['date']].append(flight)

    price_drops_found = False
    email_price_drops = {}

    for date in sorted(flights_by_date.keys()):
        flights = sorted(flights_by_date[date], key=lambda x: x['price_num'])[:5]
        if flights:
            current_lowest = flights[0]['price_num']
            if date not in lowest_prices or current_lowest < lowest_prices[date]:
                if date in lowest_prices:
                    print(f"\n🔥 PRICE DROP ALERT for {date}! 🔥")
                    print(f"Previous lowest: ₹{lowest_prices[date]:,} → New lowest: ₹{current_lowest:,}")
                    price_drops_found = True
                    email_price_drops[date] = {
                        'old_price': lowest_prices[date],
                        'new_price': current_lowest
                    }
                else:
                    print(f"\n📊 Initial price tracking for {date}")
                    price_drops_found = True

                lowest_prices[date] = current_lowest

                print(f"\n--- {date} (Top 5 Cheapest) ---")
                for i, flight in enumerate(flights, 1):
                    print(f"{i}. Dept: {flight['departure']}, Arr: {flight['arrival']}, Stops: {flight['stops']}, Price: {flight['price']}")

    if email_price_drops:
        send_price_drop_email(email_price_drops)

    if not price_drops_found:
        print("\n✅ No price drops found. Current lowest prices maintained.")
        for date, price in sorted(lowest_prices.items()):
            print(f"{date}: ₹{price:,}")

    # Save updated lowest prices
    with open(DATA_FILE, "w") as f:
        json.dump(lowest_prices, f)

    print(f"\nNext scheduled run will continue tracking from saved state.")


if __name__ == "__main__":
    print("🚀 Flight Price Monitor Started!")
    check_flights()
