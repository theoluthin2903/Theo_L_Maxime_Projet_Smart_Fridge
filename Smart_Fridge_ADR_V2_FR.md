# Smart Fridge — Registre des décisions d’architecture (ADR)

## ADR-001 — Backend Python et FastAPI

### Contexte précis

Le projet doit exposer des parcours web et des traitements serveur pour les comptes, le frigo, les recettes et le suivi nutritionnel.

### Options réalistes

- **Option retenue :** Conserver Python avec FastAPI comme socle HTTP, en séparant routes, logique métier et accès aux données.
- **Autres options :** Flask ; Django ; backend JavaScript/Node.js.

### Choix et justification

Python permet de partager les traitements métier ; FastAPI fournit un routage explicite et des dépendances. Ce choix correspond à la structure constatée.

### Avantages et limites

- **Avantages :** Python permet de partager les traitements métier ; FastAPI fournit un routage explicite et des dépendances. Ce choix correspond à la structure constatée.
- **Limites / risques :** La logique web doit rester découpée en modules ; prévoir des tests de routes, la validation des entrées et une documentation des endpoints.

### Conditions de réexamen

Si le backend doit exposer une API publique, supporter une charge nettement plus élevée ou si le coût de maintenance des routes devient excessif.

### Vérification concrète

Démarrer le serveur et vérifier que les routes de connexion, frigo et planning répondent ; exécuter les tests de routes disponibles.

### Code de référence

`app/web/routes.py` · `main.py` · `app/routers/auth.py`

---

## ADR-002 — Supabase PostgreSQL pour la persistance

### Contexte précis

Les données des utilisateurs et des repas doivent être conservées au-delà des sessions et accessibles par les développeurs depuis plusieurs postes.

### Options réalistes

- **Option retenue :** Utiliser PostgreSQL hébergé via Supabase, avec une URL de connexion fournie par configuration.
- **Autres options :** SQLite local ; PostgreSQL auto-hébergé ; MySQL.

### Choix et justification

Une base distante facilite le travail à plusieurs et offre les fonctions relationnelles de PostgreSQL. La présence du script de migration confirme une transition depuis SQLite.

### Avantages et limites

- **Avantages :** Une base distante facilite le travail à plusieurs et offre les fonctions relationnelles de PostgreSQL. La présence du script de migration confirme une transition depuis SQLite.
- **Limites / risques :** Dépendance à la connectivité et au service distant ; sécuriser les secrets, sauvegarder les données et gérer les évolutions de schéma par migrations.

### Conditions de réexamen

Si les coûts Supabase, les besoins hors ligne, la résidence des données ou les limites de connexion changent.

### Vérification concrète

Contrôler la connexion avec la configuration locale, puis vérifier qu’une donnée de test persiste après redémarrage.

### Code de référence

`app/db/database.py` · `app/db/models.py` · `migrate_sqlite_to_supabase.py`

---

## ADR-003 — SQLAlchemy pour les modèles et les accès SQL

### Contexte précis

Le système gère plusieurs entités liées : utilisateurs, inventaire, consommations, planification et notifications.

### Options réalistes

- **Option retenue :** Représenter les tables sous forme de modèles SQLAlchemy et utiliser des sessions de base de données.
- **Autres options :** SQL écrit manuellement ; autre ORM ; accès direct au pilote PostgreSQL.

### Choix et justification

Les modèles centralisent la structure des données et les relations ; les requêtes restent intégrées au code Python.

### Avantages et limites

- **Avantages :** Les modèles centralisent la structure des données et les relations ; les requêtes restent intégrées au code Python.
- **Limites / risques :** Garder des transactions explicites, fermer les sessions, surveiller les requêtes et utiliser un outil de migration pour les modifications de tables existantes.

### Conditions de réexamen

Si les changements de schéma deviennent fréquents, si les performances des requêtes se dégradent ou si un autre mode de stockage est introduit.

### Vérification concrète

Créer puis relire un enregistrement de test ; vérifier la fermeture des sessions et les migrations lors d’une modification de table.

### Code de référence

`app/db/models.py` · `app/db/database.py`

---

## ADR-004 — API externe TheMealDB pour les recettes

### Contexte précis

L’application doit proposer des idées de repas sans maintenir manuellement un catalogue exhaustif.

### Options réalistes

- **Option retenue :** Récupérer des recettes depuis un service externe, avec mise en forme et enrichissement dans l’application.
- **Autres options :** Catalogue local ; saisie manuelle ; autre fournisseur de recettes.

### Choix et justification

Le recours à un catalogue externe accélère l’accès aux recettes ; les adaptations en français et les estimations nutritionnelles relèvent du code de l’application.

### Avantages et limites

- **Avantages :** Le recours à un catalogue externe accélère l’accès aux recettes ; les adaptations en français et les estimations nutritionnelles relèvent du code de l’application.
- **Limites / risques :** Gérer les erreurs réseau, limites de requêtes et variations de données ; prévoir des valeurs de repli et distinguer les estimations nutritionnelles des valeurs garanties.

### Conditions de réexamen

Si TheMealDB devient indisponible, change ses conditions d’utilisation ou ne fournit plus assez de recettes adaptées.

### Vérification concrète

Afficher une recette connue et tester le comportement lorsque le service externe est indisponible.

### Code de référence

`app/web/data.py` · `app/web/pages/products.py` · `app/web/pages/planner.py`

---

## ADR-005 — Authentification et autorisation côté serveur

### Contexte précis

Le frigo, le profil et la nutrition sont personnels ; certaines fonctions administratives exigent des droits distincts.

### Options réalistes

- **Option retenue :** Gérer les identités et les contrôles d’accès côté serveur, avec stockage de mots de passe sous forme hachée et mécanismes de session/jeton selon les routes.
- **Autres options :** Aucune authentification ; authentification déléguée à un fournisseur externe ; sessions uniquement côté client.

### Choix et justification

Les modules de sécurité, de JWT, de dépendances et d’administration sont présents dans le projet ; la validation doit être réalisée sur chaque opération sensible.

### Avantages et limites

- **Avantages :** Les modules de sécurité, de JWT, de dépendances et d’administration sont présents dans le projet ; la validation doit être réalisée sur chaque opération sensible.
- **Limites / risques :** Vérifier l’expiration des sessions, les attributs des cookies, la protection CSRF selon les formulaires, la limitation des tentatives et l’isolation des données par utilisateur.

### Conditions de réexamen

Si les exigences de sécurité évoluent, si un incident survient ou si une authentification tierce est envisagée.

### Vérification concrète

Vérifier qu’un utilisateur non connecté ne peut pas accéder aux données privées et qu’un compte non administrateur ne peut pas ouvrir les opérations admin.

### Code de référence

`app/core/security.py` · `app/core/jwt.py` · `app/core/dependencies.py` · `app/core/admin.py` · `app/routers/auth.py`

---

## ADR-006 — Cache persistant des traductions et données nutritionnelles

### Contexte précis

Les recettes externes peuvent demander traduction et estimation nutritionnelle ; répéter ces traitements augmente le temps de réponse et la dépendance aux services tiers.

### Options réalistes

- **Option retenue :** Réutiliser les résultats déjà calculés, en mémoire ou en base selon le type de donnée.
- **Autres options :** Recalcul à chaque affichage ; cache uniquement en mémoire ; cache externe Redis.

### Choix et justification

La réutilisation réduit la latence et les appels répétés ; les modèles de cache et les modules nutritionnels sont présents dans le projet.

### Avantages et limites

- **Avantages :** La réutilisation réduit la latence et les appels répétés ; les modèles de cache et les modules nutritionnels sont présents dans le projet.
- **Limites / risques :** Définir les clés de cache, la stratégie d’invalidation et la traçabilité des sources ; prévoir un recalcul si une donnée devient obsolète.

### Conditions de réexamen

Si les recettes, les traductions ou les calculs changent, ou si des données mises en cache deviennent périmées.

### Vérification concrète

Consulter deux fois la même recette ; vérifier la cohérence du résultat et la stratégie de rafraîchissement prévue.

### Code de référence

`app/db/models.py` · `app/web/data.py` · `app/web/nutrition_engine.py`

---