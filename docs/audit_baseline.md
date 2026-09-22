# Audit baseline — Bloc 0

- Date de l'audit : 2026-09-22
- Branche : `speedrun/application-ready`
- Commit de référence : `0d58a238026744c729343f588eb3cdcd313d23fd`
- Périmètre : état local du dépôt avant toute correction applicative.

## Convention de sévérité

- **P0** : bloque une démonstration fiable ou peut produire une conclusion financière matériellement trompeuse.
- **P1** : écart majeur de correction, de reproductibilité, de sécurité ou d'exploitabilité.
- **P2** : dette de documentation, de maintenance ou d'ergonomie sans corruption immédiate démontrée.

Les faits observés et les propositions sont séparés dans les tableaux. Les propositions ne sont pas implémentées dans ce bloc.

## 1. Référence Git et arborescence observée

Avant création de ce rapport, `git status --short --branch` indiquait :

```text
## speedrun/application-ready
?? assets/Edited.png
?? docs/
```

`assets/Edited.png` et les deux plans présents sous `docs/plans/` étaient déjà non suivis. Ils n'ont été ni modifiés, ni supprimés, ni ajoutés à Git pendant l'audit.

Arborescence fonctionnelle suivie par Git :

```text
.
├── app/streamlit_app.py              # seul point d'entrée fonctionnel observé
├── assets/                           # captures suivies ; Edited.png non suivi
├── config/prompts.yaml               # fichier vide
├── main.py                           # fichier vide
├── requirements.txt
├── README.md
└── src/
    ├── data_fetcher.py
    ├── orchestrator.py
    ├── report_generator.py
    ├── utils.py                      # fichier vide
    └── agents/
        ├── base_agent.py
        ├── market_analyst.py
        ├── risk_assessor.py
        ├── portfolio_strategist.py
        └── executive_synthesizer.py
```

Éléments locaux non suivis ou ignorés utiles à l'audit : `.env`, `venv/`, `data/conversations.db`, `reports/generated/*.pdf` et `docs/plans/`. Ils ne font pas partie du commit de référence.

## 2. Point d'entrée et procédure de lancement réelle

Le seul lancement fonctionnel observé est Streamlit :

```bash
source venv/bin/activate
streamlit run app/streamlit_app.py
```

Le lancement équivalent avec l'exécutable du venv a répondu `200` sur `/_stcore/health`; la page a finalement affiché le sélecteur de période, l'historique, la zone de question et le bouton d'analyse, sans erreur navigateur. Dans cet environnement précis, le premier import de `src.orchestrator` a pris `74.904 s`, puis l'initialisation de `MultiAgentOrchestrator` `7.962 s`; ce relevé est une observation locale, pas un benchmark portable.

`venv/bin/python main.py` termine avec le code `0` sans rien exécuter, car `main.py` est vide. La « CLI mode » du README n'existe donc pas. Une analyse complète n'a pas été déclenchée pendant l'audit afin d'éviter des appels réseau yfinance/Anthropic et un coût externe.

### Constats de lancement et de packaging

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P1 | `main.py` ; README `CLI mode` lignes 274–278 | `main.py` est vide et la commande documentée ne produit aucune analyse. | Procédure annoncée non fonctionnelle. | Retirer la CLI annoncée ou créer plus tard un vrai point d'entrée testé ; au Bloc 1, documenter Streamlit comme entrée unique. |
| P1 | README `Installation` lignes 267–268 ; `.env.example` absent | Le quick start demande de copier un fichier qui n'existe ni dans l'arbre local ni dans les fichiers suivis. | Un clone propre ne suit pas la procédure documentée. | Créer au Bloc 1 un `.env.example` sans valeur et tester l'installation depuis un clone propre. |
| P1 | `requirements.txt` ; racine du dépôt | Aucune version Python n'est imposée par un fichier projet. Le `python3` système vaut `3.9.6`, le venv local `3.13.5`, alors que le README annonce `3.10+`. | Résolution et comportement variables selon la machine. | Fixer Python 3.12 dans `pyproject.toml` et un fichier de version supporté par l'outillage. |
| P1 | `requirements.txt` lignes 1–12 | Toutes les dépendances sont des bornes basses `>=`; aucun lockfile ni hash n'existe. L'environnement local résout notamment `anthropic 0.84.0`, `yfinance 1.2.0`, `pandas 2.3.3`, `numpy 2.4.2`, `streamlit 1.54.0` et `scipy 1.17.1`. | Deux installations peuvent changer les API, les défauts et les calculs. | Déclarer les dépendances dans `pyproject.toml`, générer et committer un lockfile `uv`. |
| P1 | `app/streamlit_app.py:1-6` ; import de `MultiAgentOrchestrator` | Le module modifie `sys.path` à l'exécution et dépend de la position physique du fichier. | Imports fragiles hors du lancement prévu et package non installable proprement. | Rendre le projet installable et supprimer le `sys.path.append` au Bloc 1. |
| P2 | `src/data_fetcher.py:1`, `app/streamlit_app.py:6` | Toute la pile yfinance/LLM/optimisation est importée et les quatre clients sont construits au démarrage de la page. Le cold start local a été très lent. | Démarrage coûteux et panne de dépendance live susceptible de bloquer une démo. | Introduire au Bloc 1 des interfaces et des fakes chargés en mode demo, sans initialiser la pile live. |
| P2 | `config/prompts.yaml`, `src/utils.py` | Les deux fichiers sont suivis mais vides. | Ils suggèrent des couches de configuration/utilitaires qui n'existent pas. | Les retirer des affirmations documentaires ; ne les remplir que lorsqu'un besoin du bloc concerné existe. |

## 3. Écarts factuels entre README et code

| Sévérité | Affirmation README | Preuve dans le code | Proposition |
|---|---|---|---|
| P0 | Sorties reproductibles à données identiques (`README.md:31`). | Quatre générations libres sont appelées sans température fixée ni fixture ; les données sont téléchargées deux fois (`MarketAnalystAgent.run`, `PortfolioStrategistAgent.run`). | Réserver le terme reproductible aux métriques calculées sur un snapshot figé et au mode demo testé. |
| P0 | Le LLM ne calcule jamais et ne reçoit que des nombres pré-calculés (`README.md:29,37,50`). | `RiskAssessorAgent.run` demande des impacts de stress estimés ; `PortfolioStrategistAgent.run` demande une comparaison à un benchmark non fourni et des conditions de sortie ; la synthèse peut émettre de nouveaux nombres. | Borner le LLM par un schéma, injecter les nombres en Python et valider toute référence quantitative. |
| P1 | Tous les appels yfinance sont protégés (`README.md:47`). | `fetch_market_data` capture les exceptions, mais `PortfolioStrategistAgent.get_returns_matrix` appelle `Ticker.history` sans protection. | Centraliser un fournisseur unique avec erreurs typées et résultat explicite par actif. |
| P1 | Chaque analyse génère automatiquement un PDF (`README.md:102-103`). | `generate_pdf_report` n'est importé ni appelé par l'application ou l'orchestrateur. | Décrire le PDF comme non intégré tant qu'un flux de bout en bout n'est pas testé. |
| P1 | Stockage SQLite + SQLAlchemy (`README.md:292`). | `MultiAgentOrchestrator` utilise directement `sqlite3`; aucune importation SQLAlchemy n'existe. | Corriger la documentation maintenant ; réserver repository/SQLAlchemy au bloc prévu. |
| P1 | Taux sans risque configurable dans `base_agent.py` (`README.md:206`). | `rf = 0.02` est codé en dur dans `markowitz_optimization` et valeur par défaut dans `compute_portfolio_metrics`. | Introduire plus tard une configuration datée, sourcée, avec devise et unité. |
| P1 | Formule VaR incluant la moyenne (`README.md:178-188`). | Le chemin exécuté dans `RiskAssessorAgent.run` calcule seulement `-z × volatilité journalière`; la fonction historique `calculate_var` n'est jamais appelée. | Définir conventions, signe, horizon et méthode, puis tester une implémentation unique. |
| P1 | `.env.example` et CLI présents dans l'arborescence (`README.md:297-318`). | `.env.example` est absent et `main.py` vide. | Aligner le README au dépôt réellement exécutable. |
| P2 | Clé chargée « exclusivement » depuis `.env` (`README.md:48`). | `load_dotenv()` est appelé, puis `os.getenv` accepte aussi l'environnement du processus ; l'absence/valeur vide n'est pas validée au démarrage. | Documenter « variable d'environnement, `.env` local optionnel » et valider proprement en mode live. |
| P2 | Analyse « institutional-grade » et résultat sous 60 secondes (`README.md:16`, UI `streamlit_app.py:17,57`). | Aucun SLO, test de latence ou artefact ne soutient ces termes ; quatre appels LLM sont séquentiels. | Retirer ces claims tant qu'ils ne sont pas mesurés et versionnés. |

## 4. Persistance SQLite

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P1 | `src/orchestrator.py:MultiAgentOrchestrator._init_db`, `_save_to_db`, `get_history` | Accès direct via `sqlite3.connect`; SQLAlchemy est une dépendance inutilisée et aucune interface repository n'existe. | Métier, orchestration et stockage sont couplés. | Ne pas introduire SQLAlchemy au Bloc 1 ; isoler d'abord les interfaces, puis implémenter repository/PostgreSQL au Bloc 8. |
| P1 | `MultiAgentOrchestrator._init_db` | Schéma créé par `CREATE TABLE IF NOT EXISTS`; `PRAGMA user_version` vaut `0`, sans migration. | Une évolution de schéma n'est ni reproductible ni vérifiable depuis une base vide. | Reporter les migrations à Alembic/PostgreSQL au Bloc 8 ; ne pas prétendre qu'elles existent avant. |
| P1 | table `conversations` | Seuls requête, tickers, résumé et quelques métriques sont conservés ; aucune période, donnée source, date d'extraction, version de modèle/prompt, erreurs, preuves ou PDF n'est rattaché. | Impossible de reconstruire ou auditer un run. | Définir au préalable les contrats de snapshot, métrique, preuve et appel modèle ; persister ensuite ces identités. |
| P1 | `_save_to_db`, `get_history` | Connexions gérées manuellement sans context manager/finally ; aucune transaction couvrant le workflow entier ; comportement concurrent non testé. | Fuite/lock possible après exception et sémantique partielle. | Ajouter une interface de stockage testable ; définir les frontières transactionnelles au bloc de persistance. |
| P2 | `__init__`, `_init_db` | Le chemin par défaut est relatif au répertoire courant et `_init_db` crée toujours `data/`, pas le parent de `db_path`. | L'emplacement varie selon le lancement ; un chemin personnalisé peut échouer. | Centraliser les chemins dans une configuration typée. |
| P2 | `.gitignore:5` | `data/` entier est ignoré. | Empêche de versionner plus tard de petites fixtures/manifestes fiables sans exceptions ciblées. | Affiner l'ignore au Bloc 1 ou 2 pour autoriser uniquement les fixtures prévues. |

Point positif : les valeurs de l'`INSERT` et la limite d'historique utilisent des paramètres SQL, ce qui évite ici une interpolation SQL directe.

## 5. Données de marché et données manquantes

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P0 | `MarketAnalystAgent.run`; `PortfolioStrategistAgent.get_returns_matrix/run` | Un run télécharge une première fois chaque ticker pour les métriques, puis une seconde fois pour l'optimisation. Le `period` UI est transmis au premier appel, mais le stratège appelle sa valeur par défaut `1y`. | Les agents peuvent travailler sur des prix, dates et fenêtres différents dans un même résultat. | Créer un unique `MarketSnapshot` immuable par run et le passer à tous les calculs ; aucun second téléchargement. |
| P0 | `fetch_market_data`; `MarketAnalystAgent.run`; `PortfolioStrategistAgent.run` | Les tickers sans données sont omis du dictionnaire de métriques, mais la liste originale est conservée et renvoyée. Un second téléchargement peut encore produire un autre sous-ensemble. | Tickers affichés, métriques et poids peuvent décrire des univers différents sans avertissement. | Réconcilier univers demandé/chargé/rejeté et bloquer ou dégrader explicitement si la couverture est insuffisante. |
| P1 | `PortfolioStrategistAgent.get_returns_matrix` | Aucun `try/except` autour du second appel yfinance ; `DataFrame(...).dropna()` applique une intersection complète et silencieuse des calendriers. | Une erreur live interrompt le run ; des observations ou actifs peuvent disparaître sans diagnostic. | Fournisseur unique, erreurs typées, calendrier/fréquence explicites et rapport de couverture/NaN. |
| P1 | `calculate_metrics`, `get_returns_matrix` | `pct_change()` n'explicite pas la politique de remplissage ; `history()` n'explicite ni `auto_adjust` ni intervalle. | Les défauts pandas/yfinance non verrouillés peuvent modifier rendements et prix utilisés. | Fixer prix ajusté/non ajusté, intervalle et `fill_method=None`; conserver ces métadonnées dans le snapshot. |
| P1 | `calculate_metrics` | Les gardes se limitent à `len(hist) < 2` et `returns.empty`; absence de contrôle sur colonnes, NaN/infini, doublons, fréquence, fuseau ou volume manquant. | Erreur ou métrique silencieusement invalide sur données atypiques. | Valider un schéma de série et distinguer absent, invalide et insuffisant. |
| P2 | `extract_tickers` | Recherche par sous-chaîne et regex `[A-Z]{2,5}` avec blacklist finie ; aucune validation d'instrument ni univers explicite. | Faux positifs, symboles non pris en charge et exposition inattendue. | Pour la démo, utiliser un portefeuille explicite et limité ; valider les symboles côté fournisseur en live. |

## 6. Audit des formules quantitatives

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P1 | `src/data_fetcher.py:calculate_metrics` clé `return_1y` | Calcul de rendement simple de bout en bout sur la période demandée, mais clé toujours nommée `return_1y`; aucune annualisation. | Une sélection 6 mois ou 2 ans est étiquetée à tort « 1y » et non comparable comme rendement annualisé. | Choisir rendement simple ou logarithmique, nommer période/horizon et tester l'annualisation. |
| P1 | `calculate_metrics` clé `volatility_annualized` | Écart-type d'échantillon des rendements simples multiplié par `sqrt(252)` sans stocker fréquence/calendrier. | Hypothèse incorrecte ou ambiguë pour crypto, séries irrégulières et périodes insuffisantes. | Déduire/valider la fréquence, déclarer le facteur et tester les cas constants/irréguliers. |
| P1 | `calculate_max_drawdown` | Formule standard `(P - pic)/pic`, puis minimum, correcte pour des prix positifs propres ; aucun contrôle NaN, zéro ou ordre temporel et aucun test. | Le calcul nominal est plausible mais non protégé contre des séries invalides. | Conserver la formule dans une fonction pure typée, valider l'entrée et ajouter exemples calculables/invariants. |
| P0 | `RiskAssessorAgent.calculate_var`, `RiskAssessorAgent.run` | Deux méthodes coexistent : percentile historique inutilisé et approximation normale exécutée. Cette dernière omet la moyenne, fixe l'horizon à un jour, code les quantiles en dur et retourne un pourcentage négatif présenté comme perte. | Signe, méthode et horizon ne sont pas auditables ; la documentation ne décrit pas le calcul réellement exécuté. | Implémenter et tester VaR historique et paramétrique avec convention de pertes, niveau et horizon explicites. |
| P0 | dépôt entier ; expected shortfall | Aucune implémentation d'expected shortfall n'existe. | Le risque de queue au-delà de la VaR n'est pas mesuré. | Ajouter au Bloc 2 une ES testée, définie sur la même distribution de pertes et le même horizon que la VaR. |
| P0 | `PortfolioStrategistAgent.markowitz_optimization` | Rendements moyens et covariance sont annualisés de façon conventionnelle, mais les bornes `(0.05, 0.60)` deviennent impossibles au-delà de 20 actifs ; le cas mono-actif retourne 100 % malgré le plafond ; le fallback et l'arrondi ne revalident pas somme/bornes. Seul `result.success` est contrôlé. | Des poids non conformes peuvent être affichés comme « optimaux ». | Retourner diagnostics, vérifier contraintes après calcul, traiter explicitement infeasibilité/singularité et tester les échecs. |
| P1 | `compute_portfolio_metrics`; prompt de `PortfolioStrategistAgent.run` | « Expected return » est la moyenne historique annualisée, sans estimation hors échantillon ; le prompt réclame un benchmark absent. | Le LLM est incité à inventer benchmark, performance attendue ou recommandation. | Renommer en rendement historique annualisé, fournir seulement des comparaisons calculées et supprimer tout signal non prouvé. |
| P1 | `markowitz_optimization`, `compute_portfolio_metrics` | Taux sans risque `0.02` sans date, devise, source ou cohérence avec les actifs. | Sharpe non auditable et mélange potentiel de devises/horizons. | Paramètre typé avec source/date/devise, affiché dans le résultat. |

## 7. Couche LLM, prompts et erreurs

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P1 | `src/agents/base_agent.py:BaseAgent.__init__` | Modèle `claude-sonnet-4-20250514` codé en dur ; quatre instances de client sont créées. | Changement, retrait ou comparaison de modèle difficiles ; configuration non traçable. | Interface `LLMClient`, configuration typée fournisseur/modèle et fake hors ligne. |
| P1 | quatre méthodes `run`; `config/prompts.yaml` | Prompts inline non versionnés ; `prompts.yaml` vide. | Impossible de comparer proprement les versions de prompt. | Versionner un prompt principal et son schéma au Bloc 5, après définition des contrats. |
| P0 | `BaseAgent.call_llm`; sorties des quatre agents | Réponses texte libres, sans schéma, validation, allowlist d'identifiants, contrôle des nombres ou réparation. L'instruction « EXACTLY this format » n'est pas vérifiée. | Hallucination, contradiction ou recommandation non sourcée peut être présentée comme résultat final. | Pydantic/JSON structuré, nombres injectés par Python, validateurs déterministes et état d'abstention/revue. |
| P0 | prompts `risk_assessor`, `portfolio_strategist`, `executive_synthesizer` | Le modèle produit stress chiffrés, BUY/HOLD/SELL/REBALANCE, allocations et actions sans preuves ni validation humaine. | Risque de conseil financier trompeur malgré le disclaimer. | Limiter la v1 à une synthèse de faits autorisés ; séparer évaluation automatique et décision humaine. |
| P1 | `BaseAgent.call_llm` | Aucun timeout/retry/backoff explicite au niveau applicatif ; le comportement dépend de la version SDK non verrouillée. L'absence de clé n'est pas validée avant le premier appel. | Run long ou erreur tardive, difficile à diagnostiquer et à tester. | Timeout et politique d'erreur explicites, aucun retry aveugle, erreur typée et mode demo sans client live. |
| P1 | `app/streamlit_app.py:125-128`; orchestrateur | Toute exception est affichée via `st.error(f"Error: {e}")`; aucun résultat partiel n'est conservé si un appel intermédiaire échoue. | Détails internes exposés et travail quantitatif perdu à l'écran. | Mapper les erreurs vers messages sûrs et conserver les artefacts déterministes déjà calculés. |
| P1 | interpolation de `query` et sorties précédentes dans les prompts | Entrées utilisateur et texte généré sont concaténés sans délimitation ni politique anti-injection ; la synthèse fait confiance à du texte LLM antérieur. | Injection ou propagation d'une instruction malveillante/non fiable entre étapes. | Séparer données/instructions, ne passer que des objets validés et tester des cas adversariaux. |
| P2 | `PortfolioStrategistAgent.run:133`; `ExecutiveSynthesizerAgent.run:18-24` | Contexte tronqué à 500/600 caractères, pas à des frontières sémantiques ou de tokens. | Information importante coupée arbitrairement. | Passer des structures compactes validées, pas du texte libre tronqué. |
| P1 | dépôt entier ; appels modèle | Modèle, prompt, latence, statut, tokens, coût et erreur ne sont pas enregistrés. | Aucun audit de qualité/coût ni comparaison reproductible. | Ajouter un `ModelCallRecord` lorsque le client structuré sera introduit. |

## 8. PDF, documents et sources

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P1 | `src/report_generator.py:generate_pdf_report`; dépôt entier | Le code sait générer un PDF, mais ne charge/extrait aucun PDF et l'UI n'a aucun uploader. | Aucun corpus documentaire réel n'alimente l'analyse. | Reporter l'ingestion au Bloc 4 avec manifeste, hash, pages et statut d'extraction. |
| P0 | dépôt entier ; modèle de données | Aucune entité source/preuve/citation, aucun identifiant de document/page, aucun rattachement claim → passage. La simple mention « Yahoo Finance » n'est pas une preuve ouvrable. | Une affirmation qualitative ou quantitative générée n'est pas traçable à une source. | Créer `SourceDocument`/`EvidenceRecord` et n'autoriser que des identifiants du run courant. |
| P1 | `generate_pdf_report`; `MultiAgentOrchestrator.run` | Générateur non relié au workflow, non persisté et non proposé au téléchargement. Le PDF omet l'analyse de risque et de portefeuille et tronque le marché à 40 lignes. | Fonctionnalité annoncée mais absente de bout en bout ; rapport incomplet. | Ne réintégrer l'export qu'après validation/revue, avec test de bout en bout. |
| P1 | `report_generator.py:52,80-91` | Requête et texte LLM sont passés à `Paragraph` sans échappement robuste du balisage ReportLab. | Certains caractères/balises peuvent casser ou altérer le rendu. | Échapper/sanitariser et ajouter des tests PDF avec entrées adversariales. |
| P2 | `report_generator.py:100` | `datetime.now()` local est étiqueté `UTC`. | Horodatage faux hors UTC. | Utiliser un datetime timezone-aware UTC et conserver `retrieved_at` séparément. |

## 9. Tests, qualité, CI, conteneurs et migrations

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P0 | dépôt entier | Aucun fichier de test. `venv/bin/python -m unittest discover -v` termine avec `0 tests` et code `5`. | Aucune formule ni trajectoire d'erreur n'est protégée contre les régressions. | Au Bloc 1, installer pytest et ajouter au moins cinq tests de démarrage/config/import ; réserver les tests quantitatifs complets au Bloc 2. |
| P1 | racine ; `.github/` absent | Aucune CI. | Même les contrôles minimaux ne sont pas exécutés sur changement. | GitHub Actions Python 3.12, installation verrouillée, Ruff et pytest hors réseau. |
| P1 | racine | Aucun `pyproject.toml`, Ruff/flake8/Black, mypy/pyright, pytest config ou pre-commit. | Style, erreurs statiques et configuration dispersés/non contrôlés. | Centraliser configuration projet, lint et tests dans `pyproject.toml`; choisir un typage progressif explicite. |
| P1 | racine | Aucun Dockerfile, Compose ou configuration de déploiement suivie. | Aucun environnement conteneur reproductible ; la procédure dépend du venv local. | Ne pas ajouter Docker au Bloc 1 ; conserver Streamlit Cloud, puis traiter Docker Compose au Bloc 8. |
| P1 | persistance | Aucun Alembic ni autre mécanisme de migration. | Impossible de reconstruire/faire évoluer la base avec historique. | Alembic uniquement au Bloc 8 avec PostgreSQL et test depuis base vide. |
| P2 | code Python suivi | Parsing AST réussi pour les 13 fichiers Python et `pip check` ne détecte pas de dépendance cassée dans le venv actuel. | Santé syntaxique locale seulement ; ce n'est pas une preuve reproductible. | Conserver ces contrôles comme diagnostic, les remplacer par installation verrouillée + lint + tests en CI. |
| P2 | `requirements.txt` | `sqlalchemy`, `pyyaml`, `matplotlib` et `seaborn` ne sont pas utilisés par le chemin applicatif observé ; ReportLab n'est utilisé que par un module orphelin. | Installation et démarrage alourdis, surface de mise à jour inutile. | Au Bloc 1, séparer dépendances réellement nécessaires au mode demo et groupes optionnels ; ne supprimer qu'après tests. |

## 10. Recherche accidentelle de secrets

Contrôles effectués uniquement par noms, identifiants et signatures dans les fichiers suivis ; aucune valeur de `.env` n'a été lue ou affichée.

- `.env` existe localement et est ignoré par `.gitignore:1`.
- Les seules occurrences textuelles de noms sensibles dans les fichiers suivis sont `ANTHROPIC_API_KEY` dans `README.md:268` et `src/agents/base_agent.py:11`.
- Aucun motif courant de clé Anthropic/OpenAI/AWS ou d'en-tête de clé privée n'a été détecté dans les fichiers texte suivis par la recherche limitée exécutée.
- Aucun fichier nommé `.env`, `.env.example`, `*.pem`, `*.key`, `*credential*` ou `*secret*` n'a été trouvé dans l'historique Git atteignable par la recherche de noms exécutée.
- Les binaires suivis n'ont pas été OCRisés et ce contrôle n'est pas une preuve cryptographique d'absence de secret.

| Sévérité | Fichier et symbole | Fait observé | Conséquence | Proposition |
|---|---|---|---|---|
| P1 | `BaseAgent.__init__`; configuration absente | Pas de validation explicite ni séparation demo/live ; l'erreur d'authentification apparaîtra au premier appel. | Démo dépendante d'un secret et erreur tardive. | `APP_MODE=demo` par défaut, FakeLLM et validation live sans journaliser de valeur. |
| P2 | dépôt/CI | Aucun scanner de secrets automatisé n'est configuré. | Une régression future peut être commitée sans gate. | Ajouter au plus tard au Bloc 9 un contrôle CI sur les fichiers suivis, avec sortie masquée. |

## 11. Commandes de contrôle exécutées

```bash
git status --short --branch
git rev-parse HEAD
git branch --show-current
git ls-files
python3 --version
venv/bin/python --version
venv/bin/python -m pip check
venv/bin/python -m unittest discover -v
venv/bin/python main.py
sqlite3 -readonly data/conversations.db "PRAGMA user_version; ..."
git grep -n -I -o -E '<noms de variables sensibles>'
git grep -l -I -E '<signatures de credentials>'
git log --all --name-only --pretty=format: -- '<noms de fichiers sensibles>'
streamlit run app/streamlit_app.py
```

Résultats synthétiques : commit/branche conformes à l'en-tête ; syntaxe AST valide pour 13 fichiers ; `pip check` OK dans le venv local ; zéro test découvert ; CLI vide ; SQLite `user_version=0` ; serveur Streamlit sain et interface rendue ; aucun secret courant détecté par la recherche limitée. Les appels d'analyse live n'ont pas été exécutés.

## 12. Les cinq risques les plus importants

1. **P0 — Un même run n'a pas de source de vérité marché unique.** Deux téléchargements et deux périodes possibles peuvent rendre métriques, VaR et poids mutuellement incohérents.
2. **P0 — Le noyau quantitatif critique n'est ni spécifié ni testé.** VaR incohérente avec le README, ES absente, annualisation implicite et optimisation sans validation complète des contraintes.
3. **P0 — Le texte LLM libre peut devenir une recommandation financière non prouvée.** Aucun schéma, validation numérique, rattachement de preuve, abstention ou revue humaine.
4. **P0 — Aucune suite de tests, CI ni installation verrouillée.** Le comportement dépend du Python et des versions résolues localement et peut régresser sans signal.
5. **P0 — Aucune provenance documentaire réelle.** Aucun chargement PDF, page, hash, preuve ou citation ne soutient les affirmations ; le générateur PDF est orphelin malgré les claims du README.

## 13. Périmètre exact recommandé pour le Bloc 1

Le Bloc 1 doit rester un socle reproductible et déployable, sans corriger encore les formules financières ni ajouter RAG, FastAPI, PostgreSQL ou migrations :

1. imposer Python 3.12 ; créer `pyproject.toml`, un environnement `uv` et un lockfile commité ;
2. documenter des commandes exactes d'installation, lint, test et lancement ;
3. rendre le package importable sans mutation de `sys.path` ;
4. ajouter une configuration typée avec `APP_MODE=demo` par défaut et un `.env.example` factice ;
5. introduire seulement les interfaces minimales `LLMClient`/`FakeLLM` et `MarketDataProvider`/`FrozenMarketDataProvider`, afin que le démarrage demo n'utilise ni réseau ni secret ;
6. ajouter Ruff, pytest, les dossiers `tests/unit`, `tests/integration`, `tests/evaluation` et au moins cinq tests de démarrage/configuration/import ;
7. ajouter GitHub Actions sur Python 3.12 exécutant installation verrouillée, lint et tests hors ligne ;
8. conserver une page Streamlit minimale compatible Community Cloud et vérifier son démarrage sans `.env` ;
9. corriger uniquement la documentation de lancement touchée par ce socle ; ne pas refondre le README métier avant le Bloc 10 ;
10. laisser explicitement au Bloc 2 le snapshot unique et les formules quant, aux Blocs 3–6 les contrats/preuves/LLM/validateurs, et au Bloc 8 SQLAlchemy/PostgreSQL/Alembic/Docker.
