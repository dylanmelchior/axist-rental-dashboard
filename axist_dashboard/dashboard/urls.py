from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name="dashboard"),
    path("login/", views.login, name="login"),
    path("callback/", views.callback, name="callback"),
    path("customers/", views.get_customers, name="get_customers"),
    path("createcustomer/", views.create_customer, name="create_customer"),
    path("createrental/", views.create_rental, name = "create_rental"),
    path('item/<int:item_id>/', views.get_item_data, name='get_item_data'),
    path("newcustomer/", views.newcustomer, name="newcustomer"),
]