from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SMSForm
from .models import SMSMessage
from .services import SMSError, fetch_status, send_sms


def _daily_limit_reached():
    today = timezone.localdate()
    sent_today = SMSMessage.objects.filter(
        outcome=SMSMessage.Outcome.SUBMITTED, created_at__date=today
    ).count()
    return sent_today >= settings.SMS_DAILY_LIMIT


def send_view(request):
    """Show the SMS form (GET) and process it (POST)."""
    if request.method == "POST":
        form = SMSForm(request.POST)
        if form.is_valid():
            to = form.cleaned_data["phone_number"]
            body = form.cleaned_data["message"]

            if _daily_limit_reached():
                messages.error(
                    request,
                    f"Daily limit reached ({settings.SMS_DAILY_LIMIT} messages). "
                    "Try again tomorrow or ask the project owner to raise SMS_DAILY_LIMIT.",
                )
            else:
                try:
                    result = send_sms(to, body)
                except SMSError as exc:
                    SMSMessage.objects.create(
                        recipient=to,
                        body=body,
                        outcome=SMSMessage.Outcome.FAILED,
                        error_code=exc.code,
                        error_message=exc.user_message[:300],
                    )
                    messages.error(request, exc.user_message)
                else:
                    record = SMSMessage.objects.create(
                        recipient=to,
                        body=body,
                        outcome=SMSMessage.Outcome.SUBMITTED,
                        provider_sid=result.sid,
                        provider_status=result.status,
                    )
                    messages.success(
                        request,
                        f"Submitted to TextBee for {record.masked_recipient} "
                        f"(status: {result.status or 'unknown'}). This confirms the "
                        "request was accepted, not that the phone received it. "
                        "Check the History page for delivery updates.",
                    )
                    return redirect("sms_app:send")
        # Fall through: re-display the form with the user's input and errors.
    else:
        form = SMSForm()

    return render(
        request,
        "sms_app/send.html",
        {"form": form, "max_length": settings.SMS_MAX_LENGTH},
    )


def history_view(request):
    """Dashboard of previous sending attempts."""
    stats = SMSMessage.objects.aggregate(
        total=Count("id"),
        submitted=Count("id", filter=Q(outcome=SMSMessage.Outcome.SUBMITTED)),
        failed=Count("id", filter=Q(outcome=SMSMessage.Outcome.FAILED)),
        delivered=Count("id", filter=Q(provider_status="delivered")),
    )
    paginator = Paginator(SMSMessage.objects.all(), 10)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "sms_app/history.html",
        {"page": page, "stats": stats},
    )


@require_POST
def refresh_status_view(request, pk):
    """Ask TextBee for the latest delivery status of one message."""
    record = get_object_or_404(SMSMessage, pk=pk)
    if not record.provider_sid:
        messages.error(request, "This message was never submitted, so it has no status.")
        return redirect("sms_app:history")

    try:
        result = fetch_status(record.provider_sid)
    except SMSError as exc:
        messages.error(request, exc.user_message)
    else:
        record.provider_status = result.status
        record.error_code = result.error_code
        record.error_message = result.error_message
        record.status_updated_at = timezone.now()
        record.save(
            update_fields=[
                "provider_status",
                "error_code",
                "error_message",
                "status_updated_at",
            ]
        )
        messages.info(
            request,
            f"Status for {record.masked_recipient}: {record.delivery_label}.",
        )
    return redirect("sms_app:history")
