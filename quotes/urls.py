from django.urls import path
from . import views

app_name = "quotes"

urlpatterns = [
    path("<uuid:token>/", views.public_quote_detail, name="public_quote_detail"),
    path("<uuid:token>/accept/", views.public_quote_accept, name="public_quote_accept"),
    path("<uuid:token>/thanks/", views.public_quote_thanks, name="public_quote_thanks"),
    path("invoice/<str:number>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("invoice/<str:number>/mark-paid/", views.invoice_mark_paid, name="invoice_mark_paid"),
    path("invoice/<str:number>/add-payment/", views.invoice_add_payment, name="invoice_add_payment"),
    path("invoice/webhook/", views.invoice_webhook, name="invoice_webhook"),
]
