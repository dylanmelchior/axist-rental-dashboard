# Axis T Rentals Dashboard

A Django web application for managing customers, estimates, and invoices for Axis T Rentals — an event and game rental company based in Utah.

## Features

- Customer management (create, view, update)
- Estimate creation with line items
- Convert estimates to invoices
- QuickBooks Online integration (sync customers, items, estimates, and invoices)
- SMS notifications via Twilio
- Django authentication with login-protected views

## Tech Stack

- **Backend:** Django
- **Database:** SQLite (dev)
- **Integrations:** QuickBooks Online API, Twilio SMS
- **Auth:** Django built-in auth + QuickBooks OAuth 2.0

## QuickBooks Flow

- OAuth is initiated on login and tokens are stored in the session
- Items are synced from QB using the `/sync-items/` route
- Estimates created on the dashboard are pushed to QB automatically
- Estimates can be converted to invoices and sent to the customer via QB
