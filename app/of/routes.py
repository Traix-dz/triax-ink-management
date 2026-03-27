from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, current_app)
from flask_login import login_required, current_user
from app import db
from app.models import OF, StationCouleur, Encre, Anilox, ConfigMachine
from app.utils.ink_calculator import calculer_surface, calculer_station
from app.utils.pdf_analyser import extraire_taux_couverture
from datetime import date, datetime
import os
import uuid

of_bp = Blueprint("of", __name__, url_prefix="/of")


@of_bp.route("/")
@login_required
def dashboard():
    ofs = (OF.query
           .filter_by(client_id=current_user.id)
           .order_by(OF.created_at.desc())
           .limit(20).all())
    return render_template("of/dashboard.html", ofs=ofs)


@of_bp.route("/historique")
@login_required
def historique():
    page = request.args.get("page", 1, type=int)
    ofs = (OF.query
           .filter_by(client_id=current_user.id)
           .order_by(OF.created_at.desc())
           .paginate(page=page, per_page=25))
    return render_template("of/historique.html", ofs=ofs)


@of_bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def nouveau():
    encres = Encre.query.filter_by(client_id=current_user.id).order_by(Encre.reference).all()
    anilox_list = Anilox.query.filter_by(client_id=current_user.id).order_by(Anilox.reference).all()
    configs = ConfigMachine.query.filter_by(client_id=current_user.id).order_by(ConfigMachine.nom).all()

    return render_template("of/nouveau.html",
                           encres=encres,
                           anilox_list=anilox_list,
                           configs=configs,
                           today=date.today().isoformat(),
                           marge=current_user.marge_securite_pct)


@of_bp.route("/sauvegarder", methods=["POST"])
@login_required
def sauvegarder():
    """Reçoit le formulaire complet de l'OF et sauvegarde en DB."""
    try:
        # ── En-tête OF ──────────────────────────────────────────────────────
        ref_of = request.form.get("reference_of", "").strip().upper()
        nom_produit = request.form.get("nom_produit", "").strip()
        date_of_str = request.form.get("date_of", "")
        type_tirage = request.form.get("type_tirage", "BOBINE").upper()

        if not ref_of or not date_of_str:
            flash("Référence OF et date sont obligatoires.", "danger")
            return redirect(url_for("of.nouveau"))

        date_of = datetime.strptime(date_of_str, "%Y-%m-%d").date()

        # ── Surface ─────────────────────────────────────────────────────────
        try:
            if type_tirage == "BOBINE":
                laize = float(request.form.get("laize_m", 0))
                metrage = float(request.form.get("metrage_m", 0))
                surface = calculer_surface("BOBINE", laize=laize, metrage=metrage)
                hauteur = largeur = nb_tirages = None
            else:
                hauteur = float(request.form.get("hauteur_m", 0))
                largeur = float(request.form.get("largeur_m", 0))
                nb_tirages = int(request.form.get("nb_tirages", 0))
                surface = calculer_surface("FEUILLE", hauteur=hauteur, largeur=largeur, nb_tirages=nb_tirages)
                laize = metrage = None
        except (ValueError, ZeroDivisionError) as e:
            flash(f"Erreur dans les dimensions : {e}", "danger")
            return redirect(url_for("of.nouveau"))

        # ── Marge ───────────────────────────────────────────────────────────
        try:
            marge = float(request.form.get("marge_pct", current_user.marge_securite_pct))
        except ValueError:
            marge = current_user.marge_securite_pct

        # ── Création de l'OF ─────────────────────────────────────────────────
        nouvel_of = OF(
            client_id=current_user.id,
            reference_of=ref_of,
            nom_produit=nom_produit,
            date_of=date_of,
            type_tirage=type_tirage,
            laize_m=laize,
            metrage_m=metrage,
            hauteur_m=hauteur,
            largeur_m=largeur,
            nb_tirages=nb_tirages,
            surface_m2=surface,
            taux_source="MANUEL",
            marge_appliquee_pct=marge,
            statut="CALCULE",
        )
        db.session.add(nouvel_of)
        db.session.flush()  # pour obtenir nouvel_of.id

        # ── Stations couleur ─────────────────────────────────────────────────
        # Le formulaire envoie des listes : couleur[], anilox_id[], volume[], coeff[], taux[], encre_id[]
        couleurs = request.form.getlist("couleur[]")
        anilox_ids = request.form.getlist("anilox_id[]")
        volumes = request.form.getlist("anilox_volume[]")
        coeffs = request.form.getlist("anilox_coeff[]")
        taux_list = request.form.getlist("taux_couverture[]")
        encre_ids = request.form.getlist("encre_id[]")
        encre_refs = request.form.getlist("encre_ref[]")

        for i, couleur in enumerate(couleurs):
            couleur = couleur.strip()
            if not couleur:
                continue

            try:
                volume = float(volumes[i]) if i < len(volumes) else 0
                coeff = float(coeffs[i]) if i < len(coeffs) else 0.8
                taux = float(taux_list[i]) if i < len(taux_list) and taux_list[i] else None
            except (ValueError, IndexError):
                continue

            encre_id = None
            encre_ref_m = None
            densite = current_user.densite_encre

            if i < len(encre_ids) and encre_ids[i]:
                try:
                    eid = int(encre_ids[i])
                    encre_obj = Encre.query.filter_by(id=eid, client_id=current_user.id).first()
                    if encre_obj:
                        encre_id = eid
                        densite = encre_obj.densite
                except ValueError:
                    pass
            elif i < len(encre_refs) and encre_refs[i]:
                encre_ref_m = encre_refs[i].strip()

            anilox_id = None
            anilox_ref_m = None
            if i < len(anilox_ids) and anilox_ids[i]:
                try:
                    anilox_id = int(anilox_ids[i])
                except ValueError:
                    anilox_ref_m = anilox_ids[i]

            # Calcul
            masse_nette = masse_marge = None
            if taux is not None and volume and coeff:
                res = calculer_station(volume, coeff, densite, taux, surface, marge)
                masse_nette = res["masse_nette_kg"]
                masse_marge = res["masse_avec_marge_kg"]

            station = StationCouleur(
                of_id=nouvel_of.id,
                ordre=i,
                nom_couleur=couleur,
                encre_id=encre_id,
                encre_ref_manuelle=encre_ref_m,
                densite_utilisee=densite,
                anilox_id=anilox_id,
                anilox_ref_manuelle=anilox_ref_m,
                anilox_volume=volume,
                anilox_coeff=coeff,
                taux_couverture_pct=taux,
                masse_nette_kg=masse_nette,
                masse_avec_marge_kg=masse_marge,
            )
            db.session.add(station)

        db.session.commit()
        flash(f"OF « {ref_of} » sauvegardé avec succès.", "success")
        return redirect(url_for("of.voir", of_id=nouvel_of.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la sauvegarde : {str(e)}", "danger")
        return redirect(url_for("of.nouveau"))


@of_bp.route("/<int:of_id>")
@login_required
def voir(of_id):
    ordre_fab = OF.query.filter_by(id=of_id, client_id=current_user.id).first_or_404()
    stations = ordre_fab.stations.all()
    total_nette = sum(s.masse_nette_kg or 0 for s in stations)
    total_marge = sum(s.masse_avec_marge_kg or 0 for s in stations)
    return render_template("of/voir.html", of=ordre_fab, stations=stations,
                           total_nette=round(total_nette, 3),
                           total_marge=round(total_marge, 3))


@of_bp.route("/<int:of_id>/supprimer", methods=["POST"])
@login_required
def supprimer(of_id):
    ordre_fab = OF.query.filter_by(id=of_id, client_id=current_user.id).first_or_404()
    ref = ordre_fab.reference_of
    db.session.delete(ordre_fab)
    db.session.commit()
    flash(f"OF « {ref} » supprimé.", "info")
    return redirect(url_for("of.dashboard"))


# ─── Analyse IA ─────────────────────────────────────────────────────────────

@of_bp.route("/analyser-pdf", methods=["POST"])
@login_required
def analyser_pdf():
    """Reçoit un PDF + liste de couleurs, retourne les taux via l'IA."""
    if current_user.quota_restant <= 0:
        return jsonify({"error": "Quota d'analyses IA épuisé. Contactez Triax pour recharger."}), 403

    pdf = request.files.get("pdf")
    couleurs_str = request.form.get("couleurs", "")

    if not pdf or not couleurs_str:
        return jsonify({"error": "PDF et liste de couleurs requis."}), 400

    couleurs = [c.strip() for c in couleurs_str.split(",") if c.strip()]
    if not couleurs:
        return jsonify({"error": "Aucune couleur spécifiée."}), 400

    # Sauvegarde temporaire du PDF
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(upload_dir, filename)
    pdf.save(filepath)

    try:
        taux = extraire_taux_couverture(filepath, couleurs)
        current_user.consommer_quota()
        return jsonify({"taux": taux, "quota_restant": current_user.quota_restant})
    except Exception as e:
        return jsonify({"error": f"Erreur d'analyse : {str(e)}"}), 500
    finally:
        # Nettoyage du fichier temporaire
        if os.path.exists(filepath):
            os.remove(filepath)


# ─── Config machine ─────────────────────────────────────────────────────────

@of_bp.route("/sauvegarder-config", methods=["POST"])
@login_required
def sauvegarder_config():
    """Sauvegarde une configuration de stations pour réutilisation."""
    data = request.get_json()
    nom = data.get("nom", "").strip()
    stations = data.get("stations", [])

    if not nom or not stations:
        return jsonify({"error": "Nom et stations requis."}), 400

    config = ConfigMachine(client_id=current_user.id, nom=nom)
    config.stations = stations
    db.session.add(config)
    db.session.commit()
    return jsonify({"success": True, "id": config.id, "nom": config.nom})
