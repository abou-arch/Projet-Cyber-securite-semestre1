# 1. Introduction et contexte

*Rôle A.*

## 1.1 Contexte

Les logiciels malveillants (*malwares*) sont produits en très grand nombre, mais la plupart ne
sont pas entièrement nouveaux. Ce sont des variantes de quelques **familles** : des programmes
issus d'un même code source, ou d'un même outil, et qui partagent un comportement, des techniques
et souvent les mêmes auteurs. Connaître la famille d'un fichier malveillant est utile à
plusieurs titres :

- **réagir** : la famille indique ce que le malware cherche à faire (voler des identifiants
  bancaires, télécharger d'autres malwares, chiffrer des fichiers…) et donc quelles mesures
  prendre ;
- **prioriser** : face à un grand volume d'alertes, les analystes traitent d'abord les familles
  les plus dangereuses ;
- **suivre les campagnes** : regrouper les fichiers par famille permet de voir apparaître,
  évoluer et disparaître une campagne d'attaque.

Les antivirus donnent chacun un nom à ce qu'ils détectent, mais ces noms ne s'accordent pas
toujours, et certains sont génériques. Les jeux de données de recherche s'appuient donc sur des
outils qui combinent les avis de nombreux antivirus pour attribuer une famille et une confiance
à chaque fichier, comme ClarAVy [ClarAVy].

## 1.2 Analyse statique et apprentissage automatique

Un fichier peut être analysé de deux façons :

- l'**analyse dynamique** l'exécute dans un environnement isolé et observe son comportement.
  Elle est riche, mais lente, coûteuse, et demande de manipuler du code malveillant actif ;
- l'**analyse statique** examine le fichier **sans l'exécuter** : sa structure, ses en-têtes,
  les fonctions qu'il importe, les chaînes de caractères qu'il contient, la répartition de ses
  octets. Elle est rapide et sans danger, mais elle peut être trompée par le *packing* (code
  compressé ou chiffré) et l'obfuscation.

L'apprentissage automatique permet d'exploiter ces caractéristiques statiques à grande échelle.
Le jeu EMBER [EMBER2018] a popularisé cette approche pour la détection binaire (bénin ou
malveillant) des exécutables Windows. EMBER2024 [EMBER2024] en est la version récente : il
couvre 3,2 millions de fichiers soumis entre 2023 et 2024, ajoute une étiquette de famille à
chaque malware, et sépare l'apprentissage et le test dans le temps pour mesurer la robustesse
des modèles face à l'évolution des malwares.

## 1.3 Problématique et objectifs

Nous cherchons à **prédire la famille d'un malware Windows à partir de ses seules
caractéristiques statiques**, puis à **expliquer quelles caractéristiques comptent le plus**
dans cette décision. Le projet utilise uniquement des features déjà extraites par EMBER2024 :
aucun exécutable n'est téléchargé, manipulé ou exécuté.

Nous travaillons sur les exécutables Win32 et sur les **10 familles** les plus fréquentes du
jeu d'apprentissage. Chaque fichier y est décrit par **2 568 features**. Les modèles sont
construits avec scikit-learn [scikit-learn].

Nous répondons à trois questions :

1. **Performance** : avec quelle qualité peut-on reconnaître la famille d'un malware à partir
   de ses features statiques ?
2. **Robustesse dans le temps** : un modèle appris sur une année de données reste-t-il fiable
   sur les malwares des semaines suivantes ?
3. **Interprétation** : quelles caractéristiques (imports, sections, entropie, chaînes…) le
   modèle utilise-t-il, et qu'apprennent-elles sur les familles ?

## 1.4 Démarche et contributions

Le travail s'est organisé en trois volets :

- **Données** (rôle A) : une chaîne de préparation reproductible, qui télécharge et vérifie les
  archives, sélectionne les familles et vectorise les fichiers. Elle repère aussi un défaut des
  archives (chaque ligne y figure deux fois) et le corrige. Une exploration décrit le jeu
  obtenu.
- **Modèles** (rôle B) : l'entraînement et l'évaluation de plusieurs classifieurs, avec des
  métriques adaptées au fort déséquilibre du jeu de test.
- **Importance des features** (rôle C) : la mesure de l'importance des features et leur
  interprétation. Un outil commun (`hash_lookup`) retrouve les noms réels derrière les colonnes
  hachées.

## 1.5 Plan du rapport

- La **section 2** présente les données et leur préparation.
- La **section 3** décrit ce que mesurent les 2 568 features.
- La **section 4** détaille la méthodologie : modèles, validation, métriques.
- La **section 5** présente les résultats, dont l'effet de la dérive temporelle.
- La **section 6** analyse l'importance des features.
- La **section 7** discute les limites du travail.
- La **section 8** expose les précautions d'éthique et de sécurité.
- La **section 9** conclut.
