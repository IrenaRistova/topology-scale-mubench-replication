#!/usr/bin/env python3
"""
Replication analysis script — paper figures and tables only.

Reads data/run_table.csv (at repository root) and produces only the artifacts used in the paper:

Figures (in figures/):
  - boxplot_energy_by_topology.pdf
  - boxplot_metrics_by_size_combined.pdf
  - boxplot_metrics_by_topology_and_size_combined.pdf

Tables (in tables/):
  - descriptive_stats.tex, descriptive_stats.csv
  - statistical_tests.tex, statistical_tests.csv

Run from the replication package root or from scripts/analysis/:
  python scripts/analysis/make_results.py
  # or
  cd scripts/analysis && python make_results.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import re
import warnings
warnings.filterwarnings('ignore')

# Paths: script lives in <repo>/scripts/analysis/make_results.py
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = REPO_ROOT / 'data'
FIGURES_DIR = SCRIPT_DIR / 'figures'
TABLES_DIR = SCRIPT_DIR / 'tables'

FIGURES_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

METRIC_NAMES = {
    'energy': 'Energy Consumption',
    'dram_energy': 'DRAM Energy Consumption',
    'throughput_rps': 'Throughput',
    'avg_latency_ms': 'Average Response Time',
    'p95_latency_ms': '95th Percentile Response Time',
    'failure_rate': 'Failure Rate',
    'cpu_usage_avg': 'CPU Usage',
    'memory_usage_avg': 'Memory Usage',
}

METRIC_NAMES_SHORT = {
    'energy': 'Energy Consumption',
    'dram_energy': 'DRAM Energy Consumption',
    'throughput_rps': 'Throughput',
    'avg_latency_ms': 'Avg. Response Time',
    'p95_latency_ms': '95th Percentile RT',
    'failure_rate': 'Failure Rate',
    'cpu_usage_avg': 'CPU Usage',
    'memory_usage_avg': 'Memory Usage',
}

METRIC_UNITS = {
    'energy': 'Energy (J)',
    'dram_energy': 'Energy (J)',
    'throughput_rps': 'Throughput (requests per second)',
    'avg_latency_ms': 'Latency (ms)',
    'p95_latency_ms': 'Latency (ms)',
    'failure_rate': 'Failure Rate',
    'cpu_usage_avg': 'CPU Usage',
    'memory_usage_avg': 'Memory Usage (bytes)',
}


def get_metric_title(metric, group_by='both'):
    name = METRIC_NAMES.get(metric, metric.replace('_', ' ').title())
    if group_by == 'topology':
        return f'{name} by Topology'
    if group_by == 'system_size':
        return f'{name} by System Size'
    return f'{name} by Topology and System Size'


def get_metric_label(metric):
    return METRIC_UNITS.get(metric, metric.replace('_', ' ').title())


def escape_latex(text):
    if not isinstance(text, str):
        return text
    for char, escaped in [('_', r'\_'), ('&', r'\&'), ('%', r'\%'), ('$', r'\$'),
                           ('#', r'\#'), ('^', r'\textasciicircum{}'),
                           ('{', r'\{'), ('}', r'\}'), ('~', r'\textasciitilde{}'),
                           ('\\', r'\textbackslash{}')]:
        text = text.replace(char, escaped)
    return text


def load_data():
    df = pd.read_csv(DATA_DIR / 'run_table.csv')
    return df[df['__done'] == 'DONE'].copy()


def calculate_descriptive_stats(df, metric_cols):
    rows = []
    for col in metric_cols:
        if col not in df.columns:
            continue
        mu, std = df[col].mean(), df[col].std()
        rows.append({
            'metric': col,
            'mean': mu,
            'std': std,
            'min': df[col].min(),
            'median': df[col].median(),
            'max': df[col].max(),
            'cv': std / mu if mu != 0 else np.nan,
        })
    return pd.DataFrame(rows)


def create_boxplot_energy_by_topology(df):
    """Single figure: energy by topology (paper figure)."""
    import matplotlib.colors as mcolors
    from matplotlib.patches import PathPatch

    fig, ax = plt.subplots(figsize=(12, 6))
    df.boxplot(column='energy', by='topology', ax=ax, rot=45, showfliers=False)
    plt.title(get_metric_title('energy', 'topology'), fontsize=12, fontweight='bold')
    plt.suptitle('')
    plt.ylabel(get_metric_label('energy'), fontsize=11)
    plt.xlabel('Topology', fontsize=11)
    plt.tight_layout()
    for ext in ('.pdf', '.png'):
        plt.savefig(FIGURES_DIR / f'boxplot_energy_by_topology{ext}', bbox_inches='tight')
    plt.close()


def create_combined_metrics_figure(df):
    """Vertically stacked boxplots by system size (paper figure)."""
    import matplotlib.colors as mcolors
    from matplotlib.patches import PathPatch

    configs = [
        {'metric': 'throughput_rps', 'title': 'Throughput', 'ylabel': 'Throughput (requests per second)', 'row': 0},
        {'metric': 'avg_latency_ms', 'title': 'Average Response Time', 'ylabel': 'Latency (ms)', 'row': 1},
        {'metric': 'energy', 'title': 'Energy Consumption', 'ylabel': 'Energy (J)', 'row': 2},
        {'metric': 'cpu_usage_avg', 'title': 'CPU Usage', 'ylabel': 'CPU Usage', 'row': 3},
        {'metric': 'memory_usage_avg', 'title': 'Memory Usage', 'ylabel': 'Memory Usage (bytes)', 'row': 4},
    ]
    palette = ['#1f77b4', '#ff7f0e', '#2ca02c']

    fig, axes = plt.subplots(5, 1, figsize=(10, 16), sharex=True)
    for c in configs:
        if c['metric'] not in df.columns:
            continue
        ax = axes[c['row']]
        sns.boxplot(data=df, x='system_size', y=c['metric'], ax=ax, palette=palette, width=0.6, linewidth=2, showfliers=False)
        for p in ax.patches:
            if hasattr(p, 'get_facecolor'):
                p.set_edgecolor(p.get_facecolor())
                p.set_linewidth(2.5)
        ax.set_title(c['title'], fontsize=12, fontweight='bold', pad=10)
        ax.set_ylabel(c['ylabel'], fontsize=11)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    axes[-1].set_xlabel('System Size', fontsize=12, fontweight='bold')
    plt.tight_layout()
    for ext in ('.pdf', '.png'):
        plt.savefig(FIGURES_DIR / f'boxplot_metrics_by_size_combined{ext}', bbox_inches='tight')
    plt.close()


def create_combined_metrics_by_topology_and_size_figure(df):
    """Vertically stacked boxplots by topology and system size (paper figure)."""
    import matplotlib.colors as mcolors
    from matplotlib.patches import PathPatch

    configs = [
        {'metric': 'throughput_rps', 'title': 'Throughput', 'ylabel': 'Throughput (requests per second)', 'row': 0},
        {'metric': 'avg_latency_ms', 'title': 'Average Response Time', 'ylabel': 'Latency (ms)', 'row': 1},
        {'metric': 'energy', 'title': 'Energy Consumption', 'ylabel': 'Energy (J)', 'row': 2},
    ]
    palette = ['#1f77b4', '#ff7f0e', '#2ca02c']
    topology_names = sorted(df['topology'].unique())
    n_topologies = len(topology_names)

    fig, axes = plt.subplots(3, 1, figsize=(18, 12), sharex=True)
    for c in configs:
        if c['metric'] not in df.columns:
            continue
        ax = axes[c['row']]
        sns.boxplot(data=df, x='topology', y=c['metric'], hue='system_size', ax=ax,
                    palette=palette, width=0.65, linewidth=2, showfliers=False)
        for p in ax.patches:
            if hasattr(p, 'get_facecolor'):
                p.set_edgecolor(p.get_facecolor())
                p.set_linewidth(2.5)
        for i in range(1, n_topologies):
            ax.axvline(i - 0.5, color='lightgray', linestyle=':', linewidth=1.5, alpha=0.7, zorder=0)
        ax.set_title(c['title'], fontsize=13, fontweight='bold', pad=15)
        ax.set_ylabel(c['ylabel'], fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y')
        if c['row'] == 0:
            ax.legend(title='System Size', title_fontsize=12, fontsize=11, frameon=True, fancybox=True, shadow=True, edgecolor='gray', framealpha=0.9)
        else:
            ax.legend().remove()
    axes[-1].set_xlim(-0.7, n_topologies - 0.3)
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    ax = axes[-1]
    ax.set_xticks(range(n_topologies))
    ax.set_xticklabels(topology_names, rotation=0, ha='center', fontsize=13, fontweight='bold')
    for ext in ('.pdf', '.png'):
        plt.savefig(FIGURES_DIR / f'boxplot_metrics_by_topology_and_size_combined{ext}', bbox_inches='tight')
    plt.close()


def perform_statistical_tests(df, metric):
    metric_name = METRIC_NAMES_SHORT.get(metric, METRIC_NAMES.get(metric, metric.replace('_', ' ').title()))
    results = []
    groups = [g[metric].values for _, g in df.groupby('topology')]
    if len(groups) > 2:
        h, p = stats.kruskal(*groups)
        kw_name = 'DRAM Energy' if metric_name == 'DRAM Energy Consumption' else metric_name
        results.append({'metric': metric_name, 'test': f'KW – {kw_name} (all topologies)', 'statistic': h, 'p_value': p, 'significant': p < 0.05})
    topologies = df['topology'].unique()
    for i, t1 in enumerate(topologies):
        for t2 in topologies[i + 1:]:
            g1 = df[df['topology'] == t1][metric].values
            g2 = df[df['topology'] == t2][metric].values
            u, p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
            results.append({'metric': metric_name, 'test': f'MWU ({t1} vs {t2})', 'statistic': u, 'p_value': p, 'significant': p < 0.05})
    return pd.DataFrame(results)


def main():
    print("Data:", DATA_DIR / 'run_table.csv')
    df = load_data()
    print(f"Loaded {len(df)} completed runs")

    performance_metrics = ['throughput_rps', 'avg_latency_ms', 'p95_latency_ms', 'failure_rate']
    resource_metrics = ['cpu_usage_avg', 'memory_usage_avg']
    energy_metrics = ['energy', 'dram_energy']
    all_metrics = performance_metrics + resource_metrics + energy_metrics

    # 1. Descriptive statistics (paper table)
    print("Descriptive statistics...")
    desc = calculate_descriptive_stats(df, all_metrics)
    desc['metric'] = desc['metric'].map(lambda x: METRIC_NAMES.get(x, x.replace('_', ' ').title()))
    desc.to_csv(TABLES_DIR / 'descriptive_stats.csv', index=False)
    desc_tex = desc.copy()
    desc_tex['metric'] = desc_tex['metric'].apply(escape_latex)
    latex = desc_tex.to_latex(index=False, float_format="%.4f", escape=False)
    with open(TABLES_DIR / 'descriptive_stats.tex', 'w') as f:
        f.write("\\begin{table}[h]\n\\centering\n\\caption{Descriptive Statistics of Performance and Energy Metrics}\n" + latex + "\\end{table}\n")
    print("  -> tables/descriptive_stats.csv, tables/descriptive_stats.tex")

    # 2. Figures used in the paper
    print("Figures...")
    create_boxplot_energy_by_topology(df)
    print("  -> figures/boxplot_energy_by_topology.pdf")
    create_combined_metrics_figure(df)
    print("  -> figures/boxplot_metrics_by_size_combined.pdf")
    create_combined_metrics_by_topology_and_size_figure(df)
    print("  -> figures/boxplot_metrics_by_topology_and_size_combined.pdf")

    # 3. Statistical tests (paper table)
    print("Statistical tests...")
    test_dfs = [perform_statistical_tests(df, m) for m in all_metrics if m in df.columns]
    if test_dfs:
        combined = pd.concat(test_dfs, ignore_index=True)
        combined.to_csv(TABLES_DIR / 'statistical_tests.csv', index=False)
        latex = combined.to_latex(index=False, float_format="%.6f", escape=True)
        for name in ['chain_with_branching', 'probabilistic_tree', 'parallel_fanout', 'complex_mesh', 'hierarchical_tree', 'sequential_fanout']:
            latex = re.sub(re.escape(name), name.replace('_', r'\_'), latex)
        with open(TABLES_DIR / 'statistical_tests.tex', 'w') as f:
            f.write("\\begin{table}[h]\n\\centering\n\\caption{Statistical Test Results for Performance and Energy Metrics}\n\\label{tab:statistical_tests}\n" + latex + "\\end{table}\n")
        print("  -> tables/statistical_tests.csv, tables/statistical_tests.tex")

    print("Done.")


if __name__ == '__main__':
    main()
