# Speedrun status

- Dernière mise à jour : 2026-09-23
- Branche courante : `speedrun/application-ready`
- Commit du Bloc 0 : `30c9db62b17685c5a0ed350c9780b08196b21f15`

Statuts autorisés : `TODO`, `DOING`, `DONE`. Un bloc n'est `DONE` que lorsque ses contrôles sont passés et documentés. Les commandes des blocs futurs sont les gates prévues ; elles ne sont pas encore disponibles dans le dépôt actuel.

| Bloc | Objet | Statut | Branche | Commit de référence | Commandes de contrôle |
|---:|---|---|---|---|---|
| 0 | Audit reproductible du dépôt | DONE | `speedrun/application-ready` | `30c9db62b17685c5a0ed350c9780b08196b21f15` | `git diff --check`<br>`test -s docs/audit_baseline.md`<br>`test -s SPEEDRUN_STATUS.md`<br>`git status --short --branch` |
| 1 | Socle reproductible, CI et premier déploiement | DONE | `speedrun/application-ready` | modifications locales non commitées sur `30c9db6` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run ruff check .`<br>`APP_MODE=demo uv run pytest -q`<br>`APP_MODE=demo uv run streamlit run app.py`<br>healthcheck et contrôle navigateur locaux |
| 2 | Noyau quantitatif fiable | DONE | `speedrun/application-ready` | modifications locales non commitées sur `091d73d` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run --frozen ruff check .`<br>`APP_MODE=demo uv run --frozen pytest -q`<br>`git diff --check`<br>healthcheck et contrôle navigateur locaux |
| 3 | Contrats de confiance et tranche verticale | DONE | `speedrun/application-ready` | modifications locales non commitées sur `c4fbbf4` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run --frozen ruff check .`<br>`APP_MODE=demo uv run --frozen pytest -q`<br>`git diff --check`<br>healthcheck et contrôle navigateur locaux |
| 4 | Corpus sustainable finance traçable | DONE | `speedrun/application-ready` | modifications locales non commitées sur `5972af7` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run --frozen ruff check .`<br>`APP_MODE=demo uv run --frozen pytest -q`<br>`APP_MODE=demo uv run --frozen pytest -q -k "corpus or evidence or cutoff"`<br>`git diff --check`<br>12 observations et 2 cibles vérifiées humainement contre les pages officielles |
| 5 | Retrieval évalué et LLM structuré | TODO | À créer | — | `APP_MODE=demo uv run pytest -q -k "retrieval or llm"`<br>régénérer et comparer l'artefact recall@1/recall@3/rang |
| 6 | Validateurs et évaluation de bout en bout | TODO | À créer | — | `uv run pytest -q`<br>régénérer le rapport d'évaluation et vérifier qu'aucun cas critique connu n'est `eligible_for_review` |
| 7 | Interface analyste et release publique R1 | TODO | À créer | — | `APP_MODE=demo uv run streamlit run app.py`<br>smoke test deux fois des scénarios admissible et bloqué, puis navigation privée/mobile |
| 8 | PostgreSQL, FastAPI et Docker Compose | TODO | À créer | — | `docker compose build`<br>`docker compose up -d`<br>`docker compose ps`<br>`uv run pytest -q`<br>`docker compose down` |
| 9 | Préparation et vérification du déploiement final | TODO | À créer | — | test de démarrage hors ligne en `APP_MODE=demo`<br>scan de secrets à sortie masquée<br>smoke test URL publique anonyme et mobile |
| 10 | README, preuves et release de candidature | TODO | À créer | — | vérifier chaque commande/lien depuis un clone propre<br>`uv run ruff check .`<br>`uv run pytest -q`<br>revue finale des claims contre artefacts versionnés |

## État du Bloc 0

- Livrables : `docs/audit_baseline.md` et `SPEEDRUN_STATUS.md`.
- Aucun code de production corrigé ou refactorisé.
- `assets/Edited.png` reste non suivi et hors périmètre.
- Les plans préexistants sous `docs/plans/` ont été inclus sans modification métier dans le commit du Bloc 0.
- Commit du Bloc 0 : `30c9db62b17685c5a0ed350c9780b08196b21f15` ; aucun push ou déploiement effectué par le Bloc 1.

## État du Bloc 1

- Python 3.12 explicite, package `ai_quant` importable, configuration typée et validée au démarrage.
- Reproductibilité locale revérifiée avec uv Homebrew 0.12.17 et le Python uv permanent 3.12.14 ; le contournement macOS durable du drapeau `UF_HIDDEN` est documenté dans le README.
- Dépendances centralisées dans `pyproject.toml` et résolution verrouillée dans `uv.lock`.
- Mode demo hors ligne avec `FakeLLM`, `FrozenMarketDataProvider` et point d'entrée `app.py`.
- 15 tests unitaires et d'intégration passent sous Python 3.12.14.
- Ruff passe sur l'ensemble du dépôt et la CI GitHub Actions reproduit installation, lint et tests.
- Le serveur Streamlit local répond `ok` sur `/_stcore/health`; le contrôle navigateur confirme une page non vide, sans overlay ni erreur console.
- Pendant l'implémentation locale, aucun push, commit ou déploiement n'avait été effectué avant la validation indépendante.
- `assets/Edited.png` reste non suivi, non modifié et hors périmètre.

## R0 deployment

- Status: DEPLOYED
- Date: 2026-09-22
- Branch: `speedrun/application-ready`
- Commit: `a1428e5`
- GitHub Actions: PASS
- Public application: https://emen11-ai-quant-research-assistant-app-speedrunapplicati-qq9lei.streamlit.app/
- Public verification: application rendered successfully with the frozen offline fixtures.

## État du Bloc 2

- `PortfolioDefinition` et `MarketSnapshot` sont immuables, typés et reliés à un snapshot canonique hashé par analyse.
- Une fixture synthétique d'adjusted close est versionnée et chargée hors ligne ; `SnapshotRun` interdit un second chargement fournisseur.
- Une matrice complete-case de rendements simples quotidiens, sans remplissage, est réutilisée par tous les calculs.
- Rendement, volatilité, drawdown, VaR, Expected Shortfall, covariance, corrélation et agrégats portefeuille sont déterministes et documentés.
- Markowitz long-only retourne poids et diagnostics complets, sans fallback silencieux en cas d'échec.
- Le taux sans risque demo est configurable, daté, sourcé et explicitement présenté comme une hypothèse synthétique non temps réel.
- 34 tests passent, dont 19 tests quantitatifs unitaires/intégration ajoutés au Bloc 2.
- La page Quant locale affiche snapshot, période, unités, hypothèses, poids et diagnostics sans secret ni appel réseau métier en mode demo.

## État du Bloc 3

- Contrats Pydantic stricts et indépendants du fournisseur pour métriques, preuves, génération, validation, assessment et revue humaine.
- Le fake structuré propose uniquement le brouillon ; Python crée les identifiants, contrôle le run, injecte les valeurs du Quant Core et bloque les nombres libres.
- Workflow en mémoire borné, sans boucle ni persistance, avec transitions explicites jusqu'à `pending_review`, budget d'un appel et timeout testable par horloge injectée.
- Deux fixtures synthétiques versionnées couvrent un scénario `eligible_for_review` et un scénario `review_required` sans sortie fiable ni HumanReview.
- La page Trust boundaries distingue brouillon, validation automatique et décision humaine, sans secret, télémétrie ou appel réseau en mode demo.
- 63 tests passent ; Ruff, lockfile, installation figée, `git diff --check`, healthcheck et contrôle navigateur local passent.
- `assets/Edited.png` reste non suivi, non modifié et hors périmètre.

## État du Bloc 4

- Deux PDF officiels complets (Bachem et Siegfried) ont été téléchargés exclusivement depuis les URL autorisées, vérifiés par SHA-256 et conservés sous `data/`, dossier ignoré par Git.
- Le manifeste versionné conserve URL demandée/finale, date d'accès UTC, date de publication, nom local, hash exact, nombre de pages et statut d'extraction.
- Douze observations climatiques traçables sont versionnées en JSONL, six par émetteur, avec `Decimal`, unités, périodes, pages PDF/imprimées, extraits courts, méthodes Scope 2 et statuts d'assurance.
- Les cibles, constats de couverture, évaluations d'assurance et comparaisons multidimensionnelles sont séparés dans des artefacts fermés et versionnés.
- L'extraction locale page par page est déterministe, sans OCR, LLM, embeddings, vector store, chunking, retrieval sémantique ni accès réseau en mode demo/CI.
- La documentation `docs/methodology/sustainability_corpus.md` décrit acquisition, cutoff, lignée, statuts de couverture, unités, comparabilité, assurance et limites.
- La publication Bachem est datée du 12 mars 2026 sur la preuve du communiqué officiel ; l'approbation distincte du conseil au 2 mars n'est pas utilisée comme date de publication.
- Les 12 `SustainabilityObservation` ont été vérifiées humainement contre les pages officielles : Bachem 6/6 et Siegfried 6/6 pour valeurs, unités, pages, méthodes et assurances.
- Les deux `ClimateTarget`, distinctes des 12 observations, ont été vérifiées humainement avec un résultat `PASS`.
- 83 tests passent, dont 20 tests unitaires/intégration dédiés au Bloc 4 ; le gate ciblé sélectionne 14 tests, tous verts.
- Le Bloc est `DONE` après correction du cutoff, validation des artefacts, revue humaine des 12 observations et des 2 cibles, et réussite de tous les contrôles.
- `assets/Edited.png` reste non suivi, non modifié et hors périmètre.
