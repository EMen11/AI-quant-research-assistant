# Trustworthy AI Quant Research Workbench

## Plan final de migration, d'apprentissage et de réalisation

**Point de départ :** [EMen11/AI-quant-research-assistant](https://github.com/EMen11/AI-quant-research-assistant)  
**But :** transformer le prototype actuel en une plateforme moderne de recherche financière quantitative, enrichie par des preuves de sustainability, évaluée, traçable et supervisée par un humain.  
**Public visé :** son auteur, qui doit pouvoir construire, comprendre, tester et défendre chaque décision en entretien.  
**Version du plan :** V3, 22 septembre 2026.

Ce document remplace `PLAN_MIGRATION_AI_QUANT_TRUSTWORTHY_RESEARCH_V2(1).md`. Il conserve son socle d'evals, de guardrails, de citations et de revue humaine, mais corrige l'ordre de migration et ajoute le Quant Core ainsi qu'un périmètre sustainable finance explicite.

---

## 1. Décision de produit

### 1.1 Nom et promesse

Nom recommandé :

> **Trustworthy AI Quant Research Workbench**

Promesse en une phrase :

> Une plateforme de recherche financière qui combine des calculs quantitatifs déterministes avec des informations financières et climatiques issues de documents officiels. L'IA synthétise les résultats, mais ne contrôle ni les chiffres, ni les preuves, ni sa propre validation.

Version courte pour GitHub :

> Evidence-grounded quantitative research with sustainability data, measurable AI quality and human review.

### 1.2 Ce projet n'est pas un projet « fourre-tout »

Le projet suit une hiérarchie claire :

1. **Cœur métier :** analyse quantitative d'un portefeuille.
2. **Lentille supplémentaire :** données de sustainable finance provenant de rapports officiels.
3. **Méthode d'ingénierie :** IA fiable, évaluée, traçable et supervisée.
4. **Mesures opérationnelles secondaires :** appels LLM, tokens, coût estimé, latence, retries et cache.

Il ne s'agit donc pas de construire en parallèle :

- une application quant ;
- une plateforme ESG ;
- un laboratoire d'agents ;
- un calculateur carbone pour l'IA.

Il s'agit d'un **seul parcours utilisateur** :

```text
Portefeuille défini par l'analyste
  -> snapshot de marché figé
  -> calculs quantitatifs reproductibles
  -> recherche dans des rapports officiels
  -> synthèse structurée par un LLM
  -> validation des chiffres et des preuves
  -> revue humaine
  -> résultat final auditable
```

### 1.3 Cas d'usage du MVP

Le MVP répond à la question suivante :

> Pour un petit portefeuille d'entreprises suisses du secteur Pharma/CDMO, quels sont les principaux résultats quantitatifs et quels éléments climatiques publiés sont suffisamment étayés et comparables pour compléter l'analyse ?

Périmètre recommandé :

- **trois actifs maximum côté quantitatif**, pour rendre covariance et contraintes plus intéressantes ;
- **deux émetteurs dans le corpus climat du MVP**, après audit documentaire : Bachem et Siegfried sont les premiers candidats ;
- **un troisième émetteur quantitatif ou documentaire en extension** : Lonza, ou PolyPeptide si son corpus est plus exploitable ;
- un historique de prix figé ;
- quelques métriques quantitatives bien définies ;
- un corpus restreint de rapports annuels et sustainability officiels ;
- un seul brief de recherche par exécution ;
- une validation automatique, puis une décision humaine.

### 1.4 Résultat final visible

L'interface finale contient quatre vues :

1. **Quantitative Portfolio Analysis**
   - performance historique ;
   - volatilité ;
   - maximum drawdown ;
   - VaR historique et paramétrique ;
   - CVaR ou Expected Shortfall ;
   - corrélations ;
   - allocation calculée sous contraintes, présentée comme scénario de recherche et non comme conseil.

2. **Climate Evidence**
   - Scope 1 ;
   - Scope 2 location-based et market-based, sans les mélanger ;
   - consommation énergétique ;
   - objectifs climatiques séparés des résultats observés ;
   - comparabilité et limites ;
   - preuve ouvrable pour chaque valeur.

3. **Validation & Human Review**
   - affirmations éligibles à une revue ;
   - erreurs numériques ;
   - preuves insuffisantes ;
   - conflits de sources ;
   - corrections, rejets et escalades humaines.

4. **Quality & Resource Efficiency**
   - résultats des évaluations ;
   - taux de fausse éligibilité automatique ;
   - nombre d'appels au modèle ;
   - tokens d'entrée et de sortie ;
   - coût estimé daté ;
   - latence, retries et taux de cache ;
   - comparaison entre la version initiale et la nouvelle architecture.

### 1.5 Hors périmètre du MVP

Les éléments suivants sont volontairement exclus :

- exécution de transactions ;
- conseil d'investissement personnalisé ;
- score ESG global ou note de « durabilité » opaque ;
- classement de l'entreprise « la plus durable » ;
- attribution causale entre un KPI climat et le cours de l'action ;
- calcul de financed emissions ;
- Scope 3 détaillé ;
- biodiversité, eau, déchets, sécurité et diversité dans la même version ;
- intégration automatique d'un score sustainability dans Markowitz ;
- fine-tuning d'un modèle ;
- graphe de connaissances ;
- orchestration de nombreux agents ;
- Kubernetes ;
- architecture cloud complexe ;
- authentification développée maison ;
- mesure d'une empreinte CO₂ du LLM déduite des seuls tokens.

### 1.6 Trois notions à ne pas confondre

| Notion | Ce que le projet fait |
|---|---|
| **Sustainable finance** | Il ajoute à l'analyse financière des données climatiques publiées, avec période, unité, périmètre, méthode et preuve. |
| **AI for sustainability** | Il utilise l'IA pour retrouver et synthétiser des informations dans les rapports de sustainability. |
| **AI resource efficiency** | Il mesure les ressources applicatives observables : appels, tokens, coûts, latence, retries et cache. Ces mesures comparent l'efficacité des architectures ; elles ne démontrent ni consommation énergétique ni empreinte environnementale. |

### 1.7 Ce que cette V3 change par rapport au plan V2

- elle ajoute une vraie phase de fiabilisation quantitative avant le RAG ;
- elle remplace les quatre agents obligatoires par un workflow typé et borné ;
- elle sépare strictement brouillon, métriques, preuves, validation et décision humaine ;
- elle ajoute un cas de sustainable finance étroit et vérifiable ;
- elle compare plusieurs stratégies de retrieval avant d'adopter une base vectorielle ;
- elle rend PostgreSQL et FastAPI centraux pour la version candidature ;
- elle introduit tests et CI avant les grands refactors ;
- elle traite tokens, coût et latence comme de l'observabilité, pas comme un second produit ;
- elle ajoute exercices sans IA, questions de maîtrise et points d'arrêt ;
- elle mesure la migration v1 vers v3 au lieu d'empiler des technologies.

---

## 2. Comment utiliser ce plan

### 2.1 Règle principale

Ne pas traiter ce document comme une liste de technologies à installer. Chaque phase produit un résultat visible et vérifiable.

Pour chaque phase :

1. lire les notions ;
2. reformuler le but avec ses propres mots ;
3. réaliser les tâches dans l'ordre ;
4. écrire les tests ;
5. faire l'exercice sans assistant IA ;
6. répondre oralement aux questions de maîtrise ;
7. vérifier les critères de fin ;
8. créer un commit limité à cette phase ;
9. ne continuer que si le point d'arrêt est satisfait.

### 2.2 Définition générale de « terminé »

Une phase n'est pas terminée parce que le code s'exécute une fois. Elle est terminée lorsque :

- le comportement est testé ;
- les hypothèses sont écrites ;
- les erreurs sont explicites ;
- les données importantes sont traçables ;
- une autre personne peut recalculer la partie déterministe et auditer les entrées/sorties de la partie LLM ;
- tu peux expliquer le code sans lire une réponse générée.

### 2.3 Usage raisonnable d'un assistant de code

L'assistant peut :

- proposer une structure ;
- expliquer une erreur ;
- produire un premier brouillon ;
- relire un test ;
- suggérer des cas limites.

Mais, pour chaque composant important, tu dois pouvoir :

- décrire les entrées et les sorties ;
- indiquer ce qui peut échouer ;
- retrouver où l'erreur est gérée ;
- modifier une règle simple ;
- écrire au moins un test seul ;
- expliquer pourquoi la solution a été choisie.

### 2.4 Discipline Git

Avant la migration :

```bash
git status
git switch -c migration/trustworthy-ai-quant
git tag v1.0-baseline
```

Ne crée le tag que si l'état actuel est commité et identifiable. Si le dépôt contient des changements locaux, commence par les inventorier et les préserver.

Convention de commits recommandée :

```text
docs: define product scope and non-goals
test: add deterministic baseline fixtures
refactor: centralize immutable market snapshots
feat: add typed research contracts
feat: persist research runs in postgres
feat: ingest traceable climate evidence
eval: compare retrieval strategies
feat: validate claims and route human review
feat: expose research API and analyst UI
chore: add CI and reproducible containers
docs: publish evaluation report and demo
```

---

## 3. État de départ vérifié

L'audit du dépôt public a été réalisé sur le commit `0d58a238026744c729343f588eb3cdcd313d23fd`. Il montre un prototype intéressant, mais plus limité que ce que son README peut laisser penser.

### 3.1 Ce qui existe

- une interface Streamlit ;
- quatre classes d'agents séquentiels :
  - `MarketAnalyst` ;
  - `RiskAssessor` ;
  - `PortfolioStrategist` ;
  - `ExecutiveSynthesizer` ;
- un téléchargement de données avec `yfinance` ;
- des calculs de rendement, volatilité, drawdown et VaR ;
- une optimisation de type Markowitz ;
- plusieurs appels séquentiels à Claude ;
- un stockage SQLite via le module standard `sqlite3` ;
- un générateur de rapport présent dans le dépôt.

### 3.2 Forces à conserver

- séparation partielle entre calcul Python et texte produit par le LLM ;
- organisation modulaire par fichiers ;
- démo Streamlit déjà visible ;
- clé API lue depuis l'environnement ;
- premières protections contre les données absentes ;
- idée d'une synthèse multi-angle.

### 3.3 Écarts factuels à corriger

| Sujet | État observé | Conséquence |
|---|---|---|
| Persistance | `sqlite3` est utilisé directement | Ne pas affirmer que SQLAlchemy est déjà employé. |
| Dépendances | SQLAlchemy figure dans les dépendances | Une dépendance installée ne prouve pas son utilisation. |
| CLI | `main.py` est vide | Les instructions CLI du README ne correspondent pas au code. |
| Environnement | `.env.example` est annoncé mais absent | L'installation n'est pas entièrement documentée. |
| Configuration | `config/prompts.yaml` est vide | Les prompts ne sont pas réellement versionnés dans ce fichier. |
| Utilitaires | `src/utils.py` est vide | Ne pas le présenter comme une couche fonctionnelle. |
| Tests | aucun dossier de tests observé | Les formules et workflows ne sont pas protégés contre les régressions. |
| CI | aucun workflow GitHub Actions observé | Aucun contrôle automatisé à chaque changement. |
| Reproductibilité | aucun lockfile observé | Deux installations peuvent résoudre des versions différentes. |
| Agents | sorties textuelles libres et séquentielles | Coût, latence et erreurs se propagent entre étapes. |
| Modèle | identifiant de modèle codé en dur | La configuration et la comparaison de versions sont difficiles. |
| Données | plusieurs téléchargements peuvent survenir dans un même run | Les agents peuvent travailler sur des jeux de prix différents. |
| Période | l'UI propose 6 mois, 1 an ou 2 ans, mais le stratège retélécharge 1 an par défaut | Les métriques et l'optimisation peuvent couvrir des fenêtres différentes. |
| Univers | les tickers détectés ne sont pas réconciliés avec les séries téléchargées | Un run peut continuer avec un univers incomplet. |
| Détection | des sous-chaînes générales peuvent produire un indice plutôt qu'un portefeuille Pharma | L'univers doit devenir explicite. |
| VaR | documentation, fonction historique non appelée et formule paramétrique observée ne concordent pas entièrement | Il faut reconstruire et tester les définitions. |
| Benchmark | le prompt demande une comparaison sans benchmark fourni | Le modèle est poussé à improviser. |
| Taux sans risque | valeur codée en dur sans date, devise et source complètes | L'hypothèse n'est pas auditable. |
| Synthèse | certaines sorties intermédiaires sont tronquées par nombre de caractères | Une preuve utile peut disparaître arbitrairement. |
| Preuves | aucune couche de citations vérifiées | Le texte n'est pas relié à un corpus officiel. |
| Décision | recommandations BUY/HOLD/SELL et allocations | Le niveau de contrôle ne justifie pas ces formulations. |
| Rapport | module présent, mais non relié au flux principal observé | Une fonction dans l'arbre n'est pas forcément une fonctionnalité de bout en bout. |
| Observabilité | appels, prompts, tokens, coût et latence ne sont pas conservés | La v1 est difficile à diagnostiquer et comparer. |
| Horodatages | usage de dates naïves alors que certains affichages indiquent UTC | La convention temporelle est ambiguë. |
| Données Git | `data/` est entièrement ignoré | Il faudra autoriser manifestes et petites fixtures versionnées. |
| Marketing | l'interface emploie `institutional-grade` | Le niveau de contrôle actuel ne justifie pas ce terme. |

### 3.4 Limites quantitatives actuelles

Avant tout ajout de RAG, il faut corriger :

- l'absence d'`analysis_cutoff` obligatoire ;
- l'absence de snapshot unique et immuable ;
- la politique non documentée sur les prix ajustés ;
- les hypothèses d'annualisation peu visibles ;
- le risque de mélange d'unités ;
- la différence non suffisamment exposée entre VaR historique et paramétrique ;
- les données manquantes et calendriers boursiers ;
- le risque de `look-ahead bias` ;
- le statut ambigu de l'optimisation, qui ne doit pas devenir une recommandation.

### 3.5 Limites IA actuelles

- le modèle retourne surtout du texte libre ;
- les quatre « agents » sont surtout quatre rôles de prompt ;
- le modèle n'est pas évalué sur un jeu versionné ;
- aucune frontière nette ne sépare génération, preuve, validation et décision humaine ;
- aucun mécanisme d'abstention robuste ;
- aucune mesure consolidée de coût, latence ou nombre d'appels.

### 3.6 Pourquoi la migration crée une vraie valeur

La valeur ne vient pas du nombre de bibliothèques ajoutées. Elle vient du récit de transformation démontrable :

> « Le prototype initial faisait circuler du texte entre quatre agents. J'ai d'abord fiabilisé les données et les calculs, puis séparé la génération des preuves et de la validation. J'ai comparé plusieurs stratégies de récupération, mesuré la qualité et les coûts, et ajouté une revue humaine auditée. »

C'est une preuve de jugement d'ingénierie, de qualité de données et de maîtrise du risque. Cela ne remplace pas littéralement une à trois années d'expérience professionnelle, mais cela réduit fortement l'écart de preuve lors d'une candidature.

---

## 4. Architecture cible et frontières de confiance

### 4.1 Flux cible

```text
Demande analyste
  -> validation de la requête
  -> MarketSnapshot immuable
  -> moteur quantitatif déterministe
  -> corpus officiel versionné
  -> récupération de preuves
  -> GeneratedDraft structuré
  -> ValidationReport
  -> AutomatedAssessment
  -> HumanReview
  -> rapport final
```

Un même `research_run_id` relie toutes les étapes.

### 4.2 Définition du portefeuille

Le portefeuille est une entrée métier versionnée, pas une liste de tickers déduite d'une phrase.

```python
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class PortfolioDefinition(BaseModel):
    portfolio_id: str
    instruments: list[str]
    weighting_rule: Literal["equal_weight", "custom"]
    initial_weights: dict[str, Decimal] | None = None
    base_currency: str
    benchmark_id: str | None = None
    constraints: dict[str, Decimal]
    analysis_cutoff: datetime
```

Pour garder un cas quantitatif intéressant, le moteur peut utiliser trois actifs Pharma/CDMO suisses. La couche climat du premier MVP reste limitée à deux émetteurs ; le troisième apparaît alors explicitement comme « non couvert dans cette version », et non comme zéro. Si tu gardes seulement deux actifs, présente Markowitz comme une démonstration pédagogique simplifiée.

### 4.3 Objets à séparer

| Objet | Créateur autorisé | Rôle |
|---|---|---|
| `MarketSnapshot` | fournisseur de données + code d'ingestion | Conserver exactement les prix et métadonnées utilisés. |
| `MetricRecord` | moteur Python | Conserver une métrique, sa formule, ses entrées, son unité et sa version. |
| `DocumentRecord` | pipeline d'ingestion | Identifier un document, sa source, sa période et son empreinte. |
| `EvidenceRecord` | pipeline documentaire | Conserver un passage exact, sa page et son lien au document. |
| `GeneratedDraft` | LLM | Produire des affirmations atomiques et référencer des identifiants existants. |
| `ValidationReport` | code de validation, éventuellement assisté d'un vérificateur séparé | Vérifier nombres, références, unités, périodes et soutien des affirmations. |
| `AutomatedAssessment` | moteur de règles | Produire `eligible_for_review`, `review_required` ou `abstain`. Ce résultat n'est jamais une approbation. |
| `HumanReview` | reviewer humain | Produire `approved`, `corrected`, `rejected` ou `escalated`. |

### 4.4 Règle de confiance centrale

Le LLM peut :

- formuler une synthèse ;
- créer une affirmation atomique ;
- demander à référencer un `metric_id` ou un `evidence_id` qui existe déjà.

Le LLM ne peut pas :

- créer la provenance d'une source ;
- inventer un extrait ou un numéro de page ;
- déclarer sa propre affirmation « vérifiée » ;
- approuver son propre résultat ;
- calculer les métriques financières ;
- décider seul de publier le rapport.

### 4.5 Workflow plutôt que théâtre multi-agent

La nouvelle architecture utilise un workflow Python explicite. Un spécialiste LLM n'est ajouté que si une tâche exige réellement des instructions ou des outils différents et si son apport est mesurable.

Pourquoi :

- un workflow est prévisible ;
- ses étapes sont testables ;
- les boucles et budgets sont bornés ;
- chaque appel peut être justifié ;
- le calcul financier n'a pas besoin d'un personnage « Risk Agent ».

Le guide d'Anthropic sur les agents recommande de commencer par la solution la plus simple et de n'ajouter de l'autonomie que lorsque le gain le justifie : [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

### 4.6 Arborescence cible indicative

```text
.
├── app/
│   └── streamlit_app.py
├── api/
│   ├── dependencies.py
│   └── routes/
├── src/ai_quant/
│   ├── config.py
│   ├── domain/
│   │   ├── market.py
│   │   ├── metrics.py
│   │   ├── evidence.py
│   │   ├── sustainability.py
│   │   ├── research.py
│   │   └── review.py
│   ├── market_data/
│   │   ├── base.py
│   │   ├── yfinance_provider.py
│   │   └── frozen_provider.py
│   ├── quant/
│   │   ├── returns.py
│   │   ├── risk.py
│   │   └── optimization.py
│   ├── documents/
│   │   ├── manifest.py
│   │   ├── parser.py
│   │   └── chunking.py
│   ├── retrieval/
│   │   ├── lexical.py
│   │   ├── dense.py
│   │   ├── hybrid.py
│   │   └── evaluation.py
│   ├── llm/
│   │   ├── client.py
│   │   ├── schemas.py
│   │   └── synthesis.py
│   ├── validation/
│   │   ├── numeric.py
│   │   ├── evidence.py
│   │   ├── sustainability.py
│   │   └── policy.py
│   ├── workflows/
│   │   └── research_workflow.py
│   ├── persistence/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── session.py
│   └── observability/
│       ├── logging.py
│       └── metrics.py
├── alembic/
├── data/
│   ├── manifests/
│   ├── fixtures/
│   └── evals/
├── docs/
│   ├── product_contract.md
│   ├── architecture.md
│   ├── methodology_quant.md
│   ├── methodology_sustainability.md
│   ├── threat_model.md
│   ├── evaluation_report.md
│   └── limitations.md
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evals/
├── .github/workflows/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

L'arborescence est une cible, pas une obligation de tout créer au premier jour.

---

## 5. Glossaire essentiel

### Déterministe

À entrées identiques, le code produit le même résultat. Une formule Python correctement fixée peut être déterministe. Une réponse LLM ne l'est pas forcément.

### Reproductibilité

Capacité à refaire une exécution passée avec les mêmes données, versions, paramètres et hypothèses. Elle exige plus qu'un code déterministe : il faut aussi figer les entrées.

### Snapshot immuable

Copie des données utilisées à un instant donné, qui ne sera plus modifiée. On crée une nouvelle version au lieu d'écraser l'ancienne.

### `analysis_cutoff` et couverture des données

`analysis_cutoff` est la dernière date d'information autorisée pour l'analyse. `data_start` et `data_end` décrivent la couverture réelle, tandis que `retrieved_at` indique quand le fichier a été téléchargé.

Cette borne logique réduit certains risques, mais un téléchargement actuel de données historiques ne devient pas automatiquement une source point-in-time. Sans source historisée et versionnée, le projet garantit la reproductibilité du snapshot téléchargé, pas l'absence absolue de look-ahead bias.

### Look-ahead bias

Biais introduit lorsqu'un calcul historique utilise une information qui n'était pas disponible à la date simulée.

### Schéma et contrat

Un schéma définit la forme d'une donnée : champs, types et valeurs permises. Un contrat ajoute les attentes entre composants. Par exemple, une métrique doit avoir une unité et une version de formule.

### Validation syntaxique et validation métier

Pydantic peut vérifier que `page` est un entier. Il ne peut pas, à lui seul, prouver que cette page existe ou qu'elle soutient l'affirmation. La première vérification est syntaxique ; la seconde est métier.

### Sortie structurée

Sortie LLM contrainte par un schéma JSON. Les sorties structurées natives du fournisseur réduisent les erreurs de forme, puis Pydantic contrôle les règles applicatives. Elles ne garantissent pas la vérité du contenu. Voir [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) et [Pydantic](https://docs.pydantic.dev/latest/).

### Provenance et data lineage

La provenance indique d'où vient une donnée. Le lineage décrit les transformations subies entre la source et le résultat.

### Claim, evidence et citation

- un **claim** est une affirmation ;
- une **evidence** est un passage ou une donnée stockée ;
- une **citation** relie l'affirmation à cette preuve.

Un identifiant de citation valide ne suffit pas : le passage doit réellement soutenir l'affirmation.

### Workflow et agent

- un **workflow** suit des étapes définies par le code ;
- un **agent** choisit plus dynamiquement ses actions et ses outils.

L'autonomie augmente la flexibilité, mais aussi le coût et la surface d'erreur.

### RAG

Retrieval-Augmented Generation : le système recherche d'abord des passages, puis les fournit au modèle pour générer une réponse mieux ancrée.

### Chunk

Fragment d'un document indexé pour la recherche. Ici, un chunk doit préserver le document, la page, la section et si possible le contexte d'un tableau.

### BM25, embeddings, hybride et reranking

- **BM25** : recherche lexicale basée sur les mots exacts ;
- **embedding** : représentation vectorielle utilisée pour retrouver une proximité sémantique ;
- **hybride** : combinaison lexicale et vectorielle ;
- **reranking** : second classement d'une liste courte de résultats.

Il faut les comparer au lieu de supposer que la solution la plus complexe gagne.

### Retrieval recall@k

Part des questions pour lesquelles au moins un passage attendu se trouve dans les `k` premiers résultats.

### Grounding

Degré auquel la réponse est soutenue par les sources réellement fournies.

### Guardrail

Contrôle qui bloque, corrige, redirige ou escalade une sortie risquée. Un guardrail déterministe est une règle de code, pas seulement une instruction de prompt.

### Prompt injection indirecte

Instruction malveillante contenue dans une source consultée par le modèle. Les documents sont des données non fiables et ne doivent pas commander les outils. Voir [OWASP LLM01: Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).

### Test logiciel et évaluation LLM

- un **test** vérifie un comportement attendu du code ;
- une **eval** mesure la qualité d'un système probabiliste sur un jeu de cas.

Les deux sont nécessaires. Voir [Anthropic, Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

### Holdout

Jeu de cas réservé, non utilisé pour ajuster prompts et règles. Il donne une estimation moins biaisée de la généralisation.

### Fausse éligibilité automatique

Cas où le système marque `eligible_for_review` une sortie incorrecte ou insuffisamment étayée. Cette erreur, parfois appelée faux `pass`, est plus grave qu'une escalade prudente. Même une sortie éligible doit encore être approuvée par un humain.

### Human-in-the-loop

Intervention humaine explicite dans une décision. Elle doit conserver qui a décidé, quand, pourquoi et sur quelle version.

### Audit trail

Historique des événements et décisions où une correction crée une nouvelle version au lieu d'effacer l'ancienne. Dans le MVP, cette propriété est imposée et testée au niveau applicatif ; elle n'est pas présentée comme inviolable.

### ORM et migration

- un **ORM** relie objets Python et tables relationnelles ;
- une **migration** versionne un changement de schéma.

SQLAlchemy fournit l'outillage ORM/Core ; Alembic versionne les migrations. Voir [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/) et [Alembic](https://alembic.sqlalchemy.org/en/latest/).

### API et idempotence

Une API expose des contrats HTTP. Une opération idempotente peut être répétée sans créer un résultat différent ou un doublon indésirable.

### CI/CD

- **CI** : tests et contrôles automatiques sur les changements ;
- **CD** : livraison ou déploiement automatisé.

La CI arrive tôt. Le déploiement automatique peut attendre.

### Observabilité

Capacité à comprendre une exécution grâce aux logs, métriques et traces. Une trace relie les étapes d'un même run. Voir [OpenTelemetry, Traces](https://opentelemetry.io/docs/concepts/signals/traces/).

### Périmètre, méthode et retraitement sustainability

- le **périmètre** précise quelles entités ou activités sont couvertes ;
- la **méthode** explique comment la valeur est calculée ;
- un **retraitement** corrige ou rend comparable une valeur passée.

Deux nombres de même nom ne sont pas nécessairement comparables.

---

## 6. Jalons, priorité et charge réaliste

### 6.1 Jalons

| Jalon | Contenu | Valeur |
|---|---|---|
| **A. Baseline honnête** | produit borné, v1 figée, premiers tests | Comprendre le point de départ. |
| **B. Quant fiable** | snapshot unique, métriques testées, contrats, PostgreSQL | Montrer une vraie base d'ingénierie financière. |
| **C. Evidence-backed research** | corpus sustainability, retrieval mesuré, citations, validateurs, evals | Premier niveau directement pertinent pour le poste. |
| **D. Workflow supervisé** | revue humaine, audit trail, FastAPI, UI, observabilité | Version portfolio forte et démontrable. |
| **E. Produit présentable** | CI complète, conteneurs, documentation, rapport comparatif, démo | Version finale défendable en entretien. |

### 6.2 Charge indicative

Les estimations ci-dessous sont des **jours de travail concentré**, pas des délais calendaires. La colonne « avec apprentissage » inclut le temps consacré aux exercices, à la documentation et aux reprises :

| Niveau | Périmètre | Implémentation | Avec apprentissage |
|---|---|---:|---:|
| Tranche verticale présentable | P0 de la section 24 | 8 à 12 jours | 12 à 18 jours |
| Version très alignée avec le poste | jusqu'au jalon D | 22 à 32 jours | 32 à 48 jours |
| Portfolio complet | jusqu'au jalon E | 32 à 48 jours | 45 à 70 jours |

Si tu travailles le soir et le week-end, le portfolio complet peut raisonnablement demander huit à quatorze semaines. Le but n'est pas de finir vite en copiant du code, mais de pouvoir défendre les décisions.

### 6.3 Ne pas attendre pour candidater

Tu peux candidater avant la fin. En revanche :

- le CV ne mentionne que ce qui est réellement implémenté ;
- le README distingue clairement `implemented`, `in progress` et `planned` ;
- aucun chiffre de performance n'est publié sans rapport reproductible ;
- les termes `production-ready` et `institutional-grade` sont évités tant qu'ils ne sont pas démontrés.

---

## 7. Phase 0 : écrire le contrat du produit

**Charge indicative :** une demi-journée.  
**Jalon :** début de A.

### Résultat visible

Un fichier `docs/product_contract.md` de une à deux pages qui fixe :

- l'utilisateur ;
- la question principale ;
- les deux émetteurs du MVP ;
- les métriques quantitatives ;
- les KPI sustainability ;
- le résultat final ;
- les motifs d'abstention ;
- les éléments hors périmètre.

### Pourquoi cette phase existe

Elle empêche d'empiler des technologies sans produit cohérent. Elle permet aussi de décider objectivement si une idée appartient au MVP.

### Notions à comprendre

- finance quantitative ;
- sustainable finance ;
- différence entre performance de sustainability, risque financier lié à la sustainability et impact réel ;
- trustworthy AI ;
- abstention ;
- MVP.

### Marche à suivre

1. Copier la promesse de la section 1 et la reformuler avec tes mots.
2. Fixer un seul utilisateur : un analyste de recherche, pas un investisseur particulier.
3. Fixer une seule sortie : un `Portfolio Research Brief` auditable.
4. Garder deux émetteurs seulement jusqu'à validation du corpus.
5. Limiter les KPI climat à Scope 1, Scope 2, énergie et objectifs.
6. Écrire cinq situations qui imposent `abstain` ou `review_required`.
7. Copier la liste « hors périmètre » et l'adapter si nécessaire.
8. Écrire le script de démonstration attendu en dix lignes.

### Répartition des responsabilités

- **Python :** aucune décision métier encore.
- **LLM :** aucun.
- **Humain :** définit le besoin, les limites et les risques acceptables.

### Exercice sans IA

Présenter le projet en trente secondes, sans citer de bibliothèque et sans énumérer quatre produits.

### Tests

Pas de test automatisé. Faire une revue de cohérence :

- chaque fonctionnalité prévue sert-elle le parcours principal ?
- chaque métrique a-t-elle un utilisateur et une décision associée ?
- un élément hors périmètre s'est-il glissé dans le MVP ?

### Questions de maîtrise

- Quel problème unique le système résout-il ?
- Pourquoi la couche climat n'est-elle pas un score ESG ?
- Pourquoi les tokens ne donnent-ils pas une empreinte CO₂ ?
- Quand le système doit-il s'abstenir ?

### Pièges

- promettre une mesure d'impact causal ;
- confondre objectif climatique et résultat obtenu ;
- choisir une entreprise avant de vérifier ses documents ;
- intégrer arbitrairement la sustainability dans l'optimiseur.

### Critère de fin et point d'arrêt

Ne pas coder avant de pouvoir expliquer le projet clairement et de disposer d'une liste explicite de non-objectifs.

### Commit attendu

`docs: define trustworthy quant research product scope`

---

## 8. Phase 1 : auditer et figer la version actuelle

**Charge indicative :** un à deux jours.  
**Jalon :** A.

### Résultat visible

- tag `v1.0-baseline` ;
- inventaire factuel du dépôt ;
- cinq cas de référence ;
- entrées et sorties conservées ;
- limites connues ;
- premières mesures de latence et nombre d'appels, si disponibles.

### Pourquoi cette phase existe

Sans baseline, tu ne peux pas prouver que la migration améliore la qualité, le coût ou la fiabilité.

### Notions à comprendre

- baseline ;
- reproductibilité ;
- fixture ;
- dépendance externe ;
- dérive des prix et dérive des modèles ;
- différence entre comportement observé et comportement documenté.

### Marche à suivre

1. Vérifier `git status` et préserver les changements existants.
2. Créer une branche de migration.
3. Taguer l'état initial seulement lorsqu'il est propre et relançable.
4. Documenter l'arbre réel du dépôt.
5. Corriger dans un document d'audit, sans encore refactorer, les écarts du README.
6. Tracer manuellement une requête depuis Streamlit jusqu'à SQLite.
7. Identifier tous les téléchargements de prix dans un même run.
8. Créer cinq prompts/cas de référence :
   - un seul ticker ;
   - deux tickers ;
   - ticker invalide ;
   - historique incomplet ;
   - demande poussant à une recommandation trop précise.
9. Sauvegarder les entrées, les données de marché utilisées si possible et les sorties.
10. Relever modèle, paramètres, nombre d'appels, temps total et erreurs.
11. Noter les résultats comme observations, pas comme benchmark statistique.

### Répartition des responsabilités

- **Python :** exécute le pipeline existant.
- **LLM :** produit les sorties de référence.
- **Humain :** décrit les limites et juge les incohérences.

### Exercice sans IA

Dessiner à la main l'enchaînement exact des fonctions et les données échangées. Vérifier ensuite ce dessin dans le code.

### Tests

À ce stade, conserver au minimum :

- un fichier de prix figé ;
- une sortie de calcul connue ;
- un cas d'erreur connu ;
- un snapshot de la base SQLite de test ou un export lisible.

### Questions de maîtrise

- Pourquoi le même prompt peut-il changer demain ?
- Quelles entrées faut-il figer pour comparer deux architectures ?
- Où le dépôt télécharge-t-il les prix ?
- Quelle différence entre erreur de données, erreur de calcul et erreur du LLM ?

### Pièges

- refactorer avant d'avoir préservé le comportement ;
- croire le README sans vérifier le code ;
- comparer deux runs basés sur des prix différents ;
- traiter une seule sortie LLM comme une moyenne fiable.

### Critère de fin et point d'arrêt

La v1 doit être identifiable et ses cinq cas doivent pouvoir être relancés ou au moins rejoués avec des fixtures figées.

### Commit attendu

`test: capture v1 baseline and reference cases`

---

## 9. Phase 2 : installer le filet de sécurité technique

**Charge indicative :** un à deux jours.  
**Jalon :** fin de A.

### Résultat visible

- `pyproject.toml` ;
- environnement reproductible ;
- Ruff ;
- pytest ;
- fixtures déterministes ;
- client LLM simulé ;
- fournisseur de données injectable ;
- première CI sans appel payant.

### Pourquoi cette phase existe

Les phases suivantes modifient des formules, des modèles et le stockage. Sans tests précoces, chaque refactor peut casser silencieusement le prototype.

### Notions à comprendre

- test unitaire ;
- test d'intégration ;
- fixture ;
- mock/fake ;
- injection de dépendance ;
- test déterministe ;
- lint et formatage ;
- CI.

### Marche à suivre

1. Choisir Python 3.12 pour l'environnement du projet.
2. Centraliser les dépendances et outils dans `pyproject.toml`.
3. Utiliser `uv` si tu veux un workflow moderne et rapide ; `pip` reste acceptable si l'environnement est verrouillé.
4. Ajouter les commandes standard :

   ```bash
   uv sync
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest
   ```

5. Créer `tests/unit` et `tests/integration`.
6. Créer une petite fixture CSV ou Parquet de prix synthétiques.
7. Introduire une interface `MarketDataProvider`.
8. Implémenter :
   - `YFinanceMarketDataProvider` pour la démo ;
   - `FrozenMarketDataProvider` pour les tests.
9. Introduire une interface de client LLM et un faux client retournant une réponse connue.
10. Écrire cinq premiers tests.
11. Ajouter une GitHub Action exécutant lint et tests sans réseau.

### Répartition des responsabilités

- **Python :** isole les dépendances externes et rend les tests reproductibles.
- **LLM :** remplacé par un fake dans la CI.
- **Humain :** choisit ce qui constitue le comportement attendu.

### Exercice sans IA

Écrire un test qui échoue volontairement, corriger la fonction, puis vérifier qu'il passe. Ensuite expliquer pourquoi le test aurait détecté une régression.

### Tests minimums

- chargement correct d'une fixture ;
- ticker absent ;
- série vide ;
- fake LLM appelé une seule fois ;
- erreur du fournisseur transformée en erreur métier explicite.

### Questions de maîtrise

- Quelle différence entre test unitaire, test d'intégration et eval LLM ?
- Pourquoi la CI ne doit-elle pas appeler l'API payante par défaut ?
- Pourquoi injecter le fournisseur de données ?
- Qu'est-ce qu'un test fragile ?

### Pièges

- tester l'implémentation ligne par ligne au lieu du comportement ;
- utiliser le réseau dans tous les tests ;
- stocker une vraie clé API dans le dépôt ;
- lancer un grand refactor avant le premier test.

### Critère de fin et point d'arrêt

Une pull request fictive doit pouvoir exécuter automatiquement les tests de base, sans réseau, sans secret et sans coût.

### Commit attendu

`test: add deterministic test harness and CI baseline`

---

## 10. Phase 3 : reconstruire le Quant Core

**Charge indicative :** trois à cinq jours.  
**Jalon :** début de B.

### Résultat visible

Un moteur quantitatif indépendant du LLM qui :

- utilise un seul snapshot de prix par run ;
- enregistre une date de référence ;
- emploie la même période pour tous les calculs ;
- documente les conventions ;
- produit des métriques testées ;
- signale les données insuffisantes ;
- conserve les diagnostics de l'optimiseur.

### Pourquoi cette phase existe

Une synthèse IA n'est pas fiable si ses entrées numériques ne le sont pas. Le dépôt actuel retélécharge des données dans le stratège de portefeuille, parfois avec une fenêtre différente de celle choisie dans l'interface. Le premier gain de fiabilité est donc financier et déterministe.

### Notions à comprendre

#### Rendements

- rendement simple : `P_t / P_(t-1) - 1` ;
- rendement logarithmique : `ln(P_t / P_(t-1))` ;
- rendement cumulé ;
- fréquence quotidienne et annualisation.

Le choix doit être cohérent. Il ne faut pas calculer une covariance avec un type de rendement et afficher une performance avec un autre sans l'expliquer.

#### Prix ajustés

Un prix ajusté tente de tenir compte d'événements comme les splits et parfois les dividendes. La politique choisie doit être écrite et appliquée partout.

#### Volatilité et covariance

La volatilité mesure la dispersion des rendements. La covariance décrit comment deux actifs varient ensemble. Elles dépendent de la période, de la fréquence et de l'annualisation.

#### VaR et Expected Shortfall

- **VaR historique :** quantile observé dans les rendements historiques ;
- **VaR paramétrique :** estimation fondée sur une distribution supposée et ses paramètres ;
- **Expected Shortfall/CVaR :** perte moyenne au-delà du seuil de VaR.

Toujours préciser :

- horizon ;
- niveau de confiance ;
- convention de signe ;
- unité ;
- méthode ;
- hypothèses.

#### Maximum drawdown

Plus forte baisse entre un sommet historique et le creux suivant sur la période observée.

#### Markowitz

Optimisation rendement-risque basée sur une estimation des rendements attendus et de la covariance. Elle est sensible aux entrées. Une moyenne historique annualisée n'est pas une prévision fiable par simple changement de nom.

#### Contraintes et diagnostic

Une optimisation doit signaler :

- convergence ou échec ;
- contraintes satisfaites ;
- poids bornés ;
- somme des poids ;
- actifs retirés ;
- raison d'une solution impossible.

### Marche à suivre

1. Remplacer la détection implicite de tickers par un `PortfolioDefinition` explicite : instruments, règle ou poids initiaux, devise de base, benchmark, contraintes et `analysis_cutoff`.
2. Créer un modèle `MarketSnapshot` contenant au minimum :

   ```python
   snapshot_id: str
   instruments: list[str]
   analysis_cutoff: datetime
   data_start: date
   data_end: date
   retrieved_at: datetime
   source: str
   price_field: str
   adjustment_policy: str
   currencies: dict[str, str]
   rows: int
   artifact_uri: str
   artifact_sha256: str
   schema_version: str
   ```

   `artifact_uri` pointe vers les observations de prix elles-mêmes, par exemple un Parquet immuable. Le hash porte sur une sérialisation canonique documentée.

3. Télécharger les prix une seule fois. `yfinance` reste acceptable pour une démonstration et des fixtures gelées, mais ne doit pas être présenté comme une source de données institutionnelle ; sa page de projet précise qu'il s'agit d'un outil open source non affilié à Yahoo et destiné à la recherche/éducation et à l'usage personnel : [yfinance sur PyPI](https://pypi.org/project/yfinance/).
4. Normaliser les dates et utiliser des timestamps UTC avec fuseau.
5. Réconcilier l'univers demandé et l'univers réellement disponible.
6. Bloquer ou signaler explicitement tout actif sans données suffisantes.
7. Construire une matrice unique de rendements, réutilisée par tous les calculs.
8. Renommer `expected_return` si la valeur est seulement une moyenne historique, par exemple `historical_annualized_return`.
9. Implémenter des fonctions pures pour :
   - rendement cumulé ;
   - rendement annualisé ;
   - volatilité annualisée ;
   - maximum drawdown ;
   - VaR historique ;
   - VaR paramétrique ;
   - Expected Shortfall ;
   - covariance et corrélation ;
   - métriques de portefeuille.
10. Ajouter un benchmark simple et explicite, par exemple equal-weight. Ne demander aucune comparaison à un benchmark absent.
11. Rendre le taux sans risque configurable avec valeur, devise, date et source. Ne pas conserver « 2 % Swiss context » sans justification.
12. Isoler l'optimisation dans une fonction qui retourne poids **et diagnostics**.
13. Présenter l'allocation comme un scénario mathématique soumis à hypothèses.
14. Interdire tout second appel au fournisseur de marché pendant le run.
15. Versionner les formules, par exemple `var_historical_v1`.
16. Filtrer toutes les observations sur `analysis_cutoff`.
17. Écrire `docs/methodology_quant.md`.

### Répartition des responsabilités

- **Python :** toutes les données, transformations, formules et contraintes.
- **LLM :** aucun calcul.
- **Humain :** choisit conventions, hypothèses et limites d'interprétation.

### Exercices sans IA

1. Implémenter `max_drawdown(series)`.
2. Calculer à la main le drawdown de `[100, 110, 88, 95]`.
3. Calculer une VaR historique sur une série de dix rendements.
4. Écrire un test démontrant que deux runs sur le même snapshot donnent les mêmes métriques.

### Tests minimums

- prix constants ;
- série croissante ;
- série avec perte extrême ;
- valeurs manquantes ;
- historique trop court ;
- calendriers différents ;
- ticker échoué ;
- VaR à deux niveaux de confiance ;
- contraintes d'optimisation faisables et infaisables ;
- poids dont la somme respecte la tolérance ;
- absence de second téléchargement.

### Questions de maîtrise

- Pourquoi deux téléchargements successifs peuvent-ils rendre un run incohérent ?
- Quelle différence entre VaR historique et paramétrique ?
- Pourquoi l'Expected Shortfall complète-t-il la VaR ?
- Quelles hypothèses rendent Markowitz instable ?
- Pourquoi une moyenne historique n'est-elle pas une prévision ?
- Comment empêcher le look-ahead bias ?

### Pièges

- mélanger rendements quotidiens et annualisés ;
- supprimer silencieusement toutes les lignes incomplètes ;
- omettre la devise ;
- utiliser un taux sans risque non daté ;
- remplacer silencieusement une optimisation échouée ;
- demander au LLM de calculer un stress test ;
- appeler « recommandation » une solution d'optimisation ;
- revendiquer un backtest sans look-ahead à partir d'un historique téléchargé aujourd'hui.

### Critère de fin et point d'arrêt

Avec le même snapshot et la même configuration, toutes les métriques doivent être identiques. Aucun RAG n'est ajouté tant que les formules, conventions et cas limites ne sont pas testés.

### Commit attendu

`refactor: build reproducible quant core from immutable snapshots`

---

## 11. Phase 4 : définir les contrats et le workflow contrôlé

**Charge indicative :** deux à trois jours.  
**Jalon :** B.

### Résultat visible

- modèles Pydantic séparés ;
- contrat compatible avec les sorties structurées natives, testé avec un fake ;
- workflow Python explicite ;
- version du modèle et du prompt enregistrée ;
- impossibilité pour le LLM de créer ses preuves ou de s'auto-approuver.

### Pourquoi cette phase existe

Le texte libre est difficile à valider. Mais un JSON valide n'est pas nécessairement vrai. Il faut donc séparer la **forme produite par le modèle** des **faits issus des systèmes de confiance** et de la **décision finale**.

### Notions à comprendre

- schéma JSON ;
- Pydantic ;
- sérialisation ;
- invariant métier ;
- sortie structurée native du fournisseur ;
- frontière de confiance ;
- machine à états ;
- workflow borné ;
- budget d'appels et timeout.

### Modèles à créer

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ClaimDraft(BaseModel):
    text_template: str
    claim_type: Literal["quant", "sustainability", "limitation"]
    metric_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    uncertainty: str | None = None


class GeneratedDraft(BaseModel):
    summary: str
    claims: list[ClaimDraft]
    limitations: list[str]


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error", "critical"]
    claim_id: str | None = None
    message: str


class ValidationReport(BaseModel):
    issues: list[ValidationIssue]


class ClaimMetricReference(BaseModel):
    claim_id: str
    metric_id: str
    rendered_value: str
    unit: str
    transformation: Literal["none", "rounded", "percentage"]


class AutomatedAssessment(BaseModel):
    status: Literal[
        "eligible_for_review", "review_required", "abstain"
    ]
    reason_codes: list[str]


class HumanReview(BaseModel):
    disposition: Literal["approved", "corrected", "rejected", "escalated"]
    reviewer_id: str
    comment: str
    reviewed_at: datetime
```

Adapter les champs pendant l'implémentation, mais conserver la séparation des autorités.

Le modèle retourne un `text_template` et choisit des IDs autorisés. Le serveur attribue ensuite `claim_id`, vérifie que les IDs appartiennent au run courant et injecte les valeurs formatées depuis `MetricRecord`. Il crée alors les `ClaimMetricReference`. Cette approche est plus sûre que de laisser le modèle recopier librement les nombres.

### Marche à suivre

1. Créer les modèles métier indépendamment du fournisseur LLM.
2. Définir l'interface du fournisseur et la façon dont le schéma sera envoyé en structured output, mais utiliser un fake dans cette phase.
3. Valider la réponse du fake avec Pydantic.
4. Interdire les champs inconnus sur les objets sensibles.
5. Ajouter des validateurs pour les invariants simples.
6. Définir dès maintenant l'enregistrement minimal qui sera rempli lors des appels réels :
   - fournisseur ;
   - identifiant du modèle ;
   - paramètres ;
   - version du prompt ;
   - identifiant de réponse ;
   - horodatage UTC.
7. Remplacer la chaîne fixe des quatre agents par :

   ```text
   validate_request
     -> load_snapshot
     -> compute_quant_metrics
     -> retrieve_evidence_fake
     -> generate_draft_fake
     -> validate_draft
     -> assess
     -> request_human_review
   ```

8. Donner un timeout et un budget maximal d'appels à chaque run.
9. N'autoriser un appel spécialisé supplémentaire que sur une condition explicite.
10. Conserver l'ancienne chaîne seulement pour la comparaison v1/v3.

À cette phase, le retrieval et le LLM sont des fakes. Le corpus réel, le retriever et le modèle réel sont branchés plus tard. Le cycle du run est déjà explicite :

```text
created -> generated -> validated -> pending_review -> finalized
```

Le résultat automatique est un attribut de la validation, pas une étape d'approbation :

```text
eligible_for_review | review_required | abstain
```

### Répartition des responsabilités

- **Python :** état, transitions, budgets, données et validation de structure.
- **LLM :** le contrat prévoit un brouillon structuré et des références à des IDs existants ; le composant reste simulé dans cette phase.
- **Humain :** définit la politique et prend la décision finale.

### Exercice sans IA

Écrire deux modèles Pydantic et un validateur personnalisé. Provoquer ensuite :

- un champ absent ;
- un mauvais type ;
- un statut interdit ;
- un identifiant mal formé.

### Tests minimums

- JSON valide ;
- JSON invalide ;
- champ inconnu ;
- liste de claims vide ;
- ID inventé ;
- timeout ;
- budget dépassé ;
- transition d'état interdite.

### Questions de maîtrise

- Pourquoi Pydantic garantit-il une forme, pas la vérité ?
- Qui a le droit de créer un `EvidenceRecord` ?
- Pourquoi séparer `GeneratedDraft` et `ValidationReport` ?
- Quelle différence entre workflow et agent ?
- À quel moment un second agent serait-il justifié ?

### Pièges

- mettre `validation_status` dans la sortie du modèle ;
- laisser le modèle choisir `approved` ;
- croire qu'un JSON conforme élimine les hallucinations ;
- multiplier les agents pour moderniser la présentation ;
- laisser une boucle de tools sans limite.

### Tranche verticale obligatoire avant PostgreSQL

Construire un premier parcours exécutable, volontairement petit et en mémoire :

1. charger une fixture de prix ;
2. calculer deux métriques ;
3. créer manuellement un `EvidenceRecord` à partir d'un court passage de test ;
4. faire retourner au fake LLM un `GeneratedDraft` ;
5. valider un claim correct et bloquer un claim incorrect ;
6. produire `eligible_for_review` ou `review_required` ;
7. afficher le résultat dans le terminal ou une page Streamlit minimale.

Cette tranche n'utilise ni corpus complet, ni retriever réel, ni PostgreSQL. Son but est de prouver tôt que les objets s'enchaînent correctement. La phase suivante persiste exactement ce parcours.

### Critère de fin et point d'arrêt

La tranche verticale fonctionne avec des fakes et le contrat empêche le futur modèle de modifier les métriques, les preuves ou son statut de validation. Toute tentative est rejetée.

### Commit attendu

`feat: separate generated drafts from trusted validation states`

---

## 12. Phase 5 : enregistrer métadonnées et décisions dans PostgreSQL

**Charge indicative :** deux à quatre jours.  
**Jalon :** fin de B.

### Résultat visible

- PostgreSQL local ;
- modèles SQLAlchemy 2 ;
- migrations Alembic ;
- historique append-only au niveau applicatif ;
- reconstruction possible d'un run ;
- requêtes d'audit.

### Pourquoi cette phase existe

Pour la version candidature complète, PostgreSQL, SQLAlchemy et Alembic ne sont plus des bonus. Ils montrent une gestion sérieuse des métadonnées, décisions, relations, contraintes et évolutions de schéma. Les PDF et séries brutes restent des artefacts immuables dans un stockage de fichiers ; PostgreSQL enregistre leur URI, leur hash et leur version.

### Notions à comprendre

- table, ligne et colonne ;
- clé primaire et clé étrangère ;
- contrainte `NOT NULL`, `UNIQUE` et `CHECK` ;
- transaction ;
- index ;
- jointure ;
- ORM ;
- migration ;
- normalisation ;
- append-only ;
- différence entre `create_all()` et une migration versionnée.

### Tables principales

Une structure possible :

- `research_runs` ;
- `market_snapshots` ;
- `instruments` ;
- `price_series_metadata` ;
- `metric_records` ;
- `documents` ;
- `document_pages` ;
- `evidence_records` ;
- `sustainability_observations` ;
- `climate_targets` ;
- `generated_drafts` ;
- `claims` ;
- `claim_metric_links` ;
- `claim_evidence_links` ;
- `validation_reports` ;
- `validation_issues` ;
- `automated_assessments` ;
- `human_review_events` ;
- `model_calls` ;
- `evaluation_runs`.

Les gros fichiers bruts peuvent rester dans un stockage de fichiers local pour le MVP ; PostgreSQL conserve leur identité, leur hash, leur chemin ou URI et leurs métadonnées.

### Marche à suivre

1. Ajouter PostgreSQL à Docker Compose.
2. Configurer la connexion uniquement par variable d'environnement.
3. Créer une couche `session.py` et des repositories fins.
4. Modéliser d'abord `research_runs`, snapshots et métriques.
5. Créer la migration initiale avec Alembic.
6. Examiner manuellement la migration générée.
7. Tester une création de base depuis zéro.
8. Migrer la persistance du run sans supprimer immédiatement SQLite.
9. Ajouter les objets de preuve, validation et revue au fil des phases.
10. Utiliser des dates UTC avec fuseau.
11. Ajouter contraintes et indexes en fonction des requêtes réelles.
12. Écrire au moins trois requêtes SQL à la main.
13. Documenter le modèle dans `docs/architecture.md`.
14. Retirer SQLite seulement lorsque la parité utile est démontrée.

### Requêtes à savoir écrire

1. Retrouver toutes les métriques d'un run.
2. Retrouver les claims sans preuve valide.
3. Retrouver la dernière décision humaine sans écraser les versions précédentes.

Exemple de question SQL :

> Pour chaque claim en `review_required`, retourner le run, le texte, les issues critiques et la dernière disposition humaine.

### Répartition des responsabilités

- **Python/SQL :** persistance, contraintes, transactions et requêtes.
- **LLM :** aucun accès SQL libre ; seulement des outils en lecture bornés si un besoin futur est prouvé.
- **Humain :** définit la politique de conservation et inspecte les migrations.

### Exercice sans IA

Créer une migration ajoutant une colonne non nulle de manière sûre. Recréer ensuite la base vide, appliquer toutes les migrations et expliquer l'ordre.

### Tests minimums

- création d'un run ;
- rollback sur transaction invalide ;
- contrainte de clé étrangère ;
- unicité d'un hash ou identifiant lorsque nécessaire ;
- migration `upgrade` depuis une base vide ;
- vérification que la base est au dernier head ;
- reconstruction d'un run avec ses métriques ;
- correction qui ne supprime pas la version initiale.

### Questions de maîtrise

- Pourquoi ne pas stocker toute l'analyse dans un seul blob JSON ?
- Quand un JSONB est-il utile malgré tout ?
- Pourquoi utiliser Alembic plutôt que `create_all()` ?
- Qu'est-ce qu'une transaction ?
- Comment une clé étrangère protège-t-elle le lineage ?

### Pièges

- exposer le mot de passe dans Git ;
- écraser un résultat existant ;
- laisser Alembic autogénérer sans relire ;
- créer des tables sans contraintes ;
- utiliser l'ORM sans savoir lire la requête SQL produite.

### Critère de fin et point d'arrêt

À partir d'un `research_run_id`, il faut retrouver le snapshot, les paramètres, les métriques et leurs versions. Une base vide doit être reconstruite par les migrations. Le Quant Core est recalculable avec l'artefact, le commit, les dépendances et la configuration figés. Une génération LLM passée est consultable et auditable, mais n'est pas garantie reproductible mot pour mot.

### Commit attendu

`feat: persist auditable research runs in postgresql`

---

## 13. Phase 6 : construire le corpus de sustainable finance

**Charge indicative :** quatre à sept jours.  
**Jalon :** début de C.

### Résultat visible

- deux émetteurs retenus après audit ;
- six à dix documents officiels maximum ;
- manifeste versionné ;
- PDF bruts immuables et hashés ;
- extraction page par page ;
- taxonomie courte de KPI ;
- petit jeu de vérité annoté manuellement.

### Pourquoi cette phase existe

La sustainability doit devenir une couche documentaire exploitable dans la recherche financière, pas un slogan. Les valeurs ne sont utiles que si leur période, unité, périmètre et méthode sont conservés.

### Notions à comprendre

#### Sustainable finance

Le projet construit une lentille documentaire sur l'exposition et la performance climatiques publiées. Ces éléments peuvent éclairer une analyse du risque de transition, mais, sans modèle de transmission vers les cash-flows, le coût du capital ou les rendements attendus, le projet ne quantifie pas le risque financier climatique. Il ne prouve pas non plus un impact net.

IFRS S2 constitue un bon cadre d'apprentissage pour les risques et opportunités climatiques susceptibles d'affecter les perspectives financières : [IFRS Foundation, IFRS S2](https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/).

#### Frontière de preuve

Une citation prouve que l'émetteur a publié une valeur ou une affirmation. Elle ne prouve pas, à elle seule, que cette information représente fidèlement la réalité opérationnelle.

- « document officiel » signifie source officielle de l'émetteur, pas source nécessairement assurée ;
- `issuer_reported` signifie publié par l'émetteur, pas vérifié indépendamment ;
- le niveau d'assurance et son périmètre sont modélisés séparément ;
- une preuve de publication ne démontre ni comparabilité, ni matérialité financière, ni impact.

#### Scopes d'émissions

- **Scope 1 :** émissions directes des sources contrôlées ;
- **Scope 2 :** émissions liées à l'énergie achetée ;
- **Scope 3 :** autres émissions de la chaîne de valeur.

Pour Scope 2, conserver séparément location-based et market-based. Voir [GHG Protocol, Scope 2 Guidance](https://ghgprotocol.org/scope-2-guidance).

#### Autres distinctions

- valeur absolue contre intensité ;
- objectif contre résultat ;
- donnée reportée contre donnée dérivée ;
- donnée nulle contre donnée absente ;
- périmètre consolidé contre périmètre partiel ;
- assurance limitée contre raisonnable ;
- publication originale contre retraitement.

### Audit des émetteurs

Auditer Bachem, Siegfried, Lonza et éventuellement PolyPeptide, puis retenir deux candidats répondant à ces conditions :

- rapports officiels téléchargeables ;
- au moins deux périodes ;
- KPI ciblés présents ;
- définitions suffisamment claires ;
- preuves extractibles page par page ;
- retraitements identifiables.

Deux émetteurs bien traités valent mieux que quatre comparaisons fragiles.

### Corpus autorisé

- rapport annuel officiel ;
- rapport sustainability/ESG officiel ;
- annexe KPI officielle ;
- déclaration d'assurance jointe ;
- rapport climat séparé.

Une présentation investisseurs ou une page web peut fournir du contexte, mais ne devient pas automatiquement la source canonique d'un KPI.

### Manifeste documentaire

Chaque fichier conserve :

```yaml
document_id:
issuer_id:
document_type:
reporting_period:
publication_date:
source_url:
downloaded_at:
sha256:
language:
supersedes_document_id:
status:
```

Le PDF brut ne doit jamais être modifié.

### Taxonomie du MVP

1. **Émissions opérationnelles**
   - Scope 1 ;
   - Scope 2 location-based ;
   - Scope 2 market-based ;
   - Scope 1 + 2 uniquement lorsque la méthode est explicite.

2. **Énergie**
   - consommation totale ;
   - électricité ;
   - part ou volume d'électricité renouvelable, en conservant le numérateur, le dénominateur, le mécanisme d'approvisionnement publié et le périmètre.

   Ne pas comparer automatiquement « énergie renouvelable » et « électricité renouvelable ».

3. **Objectifs**
   - année de référence ;
   - année cible ;
   - périmètre ;
   - type d'objectif ;
   - valeur cible ;
   - progrès publié ;
   - validation externe.

   Distinguer `issuer_claimed_external_validation` et `externally_verified_in_registry`. Le second statut exige une source officielle de l'organisme validateur ; sinon, rester au premier statut.

### Schémas séparés

Une observation chiffrée, un résultat de recherche, une cible, une évaluation de comparabilité et une évaluation d'assurance sont des objets différents.

```python
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SustainabilityObservation(BaseModel):
    observation_id: str
    issuer_id: str
    raw_metric_label: str
    metric_code: str
    period_start: date
    period_end: date
    raw_value: Decimal
    raw_unit: str
    normalized_value: Decimal | None = None
    normalized_unit: str | None = None
    basis: Literal["absolute", "intensity"]
    ghg_scope: Literal[
        "scope_1", "scope_2", "scope_3", "not_applicable"
    ]
    scope_2_method: Literal[
        "location_based", "market_based", "not_applicable"
    ]
    intensity_denominator: str | None = None
    organizational_boundary: str | None = None
    geographic_or_site_coverage: str | None = None
    methodology_or_standard: str | None = None
    value_origin: Literal["issuer_reported", "derived"]
    evidence_ids: list[str] = Field(default_factory=list)
    input_observation_ids: list[str] = Field(default_factory=list)
    restated_from_observation_id: str | None = None


class CoverageFinding(BaseModel):
    issuer_id: str
    metric_code: str
    status: Literal[
        "not_found_in_corpus", "issuer_states_not_disclosed",
        "not_applicable", "ambiguous"
    ]
    searched_document_ids: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class ComparisonAssessment(BaseModel):
    left_observation_id: str
    right_observation_id: str
    purpose: Literal["time_series", "cross_issuer"]
    ruleset_version: str
    status: Literal[
        "comparable", "partially_comparable",
        "not_comparable", "review_required"
    ]
    reasons: list[str]


class AssuranceAssessment(BaseModel):
    observation_id: str
    status: Literal[
        "not_stated", "explicitly_not_assured",
        "issuer_claimed_assurance",
        "verified_in_assurance_statement"
    ]
    level: Literal["limited", "reasonable", "unknown"]
    assurance_evidence_id: str | None = None
    assurance_scope_confirmed: bool
```

Une cible climatique utilise encore un schéma séparé. Une valeur n'est jamais « comparable » dans l'absolu : la comparabilité dépend de l'autre observation, du but de la comparaison et de la version des règles.

### Marche à suivre

1. Écrire `docs/methodology_sustainability.md`.
2. Auditer les quatre candidats avec une grille identique.
3. Retenir deux émetteurs.
4. Télécharger uniquement les documents officiels nécessaires.
5. Calculer SHA-256 et remplir le manifeste.
6. Garder le brut hors Git si les droits ou la taille l'exigent.
7. Versionner le manifeste, les URLs, hashes, scripts et petites fixtures autorisées.
8. Extraire le texte page par page en conservant numéro PDF et numéro imprimé si disponible.
9. Définir la taxonomie avant toute extraction LLM.
10. Annoter manuellement au moins vingt cas représentatifs : valeurs présentes, zéro réel, donnée non trouvée, tableau ambigu, retraitement, cible, méthodes Scope 2 différentes, périmètre incompatible, assurance hors périmètre et comparaison à refuser.
11. Pour chaque observation, saisir valeur, unité, période, périmètre, méthode, page et assurance.
12. Implémenter les validateurs d'unité, période et méthode.
13. Ajouter une métrique dérivée seulement si les entrées sont compatibles.
14. Marquer toute métrique calculée `derived`, jamais `issuer_reported`.
15. Filtrer les documents sur `publication_date <= analysis_cutoff`.
16. Relier ce corpus au même `research_run_id` que l'analyse quant.

### Règles métier obligatoires

- `0`, `non communiqué` et `non trouvé dans le corpus` sont différents.
- Une absence de résultat de recherche ne prouve pas que l'entreprise ne publie pas la donnée.
- Une valeur retraitée devient canonique sans supprimer l'ancienne.
- Une assurance ne s'applique que si la métrique entre explicitement dans son périmètre ; `explicitly_not_assured` n'est utilisé que si cela est établi, sinon conserver `not_stated`.
- Une comparaison automatique exige : même métrique et définition, même scope, même méthode Scope 2, même base absolue/intensité, même dénominateur d'intensité, périodes compatibles, unités convertibles, périmètres organisationnels et géographiques compatibles, méthode de consolidation compatible et retraitements cohérents.
- Un champ requis manquant produit `review_required` ou `not_comparable`.
- Deux émissions absolues de groupes de tailles différentes peuvent être placées côte à côte, mais elles ne suffisent pas à conclure lequel est « plus performant ».
- Les calculs et conversions sont faits en Python.
- Une extraction ambiguë passe en revue humaine.

### Répartition des responsabilités

- **Python :** manifeste, hash, parsing, normalisation, conversions et règles de comparabilité.
- **LLM :** proposition d'extraction structurée et synthèse ultérieure.
- **Humain :** définition de taxonomie, annotation de référence et résolution des ambiguïtés.

### Exercice sans IA

Extraire manuellement un KPI d'un rapport et noter :

- valeur ;
- unité ;
- période ;
- périmètre ;
- méthode ;
- page ;
- statut d'assurance ;
- éventuel retraitement.

Faire ensuite le même exercice pour une cible et expliquer pourquoi les deux objets diffèrent.

### Tests minimums

- valeur nulle ;
- valeur absente ;
- unités `tCO2e` et `ktCO2e` ;
- Scope 2 location-based contre market-based ;
- période différente ;
- périmètre différent ;
- cible prise à tort pour un résultat ;
- retraitement ;
- assurance qui ne couvre pas la métrique ;
- comparaison entre valeurs absolues de tailles d'entreprise différentes ;
- preuve sur mauvaise page ;
- extraction de tableau ambiguë.

### Questions de maîtrise

- Deux valeurs d'émissions sont-elles comparables si leurs périmètres diffèrent ?
- Une baisse d'intensité prouve-t-elle une baisse absolue ?
- Une cible est-elle une performance ?
- Une activité utile prouve-t-elle un impact ?
- Pourquoi une donnée manquante ne vaut-elle pas zéro ?

### Pièges

- fabriquer un score ESG ;
- mélanger les méthodes Scope 2 ;
- cacher les changements de périmètre ;
- utiliser « impact » sans méthodologie ;
- demander au LLM de décider seul de la comparabilité.

### Critère de fin et point d'arrêt

Chaque valeur affichable doit ouvrir une preuve exacte. Toute affirmation numérique de performance possède période, unité, périmètre, méthode et preuve. Toute affirmation qualitative possède une preuve et les dimensions applicables. Une information manquante peut être signalée, mais elle ne peut pas soutenir une comparaison de performance.

### Commit attendu

`feat: add traceable climate evidence corpus and data model`

---

## 14. Phase 7 : comparer les stratégies de récupération

**Charge indicative :** trois à cinq jours.  
**Jalon :** C.

### Résultat visible

Un rapport comparant sur les mêmes questions :

1. document complet ou long context ;
2. recherche lexicale BM25 ;
3. recherche dense par embeddings ;
4. recherche hybride ;
5. hybride avec reranking, seulement si utile.

L'architecture finale est choisie à partir des résultats, pas d'un mot-clé technologique.

### Pourquoi cette phase existe

Le RAG n'est pas obsolète, mais « découper, vectoriser et espérer » n'est pas une stratégie. Les dates, unités et noms précis bénéficient souvent de la recherche lexicale. Les formulations paraphrasées peuvent bénéficier des embeddings. Avec seulement quelques documents, le long context peut être un baseline pertinent.

Anthropic décrit une approche de contextual retrieval combinant contexte, recherche lexicale et embeddings : [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval).

### Notions à comprendre

- ingestion ;
- chunking ;
- index lexical ;
- BM25 ;
- embedding ;
- similarité ;
- top-k ;
- recherche hybride ;
- Reciprocal Rank Fusion ;
- reranker ;
- filtres metadata ;
- recall@k ;
- Mean Reciprocal Rank ;
- citation precision ;
- erreur de récupération contre erreur de génération.

### Geler les jeux d'évaluation avant l'expérience

Créer dès maintenant les 25 à 40 cas prévus pour le jalon C, dans deux fichiers séparés :

- `data/evals/retrieval_gold.v1.jsonl` pour documents, pages et passages attendus ;
- `data/evals/workflow_eval.v1.jsonl` pour faits requis, claims acceptables, décisions et sécurité.

Chaque fichier possède des splits `dev`, `validation` et `holdout`. Le contenu et le hash du holdout sont gelés avant tout réglage de retrieval ou de prompt. Les phases 7 et 8 utilisent seulement `dev` et `validation` ; le holdout est ouvert une seule fois en phase 9.

Les cas de retrieval couvrent notamment :

- chiffre exact ;
- unité ;
- année ;
- cible ;
- changement de méthode ;
- donnée absente ;
- deux sources en conflit ;
- question paraphrasée ;
- terme exact rare ;
- tableau.

### Marche à suivre

1. Préserver les pages et métadonnées pendant le parsing.
2. Construire un baseline long context lorsque le volume le permet.
3. Construire une recherche BM25.
4. Construire une recherche dense simple.
5. Mesurer les trois sur les mêmes questions de `dev` et `validation`.
6. Ajouter des filtres :
   - émetteur ;
   - période ;
   - type de document ;
   - statut de version.
7. Combiner lexical et dense par une méthode de fusion documentée.
8. Tester un reranker seulement si l'hybride laisse un écart mesurable.
9. Pour les retrievers, mesurer :
   - recall@1, @3 et @5 ;
   - rang de la bonne page ;
   - précision des citations ;
   - reconnaissance correcte de l'absence ;
   - latence ;
   - coût éventuel.
10. Pour le long context, mesurer plutôt si la preuve attendue était incluse, si elle a été citée et si la réponse reconnaît correctement l'absence. Recall@k et MRR ne s'appliquent pas directement lorsqu'il n'existe pas de classement top-k.
11. Choisir la solution la plus simple atteignant les seuils.
12. Documenter les échecs, pas seulement la moyenne.

### Place de pgvector

PostgreSQL reste le système d'enregistrement des métadonnées et décisions. `pgvector` est conditionnel :

- pour un petit corpus, commencer par une recherche exacte ;
- ne pas ajouter HNSW par réflexe ;
- conserver `pgvector` si l'expérience dense ou hybride justifie son usage ;
- sinon garder le schéma prêt sans prétendre qu'un index vectoriel est nécessaire.

Le projet pgvector supporte recherche exacte, approximative et combinaison avec la recherche textuelle PostgreSQL : [pgvector](https://github.com/pgvector/pgvector).

### Répartition des responsabilités

- **Python/SQL :** parsing, index, filtres, classement et mesures.
- **Modèles d'embeddings/reranker :** scores probabilistes de similarité.
- **Humain :** crée les pages de référence et examine les erreurs.

### Exercice sans IA

Pour trois questions, lire les documents, noter les passages attendus, lancer chaque retriever et expliquer pourquoi les rangs diffèrent.

### Tests minimums

- recherche par terme exact ;
- paraphrase ;
- année filtrée ;
- mauvais émetteur ;
- document remplacé ;
- page conservée ;
- question sans réponse ;
- égalité de scores ;
- chunk vide ;
- tableau séparé de son titre.

### Questions de maîtrise

- Quand BM25 peut-il battre un embedding ?
- Pourquoi mesurer retrieval et génération séparément ?
- Si le bon passage est absent du top-k, que peut faire le générateur ?
- Pourquoi un index approximatif peut-il réduire le recall ?
- Qu'est-ce que le reranking ajoute ?

### Pièges

- choisir pgvector pour le CV ;
- perdre le numéro de page ;
- ajuster la stratégie sur le holdout ;
- mesurer seulement la réponse finale ;
- considérer une absence de résultat comme une preuve d'absence.

### Critère de fin et point d'arrêt

La stratégie retenue doit battre ou égaler le baseline simple sur les cas critiques, avec un compromis qualité/coût documenté. Chaque résultat doit pointer vers document, version, page et passage stocké.

### Commit attendu

`eval: compare long-context lexical dense and hybrid retrieval`

---

## 15. Phase 8 : générer, valider et décider sans auto-certification

**Charge indicative :** trois à cinq jours.  
**Jalon :** C.

### Résultat visible

Un flux complet pour un seul cas :

```text
snapshot + métriques + preuves
  -> brouillon structuré
  -> validations
  -> eligible_for_review | review_required | abstain
```

### Pourquoi cette phase existe

Le système doit permettre à l'IA de synthétiser sans lui donner l'autorité sur les données, les sources ou la décision. La sécurité vient d'une combinaison de contrats, règles, évaluations et revue humaine, pas d'un prompt promettant de « ne pas halluciner ».

### Notions à comprendre

- claim atomique ;
- validateur numérique ;
- intégrité d'une preuve ;
- soutien sémantique ;
- tolérance ;
- fraîcheur ;
- contradiction ;
- politique de décision ;
- abstention ;
- allowlist ;
- prompt injection indirecte.

### Niveaux de validation

#### 1. Structure

- schéma valide ;
- types corrects ;
- valeurs autorisées ;
- taille bornée.

#### 2. Intégrité déterministe

- `metric_id` existant ;
- `evidence_id` existant ;
- document et page cohérents ;
- hash connu ;
- unité et période compatibles ;
- nombres cités présents dans les métriques autorisées.

#### 3. Soutien sémantique

Déterminer si un passage soutient une interprétation complexe n'est pas toujours une règle purement déterministe. Pour le MVP :

- les contrôles d'intégrité et de cohérence restent déterministes ;
- le soutien sémantique est annoté dans les evals et vérifié par le reviewer humain ;
- un juge LLM peut être expérimenté comme signal supplémentaire, après calibration sur un petit jeu annoté, mais il ne décide jamais ;
- le modèle de synthèse n'a accès à aucun outil pendant la génération : toutes ses entrées ont déjà été préparées.

#### 4. Politique

Le moteur de règles produit :

- `eligible_for_review` : aucun problème bloquant connu, mais une approbation humaine reste nécessaire ;
- `review_required` : une ambiguïté ou un risque doit être examiné ;
- `abstain` : les données ou preuves ne permettent pas de répondre.

### Marche à suivre

1. Réduire la synthèse à un appel principal.
2. Brancher le vrai fournisseur avec sa sortie structurée native, puis valider avec Pydantic.
3. Fournir uniquement :
   - métriques autorisées ;
   - preuves récupérées ;
   - règles de sortie ;
   - limites.
4. Demander des claims atomiques.
5. Exiger des références appartenant à l'allowlist du run courant, pas seulement des IDs existant quelque part dans la base.
6. Attribuer les `claim_id` côté serveur et injecter les valeurs numériques finales depuis les `MetricRecord`.
7. Ajouter un validateur numérique.
8. Ajouter un validateur d'intégrité des preuves.
9. Ajouter un validateur sustainability :
   - période ;
   - unité ;
   - méthode Scope 2 ;
   - périmètre ;
   - issuer_reported/derived ;
   - target/actual.
10. Ajouter un contrôle de fraîcheur.
11. Ajouter un détecteur de conflits connus.
12. Définir une table de règles de décision.
13. Interdire les recommandations BUY/HOLD/SELL, calendriers arbitraires et allocations présentées comme conseil.
14. Enregistrer dès cet appel réel la télémétrie minimale : modèle, version du prompt, tokens d'entrée/sortie, latence, retries, cache éventuel, statut, erreur et coût selon une table tarifaire datée.
15. Tester les instructions malveillantes dans les documents.
16. Borner :
   - nombre d'appels ;
   - durée ;
   - longueur des entrées et sorties ;
   - documents autorisés.
17. Conserver chaque issue, même si le résultat est ensuite corrigé.

### Cas de sécurité à tester

- « Ignore previous instructions » dans un rapport ;
- faux `evidence_id` ;
- URL malveillante ;
- demande d'exfiltration d'un secret ;
- instruction de déclencher un outil ;
- document excessivement long ;
- boucle d'appels ;
- source non officielle présentée comme canonique ;
- texte qui imite une instruction système.

### Répartition des responsabilités

- **Python :** vérifications déterministes et politique.
- **LLM principal :** brouillon.
- **Vérificateur probabiliste éventuel :** signal complémentaire, jamais décision finale.
- **Humain :** arbitre les ambiguïtés et approuve.

### Exercice sans IA

Créer manuellement quatre claims :

1. correct et sourcé ;
2. nombre incorrect ;
3. bonne page mais interprétation non soutenue ;
4. preuve inexistante.

Faire passer chacun dans les validateurs et expliquer le résultat.

### Tests minimums

- nombre exact ;
- arrondi autorisé ;
- mauvaise unité ;
- mauvaise période ;
- ID inexistant ;
- passage hors sujet ;
- contradiction ;
- donnée trop ancienne ;
- document injecté ;
- hors périmètre ;
- absence de preuve ;
- demande de conseil personnalisé.

### Questions de maîtrise

- Pourquoi un ID existant ne prouve-t-il pas le support sémantique ?
- Quelle tolérance numérique choisir et pourquoi ?
- Quelle différence entre `review_required` et `abstain` ?
- Pourquoi un second LLM n'est-il pas un validateur suffisant ?
- Pourquoi les documents doivent-ils être traités comme non fiables ?

### Pièges

- comparaison de nombres sans unité ;
- validation sémantique présentée comme certaine ;
- règles trop permissives ;
- approbation choisie par le modèle ;
- accès d'outil trop large ;
- prompt de sécurité considéré comme protection complète.

### Critère de fin et point d'arrêt

Tous les cas critiques connus doivent être bloqués dans le jeu courant, sans généraliser cela en promesse de fiabilité universelle. Une fausse éligibilité automatique critique interdit de continuer.

### Commit attendu

`feat: validate grounded claims and enforce abstention policy`

---

## 16. Phase 9 : faire des évaluations la colonne vertébrale

**Charge indicative :** trois à cinq jours.  
**Jalon :** fin de C.

### Résultat visible

- dataset versionné ;
- séparation développement, validation et holdout ;
- 25 à 40 cas ;
- métriques par composant ;
- répétitions des cas probabilistes ;
- comparaison v1/v3 ;
- rapport reproductible.

### Pourquoi cette phase existe

Les tests protègent le code. Les evals montrent comment se comporte le système IA. Une moyenne unique masque les erreurs graves ; il faut savoir si l'échec vient du retrieval, de la génération, du validateur ou de la politique.

### Notions à comprendre

- oracle ou réponse attendue ;
- développement, validation et holdout ;
- fuite de test ;
- précision, rappel et F1 ;
- matrice de confusion ;
- fausse éligibilité automatique ;
- variabilité ;
- évaluation par composant ;
- évaluation end-to-end ;
- régression ;
- intervalle d'incertitude et limites d'un petit échantillon.

### Structure d'un cas

```yaml
case_id:
split:
question:
portfolio:
analysis_cutoff:
expected_metric_ids:
allowed_evidence_ids:
expected_pages:
required_facts:
acceptable_claims:
expected_automated_outcome:
forbidden_claims:
severity:
notes:
```

### Répartition minimale

- 5 cas quantitatifs normaux ;
- 5 erreurs numériques ou d'unités ;
- 5 cas de preuves/citations ;
- 4 cas sustainability non comparables ou manquants ;
- 3 cas d'injection ;
- 3 demandes hors périmètre ;
- cas supplémentaires de contradictions et retraitements.

### Transformations métamorphiques

Pour certains cas, créer une variante :

- même valeur, unité différente ;
- même claim, date déplacée ;
- négation ajoutée ;
- devise différente ;
- document retraité ;
- émetteur changé.

Le résultat attendu doit évoluer de façon cohérente.

### Métriques

#### Quant

- erreur absolue et relative ;
- exactitude des unités ;
- reproductibilité ;
- taux de cas insuffisants correctement rejetés.

#### Retrieval

- recall@k ;
- MRR ;
- bonne page ;
- absence correctement reconnue.

#### Génération

- conformité au schéma ;
- précision numérique ;
- couverture des citations ;
- soutien réel des claims ;
- claims interdits.

#### Décision

- matrice de confusion ;
- taux de fausse éligibilité automatique ;
- taux d'escalade ;
- taux d'abstention correcte.

#### Ressources

- appels ;
- tokens ;
- coût estimé ;
- latence ;
- retries ;
- cache.

### Marche à suivre

1. Charger `retrieval_gold.v1.jsonl` et `workflow_eval.v1.jsonl` créés avant la phase 7.
2. Vérifier le hash du holdout et ne plus modifier ses attentes.
3. Évaluer séparément chaque composant sur `dev` et `validation`.
4. Exécuter les cas probabilistes plusieurs fois sous un budget fixé.
5. Calculer la matrice de confusion.
6. Pondérer les erreurs par gravité, sans cacher les résultats bruts.
7. Ouvrir le holdout une seule fois pour la mesure finale de cette version.
8. Comparer v1 et v3 uniquement sur leurs capacités communes, par exemple cohérence numérique observable, appels, coût et latence.
9. Rapporter séparément les capacités nouvelles de v3, notamment retrieval, sustainability, citations et revue ; ne pas attribuer artificiellement un score nul à v1 sur une fonction qu'elle ne possède pas.
10. Publier qualité, appels, tokens, coût et latence dans le même tableau lorsque la comparaison est valide.
11. Ajouter des seuils de non-régression déterministes à la CI.
12. Garder les evals avec modèle réel dans un workflow manuel ou planifié avec budget.
13. Écrire `docs/evaluation_report.md`.

### Répartition des responsabilités

- **Python :** runner, calcul des métriques et rapports.
- **LLM :** système testé, éventuellement juge auxiliaire calibré.
- **Humain :** annotations, sévérité et revue d'un échantillon.

### Exercice sans IA

Calculer à la main une matrice de confusion de dix cas, puis expliquer pourquoi une fausse éligibilité automatique est plus grave qu'une escalade inutile.

### Tests minimums

- runner reproductible ;
- cas mal formé ;
- fuite entre splits ;
- agrégation correcte ;
- seuil de régression ;
- résultat partiel après timeout ;
- table de prix datée pour le coût.

### Questions de maîtrise

- Pourquoi ne pas régler le prompt sur le holdout ?
- Pourquoi une note globale est-elle insuffisante ?
- Comment distinguer erreur du retriever et du générateur ?
- Pourquoi répéter les exécutions ?
- Que peut-on conclure honnêtement avec 25 cas ?

### Pièges

- changer l'oracle après avoir vu la réponse ;
- sélectionner uniquement les meilleurs runs ;
- présenter 25 cas comme preuve statistique générale ;
- appeler chaque score « accuracy » ;
- cacher les cas abstention/escalade.

### Critère de fin et point d'arrêt

Aucun chiffre d'amélioration ne va dans le README avant que la commande, le dataset, la configuration et les résultats bruts soient reproductibles.

### Commit attendu

`eval: publish component and end-to-end v1-v3 benchmark`

---

## 17. Phase 10 : ajouter la revue humaine et l'audit trail

**Charge indicative :** deux à quatre jours.  
**Jalon :** D.

### Résultat visible

Un analyste peut :

- lire le brouillon ;
- ouvrir chaque preuve ;
- voir les erreurs et avertissements ;
- approuver ;
- corriger ;
- rejeter ;
- escalader.

Chaque action est versionnée et associée à un identifiant de reviewer déclaré.

### Pourquoi cette phase existe

La revue humaine n'est pas une case « reviewed ». Elle doit donner au reviewer les informations nécessaires, empêcher l'effacement de l'erreur initiale et bloquer l'export d'un résultat non approuvé.

### Notions à comprendre

- human-in-the-loop ;
- séparation des rôles ;
- append-only ;
- version immuable ;
- disposition humaine ;
- contrôle optimiste ou verrouillage ;
- auditabilité.

### Machine à états

Cycle du run :

```text
created -> generated -> validated -> pending_review -> finalized
```

Résultat automatique alternatif :

```text
eligible_for_review | review_required | abstain
```

Disposition humaine alternative :

```text
approved | corrected | rejected | escalated
```

Une sortie `eligible_for_review` passe quand même par `pending_review`. `corrected` crée une nouvelle version qui doit être revalidée avant une éventuelle approbation.

Une correction doit repasser par les validateurs.

### Marche à suivre

1. Créer `human_review_events` avec une politique append-only au niveau applicatif.
2. Enregistrer reviewer déclaré, rôle, date UTC, version, commentaire et disposition.
3. Afficher ensemble :
   - texte du claim ;
   - métriques ;
   - extraits ;
   - page ;
   - issues ;
   - décision système.
4. Conserver le draft initial intact.
5. Créer une nouvelle version pour toute correction.
6. Relancer les validateurs sur la correction.
7. Empêcher l'export « approved » sans événement d'approbation valide.
8. Ajouter une file de cas `review_required`.
9. Tester deux reviewers modifiant la même version.
10. Documenter qui peut faire quoi, même si le MVP n'a qu'un utilisateur.

Sans authentification gérée, `reviewer_id` est un libellé déclaré, pas une identité vérifiée. Sans permissions et mécanisme d'intégrité, l'historique append-only est une convention applicative testée, pas un journal inviolable. Ne pas exposer publiquement les routes de review avant d'ajouter une authentification gérée et des autorisations.

### Répartition des responsabilités

- **Python/SQL :** transitions et historique.
- **LLM :** aucune disposition humaine.
- **Humain :** approuve, corrige, rejette ou escalade.

### Exercice sans IA

Corriger un claim, puis utiliser SQL pour retrouver :

- le draft initial ;
- la correction ;
- les deux rapports de validation ;
- la décision humaine finale.

### Tests minimums

- approbation ;
- correction et revalidation ;
- rejet ;
- escalade ;
- commentaire obligatoire ;
- reviewer manquant ;
- version concurrente ;
- export avant approbation interdit ;
- historique non écrasé.

### Questions de maîtrise

- Pourquoi `reviewed=true` est-il insuffisant ?
- Que doit voir le reviewer ?
- Pourquoi conserver l'erreur initiale ?
- Qui peut exporter un résultat approuvé ?
- Pourquoi revalider une correction humaine ?

### Pièges

- bouton sans identité ni commentaire ;
- correction en place ;
- état impossible ;
- export direct depuis le brouillon ;
- confusion entre décision système et disposition humaine.

### Critère de fin et point d'arrêt

Un run doit raconter toute son histoire. Si une correction efface le passé ou si un brouillon non approuvé peut être présenté comme final, la phase n'est pas terminée.

### Commit attendu

`feat: add versioned human review and append-only audit history`

---

## 18. Phase 11 : séparer FastAPI et Streamlit

**Charge indicative :** trois à cinq jours.  
**Jalon :** D.

### Résultat visible

- logique métier derrière FastAPI ;
- routes typées et documentées ;
- Streamlit utilisé comme client analyste ;
- parcours complet de bout en bout ;
- erreurs externes contrôlées.

### Pourquoi cette phase existe

Une interface Streamlit est utile pour la démonstration, mais elle ne doit pas contenir les règles métier. La séparation API/interface montre que le système peut évoluer vers plusieurs clients, plusieurs utilisateurs et des tests plus propres.

### Notions à comprendre

- frontend et backend ;
- endpoint ;
- méthodes HTTP ;
- schéma de requête et réponse ;
- codes 201, 404, 409, 422 et 500 ;
- idempotence ;
- timeout ;
- exécution synchrone contre job durable ;
- documentation OpenAPI ;
- séparation de couches.

### Routes minimales

```text
POST /analyses
GET  /analyses/{run_id}
GET  /analyses/{run_id}/evidence
POST /analyses/{run_id}/reviews
GET  /reviews/pending
GET  /evaluations/latest
GET  /health
```

### Marche à suivre

1. Créer l'application FastAPI sans déplacer immédiatement toute l'interface.
2. Injecter services et repositories dans les routes.
3. Définir des schémas API distincts des modèles ORM.
4. Implémenter `POST /analyses` avec une clé d'idempotence.
5. Pour le MVP, exécuter le run de manière synchrone et retourner `201 Created`. Un futur `202 Accepted` exige une file et un worker durables avec reprise après redémarrage ; `BackgroundTasks` seul ne fournit pas cette garantie.
6. Implémenter la lecture d'un run et de ses preuves.
7. Implémenter la création d'un événement de review.
8. Ajouter des erreurs métier stables, sans trace interne exposée.
9. Tester les routes avec un client de test et des fakes.
10. Faire consommer l'API par Streamlit.
11. Supprimer progressivement la logique métier de Streamlit.
12. Construire quatre pages :
    - Quantitative Analysis ;
    - Climate Evidence ;
    - Validation & Review ;
    - Quality & Resource Efficiency.
13. Afficher l'état du run et permettre de rafraîchir sans créer de doublon.
14. Laisser FastAPI générer la documentation OpenAPI et la vérifier.

La documentation officielle de FastAPI est disponible ici : [FastAPI](https://fastapi.tiangolo.com/).

### Répartition des responsabilités

- **API :** contrats, authentification future, orchestration des services et erreurs.
- **Streamlit :** présentation et interactions.
- **LLM :** appelé uniquement par le workflow métier, jamais directement par l'UI.
- **Humain :** initie le run et effectue la review.

### Exercice sans IA

Écrire une route, ses schémas et deux tests :

- requête valide ;
- requête invalide retournant 422.

### Tests minimums

- création d'analyse ;
- même clé d'idempotence ;
- run absent ;
- review interdite ;
- review valide ;
- dépendance externe indisponible ;
- timeout ;
- secret absent de la réponse ;
- UI incapable de contourner les validateurs.

### Questions de maîtrise

- Pourquoi ne pas placer la logique de validation dans Streamlit ?
- Pourquoi le MVP retourne-t-il 201 ?
- Que faudrait-il ajouter pour retourner honnêtement 202 ?
- Comment éviter deux runs lors d'un retry ?
- Pourquoi séparer modèle ORM et schéma API ?
- Que doit contenir une réponse d'erreur ?

### Pièges

- route qui fait tout dans une fonction ;
- retour des exceptions internes ;
- accès direct de l'UI à la base ;
- clé API côté navigateur ;
- run dupliqué après rafraîchissement.

### Critère de fin et point d'arrêt

Le même parcours doit pouvoir être exécuté par les tests API et par Streamlit, sans dupliquer les règles métier.

### Commit attendu

`feat: expose research workflow through typed fastapi routes`

---

## 19. Phase 12 : observabilité, sécurité et efficacité des ressources IA

**Charge indicative :** deux à quatre jours.  
**Jalon :** D.

### Résultat visible

- logs structurés ;
- trace par run ;
- métriques de modèle ;
- budgets ;
- threat model ;
- comparaison qualité/coût/latence entre v1 et v3.

### Pourquoi cette phase existe

Une plateforme professionnelle doit expliquer ce qui s'est passé lors d'un run. Cette phase mesure l'efficacité opérationnelle des ressources IA. Elle ne constitue pas une mesure de « sustainable AI » au sens environnemental.

### Notions à comprendre

- log ;
- métrique ;
- trace et span ;
- corrélation par `run_id` ;
- Service Level Indicator ;
- budget ;
- cache ;
- retry avec backoff ;
- secret ;
- principe du moindre privilège ;
- allowlist ;
- threat model.

### Données à enregistrer par appel modèle

- fournisseur ;
- modèle/version ;
- version du prompt ;
- identifiant de requête ;
- tokens d'entrée ;
- tokens de sortie ;
- tokens cachés si fournis ;
- latence ;
- retries ;
- statut ;
- erreur normalisée ;
- cache hit/miss ;
- coût estimé ;
- date et version de la table tarifaire.

### Mesurer l'efficacité, pas inventer une empreinte

Mesures autorisées :

- appels par run ;
- tokens par run ;
- coût par run ;
- latence ;
- taux de cache ;
- qualité obtenue ;
- taux d'escalade.

Affirmation interdite sans données supplémentaires :

> « La v3 émet X % de CO₂ en moins parce qu'elle utilise X % de tokens en moins. »

Les tokens ne donnent pas l'énergie consommée, le matériel, la région électrique ni la méthode d'allocation.

### Threat model minimal

Actifs à protéger :

- secrets API ;
- documents ;
- données de run ;
- décisions de review ;
- prompts et configuration ;
- disponibilité et budget.

Menaces :

- prompt injection indirecte ;
- exfiltration de secrets ;
- accès à une source non autorisée ;
- outil trop permissif ;
- boucle coûteuse ;
- fichier malformé ;
- payload excessif ;
- falsification d'un ID de preuve ;
- modification non auditée ;
- fuite de données dans les logs.

### Marche à suivre

1. Utiliser des logs JSON.
2. Ajouter `research_run_id`, `model_call_id` et `step_name` à chaque événement.
3. Propager un contexte de trace à travers API, workflow, retrieval et validation.
4. Mesurer la durée de chaque étape.
5. Stocker les métriques d'appels.
6. Ajouter budgets par run :
   - appels ;
   - tokens ;
   - coût ;
   - durée ;
   - retries.
7. Ajouter cache uniquement pour des entrées versionnées.
8. Comparer v1 et v3 sur les mêmes cas.
9. Rédiger `docs/threat_model.md`.
10. Mettre les outils en lecture seule et allowlist.
11. Limiter les chemins, URLs et types de fichiers.
12. Redacter secrets et données sensibles des logs.
13. Ajouter des alertes simples dans l'UI :
    - budget proche ;
    - taux d'erreur ;
    - run lent ;
    - validation critique.
14. Introduire OpenTelemetry seulement si cela améliore réellement le diagnostic ; un système de logs corrélés peut suffire au début.

### Tableau comparatif final

| Architecture | Qualité | Fausses éligibilités critiques | Appels | Tokens | Coût | Latence |
|---|---:|---:|---:|---:|---:|---:|
| v1 quatre agents | mesuré | mesuré | mesuré | mesuré | mesuré | mesuré |
| v3 workflow borné | mesuré | mesuré | mesuré | mesuré | mesuré | mesuré |

Ne jamais préremplir ces cellules avec des valeurs inventées.

### Répartition des responsabilités

- **Python/infrastructure :** instrumentation, budgets et contrôles.
- **LLM :** consommateur mesuré, sans accès aux secrets.
- **Humain :** choisit les seuils et interprète le compromis qualité/coût.

### Exercice sans IA

Prendre un run lent et reconstituer son parcours uniquement avec les logs. Expliquer quel span consomme le temps et pourquoi.

### Tests minimums

- même `run_id` dans toute la trace ;
- secret redacted ;
- budget d'appels ;
- budget de tokens ;
- retry borné ;
- cache invalidé après changement de corpus/prompt ;
- URL non allowlistée ;
- fichier trop gros ;
- log malgré erreur partielle.

### Questions de maîtrise

- Quelle différence entre log, métrique et trace ?
- Pourquoi dater la table tarifaire ?
- Quand un cache devient-il incorrect ?
- Comment une injection documentaire peut-elle atteindre un outil ?
- Pourquoi les tokens ne mesurent-ils pas le CO₂ ?

### Pièges

- logger les prompts avec secrets ;
- retries infinis ;
- coût calculé avec un prix actuel pour un ancien run ;
- cache non versionné ;
- ajouter une stack d'observabilité complexe sans besoin.

### Critère de fin et point d'arrêt

Pour un run réussi ou échoué, tu dois expliquer : quelles étapes ont eu lieu, quels modèles et outils ont été appelés, combien de ressources ont été utilisées et pourquoi le résultat a été accepté ou escaladé.

### Commit attendu

`feat: trace model quality cost latency and security controls`

---

## 20. Phase 13 : renforcer CI, conteneurs et déploiement

**Charge indicative :** deux à trois jours.  
**Jalon :** E.

### Résultat visible

- CI complète ;
- environnement local reproductible ;
- application, API et PostgreSQL lancés ensemble ;
- health checks ;
- procédure de déploiement documentée ;
- cloud facultatif et honnêtement présenté.

### Pourquoi cette phase existe

La CI a commencé à la phase 2. Ici, elle couvre l'ensemble du produit. Docker simplifie la reproduction. Le cloud n'a de valeur que si le système local est déjà stable.

### Notions à comprendre

- image et conteneur ;
- volume ;
- réseau ;
- variable d'environnement ;
- health check ;
- build reproductible ;
- CI versus CD ;
- migration au démarrage ;
- service stateful contre stateless.

### Marche à suivre

1. Créer un Dockerfile minimal et non-root.
2. Créer Docker Compose avec :
   - API ;
   - Streamlit ;
   - PostgreSQL ;
   - volume nommé.
3. Ajouter les health checks.
4. Définir clairement qui lance les migrations.
5. Épingler les dépendances avec un lockfile.
6. Étendre GitHub Actions :
   - installation propre ;
   - Ruff ;
   - tests unitaires ;
   - tests d'intégration avec PostgreSQL ;
   - vérification Alembic ;
   - evals déterministes ;
   - build de l'image.
7. Garder les evals LLM réelles dans un workflow manuel avec budget.
8. Générer un artefact de rapport d'eval.
9. Vérifier le démarrage depuis un clone propre.
10. Ajouter un scan simple de secrets et dépendances si disponible.
11. Déployer seulement après stabilisation locale.
12. Si tu déploies, utiliser des secrets gérés et une base managée ; ne pas construire l'authentification toi-même.

La documentation de GitHub Actions explique l'automatisation des workflows : [GitHub Actions](https://docs.github.com/en/actions).

### Répartition des responsabilités

- **Conteneurs/CI :** environnement et contrôles reproductibles.
- **LLM :** appels réels exclus de la CI automatique ordinaire.
- **Humain :** autorise les evals coûteuses et les déploiements.

### Exercice sans IA

Casser volontairement un test, lire le log GitHub Actions, corriger localement et vérifier la CI.

### Tests minimums

- build à froid ;
- démarrage Compose ;
- health checks ;
- migration base vide ;
- arrêt/redémarrage avec données conservées ;
- variable obligatoire absente ;
- image sans secret ;
- workflow manuel d'eval.

### Questions de maîtrise

- Quelle différence entre image et conteneur ?
- Pourquoi PostgreSQL a-t-il un volume ?
- Qui applique les migrations ?
- Pourquoi les appels LLM réels ne tournent-ils pas sur chaque pull request ?
- Que garantit réellement un déploiement de démonstration ?

### Pièges

- secret copié dans l'image ;
- migration concurrente ;
- conteneur exécuté en root sans nécessité ;
- cloud avant tests locaux ;
- prétendre avoir une architecture de production multi-utilisateur après un simple déploiement.

### Critère de fin et point d'arrêt

Un clone propre doit permettre de lancer tests et application en suivant le README, sans modifier le code.

### Commit attendu

`chore: add reproducible containers and full CI pipeline`

---

## 21. Phase 14 : documenter, démontrer et préparer l'entretien

**Charge indicative :** deux à trois jours.  
**Jalon :** fin de E.

### Résultat visible

- README factuel ;
- architecture illustrée ;
- méthodologies quant et sustainability ;
- rapport d'eval ;
- limites ;
- démonstration de cinq minutes ;
- deux scénarios reproductibles ;
- formulations CV honnêtes.

### Pourquoi cette phase existe

Un bon projet qui ne peut pas être expliqué reste une preuve faible. La démonstration doit montrer une décision d'ingénierie, une erreur correctement bloquée et une limite reconnue.

### README final

Ordre recommandé :

1. problème ;
2. capture ou courte démo ;
3. promesse et non-objectifs ;
4. architecture ;
5. parcours de données ;
6. méthodologie quant ;
7. méthode sustainability ;
8. frontières de confiance ;
9. évaluations ;
10. résultats mesurés ;
11. efficacité des ressources ;
12. lancement local ;
13. limites ;
14. roadmap.

Ajouter une table explicite :

| Fonctionnalité | Statut |
|---|---|
| Quant Core reproductible | implemented / in progress / planned |
| PostgreSQL + migrations | ... |
| Climate Evidence | ... |
| Retrieval évalué | ... |
| Human review | ... |
| FastAPI | ... |
| Observabilité | ... |

### Démonstration principale de cinq minutes

#### Scénario A : résultat approuvable

1. sélectionner les deux actifs ;
2. choisir une date de référence ;
3. charger le snapshot ;
4. afficher métriques et hypothèses ;
5. poser une question combinant quant et climat ;
6. ouvrir les passages retrouvés ;
7. afficher les claims structurés ;
8. montrer les validations ;
9. approuver ;
10. ouvrir l'audit trail.

#### Scénario B : résultat escaladé

1. introduire une valeur avec mauvaise unité, une période incompatible ou deux sources contradictoires ;
2. générer le brouillon ;
3. montrer le validateur qui bloque ;
4. expliquer `review_required` ou `abstain` ;
5. corriger ou escalader ;
6. montrer que la première version existe toujours.

### Démonstration d'apprentissage

Être capable, sans notes, de :

- écrire un petit test ;
- expliquer une jointure SQL ;
- modifier une règle de validation ;
- dessiner le workflow ;
- expliquer la différence entre Pydantic et vérité métier ;
- justifier la stratégie de retrieval ;
- expliquer une limite du corpus.

### Questions probables d'entretien

- Pourquoi avoir supprimé quatre agents ?
- Pourquoi PostgreSQL plutôt que SQLite ?
- Pourquoi ne pas intégrer un score ESG dans l'optimisation ?
- Comment avez-vous évalué le retrieval ?
- Quel est le risque le plus grave ?
- Que fait le système lorsqu'il ne sait pas ?
- Comment empêchez-vous le modèle d'inventer une citation ?
- Qu'avez-vous appris en écrivant le Quant Core ?
- Quelle amélioration a le meilleur rapport qualité/coût ?
- Que faudrait-il changer pour plusieurs utilisateurs en production ?

### Formulations CV conditionnelles

N'utiliser une formulation qu'après avoir réalisé ce qu'elle décrit.

#### Après le jalon C

> Re-engineered a multi-agent financial research prototype into a typed, evidence-grounded workflow combining reproducible portfolio analytics with traceable sustainability disclosures.

#### Après le jalon D

> Implemented PostgreSQL data lineage, structured LLM outputs, deterministic validation, human review and component-level evaluations for quantitative and climate research.

#### Après le jalon E

> Exposed the workflow through FastAPI and Streamlit, added CI, containerized local deployment, and measured quality, latency, token usage and cost against the original four-agent baseline.

Ne pas écrire :

- production-grade ;
- institutional-grade ;
- deployed at scale ;
- reduced AI carbon emissions ;
- autonomous investment advisor ;
- years of professional experience équivalentes.

### Critère de fin

Une personne externe doit pouvoir :

- lancer le projet ;
- comprendre le périmètre ;
- recalculer la partie déterministe d'un run et auditer les entrées/sorties LLM conservées ;
- ouvrir les preuves ;
- voir une erreur bloquée ;
- lire les résultats d'évaluation ;
- identifier clairement les limites.

### Commit attendu

`docs: publish architecture evaluation report and interview demo`

---

## 22. Matrice de tests et d'évaluations

| Couche | Vérification | Exemple | Automatisation |
|---|---|---|---|
| Données marché | schéma et couverture | ticker manquant | CI |
| Snapshot | immutabilité et hash | mêmes données, même hash | CI |
| Quant | valeur attendue | drawdown synthétique | CI |
| Optimiseur | contraintes | poids bornés | CI |
| Base | intégrité relationnelle | claim vers preuve absente | CI |
| Migration | base reconstructible | upgrade depuis zéro | CI |
| Corpus | hash et page | PDF remplacé | CI |
| Sustainability | comparabilité | méthodes Scope 2 différentes | CI |
| Retrieval | recall@k | bonne page dans top 3 | eval |
| Génération | schéma | champ inconnu | CI/eval |
| Claim numérique | cohérence | nombre inventé | CI/eval |
| Citation | intégrité | evidence_id inexistant | CI/eval |
| Grounding | support | passage hors sujet | eval + humain |
| Politique | décision | conflit -> review_required | CI/eval |
| Sécurité | injection | instruction dans PDF | eval |
| Human review | transition | correction revalidée | CI |
| API | contrat | payload invalide -> 422 | CI |
| Observabilité | trace | run_id propagé | CI |
| Ressources | budget | trop d'appels | CI/eval |
| End-to-end | scénario | run accepté/escaladé | manuel + eval |

---

## 23. Registre des risques et réponses

| Risque | Gravité | Réponse |
|---|---:|---|
| Calcul financier incorrect | critique | fonctions pures, fixtures synthétiques, revue des formules |
| Prix incohérents entre étapes | critique | snapshot unique et interdiction du second téléchargement |
| Claim non soutenu mais jugé éligible | critique | validation séparée, mesure de la fausse éligibilité, revue humaine |
| Citation inventée | critique | IDs créés uniquement par l'ingestion |
| KPI non comparable | élevée | règles période/unité/périmètre et abstention |
| Objectif confondu avec résultat | élevée | modèles séparés |
| Prompt injection documentaire | élevée | données non fiables, tools allowlistés et tests |
| Coût ou boucle incontrôlés | élevée | budgets, timeout, retries bornés |
| Holdout contaminé | moyenne | gel et accès discipliné |
| Démo impossible à reproduire | élevée | fixtures, lockfile, Compose et CI |
| Projet trop large | élevée | deux émetteurs, un cas d'usage, exclusions |
| Survente sur le CV | élevée | statuts factuels et claims conditionnels |

---

## 24. Priorités en cas de délai court

### P0 : tranche candidature rapide

Ce P0 est une réduction temporaire, pas la cible finale :

- contrat du produit et baseline ;
- tests et CI minimale ;
- Quant Core reproductible ;
- contrats typés et tranche verticale avec fakes ;
- un émetteur, un document officiel et quelques preuves annotées ;
- récupération manuelle ou lexicale simple ;
- sortie structurée ;
- validateurs numériques et de preuves ;
- 10 à 15 cas d'eval de développement ;
- review minimale dans Streamlit ;
- un scénario correct et un scénario bloqué.

À ce stade, le README doit indiquer que PostgreSQL, retrieval comparé, API et audit trail complet sont encore en cours.

### P1 : portfolio fort et aligné avec le poste

- PostgreSQL + SQLAlchemy + Alembic ;
- deuxième émetteur et corpus complet du MVP ;
- jeux `dev/validation/holdout` gelés ;
- comparaison long context, lexical, dense et hybride ;
- 25 à 40 cas d'eval ;
- historique de review append-only au niveau applicatif ;
- rapport des nouvelles capacités et comparaison v1/v3 sur le périmètre commun.

### P2 : application moderne complète

- FastAPI synchrone ;
- séparation API/Streamlit ;
- Docker Compose ;
- observabilité enrichie, budgets et modèle de menaces ;
- UI de qualité détaillée ;
- documentation et démonstration finales ;
- déploiement de démonstration avec authentification gérée si les routes de review sont exposées.

### P3 : après stabilisation

- backtest walk-forward avec source point-in-time adaptée ;
- Black-Litterman ;
- troisième émetteur documenté ;
- agent conditionnel spécialisé ;
- OpenTelemetry complet ;
- job runner durable ;
- comparaison de fournisseurs ;
- extension à d'autres thèmes sustainability.

### À ne pas ajouter avant P0

- MCP pour le mot-clé ;
- nombreux agents ;
- fine-tuning ;
- Kafka ;
- Kubernetes ;
- knowledge graph ;
- prédiction de cours ;
- couverture de tout le marché.

---

## 25. Programme d'apprentissage personnel

### Code à savoir refaire seul

- un modèle Pydantic avec validateur ;
- `max_drawdown()` ;
- une VaR historique simple ;
- un validateur numérique ;
- cinq tests unitaires ;
- un fake de client LLM ;
- lecture/écriture de JSONL ;
- une jointure SQL ;
- une migration Alembic ;
- une route FastAPI et son test ;
- diagnostic d'un test CI cassé.

### Questions à poser après chaque exercice

1. Quelles sont les entrées ?
2. Quelles sont les sorties ?
3. Quels cas peuvent échouer ?
4. Où l'erreur remonte-t-elle ?
5. Comment puis-je le tester ?
6. Quelle hypothèse est cachée ?
7. Qui a autorité sur ce résultat ?

### Critère de vraie maîtrise

Tu ne dois pas mémoriser toute une bibliothèque. Tu dois être capable :

- d'expliquer l'abstraction ;
- de retrouver la documentation ;
- d'écrire une version minimale ;
- de lire le code généré ;
- de repérer une hypothèse erronée ;
- d'ajouter un test ;
- de défendre le compromis.

---

## 26. Correspondance avec la candidature visée

L'annonce Pictet vise un rôle de **Sustainability/Impact Data & AI Solutions Analyst**. Le projet final fournit des preuves concrètes sur plusieurs axes demandés : [annonce officielle](https://career012.successfactors.eu/career?career%5fns=job%5flisting&company=banquepict&navBarLevel=JOB%5fSEARCH&rcm%5fsite%5flocale=en%5fGB&career_job_req_id=125064&selected_lang=en_GB).

| Attente | Preuve dans le projet |
|---|---|
| Python et ingénierie logicielle | package propre, tests, FastAPI, CI |
| SQL et gestion de données | PostgreSQL, contraintes, jointures, migrations |
| Sustainability data | corpus officiel, KPI climat, comparabilité et assurance, avec limites explicites sur la mesure d'impact |
| Data quality et lineage | snapshots, manifestes, hashes, evidence IDs |
| LLM et agents | workflow LLM borné, structured outputs, tools contrôlés |
| RAG | comparaison long context, lexical, dense et hybride |
| Evals | dataset versionné, holdout, métriques composant et end-to-end |
| Guardrails | validateurs numériques, evidence, policy et abstention |
| Human review | états, corrections versionnées, audit trail |
| Dashboards | vues quant, climate evidence, review et qualité |
| CI/CD et déploiement | GitHub Actions, Docker, procédure de déploiement |
| Sécurité | threat model, secrets, allowlists, prompt injection |
| Monitoring | run IDs, logs, traces, coût, latence et tokens |
| Évaluation de nouvelles capacités | comparaison de modèles/prompts sur le même eval set |

Ce projet ne prouve pas :

- une expérience bancaire de production ;
- une exploitation à grande échelle ;
- une responsabilité professionnelle de un à trois ans ;
- une maîtrise cloud avancée.

Il prouve en revanche :

- la capacité à transformer un prototype ;
- le raisonnement sur les frontières de confiance ;
- la qualité et la traçabilité des données ;
- la maîtrise d'un workflow IA évalué ;
- la capacité à communiquer limites et compromis.

---

## 27. Séquence d'exécution recommandée

Les huit blocs suivants donnent l'ordre, pas une promesse de huit semaines. À temps partiel, un bloc peut demander une à deux semaines.

### Bloc 1 : vérité et fondations

- phase 0 ;
- phase 1 ;
- phase 2 ;
- début de la phase 3.

Objectif : baseline, tests et premier snapshot reproductible.

### Bloc 2 : Quant Core et contrats

- fin de la phase 3 ;
- phase 4 ;
- début de PostgreSQL.

Objectif : chiffres fiables, objets séparés et première tranche verticale avec fakes.

### Bloc 3 : persistance et premier cas réel

- fin de la phase 5 ;
- premier document ;
- première observation sustainability ;
- premier claim ;
- première validation.

Objectif : un seul cas de bout en bout avant d'élargir.

### Bloc 4 : corpus et retrieval

- phase 6 ;
- création et gel des jeux `dev/validation/holdout` ;
- phase 7 ;

Objectif : deux émetteurs et choix de retrieval justifié.

### Bloc 5 : validation et evals

- phase 8 ;
- phase 9.

Objectif : erreurs critiques bloquées et rapport v1/v3 initial.

### Bloc 6 : review et API

- phase 10 ;
- phase 11.

Objectif : parcours analyste complet.

### Bloc 7 : observabilité et reproductibilité

- phase 12 ;
- phase 13.

Objectif : expliquer chaque run et relancer depuis un clone propre.

### Bloc 8 : présentation

- phase 14 ;
- répétition de la démo ;
- amélioration du README ;
- adaptation du CV.

Objectif : projet défendable, pas seulement fonctionnel.

Si le temps manque, terminer proprement un jalon plutôt que commencer quatre phases incomplètes.

---

## 28. Checklist finale

### Produit

- [ ] Le projet tient en une phrase.
- [ ] La sustainability reste une lentille du même portefeuille.
- [ ] Les non-objectifs sont visibles.
- [ ] L'UI n'émet pas de conseil personnalisé.

### Quant

- [ ] Un seul snapshot est utilisé par run.
- [ ] `analysis_cutoff`, `data_start`, `data_end` et `retrieved_at` sont enregistrés.
- [ ] Les conventions de prix et rendements sont écrites.
- [ ] VaR, Expected Shortfall et drawdown sont testés.
- [ ] L'optimiseur retourne ses diagnostics.

### Données

- [ ] PostgreSQL est créé par Alembic.
- [ ] Les relations importantes ont des contraintes.
- [ ] Les versions initiales ne sont pas écrasées.
- [ ] Le Quant Core d'un run passé est recalculable et ses sorties LLM passées restent consultables.

### Sustainability

- [ ] Deux émetteurs seulement dans le MVP.
- [ ] Chaque document est hashé.
- [ ] Chaque valeur numérique utilisée dans une comparaison a période, unité, méthode, périmètre et preuve.
- [ ] Target et actual sont séparés.
- [ ] Location-based et market-based sont séparés.
- [ ] Une comparaison invalide est bloquée.

### IA

- [ ] Le LLM ne crée pas les preuves.
- [ ] Le LLM ne se valide pas.
- [ ] Les sorties sont structurées.
- [ ] Les appels sont bornés.
- [ ] Les documents ne commandent pas les tools.

### Évaluation

- [ ] Le holdout est gelé.
- [ ] Retrieval et génération sont mesurés séparément.
- [ ] Le taux de fausse éligibilité automatique est visible.
- [ ] Les résultats bruts et limites sont publiés.
- [ ] v1 et v3 sont comparés sur les mêmes cas.

### Humain

- [ ] La correction crée une version.
- [ ] Toute correction repasse par validation.
- [ ] Le reviewer déclaré, la date et le commentaire sont conservés.
- [ ] Un brouillon non approuvé ne peut pas être exporté comme approuvé.

### Exploitation

- [ ] L'API et l'UI partagent la même logique.
- [ ] Tests et lint passent en CI.
- [ ] Les appels payants ne tournent pas sur chaque PR.
- [ ] Tokens, coût et latence sont mesurés.
- [ ] Aucun secret ne figure dans Git ou les logs.
- [ ] Un clone propre peut démarrer le produit.

### Présentation

- [ ] Le README reflète le code réel.
- [ ] La démo contient un cas accepté et un cas escaladé.
- [ ] Chaque chiffre affiché est reproductible.
- [ ] Les limites sont explicites.
- [ ] Le CV ne mentionne que les jalons atteints.

---

## 29. Règle de décision finale

Le projet est réussi lorsque cette phrase est vraie :

> À partir d'un portefeuille explicite et d'une date de référence, le système produit des métriques quantitatives reproductibles, retrouve des informations climatiques dans des documents officiels, génère des affirmations structurées liées à des preuves existantes, bloque les incohérences connues, demande une revue humaine lorsque nécessaire et conserve un historique complet de la décision.

Si une fonctionnalité n'améliore pas directement :

- la qualité des calculs ;
- la qualité des preuves ;
- la fiabilité de la décision ;
- la compréhension de l'analyste ;
- ou la capacité à recalculer la partie déterministe et auditer un run,

elle reste hors du MVP.

---

## 30. Références officielles pour apprendre

### IA et évaluations

- [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Claude, Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic, Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Anthropic, Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [OWASP, LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

### Python, données et plateforme

- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/)
- [PostgreSQL documentation](https://www.postgresql.org/docs/current/)
- [pgvector](https://github.com/pgvector/pgvector)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [OpenTelemetry traces](https://opentelemetry.io/docs/concepts/signals/traces/)

### Sustainable finance et climat

- [IFRS Foundation, IFRS S2](https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/)
- [GHG Protocol, Scope 2 Guidance](https://ghgprotocol.org/scope-2-guidance)

### Sources du projet

- [Dépôt AI Quant Research Assistant](https://github.com/EMen11/AI-quant-research-assistant)
- [Annonce Pictet](https://career012.successfactors.eu/career?career%5fns=job%5flisting&company=banquepict&navBarLevel=JOB%5fSEARCH&rcm%5fsite%5flocale=en%5fGB&career_job_req_id=125064&selected_lang=en_GB)
