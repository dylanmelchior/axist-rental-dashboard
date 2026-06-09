import os
from functools import wraps
from intuitlib.client import AuthClient
from quickbooks import QuickBooks
from django.shortcuts import redirect

def get_auth_client(request):
    return AuthClient(
        client_id=os.environ["QB_CLIENT_ID"],
        client_secret=os.environ["QB_CLIENT_SECRET"],
        redirect_uri="http://localhost:8000/callback",
        environment="sandbox",
        access_token=request.session.get("access_token"),
    )

def get_qb_client(request):
    auth_client = get_auth_client(request)
    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=request.session["refresh_token"],
        company_id=request.session["realm_id"],
        minorversion=75,
    )
    return auth_client, client

def qb_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if "access_token" not in request.session:
            return redirect("quickbooks_login")
        
        auth_client, qb_client = get_qb_client(request)
        
        try:
            response = view_func(request, *args, qb_client=qb_client, **kwargs)
        finally:
            # always persist potentially-refreshed tokens
            request.session["access_token"] = auth_client.access_token
            request.session["refresh_token"] = auth_client.refresh_token
        
        return response
    return wrapper