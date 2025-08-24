import re
txt = ("COUR D 'APPEL DE BRUXELLES ... Dans l'affaire : Body Training Studio SRL, "
       "numéro d'entreprise 0644.840.954, dont le siège social ...")
pat = re.compile(r"(?i)dans\s*l['’]?\s*affaire\s*:?\s*(?P<nom>[^,\n\r]+?)\s*(?=,\s*(?:num(?:é|e)ro|n[°º])\s+d['’]?\s*entreprise\b)")
print(pat.search(txt).group("nom"))
# → Body Training Studio SRL