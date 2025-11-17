from django.db import models
from django.contrib.auth.models import User
import uuid


class EmailVerification(models.Model):
    user = models.ForeignKey(User, related_name="email_verifications", on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Verification for {self.user.username} ({'verified' if self.verified_at else 'pending'})"

    @property
    def is_verified(self):
        return self.verified_at is not None