# 8. Éthique et sécurité

*Rôle A. Section à rédiger en Phase 3 : points à développer.*

- **Données statiques uniquement** : EMBER2024 ne contient que des caractéristiques extraites,
  aucun exécutable. Aucun code malveillant n'a été téléchargé, stocké ou exécuté.
- **Exclusion de EMBER2024-capa**, qui contient du code malveillant désassemblé, et des autres
  fichiers inutiles au projet : jamais téléchargés.
- **Le code ne lit que du JSON** et n'analyse jamais de fichier exécutable.
- **Les `sha256` servent uniquement d'identifiants** : consigne de ne jamais télécharger les
  binaires correspondants depuis une plateforme d'analyse de malwares.
- **Hygiène des données** : données hors des dossiers synchronisés (OneDrive, iCloud) et hors
  de git ; archives vérifiées par SHA-256.
- **Usage du classifieur** : outil d'aide à l'analyse (tri, priorisation), qui ne remplace pas
  l'analyste ; risques d'erreur (monde fermé, section 7).
- **Licences** : EMBER2024 et le code `thrember` (licence Apache 2.0) dont notre vectorisation
  s'inspire.
