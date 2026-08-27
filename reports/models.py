from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone


class Certificate(models.Model):
    """A formally issued Certificate of Analysis for a completed sample.

    Distinct from the ad hoc "Download COA (PDF)" export, which anyone with
    access can regenerate on demand as a draft: issuing a certificate is a
    deliberate QA action, gated on the reports.add_certificate permission,
    that stamps a permanent certificate number and records who issued it
    and when. Once issued, the client portal exposes the sample's
    certificate for download; before that, clients see the sample as still
    in progress (see accounts.views.client_portal_coa_pdf).
    """

    sample = models.OneToOneField(
        "samples.Sample", on_delete=models.CASCADE, related_name="certificate"
    )
    certificate_number = models.CharField(max_length=32, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="certificates_issued",
    )

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.certificate_number

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            self.certificate_number = self._generate_certificate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_certificate_number():
        year = timezone.localdate().year
        prefix = f"COA-{year}-"
        last = (
            Certificate.objects.filter(certificate_number__startswith=prefix)
            .aggregate(Max("certificate_number"))
            .get("certificate_number__max")
        )
        next_n = 1
        if last:
            try:
                next_n = int(last.split("-")[-1]) + 1
            except ValueError:
                next_n = Certificate.objects.filter(certificate_number__startswith=prefix).count() + 1
        return f"{prefix}{next_n:04d}"
