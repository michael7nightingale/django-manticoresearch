"""Example blog models."""

from django.db import models
import uuid

class Tags(models.Model):
    """Blog post model."""
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title

