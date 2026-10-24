from django.contrib import messages as flash
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .access import chat_user_required
from .models import Channel, Message
from .services import display_name, initials, mark_read, serialize, unread_by_channel

PAGE_SIZE = 60


def _default_channel(lab):
    return Channel.objects.filter(is_archived=False, lab=lab).order_by("id").first()


def _channel(request, pk, **extra):
    return get_object_or_404(Channel, pk=pk, lab=request.lab, **extra)


@chat_user_required
def chat_home(request):
    if request.lab is None:
        raise Http404("No lab")
    channel = _default_channel(request.lab)
    if channel is None:
        channel = Channel.objects.create(lab=request.lab, name="general", description="Whole-lab announcements and day-to-day chat")
    return redirect("chat:channel", pk=channel.pk)


@chat_user_required
def channel_view(request, pk):
    channel = _channel(request, pk)
    recent = list(
        Message.objects.filter(channel=channel).select_related("author").order_by("-id")[:PAGE_SIZE]
    )[::-1]
    if recent:
        mark_read(request.user, channel, recent[-1].id)
    unread = unread_by_channel(request.user, request.lab)
    channels = [
        {"obj": c, "unread": unread.get(c.id, 0)} for c in Channel.objects.filter(is_archived=False, lab=request.lab)
    ]
    return render(
        request,
        "chat/channel.html",
        {
            "channel": channel,
            "channels": channels,
            "initial_messages": serialize(recent, request.user, request.lab),
            "has_older": bool(recent) and Message.objects.filter(channel=channel, id__lt=recent[0].id).exists(),
            "me_name": display_name(request.user),
            "me_initials": initials(request.user),
        },
    )


@require_GET
@chat_user_required
def channel_messages(request, pk):
    """Poll endpoint. ?after=<id> returns newer messages; ?before=<id> pages back."""
    channel = _channel(request, pk)
    qs = Message.objects.filter(channel=channel).select_related("author")
    before = request.GET.get("before")
    if before and before.isdigit():
        rows = list(qs.filter(id__lt=int(before)).order_by("-id")[:PAGE_SIZE])[::-1]
        has_older = bool(rows) and qs.filter(id__lt=rows[0].id).exists()
        return JsonResponse({"messages": serialize(rows, request.user, request.lab), "has_older": has_older})
    after = request.GET.get("after", "0")
    after = int(after) if after.isdigit() else 0
    rows = list(qs.filter(id__gt=after).order_by("id")[:200])
    if rows:
        mark_read(request.user, channel, rows[-1].id)
    unread = unread_by_channel(request.user, request.lab)
    unread.pop(channel.id, None)
    return JsonResponse(
        {"messages": serialize(rows, request.user, request.lab), "unread": {str(k): v for k, v in unread.items()}}
    )


@require_POST
@chat_user_required
def send_message(request, pk):
    channel = _channel(request, pk, is_archived=False)
    body = (request.POST.get("body") or "").strip()
    if not body:
        return JsonResponse({"error": "Message is empty."}, status=400)
    if len(body) > 4000:
        return JsonResponse({"error": "Message is too long (4000 characters max)."}, status=400)
    msg = Message.objects.create(channel=channel, author=request.user, body=body)
    mark_read(request.user, channel, msg.id)
    msg.author = request.user
    return JsonResponse({"message": serialize([msg], request.user, request.lab)[0]}, status=201)


@require_POST
@chat_user_required
def create_channel(request):
    name = (request.POST.get("name") or "").strip().lstrip("#").lower().replace(" ", "-")[:60]
    description = (request.POST.get("description") or "").strip()[:200]
    if not name:
        flash.error(request, "Give the channel a name.")
        return redirect("chat:home")
    try:
        channel = Channel.objects.create(lab=request.lab, name=name, description=description, created_by=request.user)
    except IntegrityError:
        channel = Channel.objects.get(lab=request.lab, name=name)
        flash.info(request, f"#{name} already exists — opened it for you.")
    return redirect("chat:channel", pk=channel.pk)


@require_GET
@chat_user_required
def unread_total(request):
    return JsonResponse({"unread": sum(unread_by_channel(request.user, request.lab).values())})
