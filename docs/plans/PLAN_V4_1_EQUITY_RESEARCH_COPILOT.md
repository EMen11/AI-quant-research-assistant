# Plan V4.1 — AI Equity Research Copilot

## Finance au premier plan, Data et AI Engineering visibles sous le capot

**Statut :** plan d'implémentation à valider avant développement
**Date :** 5 octobre 2026
**Poste visé :** Junior Equity Analyst — recherche, sélection et suivi d'investissements en actions
**Livraison :** deux parties indépendamment démontrables
**Effort réaliste :** partie 1 = 8 à 12 h ; partie 2 = 4 à 8 h ; enveloppe complète avec intégration = 14 à 20 h
**Nature :** plan uniquement ; évolution additive, sans suppression des capacités existantes

---

## 1. Objectif de la mise à jour

Faire évoluer le projet en un **AI Equity Research Copilot** capable de comparer Bachem et Siegfried comme le ferait un analyste actions junior : qualité de la croissance, marges, génération de cash, solidité du bilan, valorisation, durabilité, risques et éléments à suivre.

L'application doit démontrer simultanément trois compétences :

1. **Equity Research :** comprendre et comparer deux sociétés, former une thèse équilibrée et organiser leur suivi ;
2. **Data Engineering :** construire un jeu de données reproductible, normalisé, versionné et traçable depuis les rapports annuels ;
3. **AI Engineering :** produire ou assister une synthèse à partir de références autorisées, contrôler les chiffres et les citations, rendre les blocages visibles et conserver une décision humaine finale.

Le projet ne devient donc pas un simple dashboard financier. L'expérience visible commence par la recherche actions, tandis que le workbench actuel reste accessible comme démonstration technique « sous le capot ».

> Principe d'autorité : l'IA recherche et propose ; Python calcule et valide ; l'analyste interprète et décide.

---

## 2. Résultat attendu

Un recruteur doit pouvoir comprendre le projet à trois niveaux :

- **en 60 secondes :** comparaison Bachem/Siegfried FY2025, principaux écarts financiers et verdict équilibré ;
- **en 5 minutes :** historique 2021–2025, valorisation, risques, durabilité et indicateurs de suivi ;
- **sous le capot :** provenance champ par champ, snapshot figé, calculs Python, validation des affirmations, citations, contrôles Responsible AI et revue humaine.

Le positionnement public devient :

> **AI Equity Research Copilot — Swiss CDMOs**

Le produit n'émet pas de recommandation personnalisée, n'exécute pas d'ordre et ne prétend pas prédire un cours de bourse.

---

## 3. Garanties non négociables

### 3.1 Conservation de l'AI Engineering

Les éléments existants suivants sont conservés et restent démontrables :

- génération structurée et contrats Pydantic fermés ;
- références autorisées et liaison des affirmations aux métriques ;
- validation déterministe des nombres, unités, périodes et citations ;
- assessment, findings bloquants et export fail-closed ;
- scénarios admissible et bloqué ;
- évaluation du retrieval et limites documentées ;
- revue humaine et séparation proposition/décision ;
- mode démo hors ligne et parcours live existant ;
- API, persistance et migrations existantes, sans refonte dans ce MVP.

Le workbench actuel reste accessible via la vue **AI audit workbench**. Aucun module `trust`, `llm`, `api` ou `persistence` ne doit être supprimé ou remplacé.

### 3.2 Conservation et renforcement de la Data

Le parcours Equity Research doit reposer sur :

- un export figé et reproductible de `pdf.extractor` ;
- un manifeste contenant version source, hash, date d'export et caveats ;
- une provenance champ par champ jusqu'au document et à l'exercice ;
- des unités normalisées et des formules versionnées ;
- des contrôles de schéma, d'exhaustivité et de cohérence ;
- une application autonome à l'exécution, sans dépendance au dépôt source ni au réseau.

### 3.3 Conservation fonctionnelle

- Les six vues actuelles du workbench continuent de fonctionner.
- Les modes `demo` et `live` gardent leur comportement.
- La démo reste utilisable sans réseau.
- Aucun appel LLM live n'est requis pour présenter le MVP.
- Aucun composant existant n'est refactoré sans nécessité directe et testée.

Ces garanties constituent des **critères d'acceptation**, pas seulement des intentions de documentation.

---

## 4. Périmètre métier

### 4.1 Univers

- **Bachem Holding AG — BANB.SW**
- **Siegfried Holding AG — SFZN.SW**

Les deux sociétés opèrent dans le secteur CDMO et publient selon Swiss GAAP FER, ce qui limite les retraitements nécessaires. Lonza est reporté car son référentiel IFRS introduirait des écarts de comparabilité.

### 4.2 Période

- exercices FY2021 à FY2025 ;
- sources officielles uniquement ;
- valorisations à la clôture de chaque exercice, clairement distinguées d'un cours actuel ;
- données semestrielles et consensus reportés à une extension ultérieure.

### 4.3 Axes de comparaison

- croissance du chiffre d'affaires ;
- marges EBITDA, EBIT et nette ;
- flux opérationnel, capex, free cash flow et conversion cash ;
- dette nette, levier et capitaux propres ;
- ROE et distribution aux actionnaires ;
- capitalisation et valeur d'entreprise ;
- EV/CA, EV/EBITDA, EV/EBIT, P/E, P/B ;
- rendements du free cash flow et du dividende ;
- émissions Scope 1 et Scope 2, intensité carbone et niveau d'assurance ;
- arguments favorables, risques, catalyseurs et indicateurs à surveiller.

---

## 5. Architecture cible

```text
Rapports annuels officiels
          │
          ▼
pdf.extractor / données validées
          │ export versionné + provenance
          ▼
Fixtures Equity immuables + manifeste + hashes
          │
          ▼
Calculs Python déterministes
          │ métriques et formules traçables
          ▼
Equity Research UI ───────────────┐
          │                       │
          ▼                       ▼
Note d'analyste assistée     AI audit workbench existant
          │                       │
          └──── validation trust ─┘
                    │
                    ▼
             Revue humaine finale
```

La nouvelle interface consomme uniquement les fixtures embarquées. Le dépôt `pdf.extractor` reste la source de vérité amont, mais n'est pas requis pour lancer l'application.

---

# Partie 1 — Socle démontrable : données, calculs et comparaison

**Objectif :** livrer une application financière crédible et traçable, tout en préservant intégralement le workbench AI/Data existant.
**Estimation :** 8 à 12 heures.
**Point d'arrêt :** version déployable et montrable même si la partie 2 n'est pas encore commencée.

## 6. Phase 0 — Baseline et protection de l'existant

**Budget : 0,5 à 1 h**

1. Établir l'état Git des deux dépôts et noter les révisions utilisées.
2. Ne pas modifier `pdf.extractor` avant d'avoir traité son éventuel retard par rapport à la branche distante et choisi la révision de référence.
3. Identifier les doublons locaux `* 2.*` ; leur suppression reste soumise à confirmation explicite.
4. Lancer la suite de tests existante avant toute modification.
5. Vérifier qu'Alembic possède une seule tête.
6. Archiver les résultats de baseline dans la description du premier commit ou dans un court journal d'implémentation.

**Gate :**

- baseline reproductible ;
- aucune suppression non autorisée ;
- révision source de `pdf.extractor` explicitement identifiée ;
- tests défaillants préexistants distingués des nouvelles régressions.

## 7. Phase 1 — Fiabilisation des données sources

**Budget : 2 à 3 h**

Travail à réaliser dans une session distincte consacrée à `pdf.extractor` :

1. Intégrer les données de marché Siegfried FY2021–FY2025 disponibles dans le rapport annuel 2025 :
   - cours de fin d'exercice ;
   - nombre d'actions enregistrées ;
   - capitalisation boursière publiée ;
   - P/E publié lorsque pertinent.
2. Utiliser la **capitalisation publiée** comme source d'autorité lorsqu'elle est calculée nette des actions propres. Ne pas la remplacer silencieusement par `cours × actions enregistrées`.
3. Conserver séparément les valeurs publiées et les valeurs recalculées, avec leur méthode.
4. Corriger ou documenter les ruptures de séries par action :
   - split Bachem 1:5 en 2022 ;
   - split Siegfried 1:10 en 2025.
5. Corriger les unités de provenance du BPA et du dividende par action de Siegfried si elles sont enregistrées en `CHF_millions`.
6. Réconcilier le statut de l'EBITDA Siegfried (`reported` ou calculé depuis EBIT + D&A) sur l'ensemble de la période.
7. Ajouter ou adapter le chemin de promotion des données de marché : le constructeur générique actuel ne doit plus effacer les champs validés nécessaires au cas Equity.
8. Exécuter les contrôles et tests du pipeline source, puis épingler le SHA retenu.

**Gate :**

- chaque valeur possède document, page, exercice, unité et méthode ;
- aucun taux de croissance par action ne traverse un split non neutralisé ;
- les valeurs publiées et calculées ne sont jamais confondues ;
- le pipeline régénère les données sans édition manuelle du produit final.

## 8. Phase 2 — Snapshot Equity reproductible

**Budget : 1 à 1,5 h**

Créer `scripts/import_equity_snapshot.py` pour produire :

- `src/ai_quant/fixtures/equity/cdmo_fundamentals.v1.csv` ;
- `src/ai_quant/fixtures/equity/cdmo_sources.v1.csv` ;
- `src/ai_quant/fixtures/equity/cdmo_climate.v1.csv` si une projection dédiée est nécessaire ;
- `src/ai_quant/fixtures/equity/manifest.v1.json`.

Le manifeste contient au minimum :

- dépôt et SHA sources ;
- date de génération ;
- liste des fichiers d'entrée ;
- SHA-256 des entrées et sorties ;
- sociétés, exercices, champs et unités ;
- version des formules ;
- valeurs manquantes et caveats ;
- règles appliquées aux splits.

L'import doit être déterministe : deux exécutions depuis les mêmes entrées produisent les mêmes données métier.

**Tests :**

- schéma et types ;
- exactement deux sociétés et cinq exercices attendus ;
- unicité société/exercice/métrique ;
- unités autorisées ;
- hashes conformes ;
- provenance présente pour toute valeur affichable ;
- absence d'accès réseau au runtime.

## 9. Phase 3 — Moteur Equity déterministe

**Budget : 2 à 3 h**

Créer `src/ai_quant/equity/` :

- `models.py` : objets immuables société/exercice/métrique/source ;
- `repository.py` : chargement et validation des fixtures ;
- `fundamentals.py` : croissance, CAGR, marges, cash conversion, capex/CA, FCF, levier, ROE et distribution ;
- `valuation.py` : capitalisation, valeur d'entreprise et multiples ;
- `climate.py` : normalisation t/kt, intensité et statut d'assurance ;
- `formatting.py` : présentation CHF m, %, x et tCO2e/CHF m sans contaminer la valeur source.

Chaque métrique calculée conserve :

- ses entrées ;
- la période ;
- l'unité ;
- la formule et sa version ;
- la provenance des entrées ;
- son statut publié, calculé, indisponible ou non comparable.

Règles particulières :

- afficher les différences de définition de l'EBITDA et du FCF ;
- ne jamais convertir automatiquement un manque en zéro ;
- ne pas calculer de multiple lorsque le dénominateur ou la base est invalide ;
- distinguer cours historique de clôture et donnée de marché actuelle ;
- utiliser la même méthode de Scope 2 pour les deux sociétés ;
- afficher l'assurance au niveau de la métrique, pas comme label global de la société.

**Gate :** tests unitaires des formules, cas limites et concordance avec les ratios sources dans une tolérance documentée.

## 10. Phase 4 — Interface Equity Research et routage sûr

**Budget : 2,5 à 3,5 h**

1. Ajouter dans `streamlit_app.main()` un sélecteur stable :
   - **Equity research** ;
   - **AI audit workbench**.
2. En mode démo, ouvrir par défaut la vue Equity Research.
3. En mode live, conserver par défaut le parcours live existant, sauf décision contraire explicitement testée.
4. Ne rendre qu'une vue à la fois afin d'éviter les imports, calculs ou appels inutiles.
5. Créer `src/ai_quant/equity_dashboard.py` avec quatre onglets :
   - **Snapshot** : comparaison FY2025 et messages clés purement descriptifs ;
   - **Fondamentaux** : séries FY2021–FY2025 ;
   - **Valorisation** : multiples historiques à chaque clôture ;
   - **ESG & sources** : climat, assurance, caveats et provenance.
6. Pour chaque métrique, permettre d'inspecter document, exercice, valeur source et formule.
7. Utiliser uniquement les composants Streamlit déjà disponibles ; aucune nouvelle bibliothèque graphique pour ce MVP.

**Tests UI concernés :**

- adapter les tests qui supposent que les six onglets historiques sont immédiatement visibles ;
- sélectionner explicitement `AI audit workbench` avant leurs assertions ;
- éviter les sélections par index lorsque label ou clé stable sont disponibles ;
- vérifier séparément les comportements `demo` et `live` ;
- ajouter un test de fumée de la vue Equity et un test d'absence de réseau.

## 11. Critères d'acceptation de la partie 1

### Finance

- La comparaison Bachem/Siegfried FY2025 est compréhensible sans ouvrir le code.
- Les tendances FY2021–FY2025 et les multiples historiques sont visibles.
- Les différences de définition comptable et les splits sont explicités.
- Aucun chiffre n'est présenté comme actuel s'il correspond à une clôture historique.

### Data Engineering

- Le snapshot est régénérable et lié à un SHA source.
- Chaque chiffre visible possède une provenance et une unité.
- Le manifeste et les hashes sont testés.
- La démo fonctionne hors ligne et ne dépend pas de `pdf.extractor` au runtime.

### AI Engineering

- Le workbench actuel reste accessible et fonctionnel.
- Les scénarios valide et bloqué continuent de démontrer les contrôles existants.
- Aucun contrat, validateur, test d'évaluation ou règle fail-closed n'est supprimé.
- Le passage d'une vue à l'autre ne déclenche pas le parcours non sélectionné.

### Qualité

- tests nouveaux et existants verts, hors défaillances préexistantes documentées ;
- aucune nouvelle dépendance sans validation ;
- aucune migration de base de données ;
- README minimal mis à jour pour lancer et comprendre la partie 1.

**Point d'arrêt 1 :** démonstrateur financier traçable, déjà présentable à un recruteur.

---

# Partie 2 — Dossier d'analyste assisté et suivi d'investissement

**Objectif :** transformer le comparateur en cas complet de recherche, sélection et suivi d'actions, tout en utilisant les contrôles AI existants.
**Estimation :** 4 à 8 heures supplémentaires.
**Prérequis :** partie 1 validée et stable.

## 12. Phase 5 — Contrat de note d'analyste

**Budget : 1 à 2 h**

Définir une note courte et structurée :

1. objet de la comparaison et date des données ;
2. profil des sociétés et modèle économique ;
3. qualité de la croissance et de la rentabilité ;
4. cash, bilan et allocation du capital ;
5. valorisation relative et historique ;
6. durabilité et limites de comparabilité ;
7. arguments favorables ;
8. risques et points d'attention ;
9. catalyseurs ;
10. indicateurs à suivre ;
11. conclusion comparative, sans BUY/SELL ni cours cible.

La note doit distinguer :

- faits sourcés ;
- métriques calculées ;
- interprétations de l'analyste ;
- limites et données indisponibles.

Créer un contrat versionné, par exemple `analyst_note.v1`, sans modifier les contrats historiques si une extension additive suffit.

## 13. Phase 6 — Liaison aux contrôles AI

**Budget : 2 à 3 h**

1. Créer `equity/records.py` pour transformer les métriques Equity en `MetricRecord` déterministes et liés au run.
2. Construire le contexte de validation avec uniquement les métriques et preuves autorisées pour cette note.
3. Matérialiser un `GeneratedDraft` conforme avant d'appeler les validateurs existants.
4. Utiliser les placeholders de métriques dans les affirmations quantitatives.
5. Valider :
   - identifiants de métriques ;
   - valeurs, unités et périodes ;
   - citations et extraits ;
   - absence de causalité finance/climat non démontrée ;
   - présence des limitations ;
   - absence de recommandation interdite.
6. En cas de finding bloquant, ne pas afficher la note comme résultat validé ; afficher le diagnostic.
7. Rendre visible le rôle exact de l'IA : recherche, structuration ou reformulation, et non calcul ou décision autonome.

Version initiale recommandée : une proposition de note versionnée et reproductible, compatible avec la démo hors ligne. L'appel LLM live reste une extension et non une condition de réussite.

## 14. Phase 7 — Vue Research Note et monitoring

**Budget : 1 à 2 h**

Ajouter une vue ou un onglet **Research note** contenant :

- résumé exécutif ;
- comparaison synthétique ;
- arguments pour et contre ;
- risques et catalyseurs ;
- valorisation en contexte ;
- limites ;
- statut de validation ;
- sources ouvrables ;
- mention de l'assistance IA.

Ajouter un tableau de suivi simple :

- KPI ;
- dernière valeur disponible ;
- direction souhaitable ou seuil descriptif, sans prédiction ;
- raison de suivi ;
- source ;
- fréquence de mise à jour ;
- statut disponible/à actualiser.

Exemples de KPI : croissance organique, marge EBITDA, conversion cash, capex/CA, dette nette/EBITDA, avancée des capacités, intensité carbone et assurance des données.

Le suivi H1 2026 réel est reporté tant que les données intermédiaires des deux sociétés ne sont pas intégrées au pipeline.

## 15. Phase 8 — Documentation et démonstration portfolio

**Budget : 0,5 à 1 h**

Mettre à jour le README avec :

- le problème métier ;
- deux captures de la vue Equity ;
- un schéma Finance/Data/AI ;
- la méthodologie de comparaison ;
- les sources et la date des données ;
- les limites ;
- un parcours de démonstration de 60 à 90 secondes ;
- une section « Under the hood » consacrée au pipeline, aux contrats et aux validations.

Préparer un pitch d'entretien :

> J'ai construit un copilote de recherche actions qui transforme des rapports annuels en une comparaison financière reproductible. Python calcule les métriques, chaque chiffre reste lié à sa source, l'IA aide à structurer la note, puis des validateurs indépendants contrôlent ses affirmations avant revue humaine.

## 16. Critères d'acceptation de la partie 2

### Equity Research

- La note couvre activité, fondamentaux, cash, bilan, valorisation, durabilité, risques, catalyseurs et suivi.
- La conclusion compare les sociétés sans simuler une certitude ni produire de recommandation personnalisée.
- Les faits, calculs et opinions sont clairement séparés.

### AI Engineering

- Toute affirmation quantitative utilise une métrique autorisée.
- Toute affirmation de preuve est rattachée à un extrait autorisé.
- Une note invalide est bloquée de manière visible.
- Le rôle de l'IA et la responsabilité humaine sont déclarés.
- Le scénario bloqué reste démontrable.

### Data Engineering

- La note ne contient aucun chiffre orphelin de provenance.
- Les unités et périodes sont rendues depuis les records autoritatifs.
- Le monitoring indique explicitement la fraîcheur et les données manquantes.

### Portfolio

- README et captures permettent de comprendre le projet sans lancer le code.
- Le scénario de démonstration tient en moins de deux minutes.
- Les limites sont honnêtes : deux sociétés, données annuelles, clôtures historiques, pas de consensus ni prévision.

**Point d'arrêt 2 :** cas portfolio complet pour un poste de Junior Equity Analyst, avec profondeur AI Engineer et Data vérifiable.

---

## 17. Budget consolidé

| Partie | Phase | Estimation |
|---|---|---:|
| 1 | Baseline | 0,5–1 h |
| 1 | Données sources | 2–3 h |
| 1 | Snapshot reproductible | 1–1,5 h |
| 1 | Moteur Equity | 2–3 h |
| 1 | Interface et tests UI | 2,5–3,5 h |
| **Partie 1** | **Socle démontrable** | **8–12 h** |
| 2 | Contrat de note | 1–2 h |
| 2 | Contrôles AI | 2–3 h |
| 2 | Research note et monitoring | 1–2 h |
| 2 | Documentation | 0,5–1 h |
| **Partie 2** | **Dossier d'analyste** | **4–8 h** |
| **Total prudent** | **Intégration et marge incluses** | **14–20 h** |

Les durées ne sont pas des garanties contractuelles. Si une phase dépasse deux fois son budget, l'agent doit s'arrêter, documenter la cause et demander une décision avant d'élargir le périmètre.

---

## 18. Fichiers prévus

### Nouveaux fichiers principaux

- `scripts/import_equity_snapshot.py`
- `src/ai_quant/equity/__init__.py`
- `src/ai_quant/equity/models.py`
- `src/ai_quant/equity/repository.py`
- `src/ai_quant/equity/fundamentals.py`
- `src/ai_quant/equity/valuation.py`
- `src/ai_quant/equity/climate.py`
- `src/ai_quant/equity/formatting.py`
- `src/ai_quant/equity/records.py` — partie 2
- `src/ai_quant/equity_dashboard.py`
- `src/ai_quant/fixtures/equity/*`
- tests unitaires et d'intégration dédiés

### Modifications limitées

- `src/ai_quant/streamlit_app.py` : routage de vue et titre ;
- tests Streamlit existants : sélection explicite du workbench ;
- `README.md` : présentation et lancement ;
- `pdf.extractor` : uniquement via sa propre session, son pipeline et ses tests.

### Hors limites sans nouvelle validation

- refonte de `ai_quant.quant` ;
- modification destructive de `ai_quant.trust` ou `ai_quant.llm` ;
- nouvelle migration ou nouvelle table ;
- changement des API existantes ;
- nouvelle dépendance lourde ;
- données de marché live ;
- DCF, consensus, target price ou recommandation BUY/SELL ;
- ajout d'un troisième émetteur.

---

## 19. Stratégie de commits et de validation

Un commit logique par phase :

1. baseline et décisions de source ;
2. correction/promotion des données dans `pdf.extractor` ;
3. import et fixtures Equity ;
4. calculs et tests unitaires ;
5. dashboard et non-régression ;
6. note et validation AI ;
7. monitoring et documentation.

Avant chaque passage de phase :

- tests ciblés verts ;
- diff relu ;
- aucune modification hors périmètre ;
- provenance et caveats mis à jour ;
- comportement offline vérifié lorsqu'il est concerné.

La partie 2 ne commence qu'après validation explicite du point d'arrêt 1.

---

## 20. Extensions futures, une par une

1. Intégrer les résultats H1 2026 et comparer les changements depuis FY2025.
2. Ajouter un calendrier de publications sourcé et actualisable.
3. Ajouter un pair sous IFRS avec une table de réconciliation explicite.
4. Brancher une génération LLM live sur le même contrat de note.
5. Persister les analyses Equity dans PostgreSQL.
6. Ajouter consensus et révisions d'estimations avec licence de données adaptée.
7. Ajouter performance relative, benchmark et beta avec un snapshot de prix redistribuable.
8. Construire un DCF inversé ou une analyse de scénarios, sans fausse précision.

Ces extensions ne font pas partie de la V4.1 et ne doivent pas retarder les deux points d'arrêt.

---

## 21. Définition finale de réussite

La V4.1 est réussie si le projet permet de répondre clairement aux trois questions suivantes :

1. **Finance :** que montrent les fondamentaux et la valorisation comparée de Bachem et Siegfried ?
2. **Data :** d'où vient chaque chiffre, comment a-t-il été transformé et peut-on reproduire le résultat ?
3. **AI Engineering :** comment le système empêche-t-il l'IA d'inventer, de déformer un chiffre ou de présenter une affirmation non sourcée ?

Si l'une de ces trois réponses n'est pas démontrable dans l'application ou ses tests, le MVP n'est pas considéré comme terminé.
