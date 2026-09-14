# Smart Fridge — panneau administrateur

## Ajouts

- Dashboard administrateur modernisé.
- Statistiques utilisateurs, admins, produits, produits bientôt périmés et produits périmés.
- Nombre de nouveaux comptes sur 7 et 30 jours.
- Graphique des créations de comptes sur les 7 derniers jours.
- Répartition des produits par catégorie.
- Alertes automatiques pour les produits périmés / bientôt périmés et les nouveaux comptes.
- Actions rapides.
- Journal d'activité avec les dernières actions administrateur.
- **Création de compte automatiquement enregistrée dans `admin_logs`**, y compris les comptes créés depuis le formulaire d'inscription normal.
- Les créations automatiques sont marquées avec `admin_user_id = 0` et affichées comme venant du « Système ».
- Gestion des utilisateurs, modification du profil, rôle admin, suppression et réinitialisation du mot de passe.
- Suppression des produits depuis l'administration.
- Interface responsive et compatible avec le mode sombre.

## Important après remplacement des fichiers

La table `admin_logs` doit être créée par `Base.metadata.create_all(bind=engine)` au démarrage de l'application. Si ton projet appelle déjà cette fonction au démarrage, aucune commande SQL supplémentaire n'est nécessaire.

Si ton application possède une migration de base de données, ajoute également la table `admin_logs` à cette migration.

## Création du compte administrateur

```bash
python create_admin.py
```

Le mot de passe ne s'affiche pas pendant la saisie dans le terminal : tape-le normalement puis appuie sur Entrée.

Puis ouvre `/admin` après t'être connecté avec un compte administrateur.
