from django.urls import path
from .views import (
    register, UserLoginView, logout_view, profile, verify_email, verify_sent, resend_verification,
    invoices_list, invoice_detail, invoice_payment_methods, pay_invoice, invoice_pay_success, invoice_pay_cancel, stripe_webhook
)

app_name = 'accounts'

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register, name='register'),
    path('profile/', profile, name='profile'),
    path('verify/<uuid:token>/', verify_email, name='verify_email'),
    path('verify-sent/', verify_sent, name='verify_sent'),
    path('resend-verification/', resend_verification, name='resend_verification'),
    path('invoices/', invoices_list, name='invoices'),
    path('invoices/<str:number>/', invoice_detail, name='invoice_detail'),
    path('invoices/<str:number>/payment-methods/', invoice_payment_methods, name='invoice_payment_methods'),
    path('invoices/<str:number>/pay/', pay_invoice, name='invoice_pay'),
    path('invoices/<str:number>/pay/success/', invoice_pay_success, name='invoice_pay_success'),
    path('invoices/<str:number>/pay/cancel/', invoice_pay_cancel, name='invoice_pay_cancel'),
    path('stripe/webhook/', stripe_webhook, name='stripe_webhook'),
]
