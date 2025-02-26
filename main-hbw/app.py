from flask import Flask, render_template, jsonify, request, flash, session, url_for
from flask_cors import CORS
import requests

app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app)

# Mock API URLs
HOTEL_API_URL = "https://67aec7a19e85da2f020e563c.mockapi.io/hotels/api/hotels"
FLIGHT_API_URL = "https://67aec7a19e85da2f020e563c.mockapi.io/hotels/api/flights"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/flights")
def flights():
    return render_template("flights.html")

@app.route("/hotels")
def hotels():
    return render_template("hotels.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/signin")
def signin():
    return render_template("signin.html")

@app.route("/contactus")
def contactus():
    return render_template("contactus.html")

@app.route("/feedback_form")
def feedback():
    return render_template("feedback_form.html")

@app.route("/privacypolicy")
def privacy_policy():
    return render_template("privacypolicy.html")

@app.route("/termsandconditions")
def terms_conditions():
    return render_template("termsandconditions.html")

# API Endpoints
@app.route("/api/hotels", methods=["GET"])
def get_hotels():
    try:
        city = request.args.get("city")
        params = {"city": city} if city else {}

        response = requests.get(HOTEL_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if city:
            data = [hotel for hotel in data if hotel.get("city") == city]

        return jsonify(data)
    except requests.RequestException as e:
        return jsonify({"error": f"Error fetching data: {e}"}), 500

@app.route("/flights", methods=["GET"])
def get_flights():
    from_city = request.args.get("from")
    to_city = request.args.get("to")

    # Debug print
    print(f"Received request: from={from_city}, to={to_city}")

    if not from_city or not to_city:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        response = requests.get(FLIGHT_API_URL)  # Fetch from mock API
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch flights"}), 500
        
        flights = response.json()

        # Filter flights based on search
        filtered_flights = [flight for flight in flights if flight["from"] == from_city and flight["to"] == to_city]

        return jsonify(filtered_flights)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
