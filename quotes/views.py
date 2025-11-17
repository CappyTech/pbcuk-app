from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse
from django.contrib import messages
from .models import Quote, QuoteAcceptance, Invoice, InvoicePayment
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from .forms import QuoteAcceptanceForm


def _ensure_session(request):
	if not request.session.session_key:
		request.session.save()
	return request.session.session_key


def _record_visit(request, quote: Quote):
	# Track visited quotes by token in the user's session
	tokens = request.session.get("visited_quote_tokens", [])
	token_str = str(quote.token)
	if token_str not in tokens:
		tokens.append(token_str)
		request.session["visited_quote_tokens"] = tokens


def public_quote_detail(request, token):
	quote = get_object_or_404(Quote, token=token)
	is_expired = quote.valid_until and quote.valid_until < timezone.localdate()
	session_key = _ensure_session(request)
	_record_visit(request, quote)
	context = {
		"quote": quote,
		"items": quote.items.all(),
		"is_expired": is_expired,
		"reservation_active": quote.is_reservation_active,
		"reservation_expires_at": quote.reservation_expires_at,
		"reservation_seconds_remaining": quote.reservation_seconds_remaining,
		"reservation_owned_by_me": bool(quote.reservation_session_key and quote.reservation_session_key == session_key),
	}
	return render(request, "quotes/quote_detail.html", context)


def public_quote_accept(request, token):
	quote = get_object_or_404(Quote, token=token)
	is_expired = quote.valid_until and quote.valid_until < timezone.localdate()
	if is_expired or quote.status in {Quote.ACCEPTED, Quote.DECLINED, Quote.EXPIRED}:
		messages.error(request, "This quote is not available for acceptance.")
		return redirect("quotes:public_quote_detail", token=quote.token)

	session_key = _ensure_session(request)
	_record_visit(request, quote)

	# Visiting the accept page triggers a reservation lock for 15 minutes
	if request.method == "GET":
		if quote.is_reservation_active and quote.reservation_session_key != session_key:
			messages.error(request, "This quote is currently reserved. Please try again soon.")
			return redirect("quotes:public_quote_detail", token=quote.token)
		if not quote.is_reservation_active:
			quote.reserve(session_key)

	if request.method == "POST":
		if not quote.is_reservation_active or quote.reservation_session_key != session_key:
			messages.error(request, "Your reservation expired. Please start acceptance again.")
			return redirect("quotes:public_quote_detail", token=quote.token)
		form = QuoteAcceptanceForm(request.POST)
		if form.is_valid():
			acceptance = form.save(commit=False)
			acceptance.quote = quote
			acceptance.save()
			quote.status = Quote.ACCEPTED
			quote.clear_reservation()
			quote.save(update_fields=["status"])
			if not hasattr(quote, "invoice"):
				user_for_invoice = request.user if request.user.is_authenticated else None
				Invoice.create_from_quote(quote, user=user_for_invoice)
			messages.success(request, "Thank you. Your acceptance has been recorded.")
			return redirect("quotes:public_quote_thanks", token=quote.token)
	else:
		form = QuoteAcceptanceForm()

	return render(request, "quotes/quote_accept.html", {
		"quote": quote,
		"form": form,
		"reservation_active": quote.is_reservation_active,
		"reservation_expires_at": quote.reservation_expires_at,
		"reservation_seconds_remaining": quote.reservation_seconds_remaining,
		"reservation_owned_by_me": bool(quote.reservation_session_key and quote.reservation_session_key == session_key),
		"contact_fields": [form["full_name"], form["email"], form["phone"], form["company"]],
		"address_fields": [form["address_line1"], form["address_line2"], form["city"], form["postcode"]],
	})


def public_quote_thanks(request, token):
	quote = get_object_or_404(Quote, token=token)
	invoice = getattr(quote, "invoice", None)
	return render(request, "quotes/quote_thanks.html", {"quote": quote, "invoice": invoice})


def invoice_pdf(request, number):
	invoice = get_object_or_404(Invoice, number=number)
	try:
		from .pdf import generate_invoice_pdf
	except ImportError:
		return HttpResponse("PDF generation library not installed.", status=501)
	pdf_bytes = generate_invoice_pdf(invoice)
	response = HttpResponse(pdf_bytes, content_type="application/pdf")
	response["Content-Disposition"] = f"inline; filename={invoice.number}.pdf"
	return response


@staff_member_required
@require_POST
def invoice_mark_paid(request, number):
	invoice = get_object_or_404(Invoice, number=number)
	invoice.mark_paid()
	return JsonResponse({"status": "ok", "invoice_status": invoice.status, "paid_at": invoice.paid_at})


@staff_member_required
@require_POST
def invoice_add_payment(request, number):
	invoice = get_object_or_404(Invoice, number=number)
	method = request.POST.get("method", "unspecified")
	amount = request.POST.get("amount")
	provider = request.POST.get("provider", "")
	provider_reference = request.POST.get("provider_reference", "")
	status = request.POST.get("status", InvoicePayment.PENDING)
	from decimal import Decimal
	try:
		amount_decimal = Decimal(amount)
	except Exception:
		return JsonResponse({"error": "Invalid amount"}, status=400)
	payment = InvoicePayment.objects.create(
		invoice=invoice,
		method=method,
		amount=amount_decimal,
		status=status,
		provider=provider,
		provider_reference=provider_reference,
	)
	return JsonResponse({"status": "ok", "payment_id": payment.id, "invoice_status": invoice.status})


@csrf_exempt
@require_POST
def invoice_webhook(request):
	"""External webhook endpoint. Authenticate via X-Webhook-Secret header.

	Expected JSON body keys:
	  invoice_number, method, amount, status (optional), provider, provider_reference
	"""
	secret = request.headers.get("X-Webhook-Secret") or request.META.get("HTTP_X_WEBHOOK_SECRET")
	if not secret or secret != getattr(settings, "PAYMENT_WEBHOOK_SECRET", ""):
		return JsonResponse({"error": "Forbidden"}, status=403)
	import json
	try:
		payload = json.loads(request.body.decode("utf-8"))
	except Exception:
		return JsonResponse({"error": "Invalid JSON"}, status=400)
	invoice_number = payload.get("invoice_number")
	if not invoice_number:
		return JsonResponse({"error": "invoice_number required"}, status=400)
	invoice = get_object_or_404(Invoice, number=invoice_number)
	from decimal import Decimal
	try:
		amount_decimal = Decimal(str(payload.get("amount")))
	except Exception:
		return JsonResponse({"error": "Invalid amount"}, status=400)
	payment = InvoicePayment.objects.create(
		invoice=invoice,
		method=payload.get("method", "unspecified"),
		amount=amount_decimal,
		status=payload.get("status", InvoicePayment.COMPLETED),
		provider=payload.get("provider", "webhook"),
		provider_reference=payload.get("provider_reference", ""),
	)
	return JsonResponse({"status": "ok", "payment_id": payment.id, "invoice_status": invoice.status})

# Create your views here.
