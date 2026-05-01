from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Customer, OutreachLog
# Create your views here.

def dashboard(request):
    customers = Customer.objects.all()
    return render(request, "dashboard.html", {"customers" : customers})