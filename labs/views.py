from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.login_views import dynamic_admin_required
from catalog.models import Instrument
from chat.models import Channel

from .context import ADMIN_VIEW_LAB_KEY
from .forms import LabForm, LabUserForm, NewLabForm
from .models import Device, Lab, LabMember, LoginEvent

DEFAULT_CHANNELS = [
    ("general", "Whole-lab announcements and day-to-day chat"),
    ("sample-intake", "Arrivals, tanker drops and storage questions"),
    ("results-qa", "Result checks, retests and COA sign-off"),
]


@dynamic_admin_required
def lab_list(request):
    labs = Lab.objects.annotate(
        logins=Count("members", filter=Q(members__user__is_active=True), distinct=True),
        pending=Count("members__user__devices", filter=Q(members__user__devices__status=Device.STATUS_PENDING), distinct=True),
        samples_n=Count("samples", distinct=True),
    )
    if request.method == "POST":
        form = NewLabForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                lab = form.save()
                for name, desc in DEFAULT_CHANNELS:
                    Channel.objects.create(lab=lab, name=name, description=desc)
                source = form.cleaned_data.get("copy_instruments_from")
                if source:
                    for inst in source.instruments.prefetch_related("test_methods"):
                        methods = list(inst.test_methods.all())
                        copy = Instrument.objects.create(
                            lab=lab, name=inst.name, model_number=inst.model_number,
                            instrument_type=inst.instrument_type, temperature_range=inst.temperature_range,
                            status=inst.status, notes=inst.notes,
                        )
                        copy.test_methods.set(methods)
            messages.success(request, f"{lab.name} created. Now add its logins.")
            return redirect("labs:detail", pk=lab.pk)
    else:
        form = NewLabForm()
    return render(request, "labs/lab_list.html", {"labs": labs, "form": form})


@dynamic_admin_required
def lab_detail(request, pk):
    lab = get_object_or_404(Lab, pk=pk)
    User = get_user_model()
    licence_form = LabForm(instance=lab, prefix="lic")
    user_form = LabUserForm(lab=lab, prefix="user")
    if request.method == "POST" and "save_licence" in request.POST:
        licence_form = LabForm(request.POST, instance=lab, prefix="lic")
        if licence_form.is_valid():
            licence_form.save()
            messages.success(request, "Licence updated.")
            return redirect("labs:detail", pk=pk)
    elif request.method == "POST" and "add_user" in request.POST:
        user_form = LabUserForm(request.POST, lab=lab, prefix="user")
        if user_form.is_valid():
            d = user_form.cleaned_data
            first, _, last = d["full_name"].strip().partition(" ")
            with transaction.atomic():
                user = User.objects.create_user(d["username"], email=d["email"], password=d["password"],
                                                first_name=first, last_name=last)
                if d["role"]:
                    user.groups.add(d["role"])
                LabMember.objects.create(user=user, lab=lab)
            messages.success(request, f"Login {user.get_username()} created for {lab.name}. "
                                      "Their first PC is approved automatically when they sign in."
                             if lab.auto_approve_first_device else
                             f"Login {user.get_username()} created. Approve their PC after their first sign-in.")
            return redirect("labs:detail", pk=pk)

    members = (
        LabMember.objects.filter(lab=lab).select_related("user").prefetch_related("user__groups", "user__devices")
        .order_by("-user__is_active", "user__username")
    )
    people = []
    for m in members:
        devices = list(m.user.devices.all())
        people.append({
            "user": m.user,
            "roles": [g.name for g in m.user.groups.all()],
            "devices": devices,
            "approved": sum(1 for d in devices if d.status == Device.STATUS_APPROVED),
        })
    events = LoginEvent.objects.filter(lab=lab).select_related("device")[:60]
    return render(request, "labs/lab_detail.html", {
        "lab": lab, "people": people, "events": events,
        "licence_form": licence_form, "user_form": user_form,
    })


def _device_redirect(request, device):
    membership = getattr(device.user, "lab_membership", None)
    nxt = request.POST.get("next")
    if nxt and nxt.startswith("/dynamic/"):
        return redirect(nxt)
    return redirect("labs:detail", pk=membership.lab_id) if membership else redirect("dynamic_console")


@require_POST
@dynamic_admin_required
def device_decide(request, pk, action):
    device = get_object_or_404(Device.objects.select_related("user", "user__lab_membership__lab"), pk=pk)
    lab = getattr(getattr(device.user, "lab_membership", None), "lab", None)
    if action == "approve":
        approved = device.user.devices.filter(status=Device.STATUS_APPROVED).exclude(pk=device.pk).count()
        if lab and approved >= lab.devices_per_login:
            messages.error(request, f"{device.user.get_username()} already has {approved} approved PC(s) — the licence allows "
                                    f"{lab.devices_per_login}. Revoke the old PC first.")
            return _device_redirect(request, device)
        device.status = Device.STATUS_APPROVED
        messages.success(request, f"PC-{device.pk} approved for {device.user.get_username()}.")
    elif action == "revoke":
        device.status = Device.STATUS_REVOKED
        messages.success(request, f"PC-{device.pk} revoked — {device.user.get_username()} is signed out there.")
    else:
        return redirect("dynamic_console")
    device.decided_by = request.user
    device.decided_at = timezone.now()
    device.save(update_fields=["status", "decided_by", "decided_at"])
    return _device_redirect(request, device)


@require_POST
@dynamic_admin_required
def user_toggle(request, pk):
    member = get_object_or_404(LabMember.objects.select_related("user", "lab"), user_id=pk)
    user = member.user
    if user.is_active:
        user.is_active = False
        user.devices.filter(status=Device.STATUS_APPROVED).update(status=Device.STATUS_REVOKED, decided_at=timezone.now())
        messages.success(request, f"{user.get_username()} deactivated — frees one licensed login.")
    else:
        if member.lab.seats_left() <= 0:
            messages.error(request, f"No licensed logins left in {member.lab.name}.")
            return redirect("labs:detail", pk=member.lab_id)
        user.is_active = True
        messages.success(request, f"{user.get_username()} reactivated. Approve their PC after they sign in.")
    user.save(update_fields=["is_active"])
    return redirect("labs:detail", pk=member.lab_id)


@dynamic_admin_required
def signin_log(request):
    events = LoginEvent.objects.select_related("lab", "device")
    if request.GET.get("flag") == "1":
        events = events.filter(Q(new_network=True) | Q(outcome__in=[LoginEvent.OUTCOME_PENDING, LoginEvent.OUTCOME_BLOCKED]))
    lab_id = request.GET.get("lab")
    if lab_id and lab_id.isdigit():
        events = events.filter(lab_id=int(lab_id))
    return render(request, "labs/signin_log.html", {
        "events": events[:300], "labs": Lab.objects.all(), "flag": request.GET.get("flag") == "1", "lab_id": lab_id,
    })


@require_POST
@dynamic_admin_required
def view_lab(request):
    lab = get_object_or_404(Lab, pk=request.POST.get("lab"))
    request.session[ADMIN_VIEW_LAB_KEY] = lab.pk
    messages.info(request, f"Now viewing {lab.name}'s data.")
    nxt = request.POST.get("next") or "/dashboard/"
    return redirect(nxt if nxt.startswith("/") else "/dashboard/")
