from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/dashboard", methods=["POST"])
def dashboard():
    email = request.form.get("email")
    password = request.form.get("password")

    strength = check_password_strength(password)
    risk_score = calculate_risk_score(strength)

    breached = is_email_breached(email)
    if breached:
        risk_score += 20
    


    return render_template(
    "dashboard.html",
    email=email,
    level=strength,
    score=risk_score,
    breached=breached
)



def check_password_strength(password):
    score = 0

    if len(password) >= 8:
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in "!@#$%^&*()" for c in password):
        score += 1

    if score <= 2:
        return "Weak"
    elif score <= 4:
        return "Medium"
    else:
        return "Strong"


def calculate_risk_score(password_strength):
    if password_strength == "Weak":
        return 80
    elif password_strength == "Medium":
        return 50
    else:
        return 20

import csv

def is_email_breached(email):
    try:
        with open("data/breached_emails.csv", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)  # skip header
            for row in reader:
                if row and row[0].strip().lower() == email.strip().lower():
                    return True
    except FileNotFoundError:
        print("CSV file not found!")
    return False



if __name__ == "__main__":
    app.run(debug=True)
