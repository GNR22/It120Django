from django.db import models


class SMSMessage(models.Model):
    """One attempt to send an SMS (successful or not)."""

    class Outcome(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        FAILED = "failed", "Failed"

    recipient = models.CharField(max_length=20)
    body = models.TextField()
    # Did TextBee accept our request? (This is NOT the same as delivery.)
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    provider_sid = models.CharField(max_length=64, blank=True)
    # Latest status reported by TextBee: pending, dispatched, sent, delivered, failed, ...
    provider_status = models.CharField(max_length=30, blank=True)
    error_code = models.CharField(max_length=20, blank=True)
    error_message = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.masked_recipient} ({self.outcome})"

    @property
    def masked_recipient(self):
        """Hide the middle digits so history pages don't expose full numbers."""
        number = self.recipient
        if len(number) < 8:
            return number
        return number[:4] + "*" * (len(number) - 7) + number[-3:]

    @property
    def delivery_label(self):
        """Human-readable status that never over-claims delivery."""
        if self.outcome == self.Outcome.FAILED:
            return "Not sent"
        labels = {
            "delivered": "Delivered (confirmed by TextBee)",
            "undelivered": "Delivery failed",
            "failed": "Delivery failed",
            "sent": "Sent to carrier - delivery not confirmed",
        }
        return labels.get(
            self.provider_status, "Submitted - delivery not yet confirmed"
        )

    @property
    def badge_class(self):
        if self.outcome == self.Outcome.FAILED:
            return "badge-danger"
        if self.provider_status == "delivered":
            return "badge-success"
        if self.provider_status in {"undelivered", "failed"}:
            return "badge-danger"
        return "badge-warning"
