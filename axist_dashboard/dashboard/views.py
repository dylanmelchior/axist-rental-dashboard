from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
import os
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer as QBCustomer
from .scripts.sync import sync_customers_from_qb
from .models import Customer, OutreachLog

# Create your views here.

def dashboard(request):
    customers = Customer.objects.all()
    return render(request, "dashboard.html", {"customers" : customers})

def get_auth_client(request):
    return AuthClient(
        client_id=os.environ["QB_CLIENT_ID"],
        client_secret=os.environ["QB_CLIENT_SECRET"],
        redirect_uri="http://localhost:8000/callback",
        environment="sandbox",
        access_token=request.session.get("access_token"),
    )

def login(request):
    auth_client = get_auth_client(request)
    auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
    request.session["state"] = auth_client.state_token
    return redirect(auth_url)

def callback(request):
    auth_client = get_auth_client(request)

    error = request.GET.get("error")
    if error:
        return JsonResponse({"error": error}, status=400)

    auth_code = request.GET.get("code")
    realm_id = request.GET.get("realmId")

    auth_client.get_bearer_token(auth_code, realm_id=realm_id)

    request.session["access_token"] = auth_client.access_token
    request.session["refresh_token"] = auth_client.refresh_token
    request.session["realm_id"] = realm_id

    return redirect("get_customers")

def get_customers(request):
    if "access_token" not in request.session:
        return redirect("login")

    auth_client = get_auth_client(request)

    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=request.session["refresh_token"],
        company_id=request.session["realm_id"],
        minorversion=75,
    )

    qb_customers = QBCustomer.all(qb=client)

    customers_json = [
        {
            "id": c.Id,
            "name": c.DisplayName,
            "email": getattr(c.PrimaryEmailAddr, "Address", None),
            "phone": getattr(c.PrimaryPhone, "FreeFormNumber", None),
        }
        for c in qb_customers
    ]

    sync_customers_from_qb(customers_json)

    # update tokens in case they got refreshed
    request.session["access_token"] = auth_client.access_token
    request.session["refresh_token"] = auth_client.refresh_token

    return JsonResponse({"customers": customers_json})