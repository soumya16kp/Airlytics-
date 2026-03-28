"""
seed_coords.py
==============
One-time script: stores real latitude/longitude for every town in the DB.
After this runs, the live /api/predict-co/ endpoint can query the RF model
directly — no random data, no pre-seeding of CO values.

Run once:
    python seed_coords.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import Town

# Real approximate coordinates for each seeded Odisha town
# Format: 'Town Name': (latitude, longitude)
TOWN_COORDS = {
    # Khordha
    'Bhubaneswar':   (20.2961,  85.8245),
    'Khordha':       (20.1817,  85.6173),
    'Jatni':         (20.1667,  85.7000),
    # Cuttack
    'Cuttack':       (20.4625,  85.8830),
    'Choudwar':      (20.5000,  85.9333),
    'Banki':         (20.3667,  85.5333),
    # Ganjam
    'Berhampur':     (19.3150,  84.7941),
    'Hinjilicut':    (19.5167,  85.0833),
    'Chhatrapur':    (19.3667,  85.0167),
    # Puri
    'Puri':          (19.8135,  85.8312),
    'Konark':        (19.8978,  86.1197),
    'Nimapada':      (20.0667,  86.0167),
    # Sambalpur
    'Sambalpur':     (21.4669,  83.9756),
    'Burla':         (21.5000,  83.8667),
    'Hirakud':       (21.5167,  83.8833),
    # Balasore
    'Balasore':      (21.4942,  86.9331),
    'Jaleswar':      (21.8000,  87.2167),
    'Soro':          (21.2500,  86.6833),
    # Bhadrak
    'Bhadrak':       (21.0583,  86.4994),
    'Dhamnagar':     (21.1667,  86.5167),
    'Chandabali':    (20.7833,  86.7333),
    # Jajpur
    'Jajpur':        (20.8500,  86.3333),
    'Vyasanagar':    (20.8000,  86.2333),
    'Chandikhole':   (20.6833,  86.0000),
    # Jagatsinghpur
    'Jagatsinghpur': (20.2667,  86.1667),
    'Paradeep':      (20.3167,  86.6167),
    'Tirtol':        (20.2333,  86.2833),
    # Kendrapara
    'Kendrapara':    (20.5000,  86.4167),
    'Pattamundai':   (20.5833,  86.5667),
    'Aul':           (20.6167,  86.6333),
    # Jharsuguda
    'Jharsuguda':    (21.8542,  84.0064),
    'Brajarajnagar': (21.8000,  83.9167),
    'Belpahar':      (21.9667,  83.9333),
}


def seed_coordinates():
    updated, skipped = 0, 0

    for town in Town.objects.all():
        coords = TOWN_COORDS.get(town.name)
        if coords:
            town.latitude, town.longitude = coords
            town.save()
            print(f"  ✓ {town.name:20s}  lat={coords[0]}  lon={coords[1]}")
            updated += 1
        else:
            print(f"  ✗ {town.name:20s}  — no coords defined, skipping.")
            skipped += 1

    print(f"\nDone. Updated: {updated}  |  Skipped: {skipped}")
    print("Live /api/predict-co/?town=<id> will now use the RF model for these towns.")


if __name__ == '__main__':
    seed_coordinates()
