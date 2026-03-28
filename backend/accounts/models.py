from django.db import models
from django.contrib.auth.models import User

class District(models.Model):
    name = models.CharField(max_length=100, unique=True)
    state = models.CharField(max_length=100, default='Odisha')

    def __str__(self):
        return self.name

class Town(models.Model):
    name = models.CharField(max_length=100)
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='towns')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}, {self.district.name}"

class CarbonEmission(models.Model):
    SECTOR_CHOICES = [
        ('Transport', 'Transport'),
        ('Industrial', 'Industrial'),
        ('Energy', 'Energy'),
        ('Agriculture', 'Agriculture'),
        ('Residential', 'Residential'),
        ('CO', 'Carbon Monoxide'),
    ]

    town = models.ForeignKey(Town, on_delete=models.CASCADE, related_name='emissions')
    sector = models.CharField(max_length=50, choices=SECTOR_CHOICES)
    value = models.FloatField() # Value in metric tons of CO2 equivalent
    date = models.DateField()
    is_prediction = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.town.name} - {self.sector} - {self.date}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    preferred_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    preferred_town = models.ForeignKey(Town, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username
