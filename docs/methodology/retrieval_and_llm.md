# Retrieval évalué et synthèse structurée

## Corpus récupérable

Le corpus hors ligne est reconstruit à la date de cutoff à partir des artefacts JSON
versionnés de `src/ai_quant/fixtures/sustainability/` : les 12
`SustainabilityObservation`, les 2 `ClimateTarget` et les 2 `CoverageFinding` qui
possèdent à la fois une page et un extrait exploitable. Chaque passage immuable conserve
l'identifiant du record source, l'émetteur, le document, son SHA-256, la période, la date de
publication, les pages PDF et imprimée, l'indicateur et le texte dérivé du record typé.

Les PDF ignorés sous `data/`, les téléchargements et les services externes ne sont pas
nécessaires. Les limitations libres du rapport de couverture ne sont jamais indexées. Cela
exclut notamment la remarque administrative périmée selon laquelle les deux cibles resteraient
à revoir ; elle n'est ni une preuve documentaire ni corrigée dans ce bloc.

## Baselines

Les deux baselines appliquent d'abord les mêmes filtres, combinés par `AND` entre champs et par
`OR` dans un champ : émetteur, document, année, type de record, indicateur et cutoff de
publication.

BM25 utilise une tokenisation locale `unicode-alnum-lower-v1` : normalisation Unicode NFKD,
suppression des diacritiques, minuscules, puis suites alphanumériques ASCII. Avec `k1 = 1.5` et
`b = 0.75`, le score d'un terme est :

`IDF(t) × tf × (k1 + 1) / (tf + k1 × (1 - b + b × dl / avgdl))`

où `IDF(t) = ln(1 + (N - df + 0.5) / (df + 0.5))`. Les égalités sont départagées par
`passage_id`. Une requête sans token est rejetée, un filtre vide retourne zéro résultat et un
passage vide est invalide dès sa construction.

La baseline long-context fournit tous les passages filtrés, ordonnés par date de publication,
document, page PDF puis identifiant. Ses séparateurs conservent les identifiants et la
provenance. La limite explicite est de 50 000 caractères et un dépassement échoue avant tout
appel LLM. Son rang est seulement la position canonique du premier passage pertinent ; ce
n'est pas un classement lexical ou probabiliste.

## Gold set et mesures

`tests/evaluation/retrieval_gold.v1.jsonl` contient exactement 10 questions gelées, leurs
filtres, passages pertinents, documents, pages et justifications. Pour une question `q` :

- `recall@k(q) = 1` si au moins un passage pertinent apparaît dans les `k` premières positions,
  sinon `0` ;
- le rang du premier passage pertinent est sa première position, ou `null` s'il est absent ;
- `candidate_count_after_filters` compte les candidats encore admissibles avant classement ;
- un cas est `filter_only` si le passage attendu est l'unique candidat, sinon `ranking` dès
  qu'au moins deux candidats restent à classer ;
- les agrégats globaux sont les moyennes sur les 10 questions et un second jeu d'agrégats
  porte uniquement sur les cas `ranking`.

Résultats de l'artefact `reports/evaluation/retrieval_baselines.v1.json` :

| Baseline | recall@1 | recall@3 | Contexte moyen | Contexte maximum |
|---|---:|---:|---:|---:|
| BM25 | 0,90 | 1,00 | 429,2 caractères | 829 caractères |
| Long context | 0,70 | 0,90 | 1 268 caractères | 3 860 caractères |

Six questions sont `filter_only` et quatre sont `ranking`. Une réussite `filter_only` mesure
la correction du filtrage, pas la qualité du classement. Sur les quatre cas `ranking`, BM25
atteint 0,75 en recall@1 et 1,00 en recall@3 ; le long context atteint respectivement 0,25 et
0,75. Le rang du premier passage pertinent reste publié dans les deux catégories.

La paraphrase difficile sur les instruments contractuels Siegfried place le passage
market-based au rang BM25 2 : c'est la lacune recall@1 mesurée, non un motif de modifier le
gold set. Dans l'ordre canonique long-context, l'énergie totale Siegfried apparaît au rang 6,
donc hors recall@3, tout en restant présente dans le contexte complet. La latence d'exécution
est volontairement exclue de l'artefact déterministe (`null`) plutôt que présentée comme une
mesure reproductible.

Régénération :

```bash
uv run --frozen python -m ai_quant.retrieval.cli evaluate \
  --output reports/evaluation/retrieval_baselines.v1.json
```

Le JSON enregistre le SHA-256 du gold set et de chaque artefact source, les paramètres, les
résultats par question, les agrégats et les échecs. Aucun embedding, reranker, vector store ou
`pgvector` n'a été ajouté : le corpus tient dans le contexte et les lacunes sont d'abord
mesurées avec deux baselines simples.

## Frontière LLM structurée

`LLMClient.synthesize` reçoit un `SynthesisRequest` fermé : version du prompt, contexte
nécessaire, projections typées des métriques Python et preuves serveur, allowlists exactes du
run et limites de sortie/timeout. Un unique appel retourne seulement un `DraftProposal`
Pydantic. Les champs supplémentaires et références hors allowlist sont rejetés avant rendu.
Le LLM propose les claims, leurs références, incertitudes et limitations. Python reste seul
propriétaire du résumé public, des `claim_id`, des valeurs numériques injectées, des preuves,
du `ValidationReport`, de l'`AutomatedAssessment` et de la `HumanReview`.

Après la validation Pydantic et avant les règles sémantiques finales, Python remplace toujours
le résumé libre par l'une des trois chaînes fermées de `canonical-summary-v1`, selon la seule
présence de métriques et/ou de preuves dans la requête. Une requête vide échoue. Cette
normalisation, commune au fake, aux fixtures et au chemin live, ne reprend aucun texte du
fournisseur, ne modifie aucun autre champ, et est déterministe et idempotente. Le résumé
canonique traverse ensuite les mêmes règles que tout autre texte : aucune exception générale
n'est ajoutée. Il n'existe ni appel de réparation ni seconde synthèse LLM.

La version courante `trust-synthesis-v3` demande au fournisseur de ne jamais émettre les
chaînes internes `reported_zero` et `not_applicable`. Après remplacement du résumé, cette
interdiction reste appliquée aux textes de claims, aux incertitudes et aux limitations, même
lorsqu'elles figurent dans une entrée autorisée. Elles doivent être reformulées comme une
valeur nulle explicitement déclarée par la source, et non comme une donnée manquante, ou comme
une méthode qui ne s'applique pas au champ précis. La règle temporelle accepte seulement trois
réserves épistémiques fermées ; toute autre formulation de même période, d'alignement des dates
ou de comparabilité temporelle échoue de manière fermée.

La projection LLM accepte, sans troncature, la même limite de 4 000 caractères que les
passages et `EvidenceRecord`; l'identité et la provenance officielles restent celles du record
serveur. Le timeout transport et le budget global partagent la même valeur par défaut et toute
configuration où le budget serait plus court est rejetée avant l'appel. En cas d'échec
contrôlé, l'exception du workflow conserve métriques, preuves et métadonnées nettoyées, mais
aucun draft ni rapport de validation.

- `FakeLLMClient` est déterministe, configurable pour succès, schéma invalide, allowlist,
  erreur et timeout, sans réseau.
- `FixtureDraftGenerator` charge, pour le scénario valide, la fixture publique revue dérivée de
  la réponse live v3 et conserve `live_provider` ainsi que le statut historique de l'appel. Le
  scénario bloqué reste une fixture synthétique hors ligne.
- `AnthropicLLMClient` reçoit explicitement clé et modèle, masque la clé dans `repr`, transmet
  réellement le timeout au transport, n'envoie aucun outil et revalide la réponse. Son
  transport est injecté et intégralement mocké dans les tests.

Chaque tentative conserve fournisseur, modèle, version du prompt, statut, latence, response ID,
tokens et retries s'ils existent, erreur nettoyée, origine et provenance tarifaire. Aucun prompt
complet ni secret n'est stocké.

Le snapshot versionné
`src/ai_quant/fixtures/llm/anthropic_pricing.v1.json` connaît explicitement
`claude-sonnet-5` au 23 septembre 2026 : 2 USD par million de tokens d'entrée standards et
10 USD par million de tokens de sortie standards, d'après la
[vue officielle des modèles Claude](https://platform.claude.com/docs/en/models/overview).
Le coût est calculé avec `Decimal` selon
`(input_tokens × 2 + output_tokens × 10) / 1 000 000`, puis sérialisé avec six décimales.
Le snapshot, son URL, sa date de consultation et la devise USD accompagnent les métadonnées.
Un modèle inconnu produit `pricing_unavailable_for_model`, une consommation absente
`token_usage_unavailable` et un appel échoué `model_call_failed`, toujours avec un coût
`null`. Aucun coût n'est inventé. L'estimation couvre uniquement les tokens standards d'entrée
et de sortie : le client n'active ni prompt caching, ni outil, ni recherche web Anthropic.

Les exceptions publiques sont construites puis levées après la sortie du contexte de
l'exception fournisseur ou Pydantic brute. Leurs `__cause__`, `__context__`, arguments et
métadonnées publiques ne conservent ni message fournisseur, ni sortie invalide, ni prompt, ni
clé ; les requêtes de transport masquent aussi les prompts dans leur représentation.

Le mode demo utilise le fake ou les fixtures hors ligne et n'initialise pas le SDK live. Le
modèle live est choisi par `ANTHROPIC_MODEL`, avec la clé fournie par `ANTHROPIC_API_KEY`. Les
tests de l'adaptateur utilisent exclusivement un transport injecté et mocké. En cas d'erreur
ou timeout, une exception métier conserve les métadonnées ainsi que les métriques et preuves
déjà calculées, sans produire de brouillon fiable.

## Préparation d'une capture live

Le module public `ai_quant.llm.live_capture` reçoit un artefact
`validated-run-input.v1` contenant les métriques Python et les preuves officielles d'un seul
run. `prepare_live_capture` reconstruit un `SynthesisRequest`, revalide l'appartenance au run,
les identifiants et les allowlists, puis contrôle le chemin de sortie sans initialiser
Anthropic. Commande hors ligne :

```bash
APP_MODE=demo ANTHROPIC_MODEL=claude-sonnet-5 \
  uv run --frozen python -m ai_quant.llm.cli capture \
  --input src/ai_quant/fixtures/validated_run_official_v1.json \
  --output /private/tmp/ai_quant_block5_live_capture_v3_preflight.json \
  --dry-run
```

Le chemin live exige `APP_MODE=live`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` et une confirmation
explicite. Le modèle vient uniquement de `ANTHROPIC_MODEL`, aucun outil n'est fourni, et un
fichier existant n'est remplacé qu'avec une autorisation d'écrasement. Après l'appel, schéma et
allowlists sont réappliqués. Une capture acceptée reste `pending_human_review`, de type
`unvalidated_live_capture`, et non éligible comme fixture demo. Les tests emploient uniquement
un transport injecté et mocké.

## Normalisation hors ligne d'une capture rejetée

`sanitize_rejected_live_capture` et la sous-commande publique `sanitize-rejected` acceptent
uniquement un `rejected-live-capture.v1` dont l'unique diagnostic est
`implicit_cross_domain_relation` sur le seul champ `summary`. Elles rechargent l'entrée de run
validée, rejouent l'intégralité des règles sur la proposition source, remplacent uniquement le
résumé, puis relancent frontière structurée, validation déterministe et rendu Python. Tout
autre diagnostic, chemin, run ou prompt, toute référence ou tout placeholder invalide, un
artefact déjà normalisé et une sortie existante sont refusés sans appel fournisseur.

```bash
APP_MODE=demo UV_OFFLINE=1 uv run --frozen python -m ai_quant.llm.cli \
  sanitize-rejected \
  --input /private/tmp/ai_quant_block5_live_capture_v3_rejected.json \
  --run-input src/ai_quant/fixtures/validated_run_official_v1.json \
  --output /private/tmp/ai_quant_block5_live_capture_v3_sanitized_candidate.json
```

Le candidat fermé conserve séparément l'échec sémantique initial, la version et le champ de la
normalisation, puis la validation et le rendu réussis. Il conserve aussi l'identité live, les
tokens, la latence, le coût, le snapshot tarifaire et les identifiants de requête/réponse sans
réécrire le statut historique `schema_error`. Son origine reste `live_provider`, sa dérivation
est `live_derived_deterministically_normalized`, aucune réponse brute n'est persistée, et son
statut demeure `pending_human_review` avec `demo_eligible=false`.

## Promotion en fixture publique

Après revue explicite le 23 septembre 2026, le candidat v3 a été promu dans
`src/ai_quant/fixtures/llm/public_demo_live_v3_v1.json`. La fixture fermée conserve les hashes
du rejet et du candidat temporaire, l'ensemble des métadonnées live, l'allowlist, la preuve
officielle et la proposition normalisée. Elle enregistre `approved_for_public_demo`,
`demo_eligible=true` et `explicit_human_approval_recorded` sans persister de réponse brute.

Deux limites éditoriales sont acceptées comme non bloquantes : la redondance « reports a zero
value explicitly reported » et les incertitudes `null` des deux claims de preuve. Cette revue
autorise la fixture pour la démonstration ; elle ne crée pas de `HumanReview` pour les sorties
analytiques produites dans une session. Le workflow demo reste donc hors ligne, relance les
validations et le rendu Python à chaque exécution, puis s'arrête encore à `pending_review`.

## Limite de statut

La réponse live v3 a été conservée comme artefact rejeté après un unique diagnostic sur son
résumé. Sa promotion n'est intervenue qu'après retraitement déterministe, réussite des
validateurs et revue humaine explicite. La fixture publique est maintenant la source du
scénario valide du mode demo ; aucun appel fournisseur n'est nécessaire à l'exécution.
