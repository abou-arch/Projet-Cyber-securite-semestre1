# 8. Éthique et sécurité

*Rôle A.*

Travailler sur des malwares impose des précautions : ne jamais exposer une machine à du code
malveillant, ne pas diffuser d'outil ou d'information dangereux, et rester honnête sur ce que le
classifieur permet ou non. Cette section décrit les choix faits dans ce sens.

## 8.1 Un projet sans code malveillant

Le projet repose entièrement sur l'**analyse statique de caractéristiques déjà extraites**.
EMBER2024 ne contient aucun exécutable : chaque fichier y est décrit par une ligne JSON de
statistiques et de noms techniques. À aucun moment un binaire malveillant n'a été téléchargé,
stocké, ouvert ou exécuté.

Notre code renforce cette garantie : il **ne lit que du JSON** et n'analyse jamais de fichier
exécutable. Nous avons volontairement écarté le paquet officiel `thrember`, car il dépend de
bibliothèques d'analyse de fichiers PE (`pefile`, `signify`) dont nous n'avions pas besoin. Notre
réimplémentation de sa vectorisation ne fait que transformer des nombres et des noms en vecteur
(section 2.3).

## 8.2 Ce qui est téléchargé, et ce qui ne l'est pas

Le script de téléchargement ne récupère que ce dont le projet a besoin : les archives
`Win32_train.zip` et `Win32_test.zip`. Il ne télécharge jamais :

- les autres types de fichiers (Android, Linux, PDF) ;
- le « challenge set » et les modèles de référence ;
- le jeu complémentaire **EMBER2024-capa**, qui contient du code malveillant désassemblé. Il
  sort du cadre de sécurité du projet.

Limiter ce qui est téléchargé réduit aussi ce qui doit être stocké et protégé.

## 8.3 Données personnelles et confidentialité

Les fichiers d'EMBER2024 ont été soumis à VirusTotal, parfois par des particuliers ou des
entreprises. Le jeu ne contient pourtant **pas le contenu de ces fichiers** :

- les chaînes de caractères n'y figurent que sous forme de **statistiques** : nombre, longueur
  moyenne, distribution des caractères, nombre de chaînes qui contiennent une URL ou une adresse
  IP. Le texte lui-même n'y est pas ;
- les seuls noms présents sont **techniques** : bibliothèques et fonctions importées, sections,
  fonctions exportées ;
- chaque fichier est identifié par ses **empreintes** (`sha256`, `md5`…), qui ne révèlent pas son
  contenu.

Nous n'avons trouvé aucune donnée personnelle dans les features utilisées. Par prudence, les
données restent hors de git et hors des dossiers synchronisés dans le cloud (OneDrive, iCloud).

## 8.4 Les empreintes servent uniquement d'identifiants

Une empreinte `sha256` permet de retrouver le fichier correspondant sur des plateformes
d'analyse de malwares. La règle de l'équipe est stricte : **les empreintes servent uniquement à
identifier les lignes du jeu**. Elles ont servi par exemple à repérer les doublons (section 2.4).
Personne ne doit télécharger les binaires correspondants.

## 8.5 Intégrité et reproductibilité

- **Archives vérifiées.** Chaque archive est contrôlée par sa somme SHA-256 publiée par Hugging
  Face. Une archive corrompue ou modifiée est rejetée.
- **Préparation reproductible.** Les familles sont choisies sur le seul train, le tirage du
  plafond utilise une graine fixe, et les trois membres de l'équipe obtiennent les mêmes données
  avec les mêmes commandes.
- **Transparence sur les erreurs.** Le défaut des archives (lignes en double) a été détecté,
  corrigé et documenté, au lieu d'être ignoré : il aurait faussé les résultats (section 2.4).
- **Tests automatiques.** 33 tests vérifient la chaîne de préparation sur des données
  synthétiques, sans aucun vrai malware. L'un d'eux compare notre vectorisation à celle du code
  officiel, au bit près.

## 8.6 Double usage

Comprendre quelles caractéristiques permettent de reconnaître une famille (section 6) aide les
défenseurs. Mais cela pourrait aussi aider un attaquant à modifier ses fichiers pour échapper à
la détection. Nous limitons ce risque :

- l'analyse d'importance reste **descriptive** : elle explique les décisions du modèle, et ne
  propose aucune méthode pour les contourner ;
- les caractéristiques en jeu (entropie, imports, sections…) sont déjà largement décrites dans
  la littérature publique sur l'analyse statique ;
- le projet ne produit, ne modifie et ne teste aucun malware.

## 8.7 Limites d'usage du classifieur

Le classifieur est un **outil d'aide** au tri et à la priorisation. Il ne remplace pas l'analyse
d'un expert, et plusieurs limites interdisent de s'y fier seul :

- il ne connaît que 10 familles, alors que 58 % des malwares du test appartiennent à d'autres
  familles : il les rangerait à tort dans l'une des 10 (section 2.7) ;
- certaines étiquettes d'apprentissage sont peu sûres, en particulier wacatac (section 2.6) ;
- les malwares évoluent : un modèle doit être réévalué et réentraîné régulièrement
  (section 2.5).

Une erreur de famille peut orienter une réponse à incident dans la mauvaise direction. Les
résultats doivent donc toujours être accompagnés de leur niveau de confiance et de ces limites.

## 8.8 Licences et conditions d'utilisation

- **Vectorisation.** Elle reprend les constantes et la méthode du code officiel d'EMBER2024
  (`thrember`), distribué sous **licence Apache 2.0**. Le fichier `ember_features.py` le
  mentionne.
- **Jeu de données.** EMBER2024 est utilisé dans le cadre de la recherche et de l'enseignement,
  et cité [EMBER2024].
- **À vérifier avant la version finale :** la licence exacte du jeu de données, sur sa page
  Hugging Face.

## 8.9 Règles suivies par l'équipe

1. Travailler **uniquement** sur les features extraites d'EMBER2024.
2. Ne jamais télécharger ni exécuter un binaire à partir de son empreinte.
3. Ne pas utiliser EMBER2024-capa.
4. Garder les données hors de git et hors des dossiers synchronisés.
5. Présenter le classifieur avec ses limites, jamais comme un outil de décision automatique.
