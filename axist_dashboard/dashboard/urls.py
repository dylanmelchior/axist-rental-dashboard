from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("qb-login/", views.quickbooks_login, name="quickbooks_login"),
    path("callback/", views.callback, name="callback"),
    path("createrental/", views.create_rental, name = "create_rental"),
    path('item/<int:item_id>/', views.get_item_data, name='get_item_data'),
    path("newcustomer/", views.new_customer, name="new_customer"),
    path("newrental/", views.new_rental, name="new_rental"),
    path("customers/", views.customers, name="customers"),
    path("createcustomer/", views.create_customer, name="create_customer"),
    path("customers/<int:customer_id>/update", views.update_customer_get, name = "update_customer_get"),
    path("customers/<int:customer_id>/update-post", views.update_customer_post, name = "update_customer_post"),
    path("rentals/", views.rentals, name="rentals"),
    path("rentals/list_view", views.rentals_list_view, name="rentals_list_view"),
    path("rentals/<int:id>", views.rental_card, name="rental_card"),
    path("send-out-for-delivery/", views.send_out_for_delivery_view, name="send_out_for_delivery"),
    path("sms-consent/", views.sms_consent_view, name = "sms_consent"),
    path("login/", views.login_view, name = "login_view")
]