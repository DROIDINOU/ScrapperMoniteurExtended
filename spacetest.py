from transformers import BertTokenizer, BertForTokenClassification
from transformers import pipeline
import numpy as np
import re

# Charger le modèle et le tokenizer de LegalBERT
tokenizer = BertTokenizer.from_pretrained('nlpaueb/legal-bert-small-uncased')
model = BertForTokenClassification.from_pretrained('nlpaueb/legal-bert-small-uncased')
nlp = pipeline('ner', model=model, tokenizer=tokenizer)

# Exemple de sortie brute du modèle
output = [
    {'entity': 'LABEL_0', 'score': np.float32(0.6955067), 'index': 144, 'word': 'par'},
    {'entity': 'LABEL_0', 'score': np.float32(0.5705638), 'index': 145, 'word': '##quet'},
    {'entity': 'LABEL_1', 'score': np.float32(0.52774566), 'index': 146, 'word': 'a'},
    {'entity': 'LABEL_0', 'score': np.float32(0.5057856), 'index': 147, 'word': '1000'},
    {'entity': 'LABEL_0', 'score': np.float32(0.5742476), 'index': 148, 'word': 'bru'},
    {'entity': 'LABEL_0', 'score': np.float32(0.5332069), 'index': 149, 'word': '##xel'},
    {'entity': 'LABEL_0', 'score': np.float32(0.5251167), 'index': 150, 'word': '##les'},
    {'entity': 'LABEL_0', 'score': np.float32(0.6682171), 'index': 151, 'word': ','},
    {'entity': 'LABEL_0', 'score': np.float32(0.636569), 'index': 152, 'word': 'place'},
    {'entity': 'LABEL_0', 'score': np.float32(0.772904), 'index': 153, 'word': 'po'},
    {'entity': 'LABEL_0', 'score': np.float32(0.5112881), 'index': 154, 'word': '##ela'},
    # Suite des tokens...
]

# Fonction pour transformer la sortie de LegalBERT en un texte compréhensible
def process_legalbert_output(output):
    tokens = []
    entities = []

    for item in output:
        # Nettoyer le token (l'index `##` dans les tokens est souvent utilisé pour signaler un morcellement de mots)
        word = item['word'].replace('##', '')
        entity = item['entity']

        # Si l'entité appartient à un groupe d'entités (par exemple, une organisation ou un nom), concatène avec le token précédent
        if entity != 'O':  # 'O' correspond à une entité non étiquetée
            if tokens and entity == entities[-1][0]:
                tokens[-1] = f"{tokens[-1]} {word}"  # concatène le mot au précédent
            else:
                tokens.append(word)
                entities.append((entity, word))
        else:
            tokens.append(word)

    # Retourne le texte traité
    return ' '.join(tokens), entities

# Appliquer le traitement sur la sortie de LegalBERT
text, entities = process_legalbert_output(output)

# Afficher le texte extrait
print("Texte traité :")
print(text)

# Afficher les entités extraites (nommées, etc.)
print("\nEntités extraites :")
for entity in entities:
    print(f"Type: {entity[0]}, Entité: {entity[1]}")
