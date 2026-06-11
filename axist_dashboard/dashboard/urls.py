from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name = "login_view"),
    path("qb-login/", views.quickbooks_login, name="quickbooks_login"),
    path("callback/", views.callback, name="callback"),
    path('item/<int:item_id>/', views.get_item_data, name='get_item_data'),
    path("customers/", views.customers, name="customers"),
    path("customers/<int:customer_id>/update", views.update_customer_get, name = "update_customer_get"),
    path("customers/<int:customer_id>/update-post", views.update_customer_post, name = "update_customer_post"),
    path("newcustomer/", views.new_customer, name="new_customer"),
    path("createcustomer/", views.create_customer, name="create_customer"),
    path("rentals/", views.rentals, name="rentals"),
    path("rentals/list_view", views.rentals_list_view, name="rentals_list_view"),
    path("rentals/<int:id>", views.rental_card, name="rental_card"),
    path("newrental/", views.new_rental, name="new_rental"),
    path("createrental/", views.create_rental, name = "create_rental"),
    path("estimates/",views.estimates_view, name = "estimates_view"),
    path("estimates/<int:id>", views.estimate_card, name="estimate_card"),
    path("estimates/new/", views.new_estimate_get, name="new_estimate_get"),
    path("estimates/new-post", views.new_estimate_post, name="new_estimate_post"),
    path("estimates/<int:estimate_id>/convert-to-invoice", views.convert_estimate_to_invoice, name="convert_estimate_to_invoice"),
    path("send-out-for-delivery/", views.send_out_for_delivery_view, name="send_out_for_delivery"),
    path("sms-consent/", views.sms_consent_view, name = "sms_consent"),
]