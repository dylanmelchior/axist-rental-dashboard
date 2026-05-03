from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name="dashboard"),
    path("login/", views.login, name="login"),
    path("callback/", views.callback, name="callback"),
    path("customers/", views.get_customers, name="get_customers"),
]