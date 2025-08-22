import re

def decode_nrn(nrn: str):
    """
    Décode un numéro de registre national belge en date de naissance + sexe.
    Retourne (YYYY-MM-DD, sexe).
    """
    nrn = re.sub(r"\D", "", nrn)  # garder seulement les chiffres
    if len(nrn) != 11:
        return None

    base = nrn[:9]    # YYMMDDXXX
    cle = int(nrn[9:])  # 2 chiffres finaux

    # Test siècle 1900
    if (97 - (int(base) % 97)) == cle:
        year = 1900 + int(base[:2])
    else:
        year = 2000 + int(base[:2])

    month = int(base[2:4])
    day = int(base[4:6])

    # Sexe = bloc XXX pair = femme / impair = homme
    sexe = "M" if int(base[6:9]) % 2 == 1 else "F"

    return f"{year:04d}-{month:02d}-{day:02d}", sexe


# Exemple
print(decode_nrn("38.11.23-014.74"))
# -> ('1938-11-23', 'F')




