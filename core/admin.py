from django.contrib import admin
from .models import Post, CompanyDetails


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
	list_display = ("title", "status", "published_at", "created_at")
	list_filter = ("status", "published_at", "created_at")
	search_fields = ("title", "body")
	prepopulated_fields = {"slug": ("title",)}
	date_hierarchy = "published_at"


@admin.register(CompanyDetails)
class CompanyDetailsAdmin(admin.ModelAdmin):
	list_display = ("name", "email", "phone", "vat_number", "updated_at")
	readonly_fields = ("created_at", "updated_at")

	def has_add_permission(self, request):
		# Allow add only if no instance exists
		if CompanyDetails.objects.exists():
			return False
		return super().has_add_permission(request)
