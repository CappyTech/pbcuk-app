from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib.auth.models import Group
from .forms import RegistrationForm, ProfileForm
from django.contrib import messages
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailVerification
from django.utils import timezone
from django.db.models import Q
from quotes.models import Invoice, InvoicePayment
from decimal import Decimal, ROUND_HALF_UP
try:
    from core.models import CompanyDetails
except Exception:
    CompanyDetails = None
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
import stripe
from django.conf import settings

CUSTOMER_GROUP_NAME = 'Customer'

class UserLoginView(LoginView):
    template_name = 'accounts/login.html'

def logout_view(request):
    # Confirmation page on GET; perform logout on POST
    if request.method == 'POST':
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect('/')
    return render(request, 'accounts/logout.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('/')
    next_url = request.GET.get('next') or ''
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = False  # Require email verification
            user.save(update_fields=['is_active'])
            group, _ = Group.objects.get_or_create(name=CUSTOMER_GROUP_NAME)
            user.groups.add(group)
            # Create verification token
            verification = EmailVerification.objects.create(user=user)
            verify_link = request.build_absolute_uri(reverse('accounts:verify_email', args=[str(verification.token)]))
            send_mail(
                subject='Verify your email',
                message=f'Thank you for registering. Please verify your email by visiting: {verify_link}',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@localhost'),
                recipient_list=[user.email],
                fail_silently=True,
            )
            messages.success(request, 'Account created. Please check your email to verify your address.')
            redirect_to = reverse('accounts:verify_sent')
            if next_url:
                redirect_to += f'?next={next_url}'
            return redirect(redirect_to)
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form, 'next': next_url})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


def verify_email(request, token):
    verification = get_object_or_404(EmailVerification, token=token)
    if not verification.is_verified:
        verification.verified_at = timezone.now()
        verification.save(update_fields=['verified_at'])
        user = verification.user
        user.is_active = True
        user.save(update_fields=['is_active'])
        messages.success(request, 'Email verified. You can now log in.')
    else:
        messages.info(request, 'Email already verified.')
    next_url = request.GET.get('next')
    if next_url:
        return redirect(f"{reverse('accounts:login')}?next={next_url}")
    return redirect('accounts:login')


def verify_sent(request):
    return render(request, 'accounts/verify_sent.html', {'next': request.GET.get('next')})


@login_required
def resend_verification(request):
    user = request.user
    if user.is_active:
        messages.info(request, 'Account already verified.')
        return redirect('accounts:profile')
    # Reuse latest pending or create new
    verification = user.email_verifications.filter(verified_at__isnull=True).first()
    if not verification:
        verification = EmailVerification.objects.create(user=user)
    verify_link = request.build_absolute_uri(reverse('accounts:verify_email', args=[str(verification.token)]))
    send_mail(
        subject='Verify your email (resend)',
        message=f'Please verify your email by visiting: {verify_link}',
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@localhost'),
        recipient_list=[user.email],
        fail_silently=True,
    )
    messages.success(request, 'Verification email resent. Check your inbox.')
    return redirect('accounts:verify_sent')


@login_required
def invoices_list(request):
    qs = Invoice.objects.filter(
        Q(user=request.user) | Q(user__isnull=True, client_email__iexact=request.user.email)
    ).order_by('-created_at')
    return render(request, 'accounts/invoices_list.html', {'invoices': qs})


@login_required
def invoice_detail(request, number):
    invoice = get_object_or_404(
        Invoice,
        Q(number=number) & (Q(user=request.user) | Q(user__isnull=True, client_email__iexact=request.user.email))
    )
    payments = invoice.payments.all().order_by('created_at')
    outstanding = invoice.total - sum(p.amount for p in payments.filter(status=InvoicePayment.COMPLETED))
    can_pay = invoice.status != Invoice.PAID and outstanding > 0
    return render(request, 'accounts/invoice_detail.html', {
        'invoice': invoice,
        'payments': payments,
        'outstanding': outstanding,
        'can_pay': can_pay,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    })


def _compute_stripe_fee(amount: Decimal) -> Decimal:
    if amount <= 0:
        return Decimal('0.00')
    percent = Decimal(str(getattr(settings, 'STRIPE_FEE_PERCENT', '2.9')))
    fixed = Decimal(str(getattr(settings, 'STRIPE_FEE_FIXED', '0.20')))
    gross_up = bool(getattr(settings, 'STRIPE_FEE_GROSS_UP', True))
    if gross_up:
        # Solve for gross so that net after fees equals amount
        gross = (amount + fixed) / (Decimal('1.00') - (percent / Decimal('100')))
        fee = (gross - amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        fee = (amount * (percent / Decimal('100')) + fixed).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return max(fee, Decimal('0.00'))


def _get_bank_details():
    details = {
        'bank_name': getattr(settings, 'COMPANY_BANK_NAME', ''),
        'account_name': getattr(settings, 'COMPANY_BANK_ACCOUNT_NAME', ''),
        'account_number': getattr(settings, 'COMPANY_BANK_ACCOUNT_NUMBER', ''),
        'sort_code': getattr(settings, 'COMPANY_BANK_SORT_CODE', ''),
        'iban': getattr(settings, 'COMPANY_BANK_IBAN', ''),
        'bic': getattr(settings, 'COMPANY_BANK_BIC', ''),
    }
    # If CompanyDetails model has bank fields, prefer those
    if CompanyDetails:
        try:
            cd = CompanyDetails.get()
            if cd:
                for k in list(details.keys()):
                    if hasattr(cd, k) and getattr(cd, k):
                        details[k] = getattr(cd, k)
        except Exception:
            pass
    return details


@login_required
def invoice_payment_methods(request, number):
    invoice = get_object_or_404(
        Invoice,
        Q(number=number) & (Q(user=request.user) | Q(user__isnull=True, client_email__iexact=request.user.email))
    )
    payments = invoice.payments.all().order_by('created_at')
    total_completed = sum(p.amount for p in payments.filter(status=InvoicePayment.COMPLETED))
    outstanding = (invoice.total - total_completed)
    stripe_available = bool(settings.STRIPE_PUBLIC_KEY and settings.STRIPE_SECRET_KEY)
    stripe_fee = _compute_stripe_fee(outstanding) if stripe_available and outstanding > 0 else Decimal('0.00')
    card_total = (outstanding + stripe_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    bank = _get_bank_details()
    completed_payments = [p for p in payments if p.status == InvoicePayment.COMPLETED]
    pending_payments = [p for p in payments if p.status == InvoicePayment.PENDING]
    failed_payments = [p for p in payments if p.status == InvoicePayment.FAILED]
    return render(request, 'accounts/invoice_payment_methods.html', {
        'invoice': invoice,
        'outstanding': outstanding,
        'invoice_total': invoice.total,
        'already_paid': total_completed,
        'stripe_available': stripe_available,
        'stripe_fee': stripe_fee,
        'card_total': card_total,
        'bank': bank,
        'stripe_percent': settings.STRIPE_FEE_PERCENT,
        'stripe_fixed': settings.STRIPE_FEE_FIXED,
        'stripe_gross_up': settings.STRIPE_FEE_GROSS_UP,
        'payments': payments,
        'completed_payments': completed_payments,
        'pending_payments': pending_payments,
        'failed_payments': failed_payments,
    })


@login_required
def pay_invoice(request, number):
    invoice = get_object_or_404(
        Invoice,
        Q(number=number) & (Q(user=request.user) | Q(user__isnull=True, client_email__iexact=request.user.email))
    )
    if invoice.status == Invoice.PAID:
        messages.info(request, 'Invoice already paid.')
        return redirect('accounts:invoice_detail', number=invoice.number)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    # Outstanding amount
    total_completed = sum(p.amount for p in invoice.payments.filter(status=InvoicePayment.COMPLETED))
    outstanding = (invoice.total - total_completed)
    if outstanding <= 0:
        messages.info(request, 'Nothing to pay.')
        return redirect('accounts:invoice_detail', number=invoice.number)

    success_url = request.build_absolute_uri(reverse('accounts:invoice_pay_success', args=[invoice.number]))
    cancel_url = request.build_absolute_uri(reverse('accounts:invoice_pay_cancel', args=[invoice.number]))
    # Add Stripe processing fee to charge when using card
    fee = _compute_stripe_fee(outstanding)
    charge_total = (outstanding + fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    line_items = [
        {
            'price_data': {
                'currency': 'gbp',
                'unit_amount': int((outstanding * 100).to_integral_value(rounding=ROUND_HALF_UP)),
                'product_data': {
                    'name': f'Invoice {invoice.number}',
                },
            },
            'quantity': 1,
        }
    ]
    if fee > 0:
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'unit_amount': int((fee * 100).to_integral_value(rounding=ROUND_HALF_UP)),
                'product_data': {
                    'name': 'Card processing fee',
                },
            },
            'quantity': 1,
        })

    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['klarna', 'card', 'afterpay_clearpay',],
        line_items=line_items,
        success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=cancel_url,
        metadata={'invoice_number': invoice.number, 'includes_card_fee': str(fee)},
    )

    # Record pending payment
    InvoicePayment.objects.create(
        invoice=invoice,
        method='card',
        amount=charge_total,
        status=InvoicePayment.PENDING,
        provider='stripe',
        provider_reference=session.id,
    )
    return redirect(session.url)


@login_required
def invoice_pay_success(request, number):
    invoice = get_object_or_404(
        Invoice,
        Q(number=number) & (Q(user=request.user) | Q(user__isnull=True, client_email__iexact=request.user.email))
    )
    session_id = request.GET.get('session_id')
    if session_id and settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                # Mark corresponding payment completed if not already
                payment = invoice.payments.filter(provider_reference=session.id, status=InvoicePayment.PENDING).first()
                if payment:
                    payment.status = InvoicePayment.COMPLETED
                    payment.save(update_fields=['status'])
        except Exception:
            pass
    return render(request, 'accounts/invoice_pay_success.html', {'invoice': invoice})


@login_required
def invoice_pay_cancel(request, number):
    invoice = get_object_or_404(
        Invoice,
        Q(number=number) & (Q(user=request.user) | Q(user__isnull=True, client_email__iexact=request.user.email))
    )
    return render(request, 'accounts/invoice_pay_cancel.html', {'invoice': invoice})


@csrf_exempt
def stripe_webhook(request):
    # Verify signature
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        return HttpResponse(status=200)  # Webhook disabled
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        data = event['data']['object']
        invoice_number = data.get('metadata', {}).get('invoice_number')
        session_id = data.get('id')
        if invoice_number and session_id:
            invoice = Invoice.objects.filter(number=invoice_number).first()
            if invoice:
                payment = invoice.payments.filter(provider_reference=session_id).first()
                if payment and payment.status != InvoicePayment.COMPLETED:
                    payment.status = InvoicePayment.COMPLETED
                    payment.save(update_fields=['status'])
    return HttpResponse(status=200)
