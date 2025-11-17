from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta
import uuid
from django.core.mail import send_mail
from django.conf import settings


class ProspectiveClient(models.Model):
	name = models.CharField(max_length=200)
	email = models.EmailField()
	phone = models.CharField(max_length=50, blank=True)
	company = models.CharField(max_length=200, blank=True)

	def __str__(self):
		return self.company or self.name


def _generate_code(prefix: str) -> str:
	return f"{prefix}-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class Quote(models.Model):
	DRAFT = "draft"
	SENT = "sent"
	ACCEPTED = "accepted"
	DECLINED = "declined"
	EXPIRED = "expired"
	STATUS_CHOICES = [
		(DRAFT, "Draft"),
		(SENT, "Sent"),
		(ACCEPTED, "Accepted"),
		(DECLINED, "Declined"),
		(EXPIRED, "Expired"),
	]

	token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	client = models.ForeignKey(ProspectiveClient, null=True, blank=True, on_delete=models.SET_NULL)
	reference = models.CharField(max_length=30, unique=True, blank=True)
	title = models.CharField(max_length=200)
	notes = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
	is_public = models.BooleanField(default=False)
	not_vat_registered = models.BooleanField(default=True)
	valid_until = models.DateField(null=True, blank=True)
	delivery_price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('20.00'))

	# Reservation/lock when someone starts acceptance
	reservation_started_at = models.DateTimeField(null=True, blank=True)
	reservation_session_key = models.CharField(max_length=64, null=True, blank=True)

	RESERVATION_DURATION = 15  # minutes
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.reference} — {self.title}"

	def save(self, *args, **kwargs):
		if not self.reference:
			# Auto-generate reference if missing
			self.reference = _generate_code('Q')
		return super().save(*args, **kwargs)

	@property
	def subtotal(self):
		value = sum((item.total for item in self.items.all()), start=Decimal("0"))
		return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

	@property
	def vat_amount(self):
		# Flat VAT across items using their own rates; compute per-item
		value = sum((item.vat_amount for item in self.items.all()), start=Decimal("0"))
		return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

	@property
	def grand_total(self):
		value = self.subtotal + self.delivery_price + self.vat_amount
		return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

	# Reservation helpers
	@property
	def reservation_expires_at(self):
		if not self.reservation_started_at:
			return None
		return self.reservation_started_at + timedelta(minutes=self.RESERVATION_DURATION)

	@property
	def is_reservation_active(self):
		expires = self.reservation_expires_at
		return bool(expires and timezone.now() < expires)

	@property
	def reservation_seconds_remaining(self):
		if not self.is_reservation_active:
			return 0
		delta = self.reservation_expires_at - timezone.now()
		return max(int(delta.total_seconds()), 0)

	def reserve(self, session_key: str | None):
		self.reservation_started_at = timezone.now()
		self.reservation_session_key = session_key or None
		self.save(update_fields=["reservation_started_at", "reservation_session_key"]) 

	def clear_reservation(self):
		self.reservation_started_at = None
		self.reservation_session_key = None
		self.save(update_fields=["reservation_started_at", "reservation_session_key"]) 


class QuoteItem(models.Model):
	quote = models.ForeignKey(Quote, related_name="items", on_delete=models.CASCADE)
	description = models.CharField(max_length=255)
	quantity = models.PositiveIntegerField(default=1)
	unit_price = models.DecimalField(max_digits=10, decimal_places=2)
	vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # e.g. 20.00 for 20%

	def __str__(self):
		return f"{self.description} (x{self.quantity})"

	@property
	def total(self):
		value = self.quantity * self.unit_price
		return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

	@property
	def vat_amount(self):
		value = (self.total * self.vat_rate) / 100
		return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class QuoteAcceptance(models.Model):
	quote = models.OneToOneField(Quote, related_name="acceptance", on_delete=models.CASCADE)
	accepted_at = models.DateTimeField(auto_now_add=True)
	full_name = models.CharField(max_length=200)
	email = models.EmailField()
	phone = models.CharField(max_length=50)
	company = models.CharField(max_length=200, blank=True)
	address_line1 = models.CharField(max_length=200)
	address_line2 = models.CharField(max_length=200, blank=True)
	city = models.CharField(max_length=100)
	postcode = models.CharField(max_length=20)
	notes = models.TextField(blank=True)

	def __str__(self):
		return f"Acceptance for {self.quote.reference}"


class Invoice(models.Model):
	UNPAID = "unpaid"
	PAID = "paid"
	STATUS_CHOICES = [
		(UNPAID, "Unpaid"),
		(PAID, "Paid"),
	]

	quote = models.OneToOneField(Quote, related_name="invoice", on_delete=models.CASCADE)
	user = models.ForeignKey(User, related_name="invoices", null=True, blank=True, on_delete=models.SET_NULL)
	assigned_to = models.ForeignKey(User, related_name="assigned_invoices", null=True, blank=True, on_delete=models.SET_NULL)
	number = models.CharField(max_length=40, unique=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	client_name = models.CharField(max_length=200, blank=True)
	client_email = models.EmailField(blank=True)
	client_phone = models.CharField(max_length=50, blank=True)
	subtotal = models.DecimalField(max_digits=10, decimal_places=2)
	delivery_price = models.DecimalField(max_digits=8, decimal_places=2)
	vat_amount = models.DecimalField(max_digits=10, decimal_places=2)
	total = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=UNPAID)
	paid_at = models.DateTimeField(null=True, blank=True)

	# Build/fulfillment progress
	items_in_stock_at = models.DateTimeField(null=True, blank=True)
	build_date = models.DateField(null=True, blank=True)
	shipping_date = models.DateField(null=True, blank=True)

	def __str__(self):
		return self.number or f"Invoice for {self.quote.reference}"

	def save(self, *args, **kwargs):
		if not self.number:
			self.number = _generate_code('INV')
		return super().save(*args, **kwargs)

	def mark_paid(self):
		if self.status != self.PAID:
			self.status = self.PAID
			self.paid_at = timezone.now()
			self.save(update_fields=["status", "paid_at"])
			InvoiceEvent.record(self, InvoiceEvent.PAID, f"Payment completed for {self.number}.")

	@classmethod
	def create_from_quote(cls, quote: Quote, user: User | None = None):
		acceptance = getattr(quote, "acceptance", None)
		invoice = cls(
			quote=quote,
			user=user,
			subtotal=quote.subtotal,
			delivery_price=quote.delivery_price,
			vat_amount=quote.vat_amount,
			total=quote.grand_total,
			client_name=getattr(acceptance, "full_name", ""),
			client_email=getattr(acceptance, "email", ""),
			client_phone=getattr(acceptance, "phone", ""),
		)
		invoice.save()
		# Once an invoice exists, ensure the quote is private
		if quote.is_public:
			quote.is_public = False
			quote.save(update_fields=["is_public"])
		return invoice

	# Convenience helpers to advance progress and notify
	def confirm_items_in_stock(self):
		if not self.items_in_stock_at:
			self.items_in_stock_at = timezone.now()
			self.save(update_fields=["items_in_stock_at"])
			InvoiceEvent.record(self, InvoiceEvent.STOCK_OK, "All items confirmed in stock.")

	def schedule_build(self, date):
		self.build_date = date
		self.save(update_fields=["build_date"])
		InvoiceEvent.record(self, InvoiceEvent.BUILD_SCHEDULED, f"Build scheduled for {date}.")

	def schedule_shipping(self, date):
		self.shipping_date = date
		self.save(update_fields=["shipping_date"])
		InvoiceEvent.record(self, InvoiceEvent.SHIP_SCHEDULED, f"Shipping scheduled for {date}.")

	def _notify_customer(self, subject: str, message: str):
		to_email = self.client_email or None
		if to_email:
			send_mail(
				subject=subject,
				message=message,
				from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@localhost'),
				recipient_list=[to_email],
				fail_silently=True,
			)
		# SMS placeholder (implement with Twilio if desired)
		if getattr(settings, 'NOTIFY_SMS_ENABLED', False) and self.client_phone:
			# Integrate SMS provider here
			pass


class InvoiceEvent(models.Model):
	PAID = "paid"
	STOCK_OK = "stock_ok"
	BUILD_SCHEDULED = "build_scheduled"
	SHIP_SCHEDULED = "ship_scheduled"
	TYPE_CHOICES = [
		(PAID, "Paid"),
		(STOCK_OK, "Items in stock"),
		(BUILD_SCHEDULED, "Build scheduled"),
		(SHIP_SCHEDULED, "Shipping scheduled"),
	]

	invoice = models.ForeignKey(Invoice, related_name="events", on_delete=models.CASCADE)
	type = models.CharField(max_length=50, choices=TYPE_CHOICES)
	message = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.type} @ {self.created_at:%Y-%m-%d %H:%M}"

	@classmethod
	def record(cls, invoice: Invoice, event_type: str, message: str = ""):
		event = cls.objects.create(invoice=invoice, type=event_type, message=message)
		# Notify via email for customer-facing milestones
		notify = {
			cls.PAID: "Payment received",
			cls.STOCK_OK: "Items confirmed in stock",
			cls.BUILD_SCHEDULED: "Build scheduled",
			cls.SHIP_SCHEDULED: "Shipping scheduled",
		}.get(event_type)
		if notify:
			invoice._notify_customer(f"{notify} for {invoice.number}", message or notify)
		return event


class InvoicePayment(models.Model):
	PENDING = "pending"
	COMPLETED = "completed"
	FAILED = "failed"
	STATUS_CHOICES = [
		(PENDING, "Pending"),
		(COMPLETED, "Completed"),
		(FAILED, "Failed"),
	]

	invoice = models.ForeignKey(Invoice, related_name="payments", on_delete=models.CASCADE)
	method = models.CharField(max_length=50)  # e.g. 'card', 'bank-transfer', 'paypal'
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
	provider = models.CharField(max_length=50, blank=True)  # gateway identifier
	provider_reference = models.CharField(max_length=100, blank=True)  # external payment id
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Payment {self.id} for {self.invoice.number}"

	def save(self, *args, **kwargs):
		new = self.pk is None
		res = super().save(*args, **kwargs)
		# Auto-mark invoice paid if total of completed payments >= invoice total
		if self.status == self.COMPLETED:
			total_completed = sum(p.amount for p in self.invoice.payments.filter(status=self.COMPLETED))
			if total_completed >= self.invoice.total and self.invoice.status != Invoice.PAID:
				self.invoice.mark_paid()
		return res
