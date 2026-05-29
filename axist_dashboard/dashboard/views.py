from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import requires_csrf_token
from django.shortcuts import get_object_or_404, redirect, render
import os
import calendar
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer as QBCustomer
from .scripts.sync import sync_customers_from_qb
from .models import Customer, OutreachLog, Item, RentalItem, Rental
from datetime import datetime, timedelta

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

    # updatetime tokens in case they got refreshed
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
    today = datetime.today()
    year  = int(request.GET.get('year',  today.year))
    month = int(request.GET.get('month', today.month))

    # prev/next month nav
    prev = datetime(year, month, 1).replace(day=1)
    prev = (prev.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_m = datetime(year, month, 28) + timedelta(days=4)
    next_m = next_m.replace(day=1)

    # pull all rentals touching this month
    month_start = datetime(year, month, 1)
    month_end   = datetime(year, month, calendar.monthrange(year, month)[1])
    rentals = Rental.objects.filter(
        pickupDate__gte=month_start,
        deliveryDate__lte=month_end
    )

    # build a lookup: datetime -> {deliveries, events, pickups}
    day_map = {}
    for r in rentals:
        for dt, bucket in [
            (r.deliveryDate, 'deliveries'),
            (r.eventDateStart,   'events'),
            (r.eventDateEnd,     'events'),
            (r.pickupDate,   'pickups'),
        ]:
            d = dt.date()
            if d not in day_map:
                day_map[d] = {'deliveries': [], 'events': [], 'pickups': []}
            # avoid dupe event pills for multi-day events
            if r not in day_map[d][bucket]:
                day_map[d][bucket].append(r)

    # build calendar weeks
    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for d in week:
            row.append({
                'date':      d,
                'in_month':  d.month == month,
                'is_today':  d == today,
                'deliveries': day_map.get(d, {}).get('deliveries', []),
                'events':     day_map.get(d, {}).get('events', []),
                'pickups':    day_map.get(d, {}).get('pickups', []),
            })
        weeks.append(row)

    return render(request, 'rentals.html', {
        'calendar_weeks': weeks,
        'month_label':    datetime(year, month, 1).strftime('%B %Y'),
        'day_names':      ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
        'prev_year':      prev.year,   'prev_month': prev.month,
        'next_year':      next_m.year, 'next_month': next_m.month,
    })

def rental_card(request, id):
    rental = get_object_or_404(Rental, pk=id)
    rental_items = RentalItem.objects.filter(rental = rental)
    return render(request, "rental_card.html", {
        "rental" : rental,
        "rental_items" : rental_items,
    })

def rentals_list_view(request):
    today = datetime.today()
    year  = int(request.GET.get('year', today.year))

    year_start = datetime(year, 1, 1)
    year_end   = datetime(year, 12, 31, 23, 59, 59)

    rentals = Rental.objects.prefetch_related('rentalitem_set__item').filter(
        pickupDate__gte=year_start,
        deliveryDate__lte=year_end
    ).order_by('deliveryDate')

    return render(request, 'rentals_list_view.html', {
        'rentals': rentals,
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