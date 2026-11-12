from sqlalchemy.orm import Session

from .models import Product

SEED = [
    ("Fusender Pro LED 800 Kit", "Lighting", 85000, 98000, 4.8, 124, "Bi-color 3200–5600K, 800 LED, AC adapter + stand.", "#DCE8F7", "LED"),
    ("Unique Leather S25 / S24 Case", "Cases", 12500, 16000, 4.6, 89, "Genuine leather for S25 Ultra and S24 Plus, magnetic.", "#EADFD0", "S25"),
    ("Hello Kitty 3D iPhone Case", "Cases", 8500, 11000, 4.9, 210, "3D bow, soft silicone. Fits iPhone 15, 14 and 13.", "#F6D6EA", "3D"),
    ("F12 3-Axis Foldable Gimbal", "Gadgets", 48000, 58000, 4.7, 67, "3-axis stabilization, face tracking, foldable.", "#E1E4EA", "F12"),
    ("Camera Lens Film Protectors (Bulk)", "Protection", 3500, 5000, 4.5, 342, "9H tempered glass, anti-scratch, for all phones.", "#E3EDEA", "9H"),
    ("RGB Soft Ring Light MJ33", "Lighting", 22000, 28000, 4.8, 156, "13-inch RGB, 22 colors, tripod stand, Bluetooth.", "#E6DDF5", "RGB"),
    ("JBL X68 MAX Bass Stereo", "Gadgets", 15500, 19500, 4.6, 98, "Bluetooth 5.3, 20W bass, RGB lights, TWS.", "#E9E6E1", "X68"),
    ("Cat Ear SNK-B39M RGB Headset", "Gadgets", 14200, 18000, 4.7, 112, "Cat ear LED, RGB lighting, Bluetooth + wired.", "#F8DDE0", "B39M"),
]


def seed_products(db: Session):
    if db.query(Product).count():
        return
    for n, c, p, w, r, rv, d, t, m in SEED:
        db.add(Product(name=n, cat=c, price=p, was=w, rating=r, reviews=rv, desc=d, tint=t, mark=m, stock=50))
    db.commit()
