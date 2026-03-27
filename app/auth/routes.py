from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import Client

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("of.dashboard"))

    if request.method == "POST":
        reference = request.form.get("reference", "").strip().upper()
        password = request.form.get("password", "")

        client = Client.query.filter_by(reference=reference, actif=True).first()

        if client and client.check_password(password):
            login_user(client, remember=request.form.get("remember") == "on")
            next_page = request.args.get("next")
            flash(f"Bienvenue, {client.nom} !", "success")
            return redirect(next_page or url_for("of.dashboard"))
        else:
            flash("Référence ou mot de passe incorrect.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "change_password":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")

            if not current_user.check_password(old_pw):
                flash("Mot de passe actuel incorrect.", "danger")
            elif len(new_pw) < 8:
                flash("Le nouveau mot de passe doit contenir au moins 8 caractères.", "danger")
            elif new_pw != confirm_pw:
                flash("Les mots de passe ne correspondent pas.", "danger")
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash("Mot de passe mis à jour.", "success")

        elif action == "update_marge":
            try:
                marge = float(request.form.get("marge_securite_pct", 10))
                if 0 <= marge <= 50:
                    current_user.marge_securite_pct = marge
                    db.session.commit()
                    flash(f"Marge de sécurité mise à jour : {marge}%", "success")
                else:
                    flash("La marge doit être entre 0% et 50%.", "danger")
            except ValueError:
                flash("Valeur invalide.", "danger")

    return render_template("auth/profil.html")
