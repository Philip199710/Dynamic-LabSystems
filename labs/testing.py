"""Test helpers: lab staff logins with an approved PC."""

from django.contrib.auth import get_user_model

from .models import Device, Lab, LabMember, hash_key, new_device_key
from .devices import DEVICE_COOKIE


def default_lab():
    return Lab.objects.order_by("id").first()


def make_lab_user(username, password="x", lab=None, **extra):
    user = get_user_model().objects.create_user(username, password=password, **extra)
    LabMember.objects.create(user=user, lab=lab or default_lab())
    return user


def approve_pc(client, user):
    """Give the test client's 'browser' an approved PC for this user."""
    raw = client.cookies[DEVICE_COOKIE].value if DEVICE_COOKIE in client.cookies else new_device_key()
    Device.objects.get_or_create(user=user, key_hash=hash_key(raw), defaults={"status": Device.STATUS_APPROVED})
    Device.objects.filter(user=user, key_hash=hash_key(raw)).update(status=Device.STATUS_APPROVED)
    client.cookies[DEVICE_COOKIE] = raw


def login_lab_user(client, user):
    client.force_login(user)
    approve_pc(client, user)
