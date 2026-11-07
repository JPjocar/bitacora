from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_safe

from .models import Notification
from .services import mark_read, require_access


@login_required
@require_safe
def inbox(request):
    actor = require_access(request.user)
    notices = Notification.objects.filter(recipient=actor).select_related("event", "target")
    state = request.GET.get("state", "unread")
    if state == "unread":
        notices = notices.filter(read_at=None, resolved_at=None)
    elif state == "read":
        notices = notices.filter(read_at__isnull=False)
    elif state == "resolved":
        notices = notices.filter(resolved_at__isnull=False)
    else:
        state = "all"
    return render(
        request,
        "notifications/inbox.html",
        {
            "page_obj": Paginator(notices, 20).get_page(request.GET.get("page")),
            "state": state,
        },
    )


@login_required
@require_safe
def counter(request):
    actor = require_access(request.user)
    count = Notification.objects.filter(recipient=actor, read_at=None, resolved_at=None).count()
    return render(request, "notifications/counter.html", {"unread_count": count})


@login_required
@require_POST
def read_notice(request, pk):
    try:
        notice = mark_read(actor=request.user, notice_id=pk)
    except Notification.DoesNotExist as exc:
        raise Http404 from exc
    return redirect(notice.get_absolute_url())


@login_required
@require_POST
def read_all(request):
    mark_read(actor=request.user)
    return redirect("notifications:inbox")
