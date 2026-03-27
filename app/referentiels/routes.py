from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Encre, Anilox, ConfigMachine
import pandas as pd
import io

ref_bp = Blueprint("ref", __name__, url_prefix="/referentiels")

DENSITES = {"UV": 1.1, "EAU": 1.0, "SOLVANT": 0.9}


# ─── ENCRES ────────────────────────────────────────────────────────────────────

@ref_bp.route("/encres")
@login_required
def encres():
    liste = Encre.query.filter_by(client_id=current_user.id).order_by(Encre.reference).all()
    return render_template("referentiels/encres.html", encres=liste)


@ref_bp.route("/encres/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_encre():
    if request.method == "POST":
        ref = request.form.get("reference", "").strip().upper()
        nom = request.form.get("nom", "").strip()
        type_encre = request.form.get("type_encre", "").strip().upper()
        try:
            densite = float(request.form.get("densite", DENSITES.get(type_encre, 1.0)))
        except ValueError:
            densite = DENSITES.get(type_encre, 1.0)

        if not ref or not nom or type_encre not in ("UV", "EAU", "SOLVANT"):
            flash("Tous les champs sont requis.", "danger")
            return render_template("referentiels/form_encre.html", action="Ajouter", encre=None)

        existing = Encre.query.filter_by(client_id=current_user.id, reference=ref).first()
        if existing:
            flash(f"Une encre avec la référence « {ref} » existe déjà.", "danger")
            return render_template("referentiels/form_encre.html", action="Ajouter", encre=None)

        encre = Encre(client_id=current_user.id, reference=ref, nom=nom,
                      type_encre=type_encre, densite=densite)
        db.session.add(encre)
        db.session.commit()
        flash(f"Encre « {ref} » ajoutée.", "success")
        return redirect(url_for("ref.encres"))

    return render_template("referentiels/form_encre.html", action="Ajouter", encre=None)


@ref_bp.route("/encres/<int:encre_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier_encre(encre_id):
    encre = Encre.query.filter_by(id=encre_id, client_id=current_user.id).first_or_404()

    if request.method == "POST":
        encre.nom = request.form.get("nom", "").strip()
        type_encre = request.form.get("type_encre", "").strip().upper()
        if type_encre in ("UV", "EAU", "SOLVANT"):
            encre.type_encre = type_encre
        try:
            encre.densite = float(request.form.get("densite", encre.densite))
        except ValueError:
            pass
        db.session.commit()
        flash("Encre mise à jour.", "success")
        return redirect(url_for("ref.encres"))

    return render_template("referentiels/form_encre.html", action="Modifier", encre=encre)


@ref_bp.route("/encres/<int:encre_id>/supprimer", methods=["POST"])
@login_required
def supprimer_encre(encre_id):
    encre = Encre.query.filter_by(id=encre_id, client_id=current_user.id).first_or_404()
    db.session.delete(encre)
    db.session.commit()
    flash("Encre supprimée.", "info")
    return redirect(url_for("ref.encres"))


@ref_bp.route("/encres/importer", methods=["POST"])
@login_required
def importer_encres():
    fichier = request.files.get("fichier")
    if not fichier:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for("ref.encres"))

    try:
        content = fichier.read()
        if fichier.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        df.columns = [c.strip().lower() for c in df.columns]
        ajoutes, ignores = 0, 0

        for _, row in df.iterrows():
            ref = str(row.get("reference", "")).strip().upper()
            nom = str(row.get("nom", "")).strip()
            type_e = str(row.get("type_encre", row.get("type", ""))).strip().upper()
            if not ref or not nom or type_e not in ("UV", "EAU", "SOLVANT"):
                ignores += 1
                continue
            densite = float(row.get("densite", DENSITES.get(type_e, 1.0)))

            existing = Encre.query.filter_by(client_id=current_user.id, reference=ref).first()
            if existing:
                ignores += 1
                continue

            db.session.add(Encre(client_id=current_user.id, reference=ref,
                                 nom=nom, type_encre=type_e, densite=densite))
            ajoutes += 1

        db.session.commit()
        flash(f"Import terminé : {ajoutes} encre(s) ajoutée(s), {ignores} ignorée(s) (doublons ou données invalides).", "success")
    except Exception as e:
        flash(f"Erreur lors de l'import : {str(e)}", "danger")

    return redirect(url_for("ref.encres"))


# ─── ANILOX ────────────────────────────────────────────────────────────────────

@ref_bp.route("/anilox")
@login_required
def anilox():
    liste = Anilox.query.filter_by(client_id=current_user.id).order_by(Anilox.reference).all()
    return render_template("referentiels/anilox.html", anilox_list=liste)


@ref_bp.route("/anilox/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_anilox():
    if request.method == "POST":
        ref = request.form.get("reference", "").strip().upper()
        try:
            lineature = float(request.form.get("lineature") or 0) or None
            volume = float(request.form.get("volume_cm3_m2", 0))
            coeff = float(request.form.get("coeff_transfert", 0.80))
        except ValueError:
            flash("Valeurs numériques invalides.", "danger")
            return render_template("referentiels/form_anilox.html", action="Ajouter", anilox=None)

        if not ref or not volume:
            flash("Référence et volume sont requis.", "danger")
            return render_template("referentiels/form_anilox.html", action="Ajouter", anilox=None)

        existing = Anilox.query.filter_by(client_id=current_user.id, reference=ref).first()
        if existing:
            flash(f"Un anilox « {ref} » existe déjà.", "danger")
            return render_template("referentiels/form_anilox.html", action="Ajouter", anilox=None)

        ani = Anilox(client_id=current_user.id, reference=ref, lineature=lineature,
                     volume_cm3_m2=volume, coeff_transfert=coeff)
        db.session.add(ani)
        db.session.commit()
        flash(f"Anilox « {ref} » ajouté.", "success")
        return redirect(url_for("ref.anilox"))

    return render_template("referentiels/form_anilox.html", action="Ajouter", anilox=None)


@ref_bp.route("/anilox/<int:ani_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier_anilox(ani_id):
    ani = Anilox.query.filter_by(id=ani_id, client_id=current_user.id).first_or_404()

    if request.method == "POST":
        try:
            ani.lineature = float(request.form.get("lineature") or 0) or None
            ani.volume_cm3_m2 = float(request.form.get("volume_cm3_m2", ani.volume_cm3_m2))
            ani.coeff_transfert = float(request.form.get("coeff_transfert", ani.coeff_transfert))
        except ValueError:
            flash("Valeurs numériques invalides.", "danger")
        else:
            db.session.commit()
            flash("Anilox mis à jour.", "success")
            return redirect(url_for("ref.anilox"))

    return render_template("referentiels/form_anilox.html", action="Modifier", anilox=ani)


@ref_bp.route("/anilox/<int:ani_id>/supprimer", methods=["POST"])
@login_required
def supprimer_anilox(ani_id):
    ani = Anilox.query.filter_by(id=ani_id, client_id=current_user.id).first_or_404()
    db.session.delete(ani)
    db.session.commit()
    flash("Anilox supprimé.", "info")
    return redirect(url_for("ref.anilox"))


@ref_bp.route("/anilox/importer", methods=["POST"])
@login_required
def importer_anilox():
    fichier = request.files.get("fichier")
    if not fichier:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for("ref.anilox"))

    try:
        content = fichier.read()
        if fichier.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        df.columns = [c.strip().lower() for c in df.columns]
        ajoutes, ignores = 0, 0

        for _, row in df.iterrows():
            ref = str(row.get("reference", "")).strip().upper()
            try:
                volume = float(row.get("volume_cm3_m2", row.get("volume", 0)))
                coeff = float(row.get("coeff_transfert", row.get("coeff", 0.80)))
                lineature = float(row.get("lineature", 0)) or None
            except (ValueError, TypeError):
                ignores += 1
                continue

            if not ref or not volume:
                ignores += 1
                continue

            existing = Anilox.query.filter_by(client_id=current_user.id, reference=ref).first()
            if existing:
                ignores += 1
                continue

            db.session.add(Anilox(client_id=current_user.id, reference=ref,
                                  lineature=lineature, volume_cm3_m2=volume,
                                  coeff_transfert=coeff))
            ajoutes += 1

        db.session.commit()
        flash(f"Import terminé : {ajoutes} anilox ajouté(s), {ignores} ignoré(s).", "success")
    except Exception as e:
        flash(f"Erreur lors de l'import : {str(e)}", "danger")

    return redirect(url_for("ref.anilox"))


# ─── API JSON (pour le formulaire OF dynamique) ─────────────────────────────

@ref_bp.route("/api/encres")
@login_required
def api_encres():
    encres = Encre.query.filter_by(client_id=current_user.id).order_by(Encre.reference).all()
    return jsonify([{"id": e.id, "reference": e.reference, "nom": e.nom,
                     "densite": e.densite} for e in encres])


@ref_bp.route("/api/anilox")
@login_required
def api_anilox():
    anis = Anilox.query.filter_by(client_id=current_user.id).order_by(Anilox.reference).all()
    return jsonify([{"id": a.id, "reference": a.reference, "volume": a.volume_cm3_m2,
                     "coeff": a.coeff_transfert, "lineature": a.lineature} for a in anis])


@ref_bp.route("/api/configs")
@login_required
def api_configs():
    configs = ConfigMachine.query.filter_by(client_id=current_user.id).order_by(ConfigMachine.nom).all()
    return jsonify([{"id": c.id, "nom": c.nom, "stations": c.stations} for c in configs])
