import os

# Ce script remplace tous les guillemets typographiques
# par des guillemets droits standard dans tes fichiers HTML et Python

REMPLACEMENTS = [
    ('\u201c', '"'),
    ('\u201d', '"'),
    ('\u2018', "'"),
    ('\u2019', "'"),
    ('\u00ab', '"'),
    ('\u00bb', '"'),
    ('\u2013', '-'),
    ('\u2014', '-'),
]

FICHIERS = [
    'templates/agent.html',
    'templates/historique.html',
    'templates/base.html',
    'templates/index.html',
    'templates/login.html',
    'app.py',
]

for fichier in FICHIERS:
    if not os.path.exists(fichier):
        print('IGNORE (introuvable): ' + fichier)
        continue

    with open(fichier, 'r', encoding='utf-8') as f:
        contenu = f.read()

    contenu_original = contenu
    for mauvais, bon in REMPLACEMENTS:
        contenu = contenu.replace(mauvais, bon)

    if contenu != contenu_original:
        with open(fichier, 'w', encoding='utf-8') as f:
            f.write(contenu)
        print('CORRIGE: ' + fichier)
    else:
        print('OK (rien a corriger): ' + fichier)

print('')
print('Termine. Tu peux relancer python app.py')