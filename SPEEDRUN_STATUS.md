# Speedrun status

- Dernière mise à jour : 2026-09-24
- Branche courante : `codex/block-9-secure-demo-deployment`
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
| 6 | Validateurs et évaluation de bout en bout | DONE | `codex/implementer-bloc-6-evaluateurs-et-rapport` | corrections locales sur `cd61978`, seconde revue indépendante `PASS` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run --frozen ruff check .`<br>`APP_MODE=demo uv run --frozen pytest -q -k "evaluation or validation or workflow or trust"`<br>`APP_MODE=demo uv run --frozen pytest -q`<br>double génération byte-identique du rapport<br>seconde revue indépendante `PASS`, aucun P0/P1 |
| 7 | Interface analyste et release publique R1 | DONE | `speedrun/application-ready` | `2f15f1fd426db312eb38a8c334746d8169ba1199` | PR #2 fusionnée en fast-forward<br>CI post-fusion réussie<br>application publique vérifiée sur desktop anonyme<br>contrôle mobile public 390×844 confirmé manuellement |
| 8 | PostgreSQL, FastAPI et Docker Compose | DONE | `codex/block-8-postgres-fastapi-docker` | `23c4f9192aedf9899989a839ae53f3b80b99f6a2` | Deux revues indépendantes exécutées<br>tous les constats confirmés corrigés<br>tests ciblés : 24 PASS<br>suite locale et Docker : 367 PASS, 1 SKIP expliqué, 2 warnings tiers<br>smoke live : 1 PASS<br>migration vide, Alembic, healthchecks et teardown : PASS |
| 9 | Préparation et vérification du déploiement final | DOING | `codex/block-9-secure-demo-deployment` | commit candidat de cette branche (`feat: prepare isolated public demo deployment`) | lock, sync et Ruff : PASS<br>tests ciblés hors ligne : 94 PASS<br>suite complète hors ligne : 353 PASS, 20 SKIP PostgreSQL/live attendus, 2 warnings tiers<br>scan masqué : 147 fichiers suivis dans le candidat, PASS<br>serveur gardé, healthcheck et navigateur local : PASS<br>URL publique anonyme et mobile : non vérifiées |
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

## État du Bloc 6

- Statut `DONE` après une seconde revue indépendante `PASS`, sans P0 ni P1.
- La première revue indépendante avait identifié six P1 : indépendance réelle des splits, liaison claim/référence, familles d'injection bornées, cross-run sans crash, rétablissement de `abstain` et passage par `validate_draft`. Les six ont été reproduits indépendamment puis corrigés.
- Le dataset conserve 24 cas équilibrés : 8 dev, 8 validation et 8 holdout, avec deux contrôles propres et six cas adversariaux sémantiquement distincts par split.
- La politique automatique reçoit toujours uniquement un `ValidationReport`. `eligible_for_review` n'est jamais une approbation ; `review_required` signale un finding bloquant ; `abstain` signale l'absence d'entrées de confiance suffisantes.
- La détection d'injection est explicitement limitée aux familles directes, paraphrasées et obfusquées versionnées ; aucune protection universelle n'est revendiquée.
- Le rapport canonique conserve uniquement les résultats et la charge en cas. Les durées réelles restent dans le sidecar local et concernent précisément le pipeline déterministe d'évaluation de validation, pas le workflow applicatif complet.
- Les contrôles locaux de correction passent : 95 tests ciblés, 291 tests complets, 20 tests spécifiques P1, smoke test demo hors ligne et deux régénérations temporaires byte-identiques du rapport.
- Hashes locaux après correction : dataset `db7cab17163e5df41d4e15ceb7c8e3524ccb1f6d2529c1a9c23967a967d6516e`, rapport `25fc32da059c07a0df3c3b36efa6cf69b7425fc4d61d0f39f2f8b5901d3c4c70`, sidecar `c85bc603abe21f01fef53161f302da06b0719f79255fb77fa3f21f5c45ca7217`.
- Limites P2 conservées : les résultats valent uniquement pour ce dataset versionné et les familles d'attaques couvertes ; treize catégories ne disposent que d'un cas positif chacune.
- Le détecteur déterministe d'injection est volontairement borné et peut bloquer certaines formulations bénignes proches d'une instruction.
- Le holdout actuel a été construit pendant la correction et est gelé à partir de cette version ; ce n'est ni un jeu externe ni un holdout historiquement aveugle.
- Les contrôles dépendant de `StructuredValidationContext` sont exercés par l'évaluation versionnée ; ils ne sont pas tous alimentés par `InMemoryTrustWorkflow`.
- Les statuts restent calculés exclusivement par Python et `eligible_for_review` ne signifie jamais une approbation humaine.
- Les durées du sidecar dépendent du matériel, des caches, de l'ordonnancement et de la charge système ; elles ne sont ni portables ni reproductibles byte-for-byte.
- À l'issue du Bloc 6, le Bloc 7 restait `TODO` et aucun de ses travaux n'avait commencé.

## État du Bloc 7

- Statut `DONE` au commit `2f15f1fd426db312eb38a8c334746d8169ba1199` sur `speedrun/application-ready`.
- La PR #2 a été fusionnée en fast-forward ; la branche distante `origin/speedrun/application-ready` pointe sur le même SHA exact.
- La CI GitHub Actions post-fusion a réussi : https://github.com/EMen11/AI-quant-research-assistant/actions/runs/35936423615.
- L'application publique est disponible à l'adresse https://emen11-ai-quant-research-assistant-app-speedrunapplicati-qq9lei.streamlit.app/ ; Streamlit Community Cloud a nécessité un reboot manuel après la fusion avant de servir la nouvelle version.
- Le chargement public anonyme a réussi. Le contrôle desktop/anonyme a été effectué séparément et n'a montré aucune exception applicative ni traceback.
- L'application Streamlit contient exactement six vues : Overview, Quant, Climate Evidence, Validation & Review, Quality et Methodology.
- Les six vues sont présentes et accessibles publiquement. Le scénario admissible affiche `eligible_for_review` sans `HumanReview` créée ; le scénario bloqué affiche `review_required` sans export approuvé disponible.
- Le scénario bloqué présente le libellé `failed validation`, le bandeau `Untrusted and non-reliable`, ainsi que les findings `cross_run_reference` et `free_numeric_literal` avec la sévérité `critical`.
- Une nouvelle session publique anonyme démarre sans revue persistée. Les revues demo restent session-only et utilisent une identité explicitement non authentifiée.
- Le contrôle mobile public à 390×844 a été confirmé manuellement par le propriétaire : les six vues restent accessibles, aucun débordement horizontal global n'a été observé, le scénario bloqué est sélectionnable et ses findings restent lisibles.
- Les scénarios admissible et bloqué sont reconstruits hors ligne depuis les artefacts versionnés. Deux exécutions navigateur de chaque scénario ont conservé le même run ID, snapshot ID, SHA-256 et assessment, sans doublon ni appel live.
- La couche `analyst_dashboard` isole le chargement des artefacts, les view models, le repository session-only, les révisions, la validation des corrections et la politique d'export. Streamlit demeure une couche de présentation.
- Une `HumanReview` demo porte sur une version exacte du draft, utilise le reviewer explicitement non authentifié `demo-reviewer-unauthenticated`, est horodatée côté serveur en UTC et reste uniquement dans `st.session_state`.
- Une correction conserve l'ancienne version et sa revue dans l'historique de session, crée une nouvelle version, relance `validate_draft`, `assess_draft` et `render_validated_draft`, puis exige une nouvelle revue.
- Aucun export portant `approved` n'est disponible sans `HumanReview` approved sur la version courante, fiable et `eligible_for_review`, liée au run, au draft, au numéro de révision, au SHA-256 du draft canonique complet et au SHA-256 du texte final exact. La frontière d'export revalide les données sérialisées et échoue fermée ; les 16 contournements P1, les 6 mutations de draft P2 et leurs cas positifs dédiés passent.
- Les versions bloquées utilisent le libellé factuel `failed validation` et affichent le même bandeau non fiable, y compris lorsqu'une correction humaine demeure `review_required`. Overview sépare l'origine du contenu courant de la génération source historique.
- La vue Quality lit uniquement `reports/evaluation/retrieval_baselines.v1.json`, `reports/evaluation/workflow_eval.v1.json` et les métadonnées d'appel déjà présentes dans la fixture sélectionnée. Aucune métrique de cache, latence ou coût absente n'est créée.
- Gates locaux : lock et sync figés, Ruff, 7/7 nouveaux cas de hash du draft, 53 tests de fichiers ciblés, 341 tests complets, `/_stcore/health=ok`, six vues accessibles, aucun overlay ni erreur console dans une session navigateur propre.
- Le viewport mobile 390×844 conserve les six vues, les preuves et les findings accessibles, sans débordement horizontal. Un rechargement et un nouvel onglet redémarrent sans revue persistée dans l'environnement testé.
- Captures 1280×720 : `docs/screenshots/block-7/admissible-overview.jpg` montre la provenance historique, `eligible_for_review` et l'absence de revue ; `docs/screenshots/block-7/blocked-validation-findings.jpg` montre `failed validation`, le bandeau, `ValidationReport` et les codes bloquants.
- Le serveur local lancé sur `127.0.0.1:8519` avec les connexions sortantes interdites par la politique OS a été arrêté par `SIGTERM` ; son PID `61441` est terminé et le port est libre.
- Aucun appel Anthropic, PostgreSQL ou réseau métier n'a été effectué pendant les contrôles locaux. Aucune persistance PostgreSQL n'existe encore ; elle relève du Bloc 8.
- `assets/Edited.png` reste non suivi et hors périmètre.

## État du Bloc 8

- Statut `DONE` : livraison clôturée sur `codex/block-8-postgres-fastapi-docker` par le commit portant
  le message `feat: complete Block 8 PostgreSQL API and Docker workflow`. La première revue
  indépendante avait relevé 0 P0, 4 P1 et 3 P2 ; la seconde 0 P0, 2 P1 et 1 P2. Tous les constats
  confirmés ont été corrigés et le rapport final de correction a été accepté.
- Architecture ajoutée : Streamlit live → FastAPI → service transactionnel → repositories
  SQLAlchemy 2 → PostgreSQL, avec modèles métier séparés des modèles ORM.
- La migration Alembic pre-release finale porte le nouvel identifiant `20260924_0002` et est
  appliquée depuis un volume PostgreSQL
  jetable initialement vide. Le catalogue contient les douze tables métier minimales imposées :
  `research_runs`, `market_snapshots`, `metric_records`, `source_documents`, `evidence_records`,
  `generated_drafts`, `draft_claims`, `validation_issues`, `automated_assessments`,
  `human_reviews`, `model_calls` et `evaluation_runs`, plus les deux tables d'association
  `draft_claim_metric_refs` et `draft_claim_evidence_refs`.
- L'identifiant antérieur `20260924_0001` était une révision éphémère, locale et jamais publiée ;
  il n'est pas supporté comme prédécesseur dans le graphe final. Il n'est pas affirmé qu'aucun
  consommateur externe n'a pu l'enregistrer. Une base portant cet ancien stamp doit être recréée
  ou migrée explicitement avant usage ; elle échoue fermée et n'est jamais supprimée
  automatiquement.
- Les références acceptées de claims sont normalisées et ordonnées. Des clés étrangères composites imposent
  le même run pour claim/draft et métrique ou preuve ; les références inconnues, cross-run,
  dupliquées ou aux positions dupliquées sont rejetées par PostgreSQL. Les JSONB immuables
  `declared_metric_ids` et `declared_evidence_ids` conservent séparément les déclarations d'audit,
  y compris rejetées, sans constituer une preuve d'acceptation ni une seconde source de vérité pour
  les associations actives. Les références délibérément invalides de la fixture bloquée ne
  deviennent pas des associations ; elles sont exposées comme données déclarées non fiables avec
  les vrais findings. Une correction peut remplacer explicitement ces déclarations dans une
  nouvelle version sans muter la précédente.
- Le schéma impose clés, appartenances au run, unicités métier, versions positives, statuts fermés
  et timestamps timezone-aware. Les tests PostgreSQL réels vérifient aussi idempotence, rollback,
  atomicité, contraintes, versions et append-only applicatif.
- L'idempotence de `POST /analyses` utilise un verrou advisory PostgreSQL lié à la clé et une
  transaction unique. Le premier appel retourne `201`, même clé/même payload retourne `200` avec
  le même run sans doublon, et même clé/payload différent retourne `409` avec une erreur publique
  stable ne contenant ni traceback ni donnée interne.
- Les repositories n'exposent ni update ni delete pour les artefacts historiques. Cette garantie
  append-only reste applicative : elle n'est ni réglementaire, ni cryptographique, ni résistante à
  un administrateur PostgreSQL.
- Le reviewer est un libellé saisi, non vérifié et non authentifié. Les revues sont append-only et
  liées au run, au draft et à sa version courante. Les corrections verrouillent la ligne stable du
  run avec `SELECT ... FOR UPDATE`, relisent la version courante sous verrou et retournent `409`
  lorsque la précondition draft/version est devenue obsolète. Deux corrections concurrentes sur
  v1 produisent exactement un `201`, un `409`, une seule v2 et une seule revue de correction.
- Une correction reconstruit un `GeneratedDraft` versionné puis réutilise `validate_draft`,
  `assess_draft` et `render_validated_draft`. Une correction admissible peut devenir
  `eligible_for_review`, sans approbation automatique ; une approbation explicite ultérieure de la
  version exacte reste nécessaire. Une correction invalide conserve ses vrais findings
  déterministes et reste `review_required`. Tout échec rollbacke version, claims, références,
  findings, assessment et revue.
- Le chemin `APP_MODE=demo` demeure hors réseau, PostgreSQL, FastAPI et Anthropic ; un contrôle
  isolé passe. La suite complète finale `APP_MODE=demo` avec PostgreSQL passe avec 367 tests réussis et un
  test live sauté faute d'URL dans cette commande ; ce test est exécuté séparément avec 1 PASS.
  Aucun import ni contact
  PostgreSQL, FastAPI ou Anthropic n'est requis au démarrage demo.
- `httpx` demeure déclaré directement dans le groupe de développement ; il apparaît aussi
  transitivement dans le runtime via le SDK Anthropic, dont le chemin fournisseur reste distinct et
  désactivé sans autorisation/configuration explicite. Le chemin `APP_MODE=live` du Bloc 8 persiste
  la fixture `frozen_offline_fixture` sans clé Anthropic et sans appel fournisseur.
- Contrôles uv : `uv lock --check` PASS avec 79 packages résolus et
  `uv sync --frozen --all-groups` PASS. Le lockfile régénéré fait partie des modifications du Bloc 8.
- Contrôles qualité après première revue : Ruff PASS ; 14 tests PostgreSQL P1/repositories PASS ;
  contrats API/OpenAPI PASS ; suite demo complète avec PostgreSQL 361 PASS et 1 SKIP expliqué ;
  test live Streamlit → FastAPI → PostgreSQL 1 PASS ; `alembic check` sans dérive.
- Docker CLI 29.8.0, Engine 29.8.0 et Compose v5.5.1 ont été vérifiés. `docker compose config`,
  `build` et `up -d` passent avec le projet jetable `ai-quant-block8-test-run2`, les services API,
  PostgreSQL et Streamlit sont devenus healthy, et la migration one-shot s'est terminée avec le
  code 0. API, migration et Streamlit s'exécutent sous l'utilisateur non-root `app`.
- Les six routes attendues ont été exercées réellement. Le smoke HTTP a obtenu `201`, `200` et
  `409` pour les trois cas d'idempotence, `200` pour la lecture d'analyse, des preuves et de la
  dernière évaluation, puis `201` pour une revue liée à la version courante. Les healthchecks API,
  PostgreSQL et Streamlit ont réussi ; le smoke Streamlit live a traversé FastAPI et PostgreSQL.
- Trois défauts révélés par l'exécution réelle ont été corrigés : projection des références de la
  fixture sur le run créé par le serveur, ordre explicite des flush SQLAlchemy pour respecter les
  clés étrangères tout en conservant une transaction atomique, et acceptation stricte des tableaux
  JSON de corrections avant conversion immédiate en tuple métier immuable.
- Les quatre P1 reproduits avant correction étaient : acceptation d'une référence cross-run JSONB,
  résultats concurrents `201/500`, correction valide forcée en `missing_required_field`, et
  acceptation de valeurs invalides dans quatre vocabulaires SQL. Les P2 corrigent les contrats
  OpenAPI fermés, l'image runtime et la documentation live/psycopg.
- Les vocabulaires SQL fermés couvrent scénario, état du run, origine des données, type de document,
  statut de preuve, type de claim, code et sévérité de finding, statut et reason code d'assessment,
  disposition de revue, statut et origine de réponse des model calls.
- La contrainte `ck_assessment_status_reason_exact` couple exactement les trois statuts aux trois
  listes unitaires de raisons autorisées. Les trois couples valides passent ; les six couples
  croisés ainsi que les listes vide, multiple et inconnue sont rejetés. Le service reconstruit en
  outre `AutomatedAssessment` avec le modèle métier avant toute autorisation de revue ou
  d'approbation ; une ligne incohérente simulée échoue avec une erreur publique fermée.
- Le target Docker `runtime` n'utilise pas `--all-groups`, ne contient ni pytest, Ruff, uv ni le
  répertoire `tests/`. Il contient uniquement le virtualenv applicatif, `app.py`, Alembic/migrations,
  les documents méthodologiques et les rapports versionnés nécessaires. Le target `test` séparé
  porte les dépendances de développement.
- Les logs applicatifs finaux ne contiennent aucune traceback. Les erreurs de contraintes présentes
  dans l'historique PostgreSQL proviennent des tests de rollback/contraintes et des tentatives ayant
  révélé l'ordre de flush désormais corrigé ; elles n'ont laissé aucun écrit partiel.
- Le teardown Compose a été exécuté. Les trois conteneurs inactifs laissés par le premier essai ont
  également été supprimés ; aucun conteneur, réseau ou volume portant le marqueur
  `ai-quant-block8-test` ne subsiste. Seul le volume jetable exact
  `ai-quant-block8-test-postgres-data` a été supprimé, sans `docker volume prune`, et les ports
  18000/18501 ne répondent plus.
- Le projet de correction `ai-quant-block8-fix` a lui aussi été arrêté. Le seul volume supprimé est
  `ai-quant-block8-fix-postgres-data` après vérification exacte de son nom ; aucun conteneur, réseau
  ou volume portant ce marqueur ne subsiste et les ports 18100/18601 sont arrêtés.
- Aucun appel Anthropic ni réseau métier n'a été effectué. Les seuls téléchargements ont concerné
  les dépendances techniques et les images Docker nécessaires à ces gates locaux.
- La seconde revue indépendante a conclu `FAIL` avec 0 P0, 2 P1 et 1 P2. Les trois constats ciblés
  sont corrigés localement. Le projet jetable `ai-quant-block8-finalfix` a confirmé : migration
  vide vers `20260924_0002`, ancien stamp `20260924_0001` refusé sans suppression automatique,
  `alembic check` sans dérive, 24 tests ciblés PASS, 367 tests complets PASS avec 1 SKIP live
  attendu et 2 warnings tiers, smoke live séparé 1 PASS, et healthchecks des trois services PASS.
  Le teardown a supprimé uniquement le volume exact `ai-quant-block8-finalfix-postgres-data` ;
  aucun conteneur, réseau ou volume `ai-quant-block8-finalfix` ne subsiste et les ports
  18108, 18608 et 55438 ne sont plus en écoute.
  Aucune nouvelle revue indépendante n'a été lancée après cette dernière correction. Le Bloc 8 est
  clôturé `DONE`. Le Bloc 9 a ensuite commencé sur sa branche dédiée.

## État du Bloc 9

- Statut `DOING` : la préparation locale est vérifiée, mais le bloc ne pourra devenir `DONE`
  qu'après publication du commit candidat et contrôle de l'URL réelle conformément au plan.
- La branche `codex/block-9-secure-demo-deployment` part exactement du commit Bloc 8
  `23c4f9192aedf9899989a839ae53f3b80b99f6a2`. Le commit candidat regroupe uniquement les
  changements Bloc 9 revus ; aucun push, merge ou déploiement n'a été effectué.
- En `APP_MODE=demo`, les variables réservées au live sont ignorées. L'adaptateur Anthropic est
  importé paresseusement uniquement lorsqu'un appelant live le demande. Le test dédié présente
  volontairement une clé factice et une URL API invalide, refuse l'import des frontières
  Anthropic/FastAPI/PostgreSQL, et confirme le parcours admissible puis bloqué sans export approuvé.
- Les fixtures approuvées et bloquées restent versionnées avec leur provenance, dates, hashes et
  statuts. L'approbation de promotion de la fixture historique ne crée aucune approbation
  analytique : chaque session demo démarre sans `HumanReview`, et `eligible_for_review` reste une
  invitation à la revue humaine.
- Installation et exécution sont distinguées : `uv sync --frozen --all-groups` peut nécessiter le
  réseau si son cache est vide ; les tests et le serveur ont ensuite été lancés avec
  `UV_OFFLINE=1` et `uv run --offline --frozen`.
- Le vrai serveur Streamlit a démarré avec les connexions socket Python non-loopback bloquées ; son
  healthcheck localhost a répondu `ok`, aucune tentative sortante n'a été enregistrée, et le port
  temporaire 8519 a été arrêté. Ce garde de processus Python n'est pas un pare-feu OS et ne couvre
  ni le navigateur, ni du code natif contournant `socket`, ni un sous-processus retirant le garde.
- Le contrôle navigateur desktop local via le Playwright fourni par le runtime Codex a rendu une
  page non vide, les six vues, sans erreur console ni erreur de page. L'outil `agent-browser`
  n'était pas installé ; ce contrôle local ne vaut donc ni contrôle anonyme distant, ni contrôle
  mobile public.
- Après indexation explicite du candidat, le scan à sortie masquée passe sur ses 147 fichiers texte
  suivis, y compris les 4 nouveaux fichiers Bloc 9 ; il n'affiche jamais les valeurs et reste un
  scan ciblé à haute confiance, pas un scan de tout l'historique Git ni un substitut à la protection
  de secrets de l'hébergeur.
- Contrôles exécutés : `uv lock --check` PASS ; `uv sync --frozen --all-groups` PASS ;
  `uv run --frozen ruff check .` PASS ; 94 tests ciblés hors ligne PASS ; suite complète hors ligne
  353 PASS, 20 SKIP attendus : 19 tests exigent la base PostgreSQL jetable Bloc 8 et 1 exige le
  service FastAPI live Bloc 8. Ces gates avaient réussi sous Docker au Bloc 8 ; leur exclusion de
  la passe demo sans service est intentionnelle. Deux warnings tiers restent présents ; healthcheck,
  rendu navigateur local et arrêt du serveur PASS.
- `docs/deployment.md` décrit la configuration, le démarrage, les limites, la publication manuelle
  et les checklists locale, anonyme distante et mobile. Les cases distante et mobile restent
  explicitement non vérifiées avant un véritable déploiement.
- Les revues demo restent session-only et non authentifiées ; aucune persistance PostgreSQL ne fait
  partie de la démo publique. Le Bloc 10 reste `TODO` et n'a pas commencé.
