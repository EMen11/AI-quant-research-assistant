# Speedrun status

- Dernière mise à jour : 2026-09-22
- Branche courante : `speedrun/application-ready`
- Commit du Bloc 0 : `30c9db62b17685c5a0ed350c9780b08196b21f15`

Statuts autorisés : `TODO`, `DOING`, `DONE`. Un bloc n'est `DONE` que lorsque ses contrôles sont passés et documentés. Les commandes des blocs futurs sont les gates prévues ; elles ne sont pas encore disponibles dans le dépôt actuel.

| Bloc | Objet | Statut | Branche | Commit de référence | Commandes de contrôle |
|---:|---|---|---|---|---|
| 0 | Audit reproductible du dépôt | DONE | `speedrun/application-ready` | `30c9db62b17685c5a0ed350c9780b08196b21f15` | `git diff --check`<br>`test -s docs/audit_baseline.md`<br>`test -s SPEEDRUN_STATUS.md`<br>`git status --short --branch` |
| 1 | Socle reproductible, CI et premier déploiement | DONE | `speedrun/application-ready` | modifications locales non commitées sur `30c9db6` | `uv lock --check`<br>`uv sync --frozen --all-groups`<br>`uv run ruff check .`<br>`APP_MODE=demo uv run pytest -q`<br>`APP_MODE=demo uv run streamlit run app.py`<br>healthcheck et contrôle navigateur locaux |
| 2 | Noyau quantitatif fiable | TODO | À créer | — | `uv run ruff check .`<br>`uv run pytest -q tests/unit`<br>`uv run pytest -q` |
| 3 | Contrats de confiance et tranche verticale | TODO | À créer | — | `APP_MODE=demo uv run pytest -q tests/unit tests/integration`<br>`APP_MODE=demo uv run streamlit run app.py` |
| 4 | Corpus sustainable finance traçable | TODO | À créer | — | `uv run pytest -q -k "corpus or evidence or cutoff"`<br>contrôle manuel du manifeste, des hashes, pages et 12 annotations |
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
- Aucun déploiement, push, commit ou ajout à l'index n'a été effectué, conformément à la demande.
- `assets/Edited.png` reste non suivi, non modifié et hors périmètre.
