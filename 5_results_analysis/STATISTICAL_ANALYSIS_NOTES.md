# Statistical analysis — tests and metrics

Short reference for what the Structural_Groups_Analysis notebook does and how derived metrics are defined. Use this to explain the tests in the paper and to answer “how do we calculate energy per request, etc.”.

## Tests performed

- **Normality:** Shapiro–Wilk per metric and topology. Most groups have \(p < 0.05\), so we treat distributions as non-normal and use non-parametric tests throughout.
- **Structural contrasts (RQ1):** Mann–Whitney \(U\) with **Holm correction** for multiple comparisons. Contrasts: Dense vs Others, Centralized vs Structured, Seq vs Par, Probabilistic vs Deterministic. Reported in Table 3 (structural groups) and in the Energy (J) table.
- **Global effects:** **Kruskal–Wallis** for topology (and, where used, size and interaction). Used for Energy (J), and for topology × size (energy, throughput).
- **Performance–energy (RQ2):** **Spearman** rank correlation per topology: throughput–energy, latency–energy, failure–energy (Table 5).
- **Significance level:** \(\alpha = 0.05\); bold in tables indicates \(p < 0.05\).

So: we report **descriptive statistics per topology** (e.g. in Descriptive_Statistics and boxplots), then in the statistical analysis we **aggregate by structural group** (Centralized, Structured, Probabilistic, Dense) and test contrasts and correlations. That is why we first describe each topology and then discuss differences by these higher-level characteristics.

## Metrics in the paper output

Included in `table3_4_5_statistics.tex` (paper Tables 3, 4, 5):

- **Throughput (RPS), Avg. response time (ms), P95 latency (ms), Energy (J), CPU utilization, Failure rate** — structural contrasts (Table 3).
- **Energy (J)** — Kruskal–Wallis + structural contrasts (RQ1 Energy table).
- **Topology × Size** — Kruskal–Wallis for energy and throughput.
- **Spearman** — throughput–energy, latency–energy, failure–energy per topology (Table 5).

Excluded from the paper narrative (but computed in the notebook):

- **Energy per request**, **Energy per success**, **Energy per RPS** — see below. They are not included in the merged LaTeX output or in the discourse.

## How the derived energy metrics are calculated (and why they are legit)

These are computed in the notebook from `run_table.csv` columns; they are **not** raw sensor outputs.

- **Energy per request**  
  `energy (J) / request_count`  
  Total CPU package energy during the run divided by total number of requests. Unit: J/request. Legit as “average energy per request” for that run.

- **Energy per successful request**  
  `energy (J) / (request_count × (1 - failure_rate))`  
  With `failure_rate` as fraction (0–1). So denominator = number of successful requests. Unit: J per successful request. Legit as “average energy per successful request.”

- **Energy per RPS (energy per unit throughput)**  
  `energy (J) / throughput_rps`  
  Total energy divided by requests per second. Unit: J/(req/s) = J·s/request. Legit as “energy per unit of throughput” for that run.

So they are standard derived efficiency metrics. The decision to **exclude them from the paper** is about scope of the narrative (focus on raw energy and performance), not about validity of the formulas. The notebook still computes them for optional use; only the merged section and the main text omit them.

## Failure rate and latency in the results

- **Latency** in the analysis is **average response time** (avg_latency_ms).
- **Failure rate** is included in the structural contrasts (Table 3) and in the Spearman table (Failure–Energy, Table 5). It is also in the boxplots; if it was “not commented” in the results text, add a short sentence that failure rate is reported in Table 3 and in the performance–energy correlations (Table 5).
