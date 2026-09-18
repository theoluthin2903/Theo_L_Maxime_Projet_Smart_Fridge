# 🧊 Smart Fridge & Nutrition Coach

Application web permettant de gérer le contenu de son réfrigérateur, de suivre les dates de péremption, de recevoir des alertes, et d'obtenir des informations nutritionnelles et des idées de recettes à partir des produits disponibles.

Projet réalisé par **Théo L.** et **Maxime**.

## ✨ Fonctionnalités

- **Authentification** des utilisateurs (inscription, connexion, gestion de profil).
- **Gestion du frigo** : ajout, modification et suppression des produits stockés.
- **Catalogue de produits** avec récupération de données nutritionnelles (via l'API USDA) et de recettes associées (via TheMealDB).
- **Alertes** automatiques pour les produits périmés ou bientôt périmés.
- **Coach nutrition** basé sur les produits présents dans le frigo.
- **Panneau d'administration** avec :
  - statistiques (utilisateurs, admins, produits, produits périmés/bientôt périmés) ;
  - graphique des créations de comptes sur les 7 derniers jours ;
  - répartition des produits par catégorie ;
  - journal d'activité (`admin_logs`) ;
  - gestion des utilisateurs (rôle, suppression, réinitialisation du mot de passe) ;
  - actions rapides et alertes automatiques.
- Interface **responsive**, compatible **mode sombre**.

## 🛠️ Stack technique

- **Backend** : [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **ORM / Base de données** : **Supabase**
- **Frontend** : pages rendues côté serveur, mise en forme avec Tailwind CSS
- **Authentification** : middleware + support JWT (Bearer) documenté dans le schéma OpenAPI
- **APIs externes** : USDA FoodData Central (données nutritionnelles), TheMealDB (recettes)

## 📁 Structure du projet

```
.
├── app/                 # Code applicatif (routers, pages web, base de données, logique métier)
├── routers/             # Routes de l'API
├── static/              # Fichiers statiques (CSS, JS, images)
├── main.py              # Point d'entrée de l'application FastAPI
├── create_admin.py      # Script de création d'un compte administrateur
├── migrate_sqlite_to_supabase.py   # Script de migration SQLite → Supabase
├── test_supabase_connection.py     # Script de test de connexion à Supabase
├── requirements-supabase.txt       # Dépendances spécifiques à Supabase (psycopg, python-dotenv)
└── Project Brief Smart Fridge & Nutrition Coach.pdf   # Cahier des charges du projet
```

## 🚀 Installation

### Prérequis

- Python 3.10+
- pip

### Étapes

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/theoluthin2903/Theo_L_Maxime_Projet_Smart_Fridge.git
   cd Theo_L_Maxime_Projet_Smart_Fridge
   ```

2. Créer et activer un environnement virtuel :
   ```bash
   python -m venv venv
   source venv/bin/activate   # Sur Windows : venv\Scripts\activate
   ```

3. Installer les dépendances du projet (voir `requirements.txt` à la racine) :
   ```bash
   pip install -r requirements.txt
   ```

4. (Optionnel) Si vous souhaitez utiliser **Supabase** comme base de données au lieu de SQLite, installez également :
   ```bash
   pip install -r requirements-supabase.txt
   ```
   puis configurez vos variables d'environnement (ex. `DATABASE_URL`) dans un fichier `.env` à la racine du projet.

5. Lancer l'application :
   ```bash
   uvicorn main:app --reload
   ```

   L'application est alors accessible sur [http://localhost:8000](http://localhost:8000).

## 👑 Créer un compte administrateur

```bash
python create_admin.py
```

Le mot de passe ne s'affiche pas pendant la saisie dans le terminal : tapez-le normalement puis appuyez sur Entrée.

Connectez-vous ensuite avec ce compte et rendez-vous sur `/admin` pour accéder au panneau d'administration.

## ☁️ Migration vers Supabase

Le projet peut fonctionner avec SQLite (par défaut) ou avec une base PostgreSQL hébergée sur Supabase.

1. Configurez votre connexion Supabase dans `.env`.
2. Testez la connexion :
   ```bash
   python test_supabase_connection.py
   ```
3. Migrez vos données existantes depuis SQLite :
   ```bash
   python migrate_sqlite_to_supabase.py
   ```

> ℹ️ La table `admin_logs` est créée automatiquement via `Base.metadata.create_all(bind=engine)` au démarrage de l'application. Si votre projet dispose déjà d'un système de migration, pensez à y ajouter cette table.

## 📄 Documentation du projet

Le cahier des charges complet est disponible dans le fichier [`Project Brief Smart Fridge & Nutrition Coach.pdf`](./Project%20Brief%20Smart%20Fridge%20%26%20Nutrition%20Coach%20(1).pdf).

## 👥 Auteurs

- Théo LUTHIN
- Maxime HEINZ