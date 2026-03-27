"""
Moteur de calcul de consommation d'encre en flexographie.
Toutes les fonctions sont pures (sans dépendance à la DB).
"""


def calculer_surface(type_tirage, laize=None, metrage=None,
                     hauteur=None, largeur=None, nb_tirages=None):
    """
    Calcule la surface totale imprimée en m².

    Bobine  : laize (m) × métrage (m)
    Feuille : hauteur (m) × largeur (m) × nb_tirages
    """
    if type_tirage == "BOBINE":
        if not (laize and metrage):
            raise ValueError("Laize et métrage requis pour un tirage bobine.")
        return round(float(laize) * float(metrage), 4)
    elif type_tirage == "FEUILLE":
        if not (hauteur and largeur and nb_tirages):
            raise ValueError("Hauteur, largeur et nombre de tirages requis pour un tirage feuille.")
        return round(float(hauteur) * float(largeur) * int(nb_tirages), 4)
    else:
        raise ValueError(f"Type de tirage inconnu : {type_tirage}")


def calculer_station(volume_anilox, coeff_transfert, densite_encre,
                     taux_couverture_pct, surface_m2, marge_pct=10.0):
    """
    Calcule la consommation d'encre pour une station couleur.

    Paramètres
    ----------
    volume_anilox      : float — volume de l'anilox en cm³/m²
    coeff_transfert    : float — coefficient de transfert réel (0.0 à 1.0)
    densite_encre      : float — densité de l'encre en kg/L
                         (UV ≈ 1.1 / Eau ≈ 1.0 / Solvant ≈ 0.9)
    taux_couverture_pct: float — taux de couverture en % (0 à 100)
    surface_m2         : float — surface totale imprimée en m²
    marge_pct          : float — pourcentage de sécurité à ajouter

    Retour
    ------
    dict avec :
        volume_encre_cm3   : volume d'encre déposée (cm³)
        masse_nette_kg     : masse exacte calculée (kg)
        masse_avec_marge_kg: masse recommandée à préparer/commander (kg)
        marge_pct          : marge appliquée (%)
    """
    volume_anilox = float(volume_anilox)
    coeff_transfert = float(coeff_transfert)
    densite_encre = float(densite_encre)
    taux_couverture_pct = float(taux_couverture_pct)
    surface_m2 = float(surface_m2)
    marge_pct = float(marge_pct)

    # Volume d'encre effectivement déposé (cm³)
    # = volume_anilox [cm³/m²] × coeff_transfert × (couverture/100) × surface [m²]
    volume_encre_cm3 = volume_anilox * coeff_transfert * (taux_couverture_pct / 100.0) * surface_m2

    # Conversion cm³ → kg via densité (1 cm³ = 0.001 L, densité en kg/L)
    masse_nette_kg = (volume_encre_cm3 * densite_encre) / 1000.0

    # Ajout de la marge de sécurité
    masse_avec_marge_kg = masse_nette_kg * (1.0 + marge_pct / 100.0)

    return {
        "volume_encre_cm3": round(volume_encre_cm3, 2),
        "masse_nette_kg": round(masse_nette_kg, 3),
        "masse_avec_marge_kg": round(masse_avec_marge_kg, 3),
        "marge_pct": marge_pct,
    }


def calculer_of_complet(stations_data, surface_m2, marge_pct=10.0):
    """
    Calcule toutes les stations d'un OF.

    stations_data : liste de dicts avec clés :
        nom_couleur, anilox_volume, anilox_coeff, densite_encre, taux_couverture_pct

    Retourne une liste de résultats + totaux.
    """
    resultats = []
    total_nette = 0.0
    total_marge = 0.0

    for station in stations_data:
        if station.get("taux_couverture_pct") is None:
            continue
        res = calculer_station(
            volume_anilox=station["anilox_volume"],
            coeff_transfert=station["anilox_coeff"],
            densite_encre=station["densite_encre"],
            taux_couverture_pct=station["taux_couverture_pct"],
            surface_m2=surface_m2,
            marge_pct=marge_pct,
        )
        res["nom_couleur"] = station["nom_couleur"]
        resultats.append(res)
        total_nette += res["masse_nette_kg"]
        total_marge += res["masse_avec_marge_kg"]

    return {
        "stations": resultats,
        "total_nette_kg": round(total_nette, 3),
        "total_avec_marge_kg": round(total_marge, 3),
    }
