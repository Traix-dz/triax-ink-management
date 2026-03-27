"""
Analyse PDF par l'IA Anthropic.
Extrait les taux de couverture par couleur depuis une maquette flexo.
"""
import anthropic
import base64
import json
import os


def extraire_taux_couverture(pdf_path: str, couleurs: list[str]) -> dict:
    """
    Envoie le PDF à Claude Sonnet et retourne un dict {couleur: taux_pct}.

    Paramètres
    ----------
    pdf_path : chemin complet vers le fichier PDF uploadé
    couleurs : liste des noms de stations, ex. ["C","M","J","N","Blanc","Vernis"]

    Retour
    ------
    dict : {"C": 34.2, "M": 67.8, ...}
    Lève une exception si l'API échoue ou si la réponse n'est pas parsable.
    """
    client_api = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    couleurs_str = ", ".join(couleurs)

    prompt = f"""Tu es un expert en prépresse et en impression flexographique.
Analyse ce fichier PDF qui contient les séparations couleur d'une maquette d'emballage.

Ta mission : pour chacune des couleurs listées ci-dessous, détermine le taux de couverture moyen
sur la surface imprimable totale (en pourcentage, de 0 à 100).

Couleurs à analyser : {couleurs_str}

Règles :
- Un taux de 100% signifie que toute la surface imprimable est couverte par cette couleur.
- Analyse uniquement les zones imprimables, pas les marges ou repères.
- Si une couleur n'est pas présente dans le PDF, indique 0.
- Pour le Blanc et le Vernis, un taux de 100% est fréquent s'ils couvrent tout le fond.
- Pour les Pantone, évalue la couverture de cette teinte spécifique.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni après, sans balises markdown.
Format exact attendu (exemple) :
{{"C": 34.2, "M": 67.8, "J": 12.1, "N": 88.5, "Blanc": 100.0, "Vernis": 45.0}}

Les clés doivent correspondre exactement aux noms fournis : {couleurs_str}"""

    response = client_api.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()

    # Nettoyage au cas où le modèle ajouterait des backticks
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Réponse IA non parsable : {raw}\nErreur : {e}")

    # S'assurer que toutes les couleurs sont présentes
    for couleur in couleurs:
        if couleur not in result:
            result[couleur] = 0.0
        else:
            result[couleur] = float(result[couleur])

    return result
