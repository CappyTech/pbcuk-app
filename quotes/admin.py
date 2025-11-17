from django.contrib import admin
from django.utils.html import format_html
from .models import ProspectiveClient, Quote, QuoteItem, QuoteAcceptance, Invoice, InvoicePayment, InvoiceEvent


@admin.register(ProspectiveClient)
class ProspectiveClientAdmin(admin.ModelAdmin):
	list_display = ("name", "company", "email", "phone")
	search_fields = ("name", "company", "email")


class QuoteItemInline(admin.TabularInline):
	model = QuoteItem
	extra = 1


def _format_mmss(seconds: int) -> str:
    try:
        m, s = divmod(max(int(seconds), 0), 60)
        return f"{m:02}:{s:02}"
    except Exception:
        return "00:00"

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
	list_display = ("reference", "title", "status", "delivery_display", "not_vat_registered", "is_public", "created_at", "valid_until", "reservation_badge")
	list_filter = ("status", "not_vat_registered", "is_public", "created_at", "valid_until")
	search_fields = ("reference", "title", "notes")
	inlines = [QuoteItemInline]
	readonly_fields = ("subtotal", "delivery_price", "vat_amount", "grand_total")
	actions = ("release_reservation",)

	@admin.action(description="Release reservation (clear lock)")
	def release_reservation(self, request, queryset):
		count = 0
		for quote in queryset:
			if quote.reservation_started_at or quote.reservation_session_key:
				quote.clear_reservation()
				count += 1
		self.message_user(request, f"Released reservation on {count} quote(s).")

	def reservation_badge(self, obj):
		if obj.is_reservation_active:
			return format_html(
				'<span class="admin-badge reserved" data-expires="{}">Reserved · {}</span>',
				obj.reservation_expires_at.isoformat(),
				_format_mmss(obj.reservation_seconds_remaining),
			)
		return ""
	reservation_badge.short_description = "Reservation"

	class Media:
		js = ("countdown.js",)

	def delivery_display(self, obj):
		return format_html(
			'<span title="The £20 delivery fee includes:&#10;• Heavy-duty protective packaging&#10;• Internal foam bracing to protect components&#10;• Full tracking and signature&#10;• Front-door courier service&#10;• Insurance for loss or damage&#10;• Specialist handling of fragile PC systems">Secure Insured Delivery — £{}</span>',
			obj.delivery_price,
		)
	delivery_display.short_description = "Delivery"


@admin.register(QuoteAcceptance)
class QuoteAcceptanceAdmin(admin.ModelAdmin):
	list_display = ("quote", "accepted_at", "full_name", "email")
	search_fields = ("quote__reference", "full_name", "email")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
	list_display = ("number", "quote", "client_name", "client_email", "total", "status", "assigned_to", "created_at", "paid_at")
	search_fields = ("number", "quote__reference", "client_name", "client_email", "assigned_to__username", "assigned_to__first_name", "assigned_to__last_name")
	list_filter = ("status", "created_at", "paid_at", "assigned_to")
	readonly_fields = ("quote", "number", "subtotal", "delivery_price", "vat_amount", "total", "client_name", "client_email", "created_at", "paid_at")
	actions = ("mark_as_paid", "confirm_items_in_stock_now", "mark_bank_transfer_received",)

	@admin.action(description="Mark selected invoices paid")
	def mark_as_paid(self, request, queryset):
		count = 0
		for inv in queryset:
			if inv.status != Invoice.PAID:
				inv.mark_paid()
				count += 1
		self.message_user(request, f"Marked {count} invoice(s) as paid.")

	class PaymentInline(admin.TabularInline):
		model = InvoicePayment
		extra = 0

	class EventInline(admin.TabularInline):
		model = InvoiceEvent
		extra = 0
		readonly_fields = ("created_at",)
		can_delete = False

	inlines = [PaymentInline, EventInline]

	@admin.action(description="Confirm items in stock (now)")
	def confirm_items_in_stock_now(self, request, queryset):
		count = 0
		for inv in queryset:
			prev = inv.items_in_stock_at
			inv.confirm_items_in_stock()
			if inv.items_in_stock_at and inv.items_in_stock_at != prev:
				count += 1
		self.message_user(request, f"Confirmed items in stock on {count} invoice(s).")

	@admin.action(description="Mark bank transfer received (full outstanding)")
	def mark_bank_transfer_received(self, request, queryset):
		from decimal import Decimal
		count = 0
		for inv in queryset:
			if inv.status == Invoice.PAID:
				continue
			# Calculate outstanding based on completed payments
			total_completed = sum((p.amount for p in inv.payments.filter(status=InvoicePayment.COMPLETED)), start=Decimal('0'))
			outstanding = inv.total - total_completed
			if outstanding <= 0:
				continue
			InvoicePayment.objects.create(
				invoice=inv,
				method='bank-transfer',
				amount=outstanding,
				status=InvoicePayment.COMPLETED,
				provider='bank-transfer',
				provider_reference=f'BANK-{inv.number}',
			)
			count += 1
		self.message_user(request, f"Recorded bank transfer on {count} invoice(s).")


@admin.register(InvoiceEvent)
class InvoiceEventAdmin(admin.ModelAdmin):
	list_display = ("invoice", "type", "message", "created_at")
	list_filter = ("type", "created_at")
	search_fields = ("invoice__number", "message")
	readonly_fields = ("invoice", "type", "message", "created_at")
