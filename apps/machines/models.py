from django.db import models


class Machine(models.Model):
    machine_id = models.SlugField(max_length=64, unique=True)
    model = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    plant = models.CharField(max_length=64, default="PLANT-1")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["machine_id"]

    def __str__(self) -> str:
        return f"{self.machine_id} ({self.model})"
