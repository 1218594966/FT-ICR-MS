# FT-ICR MS Molecular Intelligence Platform

A web-based analytical platform for Fourier transform ion cyclotron resonance mass spectrometry (FT-ICR MS) data. The system integrates molecular formula curation, Van Krevelen visualization, DPR fate analysis, molecular source-database comparison, PMD reaction-network construction, batch processing, and XGBoost-SHAP machine-learning interpretation in a reproducible browser workflow.

The project is designed for research scenarios in dissolved organic matter, environmental molecular characterization, molecular transformation inference, and comparative source analysis. It provides deployable full-stack software with Docker and non-Docker Linux deployment scripts.

## Core Capabilities

- Conventional FT-ICR MS data processing with molecular index completion, filtering, history management, and export.
- Batch processing for multiple conventional analysis files, including synchronized Van Krevelen plots, editable PDF exports, and weighted-average summary tables.
- DPR fate analysis for disappearance, persistence/resistance, and production categories, with DPR-specific plots, heatmaps, and downloadable result files.
- Molecular source-database construction from arbitrary grouped files, with database download, deletion, and sample-to-database comparison.
- Two-sample DPR/database comparison, including D/P/R grouping and chi-square contingency analysis.
- PMD analysis for single-sample and cross-sample putative molecular reaction networks, with customizable reaction dictionaries and GraphML/GEXF export.
- XGBoost machine-learning classification for binary and three-class DPR tasks, trained with GridSearchCV and interpreted by SHAP.
- Editable vector PDF output using embedded TrueType/Type 42 fonts where Matplotlib is used.
- English/Chinese interface switching, light/dark themes, and browser-based operation.

## Analytical Scope

This platform is intended to support molecular-level exploratory analysis and hypothesis generation. The implemented workflows should be interpreted with standard domain caution:

- Van Krevelen and elemental-class plots describe molecular compositional space.
- DPR analysis compares molecular presence/absence patterns between paired samples.
- Source-database comparison quantifies molecular overlap and group-level enrichment rather than proving absolute source attribution.
- PMD networks represent putative formula-difference relationships based on predefined reaction mass differences; edges indicate plausible transformations, not direct experimental proof of reaction occurrence.
- SHAP values explain the trained XGBoost model output and should not be interpreted as causal effects without independent validation.

## Machine Learning Method

The machine-learning module follows a supervised classification workflow:

1. Molecular formulas are parsed into elemental counts and derived ratio features.
2. Numeric molecular descriptors are used as model features.
3. Class labels are read from `NewCol`, supporting binary classification or three-class DPR classification.
4. Data are split into stratified training and test sets.
5. XGBoost is optimized using `GridSearchCV` with accuracy scoring.
6. Independent test-set metrics, training metrics, confusion matrices, correlation matrices, and SHAP plots are generated.

The current parameter grid follows the reference workflow:

```python
{
    "max_depth": [3, 5, 7],
    "learning_rate": [0.1, 0.2],
    "n_estimators": [100, 200],
    "gamma": [0, 0.1],
    "subsample": [0.8, 1.0],
    "colsample_bytree": [0.8, 1.0],
}
```

For sufficiently populated classes, five-fold cross-validation is used. When a selected class has fewer training samples than five, the number of folds is reduced to the maximum valid value to avoid invalid cross-validation splits.

## PMD Reaction-Network Analysis

The PMD module constructs putative reaction networks from exact molecular formula mass differences. It supports:

- Single-sample reaction networks.
- Cross-sample reaction networks.
- PageRank and peak-intensity node annotations where applicable.
- GraphML and GEXF exports for Cytoscape, Gephi, and other network tools.
- Reaction-count CSV export.
- Radar-style reaction summary plots.
- Default and user-defined reaction classes, signs, formulas, names, and colors.

The default reaction dictionary includes representative transformations such as decarboxylation, methylation/demethylation, hydrogenation/dehydrogenation, hydration/dehydration, oxidation/reduction, sulfate-related reactions, nitration/denitration, amination/deamination, and dealkylation reactions.

## Source-Database Analysis

The molecular source-database module allows users to create databases from arbitrary groups of uploaded files. For example, several reclaimed-water samples can be merged into a single reclaimed-water molecular database. A new sample or a paired DPR comparison can then be evaluated against that database.

Implemented outputs include:

- Database molecular inventory.
- Source-file contribution table.
- Sample/database molecular overlap categories.
- Elemental-class distribution across overlap, sample-only, and database-only molecules.
- DPR fate versus database-presence contingency analysis.
- Chi-square tests and heatmap visualization for group-level association.

The analysis is designed to quantify molecular compositional association. It should be reported as evidence of overlap or enrichment, not as deterministic source apportionment.

## Deployment

The repository supports both Docker and non-Docker Linux deployment.

### Docker Deployment

Recommended for servers because all Python and Node dependencies are built inside containers.

```bash
git clone https://github.com/1218594966/FT-ICR-MS.git
cd FT-ICR-MS
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Default access:

```text
http://<server-ip>:8080
```

If the server uses a panel such as 1Panel or an external Nginx reverse proxy, proxy the domain to:

```text
http://127.0.0.1:8080
```

### Non-Docker Deployment

Use this when Docker is not available. The server should provide Git and Python 3.10+. If Node.js/npm is available, the frontend can be rebuilt during deployment; otherwise the committed `frontend/dist` build is served directly.

```bash
git clone https://github.com/1218594966/FT-ICR-MS.git
cd FT-ICR-MS
chmod +x deploy/deploy-linux.sh deploy/stop-linux.sh
PORT=8000 ./deploy/deploy-linux.sh
```

Default access:

```text
http://<server-ip>:8000
```

Stop the non-Docker service:

```bash
./deploy/stop-linux.sh
```

## Server Update

For Docker deployments:

```bash
cd ~/FT-ICR-MS
git pull
cd deploy
docker compose up -d --build
```

For non-Docker deployments:

```bash
cd ~/FT-ICR-MS
git pull
PORT=8000 ./deploy/deploy-linux.sh
```

If `git pull` reports that local deployment files would be overwritten, and the server-side edits do not need to be preserved:

```bash
cd ~/FT-ICR-MS
git restore deploy/deploy.sh deploy/docker-compose.yml
git pull
cd deploy
docker compose up -d --build
```

## Logs

Docker logs:

```bash
docker compose -f deploy/docker-compose.yml logs -f
```

Non-Docker logs:

```bash
tail -f logs/server.log logs/server.err.log
```

## Fonts and Editable PDF Output

The Docker image installs Times-compatible serif fonts and Noto CJK fonts to avoid missing glyphs on Linux servers. Matplotlib PDF outputs are configured to embed TrueType/Type 42 fonts, making text more likely to remain selectable and editable in professional PDF editors.

Microsoft Times New Roman is not bundled because it is proprietary. To obtain exact Times New Roman output on Linux, place legally licensed font files such as `times.ttf`, `timesbd.ttf`, `timesi.ttf`, and `timesbi.ttf` into:

```text
backend/app/fonts/
```

Then rebuild the deployment.

## Repository Structure

```text
backend/    FastAPI backend, analytical APIs, database models, and processing logic
frontend/   Vue 3 frontend and production build artifacts
deploy/     Docker and Linux deployment scripts
```

## Citation and Research Use

When using this platform in academic work, report the analytical assumptions and parameter settings used in each module. In particular, specify:

- FT-ICR MS preprocessing and filtering criteria.
- Elemental classes included in visualization and batch processing.
- DPR category definitions.
- PMD reaction dictionary and mass matching precision.
- Machine-learning feature set, class labels, train/test split, GridSearchCV parameter grid, cross-validation folds, and evaluation metrics.
- SHAP target class and SHAP explanation dataset.

The platform is intended to make molecular-level workflows reproducible, inspectable, and deployable. Scientific conclusions should be supported by appropriate experimental design, statistical reporting, and domain interpretation.
