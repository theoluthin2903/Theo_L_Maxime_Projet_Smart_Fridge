# Panneau administrateur Smart Fridge

Le panneau `/admin` a été amélioré avec :

- tableau de bord avec statistiques utilisateurs / produits / expirations ;
- recherche d'utilisateurs ;
- modification des profils ;
- attribution/retrait du rôle administrateur ;
- suppression d'un utilisateur et de ses produits ;
- suppression des produits depuis l'administration ;
- réinitialisation du mot de passe d'un utilisateur ;
- journal des actions administratives ;
- interface responsive et compatible mode sombre.

## Lancer le projet

Depuis le dossier du projet :

```bash
python create_admin.py
```

Le mot de passe n'est volontairement pas affiché dans le terminal pendant la saisie : tape-le normalement puis appuie sur Entrée.

Puis lance l'application avec la commande habituelle de ton projet (par exemple `uvicorn main:app --reload` si c'est celle que tu utilises).

Connecte-toi avec le compte administrateur puis ouvre `/admin`.

## Base de données

La table `admin_logs` est créée automatiquement par `Base.metadata.create_all(...)` au démarrage.
