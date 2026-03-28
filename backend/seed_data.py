import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import District, Town, CarbonEmission
import datetime
import random

def seed_data():
    # Initial Districts and Towns
    districts_data = [
        ('Khordha', ['Bhubaneswar', 'Khordha', 'Jatni']),
        ('Cuttack', ['Cuttack', 'Choudwar', 'Banki']),
        ('Ganjam', ['Berhampur', 'Hinjilicut', 'Chhatrapur']),
        ('Puri', ['Puri', 'Konark', 'Nimapada']),
        ('Sambalpur', ['Sambalpur', 'Burla', 'Hirakud']),
        ('Balasore', ['Balasore', 'Jaleswar', 'Soro']),
        ('Bhadrak', ['Bhadrak', 'Dhamnagar', 'Chandabali']),
        ('Jajpur', ['Jajpur', 'Vyasanagar', 'Chandikhole']),
        ('Jagatsinghpur', ['Jagatsinghpur', 'Paradeep', 'Tirtol']),
        ('Kendrapara', ['Kendrapara', 'Pattamundai', 'Aul']),
        ('Jharsuguda', ['Jharsuguda', 'Brajarajnagar', 'Belpahar']),
    ]

    for dist_name, towns in districts_data:
        district, _ = District.objects.get_or_create(name=dist_name)
        for town_name in towns:
            town, _ = Town.objects.get_or_create(name=town_name, district=district)
            
            # Seed some sample emissions for visualization
            sectors = ['Transport', 'Industrial', 'Energy', 'Agriculture', 'Residential']
            for sector in sectors:
                # Historical data (last 6 months)
                for i in range(6):
                    date = datetime.date.today() - datetime.timedelta(days=30*i)
                    CarbonEmission.objects.create(
                        town=town,
                        sector=sector,
                        value=random.uniform(10.0, 100.0),
                        date=date,
                        is_prediction=False
                    )
                # Prediction data (next month)
                CarbonEmission.objects.create(
                    town=town,
                    sector=sector,
                    value=random.uniform(50.0, 150.0),
                    date=datetime.date.today() + datetime.timedelta(days=30),
                    is_prediction=True
                )

    print("Successfully seeded database with Districts, Towns, and Emission data.")

if __name__ == "__main__":
    seed_data()
