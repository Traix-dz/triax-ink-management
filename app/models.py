from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json


@login_manager.user_loader
def load_user(user_id):
    return Client.query.get(int(user_id))


class Client(UserMixin, db.Model):
    """Imprimeur / utilisateur de l'application."""
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    nom = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)

    # Paramètres encre du client (fixes pour toute son activité)
    type_encre = db.Column(db.String(10), nullable=False)  # UV / EAU / SOLVANT
    densite_encre = db.Column(db.Float, nullable=False, default=1.0)

    # Marge de sécurité configurable (% appliqué sur le résultat)
    marge_securite_pct = db.Column(db.Float, nullable=False, default=10.0)

    # Quotas analyses IA
    quota_total = db.Column(db.Integer, nullable=False, default=0)
    quota_utilise = db.Column(db.Integer, nullable=False, default=0)

    # Authentification
    mot_de_passe_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="CLIENT")  # CLIENT / ADMIN

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)

    # Relations
    encres = db.relationship("Encre", backref="client", lazy="dynamic", cascade="all, delete-orphan")
    anilox = db.relationship("Anilox", backref="client", lazy="dynamic", cascade="all, delete-orphan")
    configs_machines = db.relationship("ConfigMachine", backref="client", lazy="dynamic", cascade="all, delete-orphan")
    ofs = db.relationship("OF", backref="client", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.mot_de_passe_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.mot_de_passe_hash, password)

    @property
    def quota_restant(self):
        return max(0, self.quota_total - self.quota_utilise)

    @property
    def is_admin(self):
        return self.role == "ADMIN"

    def consommer_quota(self):
        """Décrémente le quota d'une unité. Retourne True si OK."""
        if self.quota_restant > 0:
            self.quota_utilise += 1
            db.session.commit()
            return True
        return False

    def __repr__(self):
        return f"<Client {self.reference} — {self.nom}>"


class Encre(db.Model):
    """Référentiel des encres d'un client."""
    __tablename__ = "encres"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    reference = db.Column(db.String(80), nullable=False)
    nom = db.Column(db.String(150), nullable=False)
    # On garde le type et la densité sur l'encre pour permettre des encres spéciales
    type_encre = db.Column(db.String(10), nullable=False)   # UV / EAU / SOLVANT
    densite = db.Column(db.Float, nullable=False, default=1.0)

    __table_args__ = (
        db.UniqueConstraint("client_id", "reference", name="uq_encre_client_ref"),
    )

    def __repr__(self):
        return f"<Encre {self.reference} — {self.nom}>"


class Anilox(db.Model):
    """Référentiel des anilox d'un client."""
    __tablename__ = "anilox"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    reference = db.Column(db.String(80), nullable=False)
    lineature = db.Column(db.Float, nullable=True)          # lignes/cm
    volume_cm3_m2 = db.Column(db.Float, nullable=False)     # cm³/m²
    coeff_transfert = db.Column(db.Float, nullable=False, default=0.80)  # 0 à 1

    __table_args__ = (
        db.UniqueConstraint("client_id", "reference", name="uq_anilox_client_ref"),
    )

    def __repr__(self):
        return f"<Anilox {self.reference} — {self.volume_cm3_m2} cm³/m²>"


class ConfigMachine(db.Model):
    """Configuration machine sauvegardée (stations + anilox)."""
    __tablename__ = "configs_machines"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    nom = db.Column(db.String(150), nullable=False)
    # JSON : [{"couleur": "C", "anilox_id": 3, "anilox_ref": "ANI-012", "volume": 3.5, "coeff": 0.82}, ...]
    stations_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def stations(self):
        return json.loads(self.stations_json)

    @stations.setter
    def stations(self, value):
        self.stations_json = json.dumps(value)

    def __repr__(self):
        return f"<ConfigMachine {self.nom}>"


class OF(db.Model):
    """Ordre de fabrication."""
    __tablename__ = "ofs"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    reference_of = db.Column(db.String(100), nullable=False)
    nom_produit = db.Column(db.String(200), nullable=True)
    date_of = db.Column(db.Date, nullable=False)

    # Type de tirage
    type_tirage = db.Column(db.String(10), nullable=False)  # BOBINE / FEUILLE
    # Bobine
    laize_m = db.Column(db.Float, nullable=True)
    metrage_m = db.Column(db.Float, nullable=True)
    # Feuille
    hauteur_m = db.Column(db.Float, nullable=True)
    largeur_m = db.Column(db.Float, nullable=True)
    nb_tirages = db.Column(db.Integer, nullable=True)
    # Calculé
    surface_m2 = db.Column(db.Float, nullable=True)

    # Source des taux de couverture
    taux_source = db.Column(db.String(10), nullable=False, default="MANUEL")  # IA / MANUEL
    pdf_filename = db.Column(db.String(255), nullable=True)

    # Statut
    statut = db.Column(db.String(20), nullable=False, default="BROUILLON")  # BROUILLON / CALCULE / EXPORTE
    marge_appliquee_pct = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    stations = db.relationship("StationCouleur", backref="of", lazy="dynamic",
                               cascade="all, delete-orphan", order_by="StationCouleur.ordre")

    def calculer_surface(self):
        if self.type_tirage == "BOBINE" and self.laize_m and self.metrage_m:
            self.surface_m2 = round(self.laize_m * self.metrage_m, 4)
        elif self.type_tirage == "FEUILLE" and self.hauteur_m and self.largeur_m and self.nb_tirages:
            self.surface_m2 = round(self.hauteur_m * self.largeur_m * self.nb_tirages, 4)

    def __repr__(self):
        return f"<OF {self.reference_of}>"


class StationCouleur(db.Model):
    """Une station couleur au sein d'un OF."""
    __tablename__ = "stations_couleur"

    id = db.Column(db.Integer, primary_key=True)
    of_id = db.Column(db.Integer, db.ForeignKey("ofs.id"), nullable=False)
    ordre = db.Column(db.Integer, nullable=False, default=0)

    # Identification de la couleur
    nom_couleur = db.Column(db.String(80), nullable=False)  # "C","M","J","N","Pantone 485","Blanc","Vernis"...

    # Encre (depuis référentiel ou saisie libre)
    encre_id = db.Column(db.Integer, db.ForeignKey("encres.id"), nullable=True)
    encre_ref_manuelle = db.Column(db.String(100), nullable=True)
    densite_utilisee = db.Column(db.Float, nullable=False, default=1.0)

    # Anilox (depuis référentiel ou saisie libre)
    anilox_id = db.Column(db.Integer, db.ForeignKey("anilox.id"), nullable=True)
    anilox_ref_manuelle = db.Column(db.String(80), nullable=True)
    anilox_volume = db.Column(db.Float, nullable=False)      # cm³/m²
    anilox_coeff = db.Column(db.Float, nullable=False)       # coefficient de transfert

    # Taux de couverture (% entre 0 et 100)
    taux_couverture_pct = db.Column(db.Float, nullable=True)

    # Résultats calculés
    masse_nette_kg = db.Column(db.Float, nullable=True)
    masse_avec_marge_kg = db.Column(db.Float, nullable=True)

    # Relations
    encre = db.relationship("Encre", backref="stations")
    anilox_obj = db.relationship("Anilox", backref="stations")

    @property
    def encre_label(self):
        if self.encre:
            return f"{self.encre.reference} — {self.encre.nom}"
        return self.encre_ref_manuelle or "—"

    @property
    def anilox_label(self):
        if self.anilox_obj:
            return self.anilox_obj.reference
        return self.anilox_ref_manuelle or "—"

    def __repr__(self):
        return f"<Station {self.nom_couleur} OF#{self.of_id}>"
