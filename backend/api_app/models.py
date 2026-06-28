from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # optional: last known GPS (for dashboard personalization)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.user.username
    
class PollutionReading(models.Model):

    POLLUTANT_CHOICES = [
        ('CO', 'Carbon Monoxide'),
        ('NO2', 'Nitrogen Dioxide'),
        ('O3', 'Ozone'),
        ('SO2', 'Sulfur Dioxide'),
        ('PM25', 'PM2.5'),
        ('PM10', 'PM10'),
    ]

    latitude = models.FloatField()
    longitude = models.FloatField()

    pollutant_type = models.CharField(max_length=10, choices=POLLUTANT_CHOICES)
    value = models.FloatField()  # AQI or concentration value

    timestamp = models.DateTimeField(auto_now_add=True)

    # optional metadata (very useful later)
    source = models.CharField(max_length=50, default='sensor')  # sensor / api / ml
    is_prediction = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.pollutant_type} @ ({self.latitude}, {self.longitude})"
    
class PollutionPrediction(models.Model):
    latitude = models.FloatField()
    longitude = models.FloatField()

    pollutant_type = models.CharField(max_length=10)

    predicted_value = models.FloatField()
    prediction_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prediction {self.pollutant_type}"