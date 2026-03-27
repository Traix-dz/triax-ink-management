from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import Client

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Accès réservé à l'administration Triax.", "danger")
            return redirect(url_for("of.dashboard"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@login_required
@admin_required
def index():
    clients = Client.query.order_by(Client.reference).all()
    return render_template("admin/index.html", clients=clients)


@admin_bp.route("/clients/ajouter", methods=["GET", "POST"])
@login_required
@admin_required
def ajouter_client():
    if request.method == "POST":
        ref = request.form.get("reference", "").strip().upper()
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip() or None
        type_encre = request.form.get("type_encre", "").upper()
        password = request.form.get("password", "")
        quota = int(request.form.get("quota_total", 0))
        marge = float(request.form.get("marge_securite_pct", 10.0))

        densites = {"UV": 1.1, "EAU": 1.0, "SOLVANT": 0.9}

        if not ref or not nom or type_encre not in densites or len(password) < 8:
            flash("Tous les champs sont requis (mot de passe ≥ 8 car.).", "danger")
            return render_template("admin/form_client.html", action="Ajouter", client=None)

        if Client.query.filter_by(reference=ref).first():
            flash(f"La référence « {ref} » est déjà utilisée.", "danger")
            return render_template("admin/form_client.html", action="Ajouter", client=None)

        client = Client(
            reference=ref, nom=nom, email=email,
            type_encre=type_encre,
            densite_encre=densites[type_encre],
            quota_total=quota,
            marge_securite_pct=marge,
            role="CLIENT",
        )
        client.set_password(password)
        db.session.add(client)
        db.session.commit()
        flash(f"Client « {ref} » créé.", "success")
        return redirect(url_for("admin.index"))

    return render_template("admin/form_client.html", action="Ajouter", client=None)


@admin_bp.route("/clients/<int:client_id>/modifier", methods=["GET", "POST"])
@login_required
@admin_required
def modifier_client(client_id):
    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        client.nom = request.form.get("nom", client.nom).strip()
        client.email = request.form.get("email", "").strip() or None
        type_encre = request.form.get("type_encre", client.type_encre).upper()
        densites = {"UV": 1.1, "EAU": 1.0, "SOLVANT": 0.9}
        if type_encre in densites:
            client.type_encre = type_encre
            client.densite_encre = densites[type_encre]
        try:
            client.marge_securite_pct = float(request.form.get("marge_securite_pct", client.marge_securite_pct))
        except ValueError:
            pass
        new_pw = request.form.get("new_password", "")
        if new_pw and len(new_pw) >= 8:
            client.set_password(new_pw)
        db.session.commit()
        flash("Client mis à jour.", "success")
        return redirect(url_for("admin.index"))

    return render_template("admin/form_client.html", action="Modifier", client=client)


@admin_bp.route("/clients/<int:client_id>/quotas", methods=["POST"])
@login_required
@admin_required
def recharger_quota(client_id):
    client = Client.query.get_or_404(client_id)
    try:
        ajout = int(request.form.get("ajout", 0))
        if ajout > 0:
            client.quota_total += ajout
            db.session.commit()
            flash(f"{ajout} crédit(s) ajouté(s) à {client.nom}. Nouveau total : {client.quota_total}.", "success")
        else:
            flash("Valeur invalide.", "danger")
    except ValueError:
        flash("Valeur invalide.", "danger")
    return redirect(url_for("admin.index"))


@admin_bp.route("/clients/<int:client_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_client(client_id):
    client = Client.query.get_or_404(client_id)
    client.actif = not client.actif
    db.session.commit()
    etat = "activé" if client.actif else "désactivé"
    flash(f"Client {client.nom} {etat}.", "info")
    return redirect(url_for("admin.index"))


@admin_bp.route("/init", methods=["GET", "POST"])
def init_admin():
    """Route de premier démarrage pour créer le compte admin Triax.
    Accessible uniquement si aucun admin n'existe.
    """
    if Client.query.filter_by(role="ADMIN").first():
        flash("Un compte admin existe déjà.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(password) < 8 or password != confirm:
            flash("Mot de passe invalide ou non confirmé (min 8 car.).", "danger")
            return render_template("admin/init.html")

        admin = Client(
            reference="TRIAX-ADMIN",
            nom="Triax Administration",
            type_encre="UV",
            densite_encre=1.1,
            quota_total=9999,
            role="ADMIN",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        flash("Compte admin créé. Connectez-vous.", "success")
        return redirect(url_for("auth.login"))

    return render_template("admin/init.html")
