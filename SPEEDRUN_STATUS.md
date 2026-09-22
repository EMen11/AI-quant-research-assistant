# Speedrun status

- Dernière mise à jour : 2026-09-22
- Branche courante : `speedrun/application-ready`
- Commit de référence du baseline : `0d58a238026744c729343f588eb3cdcd313d23fd`

Statuts autorisés : `TODO`, `DOING`, `DONE`. Un bloc n'est `DONE` que lorsque ses contrôles sont passés et documentés. Les commandes des blocs futurs sont les gates prévues ; elles ne sont pas encore disponibles dans le dépôt actuel.

| Bloc | Objet | Statut | Branche | Commit de référence | Commandes de contrôle |
|---:|---|---|---|---|---|
| 0 | Audit reproductible du dépôt | DONE | `speedrun/application-ready` | `0d58a238026744c729343f588eb3cdcd313d23fd` | `git diff --check`<br>`test -s docs/audit_baseline.md`<br>`test -s SPEEDRUN_STATUS.md`<br>`git status --short --branch` |
| 1 | Socle reproductible, CI et premier déploiement | TODO | À créer | — | `uv sync --frozen --all-groups`<br>`uv run ruff check .`<br>`uv run pytest -q`<br>`APP_MODE=demo uv run streamlit run app.py` |
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
- Les plans préexistants sous `docs/plans/` restent non suivis et inchangés.
- Aucun push, déploiement, commit ou ajout à l'index effectué.
