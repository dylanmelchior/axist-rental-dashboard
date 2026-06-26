# Django imports
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import requires_csrf_token
from django.shortcuts import get_object_or_404, redirect, render
from .models import Customer, OutreachLog, Rental, RentalItem, Item, Estimate, EstimateItem

# Quickbooks imports
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer as QBCustomer
from quickbooks.objects.base import EmailAddress, PhoneNumber
from quickbooks.objects.estimate import Estimate as QBEstimate
from quickbooks.objects.detailline import SalesItemLine, SalesItemLineDetail
from quickbooks.objects.item import Item as QBItem
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.taxcode import TaxCode

# Utility imports
import os 
import calendar
from decimal import Decimal
from .scripts.sync import sync_customers_from_qb
from .scripts.utils import send_sms
from .scripts.quickbooks_utils import qb_required, get_auth_client
from datetime import datetime, timedelta

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('quickbooks_login')
        else: 
            return render(request, 'login.html', {'error': 'Invalid Credentials'})

    return render(request, 'login.html')
    
@login_required
def quickbooks_login(request):
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

    return redirect("dashboard")

@login_required
def dashboard(request):
    customers = Customer.objects.all()
    items = Item.objects.all()
    return render(request, "dashboard.html", {
        "customers" : customers,
        "items" : items,
        })

@qb_required
@requires_csrf_token
@login_required
def create_customer(request, qb_client=None):
    if request.method == "POST":
        name = request.POST["name"]
        email = request.POST["email"]
        phone = request.POST.get("phone")
        if not phone:
            phone = ""
        
        # Create Customer in Quickbooks
        qb_customer = QBCustomer()
        qb_customer.DisplayName = name

        qb_customer.PrimaryEmailAddr = EmailAddress()
        qb_customer.PrimaryEmailAddr.Address = email

        qb_customer.PrimaryPhone = PhoneNumber()
        qb_customer.PrimaryPhone.FreeFormNumber = phone

        qb_customer.save(qb=qb_client)

        Customer.objects.create(name = name, phone = phone, email = email, qb_id = qb_customer.Id)
        print("New Customer Created")
    return redirect("dashboard")

@login_required
def get_item_data(request, item_id):
    item = Item.objects.get(pk=item_id)
    return JsonResponse({
        'name': item.name,
        'price': item.itemPrice,
        'description': item.itemDescription,
    })

@login_required
def new_customer(request):
    return render(request, "new_customer_form.html")

@qb_required
@requires_csrf_token
@login_required
def update_customer_post(request, customer_id, qb_client = None):
    if request.method == "POST":

        tax_codes = TaxCode.all(qb=qb_client)
        for tc in tax_codes:
            print(tc.Id, tc.Name)
        # Get form input
        customer = Customer.objects.get(pk = customer_id)
        name = request.POST["name"]
        email = request.POST["email"]
        phone = request.POST.get("phone")
        if not phone:
            phone = ""

        # Modify Local Database
        customer.name = name
        customer.email = email
        customer.phone = phone
        customer.save()

        # Modify QB Database
        qb_customer = QBCustomer.get(customer.qb_id, qb=qb_client)
        qb_customer.DisplayName = name

        qb_customer.PrimaryEmailAddr = EmailAddress()
        qb_customer.PrimaryEmailAddr.Address = email

        qb_customer.PrimaryPhone = PhoneNumber()
        qb_customer.PrimaryPhone.FreeFormNumber = phone

        qb_customer.save(qb=qb_client)
    return redirect("dashboard")
    

@login_required
def update_customer_get(request, customer_id):
    customer = Customer.objects.get(pk=customer_id)
    return render(request, "update_customer_form.html", {
        "customer" : customer,
    })

@login_required
def customers(request):
    customers = Customer.objects.all()
    return render(request, "customers.html", {
        "customers" : customers,
    })

@login_required
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

@login_required
def rental_card(request, id):
    rental = get_object_or_404(Rental, pk=id)
    rental_items = RentalItem.objects.filter(rental = rental)
    customer = rental.customer
    return render(request, "rental_card.html", {
        "rental" : rental,
        "rental_items" : rental_items,
        "customer" : customer,
    })

@login_required
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

@login_required
def new_rental(request):
    items = Item.objects.all()
    return render(request, "new_rental_form.html", {
        "items" : items,
        })

@login_required
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

@login_required
def estimates_view(request):
    today = datetime.today()
    year  = int(request.GET.get('year', today.year))

    year_start = datetime(year, 1, 1)
    year_end   = datetime(year, 12, 31, 23, 59, 59)

    estimates = Estimate.objects.prefetch_related('estimateitem_set__item').filter(
        pickupDate__gte=year_start,
        deliveryDate__lte=year_end
    ).order_by('deliveryDate')

    return render(request, 'estimates.html', {
        'estimates': estimates,
    })

@login_required
def estimate_card(request, id):
    estimate = get_object_or_404(Estimate, pk=id)
    estimate_items = EstimateItem.objects.filter(estimate = estimate)
    customer = estimate.customer
    return render(request, "estimate_card.html", {
        "estimate" : estimate,
        "estimate_items" : estimate_items,
        "customer" : customer,
    })

@login_required
def new_estimate_get(request):
    items = Item.objects.all()
    customers = Customer.objects.all()
    return render(request, "new_estimate_form.html", {
        "items": items,
        "customers": customers,
    })

@requires_csrf_token
@qb_required
@login_required
def new_estimate_post(request, qb_client = None):
    if request.method == "POST":
        # Local DB estimate creation
        customer = get_object_or_404(Customer, id = int(request.POST["id"]))
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

        estimate = Estimate.objects.create(
            customer = customer,
            location = location,
            deliveryDate = deliveryDate,
            eventDateStart = eventStart,
            eventDateEnd = eventEnd,
            pickupDate = pickupDate,
            totalPrice = 0,
        )

        # Create all rental items
        i = 0
        totalPrice = 0
        while f"items-{i}-item_id" in request.POST:
            item_id   = request.POST[f"items-{i}-item_id"]
            quantity  = request.POST[f"items-{i}-quantity"]
            unit_price = request.POST[f"items-{i}-unit_price"]

            EstimateItem.objects.create(
                estimate=estimate,
                item=Item.objects.get(pk=item_id),
                quantity=quantity,
            )
            totalPrice += float(unit_price) * int(quantity)
            i += 1
        
        # QB Estimate Creation
        qb_estimate = QBEstimate()
    
        # Attach Customer
        qb_estimate.CustomerRef = QBCustomer.get(estimate.customer.qb_id, qb=qb_client).to_ref()
        qb_estimate.BillEmail = EmailAddress()
        qb_estimate.BillEmail.Address = customer.email

        # Build Line Items
        lines = []
        for estimateItem in estimate.estimateitem_set.all():
            line = SalesItemLine()
            item = estimateItem.item

            line.Amount = Decimal(estimateItem.quantity * item.itemPrice)
            detail = SalesItemLineDetail()
            detail.ItemRef = QBItem.get(item.qb_id, qb=qb_client).to_ref()
            detail.Qty = estimateItem.quantity
            detail.UnitPrice = item.itemPrice
            detail.TaxCodeRef = {"value": "TAX" if item.taxable else "NON"}
        
            line.SalesItemLineDetail = detail
            lines.append(line)

        qb_estimate.Line = lines
        qb_estimate.save(qb=qb_client)

        # store QB id back
        estimate.qb_id = qb_estimate.Id
        estimate.totalPrice = totalPrice
        estimate.save()

    return redirect("estimates_view")

@requires_csrf_token
@qb_required
@login_required
def convert_estimate_to_invoice(request, estimate_id, qb_client = None):
    estimate = Estimate.objects.get(pk=estimate_id)
    customer = estimate.customer
    
    invoice = Invoice()
    invoice.CustomerRef = QBCustomer.get(estimate.customer.qb_id, qb=qb_client).to_ref()
    invoice.BillEmail = EmailAddress()
    invoice.BillEmail.Address = customer.email
    invoice.LinkedTxn = [{"TxnId": estimate.qb_id, "TxnType": "Estimate"}]

    lines = []
    for estimate_item in estimate.estimateitem_set.all():
        line = SalesItemLine()
        item = estimate_item.item
        line.Amount = Decimal(estimate_item.quantity * item.itemPrice)

        detail = SalesItemLineDetail()
        detail.ItemRef = QBItem.get(estimate_item.item.qb_id, qb=qb_client).to_ref()
        detail.Qty = estimate_item.quantity
        detail.UnitPrice = item.itemPrice
        detail.TaxCodeRef = {"value": "TAX" if item.taxable else "NON"}

        line.SalesItemLineDetail = detail
        lines.append(line)

    invoice.Line = lines
    invoice.save(qb=qb_client)

    estimate.invoice_qb_id = invoice.Id
    estimate.save()

    return redirect("estimates_view")

@requires_csrf_token
@qb_required
@login_required
def send_estimate_to_customer(request, estimate_id, qb_client = None):
    if request.method == "POST":
        estimate = get_object_or_404(Estimate, pk = estimate_id)
        qb_estimate = QBEstimate.get(estimate.qb_id, qb=qb_client)
        qb_estimate.send(send_to = estimate.customer.email, qb=qb_client)
    return redirect("estimates_view")

@login_required
def send_out_for_delivery_view(request):
    if request.method == "POST":
        customer_id = request.POST.get('customer_id')
        customer = Customer.objects.get(id = customer_id)
        send_sms(customer.phone, f"Hello {customer.name}, this is an automated message from Axis T. Our delivery crew is on the way to your address. Please be on the lookout for a call when they arrive.")
        return redirect('/rentals/')

def sms_consent_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        customer = Customer.objects.filter(phone=phone).first()
        if customer:
            customer.sms_consent = True
            customer.save()
        return redirect('/consent-confirmed/')
    return render(request, 'sms_consent.html')

def privacy_policy(request):
    return render(request, "privacy.html")

def eula(request):
    return render(request, "eula.html")