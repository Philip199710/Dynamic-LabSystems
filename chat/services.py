import re

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from samples.models import Sample

from .models import Channel, Message, ReadState

SAMPLE_ID_RE = re.compile(r"\bFS-\d{4}-\d{4,}\b")
URL_RE = re.compile(r"(https?://[^\s<]+)")


def display_name(user):
    if user is None:
        return "Former member"
    return user.get_full_name() or user.get_username()


def initials(user):
    name = display_name(user)
    parts = [p for p in re.split(r"[\s._-]+", name) if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def render_body(text, sample_links):
    """Escape the message, then link URLs and sample IDs (FS-2026-0003 → its page)."""
    html = escape(text)
    html = URL_RE.sub(r'<a href="\1" target="_blank" rel="noopener">\1</a>', html)

    def sample(match):
        url = sample_links.get(match.group(0))
        return f'<a class="chat-sample" href="{url}">{match.group(0)}</a>' if url else match.group(0)

    html = SAMPLE_ID_RE.sub(sample, html)
    return html.replace("\n", "<br>")


def serialize(messages, me):
    messages = list(messages)
    ids = {m for msg in messages for m in SAMPLE_ID_RE.findall(msg.body)}
    links = {
        sid: reverse("samples:detail", args=[pk])
        for sid, pk in Sample.objects.filter(sample_id__in=ids).values_list("sample_id", "pk")
    }
    out = []
    for m in messages:
        local = timezone.localtime(m.created_at)
        out.append(
            {
                "id": m.id,
                "author": display_name(m.author),
                "initials": initials(m.author),
                "author_id": m.author_id,
                "mine": m.author_id == me.id,
                "html": render_body(m.body, links),
                "time": local.strftime("%H:%M"),
                "date": local.strftime("%A %d %B %Y"),
                "iso": local.isoformat(),
            }
        )
    return out


def mark_read(user, channel, up_to_id):
    state, _ = ReadState.objects.get_or_create(user=user, channel=channel)
    if up_to_id and up_to_id > state.last_read_id:
        state.last_read_id = up_to_id
        state.save(update_fields=["last_read_id"])


def unread_by_channel(user):
    """{channel_id: unread count} for active channels, ignoring your own messages."""
    last_read = dict(ReadState.objects.filter(user=user).values_list("channel_id", "last_read_id"))
    counts = {}
    for channel in Channel.objects.filter(is_archived=False).only("id"):
        counts[channel.id] = 0
    if not counts:
        return counts
    cond = Q()
    for cid in counts:
        cond |= Q(channel_id=cid, id__gt=last_read.get(cid, 0))
    rows = (
        Message.objects.filter(cond)
        .exclude(author=user)
        .values("channel_id")
        .annotate(n=Count("id"))
    )
    for row in rows:
        counts[row["channel_id"]] = row["n"]
    return counts
