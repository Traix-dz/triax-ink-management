"""
Script à lancer UNE SEULE FOIS pour créer les tables.
En local : python init_db.py
Sur Render : intégré dans le buildCommand via flask db upgrade
"""
from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ Tables créées avec succès.")
    print("   → Rendez-vous sur /admin/init pour créer le compte admin Triax.")
