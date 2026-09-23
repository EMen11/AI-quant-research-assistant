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
| 5 | Retrieval évalué et LLM structuré | DONE | `speedrun/application-ready` | modifications locales non commitées sur `ca10c3e` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run --frozen ruff check .`<br>`APP_MODE=demo uv run --frozen pytest -q -k "content_rules or trust or llm or anthropic or live_capture"`<br>`APP_MODE=demo uv run --frozen pytest -q`<br>fixture live v3 normalisée, validée et revue humainement |
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

## État du Bloc 5

- Seize passages immuables sont reconstruits hors ligne depuis les observations, cibles et constats de couverture typés ; les limitations administratives libres ne sont pas indexées.
- Le gold set gelé contient exactement 10 questions : 6 cas `filter_only` et 4 cas `ranking`. L'artefact publie le nombre de candidats après filtrage, recall@1, recall@3 et le rang du premier passage pertinent.
- Les métriques globales restent 0,90/1,00 pour BM25 et 0,70/0,90 pour le long context ; sur les seuls cas `ranking`, elles sont 0,75/1,00 et 0,25/0,75 respectivement.
- `LLMClient`, `FakeLLMClient` et `AnthropicLLMClient` partagent une synthèse structurée à allowlists exactes, un seul appel, aucun outil et des métadonnées typées de succès ou d'échec.
- La projection LLM accepte sans troncature les extraits officiels jusqu'à 4 000 caractères ; le passage Bachem de 287 caractères traverse le workflow complet avec identité et provenance intactes.
- Le workflow conserve métriques, preuves et métadonnées nettoyées sur erreur ou timeout, sans draft validé ; les timeouts transport/contrôleur sont alignés et les exceptions publiques sont détachées des erreurs et sorties brutes.
- La réponse live v3 à appel unique a été conservée avec ses métadonnées sûres, puis son unique défaut sur `summary` a été corrigé hors ligne par `canonical-summary-v1`, sans seconde synthèse LLM.
- La fixture publique `public_demo_live_v3_v1.json` conserve la provenance `live_provider`, le statut historique `schema_error`, les tokens, la latence, le coût, les identifiants et les hashes sources ; aucune réponse brute n'est persistée.
- La revue humaine du 23 septembre 2026 approuve la fixture pour le mode demo et accepte comme limites non bloquantes la redondance éditoriale du troisième claim et les deux incertitudes `null` des claims de preuve.
- L'approbation de promotion ne crée aucune `HumanReview` de session : le workflow relance les validations et le rendu Python, puis demeure `pending_review` pour chaque sortie analytique.
- Les contrôles figés passent : Ruff, lockfile, installation verrouillée, tests ciblés et suite complète hors ligne, ainsi que la double génération byte-identique de l'artefact retrieval (`25eec8ba5c3f5e87d4bb1c7ced6b8891f5730a2c0266b191f0e6fdaa18f57d27`).
- Le Bloc est `DONE` après validation déterministe, revue humaine et promotion explicite de la fixture live normalisée dans le mode demo hors ligne.
- `assets/Edited.png` reste non suivi, non lu, non modifié et hors périmètre.
