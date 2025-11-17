from django.db import models
from django.core.exceptions import ValidationError


class Post(models.Model):
	DRAFT = "draft"
	PUBLISHED = "published"
	STATUS_CHOICES = [
		(DRAFT, "Draft"),
		(PUBLISHED, "Published"),
	]

	title = models.CharField(max_length=200)
	slug = models.SlugField(max_length=220, unique=True)
	body = models.TextField()
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
	published_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-published_at", "-created_at"]

	def __str__(self):
		return self.title


class CompanyDetails(models.Model):
	name = models.CharField(max_length=200)
	address_line1 = models.CharField(max_length=200, blank=True)
	address_line2 = models.CharField(max_length=200, blank=True)
	city = models.CharField(max_length=100, blank=True)
	postcode = models.CharField(max_length=20, blank=True)
	country = models.CharField(max_length=100, blank=True)
	email = models.EmailField(blank=True)
	phone = models.CharField(max_length=50, blank=True)
	vat_number = models.CharField(max_length=50, blank=True)
	company_number = models.CharField(max_length=50, blank=True)
	logo_path = models.CharField(max_length=300, blank=True, help_text="Static/absolute path or URL to logo image")
	# Bank transfer details (optional; shown on Payment Methods page)
	bank_name = models.CharField(max_length=200, blank=True)
	account_name = models.CharField(max_length=200, blank=True)
	account_number = models.CharField(max_length=50, blank=True)
	sort_code = models.CharField(max_length=20, blank=True)
	iban = models.CharField(max_length=34, blank=True)
	bic = models.CharField(max_length=11, blank=True)
	updated_at = models.DateTimeField(auto_now=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Company Details"
		verbose_name_plural = "Company Details"

	def clean(self):
		if not self.pk and CompanyDetails.objects.exists():
			raise ValidationError("Only one CompanyDetails instance is permitted.")

	def __str__(self):
		return self.name

	@classmethod
	def get(cls):
		obj = cls.objects.first()
		return obj
