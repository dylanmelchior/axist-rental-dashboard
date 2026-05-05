from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import requires_csrf_token
from django.shortcuts import get_object_or_404, redirect, render
import os
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer as QBCustomer
from .scripts.sync import sync_customers_from_qb
from .models import Customer, OutreachLog, Item, RentalItem, Rental

# Create your views here.

def dashboard(request):
    customers = Customer.objects.all()
    items = Item.objects.all()
    return render(request, "dashboard.html", {
        "customers" : customers,
        "items" : items,
        })

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

    return redirect("dashboard")

@requires_csrf_token
def create_customer(request):
    if request.method == "POST":
        name = request.POST["name"]
        email = request.POST["email"]
        phone = request.POST.get("phone")
        if not phone:
            phone = ""
        qbID = request.POST["qbID"]
        Customer.objects.create(name = name, phone = phone, email = email, qb_id = qbID)
        print("New Customer Created")
    customers = Customer.objects.all()
    items = Item.objects.all()
    return redirect("dashboard")


def get_item_data(request, item_id):
    item = Item.objects.get(pk=item_id)
    return JsonResponse({
        'name': item.name,
        'price': item.itemPrice,
        'description': item.itemDescription,
    })

def new_customer(request):
    return render(request, "new_customer_form.html")

def customers(request):
    customers = Customer.objects.all()
    return render(request, "customers.html", {
        "customers" : customers,
    })

def rentals(request):
    rentals = Rental.objects.all()
    return render(request, "rentals.html", {
        "rentals": rentals,
    })

def rental_card(request, id):
    rental = get_object_or_404(Rental, pk=id)
    rental_items = RentalItem.objects.filter(rental = rental)
    return render(request, "rental_card.html", {
        "rental" : rental,
        "rental_items" : rental_items,
    })

def new_rental(request):
    items = Item.objects.all()
    return render(request, "new_rental_form.html", {
        "items" : items,
        })

@requires_csrf_token
def create_rental(request):
    if request.method == "POST":
        customer = get_object_or_404(Customer, qb_id = int(request.POST["qbID"]))
        location = request.POST["location"]

        deliveryDate = request.POST.get("deliveryDate")
        if not deliveryDate:
            deliveryDate = "TBD"

        eventStart = request.POST.get("eventStart")
        if not eventStart:
            eventStart = "TBD"

        eventEnd = request.POST.get("eventEnd")
        if not eventEnd:
            eventEnd = "TBD"

        pickupDate = request.POST.get("pickupDate")
        if not pickupDate:
            pickupDate = "TBD"

        rental = Rental.objects.create(
            customer = customer,
            location = location,
            deliveryDate = deliveryDate,
            eventDateStart = eventStart,
            eventDateEnd = eventEnd,
            pickupDate = pickupDate,
            totalPrice = 0
        )

        # Create all rental items
        i = 0
        totalPrice = 0
        while f"items-{i}-item_id" in request.POST:
            item_id   = request.POST[f"items-{i}-item_id"]
            quantity  = request.POST[f"items-{i}-quantity"]
            unit_price = request.POST[f"items-{i}-unit_price"]

            RentalItem.objects.create(
                rental=rental,
                item=Item.objects.get(pk=item_id),
                quantity=quantity,
            )
            totalPrice += float(unit_price) * int(quantity)
            i += 1

        rental.totalPrice = totalPrice
        rental.save()
    return redirect("rentals")