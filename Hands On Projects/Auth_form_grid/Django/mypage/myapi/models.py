from django.db import models

# Create your models here.
# authapp/models.py
from djongo import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Add custom fields here, if needed
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.username
