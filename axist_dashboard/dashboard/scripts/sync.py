from dashboard.models import Customer

def sync_customers_from_qb(customers_json):
    for c in customers_json:
        Customer.objects.update_or_create(
            name=c["name"],
            phone=c["phone"],
            email=c["email"],
            qb_id=c["id"]
        )