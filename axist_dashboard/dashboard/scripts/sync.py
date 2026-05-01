#!/usr/bin/env python
from intuitlib.client import AuthClient
from quickbooks import QuickBooks

import os
from flask import Flask, redirect, request, session, url_for
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "5bc3e82775d10aab0c08794beb8c135a63a011b45805598e36b6711aba79c781")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_DOMAIN"] = "localhost"


# --- Build the auth client ---
def get_auth_client():
    return AuthClient(
        client_id=os.environ["QB_CLIENT_ID"],
        client_secret=os.environ["QB_CLIENT_SECRET"],
        redirect_uri="http://localhost:5000/callback",
        environment="sandbox",  # "production" when live
    )

@app.route("/login")
def login():
    auth_client = get_auth_client()
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    # Don't use session, just let Intuit echo the state back
    return redirect(auth_url)

@app.route("/callback")
def callback():
    auth_client = get_auth_client()

    # Skip the CSRF check for now, add it back properly later
    error = request.args.get("error")
    if error:
        return f"OAuth error: {error}", 400

    auth_code = request.args.get("code")
    realm_id = request.args.get("realmId")

    auth_client.get_bearer_token(auth_code, realm_id=realm_id)

    session["access_token"] = auth_client.access_token
    session["refresh_token"] = auth_client.refresh_token
    session["realm_id"] = realm_id

    return redirect(url_for("get_customers"))

# --- Step 3: Actually use the API ---
@app.route("/customers")
def get_customers():
    if "access_token" not in session:
        return redirect(url_for("login"))

    auth_client = get_auth_client()
    auth_client.access_token = session["access_token"]

    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=session["refresh_token"],
        company_id=session["realm_id"],
        minorversion=75,
    )

    customers = Customer.all(qb=client)

    # Update tokens if they got refreshed under the hood
    session["access_token"] = auth_client.access_token
    session["refresh_token"] = auth_client.refresh_token

    output = [
        {"id": c.Id, "name": c.DisplayName, "email": getattr(c.PrimaryEmailAddr, "Address", None)}
        for c in customers
    ]

    return {"customers": output}

if __name__ == "__main__":
    app.run(debug=True, port=5000)