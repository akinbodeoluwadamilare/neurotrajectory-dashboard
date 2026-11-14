from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback, ctx, dash_table, dcc, html, no_update


# =========================================================
# CONFIGURATION
# =========================================================

DATA_FILE = Path("data/processed/oasis_longitudinal_analysis_ready.csv")

GROUP_ORDER = ["Nondemented", "Converted", "Demented"]

GROUP_COLORS = {
    "Nondemented": "#0072B2",
    "Converted": "#E69F00",
    "Demented": "#CC79A7",
}

MAX_SELECTED_SUBJECTS = 5

SUBJECT_LINE_DASHES = [
    "solid",
    "dash",
    "dot",
    "dashdot",
    "longdash",
]

SUBJECT_MARKERS = [
    "circle",
    "square",
    "diamond",
    "triangle-up",
    "cross",
]


# =========================================================
# LOAD + VALIDATE DATA
# =========================================================

if not DATA_FILE.exists():
    raise FileNotFoundError(
        f"Could not find '{DATA_FILE}'. "
        "Run prepare_oasis2_analysis.py first."
    )

df = pd.read_csv(DATA_FILE)

REQUIRED_COLUMNS = [
    "Subject ID",
    "MRI ID",
    "Group",
    "Visit",
    "MR Delay",
    "YearsFromBaseline",
    "M/F",
    "Age",
    "EDUC",
    "SES",
    "MMSE",
    "Delta_MMSE",
    "CDR",
    "eTIV",
    "nWBV",
    "Delta_nWBV",
    "ASF",
]

missing_columns = [
    col for col in REQUIRED_COLUMNS
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        "Missing required columns:\n"
        + "\n".join(f" - {col}" for col in missing_columns)
    )

df = df.sort_values(
    ["Subject ID", "MR Delay", "Visit", "MRI ID"]
).reset_index(drop=True)


# =========================================================
# DATA HELPERS
# =========================================================

def get_baseline_rows(data):
    """
    Strict earliest row per subject.

    head(1) preserves the actual row, including genuine missing values.
    """
    return (
        data.sort_values(
            ["Subject ID", "MR Delay", "Visit", "MRI ID"]
        )
        .groupby("Subject ID", group_keys=False)
        .head(1)
        .reset_index(drop=True)
    )


def get_latest_rows(data):
    """
    Strict latest row per subject.
    """
    return (
        data.sort_values(
            ["Subject ID", "MR Delay", "Visit", "MRI ID"]
        )
        .groupby("Subject ID", group_keys=False)
        .tail(1)
        .reset_index(drop=True)
    )


BASELINE_DF = get_baseline_rows(df)
LATEST_DF = get_latest_rows(df)


def apply_filters(
    data,
    groups,
    sexes,
    age_range,
    education_range,
    ses_values,
    visit_range,
):
    """
    Apply cohort filters to subject-visit rows.

    Age is visit-level. EDUC, SES and sex are effectively subject
    descriptors in this dataset.
    """
    filtered = data.copy()

    if groups:
        filtered = filtered[
            filtered["Group"].isin(groups)
        ]
    else:
        return filtered.iloc[0:0].copy()

    if sexes:
        filtered = filtered[
            filtered["M/F"].isin(sexes)
        ]
    else:
        return filtered.iloc[0:0].copy()

    if age_range is not None:
        filtered = filtered[
            filtered["Age"].between(
                age_range[0],
                age_range[1],
                inclusive="both",
            )
        ]

    if visit_range is not None:
        filtered = filtered[
            filtered["Visit"].between(
                visit_range[0],
                visit_range[1],
                inclusive="both",
            )
        ]

    if education_range is not None:
        filtered = filtered[
            filtered["EDUC"].between(
                education_range[0],
                education_range[1],
                inclusive="both",
            )
        ]

    if ses_values:
        allow_missing = "Unknown" in ses_values
        numeric_ses = [
            float(value)
            for value in ses_values
            if value != "Unknown"
        ]

        mask = filtered["SES"].isin(numeric_ses)

        if allow_missing:
            mask = mask | filtered["SES"].isna()

        filtered = filtered[mask]
    else:
        return filtered.iloc[0:0].copy()

    return filtered


def subjects_surviving_filters(filtered_visits):
    return sorted(
        filtered_visits["Subject ID"]
        .dropna()
        .unique()
        .tolist()
    )


def blank_figure(message):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=15),
            )
        ],
        margin=dict(l=30, r=30, t=50, b=30),
    )
    return fig


def apply_common_layout(
    fig,
    title,
    legend_title="Diagnostic group",
):
    fig.update_layout(
        title=title,
        template="plotly_white",
        font=dict(size=13),
        margin=dict(l=65, r=25, t=75, b=55),
        legend_title_text=legend_title,
        hoverlabel=dict(align="left"),
    )
    return fig


# =========================================================
# FIGURE BUILDERS
# =========================================================

def create_age_nwbv_scatter(
    filtered_visits,
    observation_mode="all",
    selected_subjects=None,
    cohort_revision="cohort",
    full_visits=None,
):
    """
    Step 8 comparison-state scatter.

    Visual hierarchy:
    1. Full cohort      -> faint gray context
    2. Filtered cohort  -> diagnostic-group colors
    3. Selected subjects-> larger, opaque, outlined marks
    """

    selected_subjects = selected_subjects or []
    selected_set = set(selected_subjects)

    if observation_mode == "baseline":
        plot_df = filtered_visits[
            filtered_visits["MR Delay"].eq(0)
        ].copy()

        full_context = (
            full_visits[
                full_visits["MR Delay"].eq(0)
            ].copy()
            if full_visits is not None
            else None
        )

        mode_label = "Baseline only"

    else:
        plot_df = filtered_visits.copy()

        full_context = (
            full_visits.copy()
            if full_visits is not None
            else None
        )

        mode_label = "All longitudinal visits"

    if plot_df.empty:
        return blank_figure(
            "No observations match the current filters."
        )

    fig = go.Figure()

    # -----------------------------------------------------
    # State 1: full cohort context
    # -----------------------------------------------------
    if (
        full_context is not None
        and not full_context.empty
    ):
        fig.add_trace(
            go.Scatter(
                x=full_context["Age"],
                y=full_context["nWBV"],
                mode="markers",
                name="Full cohort context",
                marker=dict(
                    size=5,
                    color="#cfd4dc",
                    opacity=0.20,
                ),
                customdata=np.stack(
                    [
                        full_context["Subject ID"],
                        full_context["MRI ID"],
                        full_context["Visit"],
                        full_context["YearsFromBaseline"],
                        full_context["MMSE"],
                        full_context["CDR"],
                        full_context["Group"],
                    ],
                    axis=-1,
                ),
                hoverinfo="skip",
                showlegend=True,
            )
        )

    # -----------------------------------------------------
    # State 2: active filtered cohort
    # -----------------------------------------------------
    filtered_fig = px.scatter(
        plot_df,
        x="Age",
        y="nWBV",
        color="Group",
        category_orders={"Group": GROUP_ORDER},
        color_discrete_map=GROUP_COLORS,
        custom_data=[
            "Subject ID",
            "MRI ID",
            "Visit",
            "YearsFromBaseline",
            "MMSE",
            "CDR",
            "Group",
        ],
        labels={
            "Age": "Age (years)",
            "nWBV": "Normalized whole-brain volume (nWBV)",
            "Group": "Diagnostic group",
        },
    )

    for trace in filtered_fig.data:
        subjects = [
            row[0]
            for row in trace.customdata
        ]

        # -------------------------------------------------
        # State 3: selected subjects
        # -------------------------------------------------
        if selected_set:
            trace.marker.opacity = [
                1.0
                if subject in selected_set
                else 0.32
                for subject in subjects
            ]

            trace.marker.size = [
                11
                if subject in selected_set
                else 7
                for subject in subjects
            ]

            trace.marker.line = dict(
                width=[
                    2.0
                    if subject in selected_set
                    else 0
                    for subject in subjects
                ],
                color="#1f2937",
            )

        else:
            trace.marker.opacity = [0.72] * len(subjects)
            trace.marker.size = [8] * len(subjects)

        trace.hovertemplate = (
            "Subject=%{customdata[0]}"
            "<br>Group=%{customdata[6]}"
            "<br>Visit=%{customdata[2]}"
            "<br>Age=%{x}"
            "<br>nWBV=%{y:.4f}"
            "<br>Years from baseline=%{customdata[3]:.2f}"
            "<br>MMSE=%{customdata[4]}"
            "<br>CDR=%{customdata[5]}"
            "<extra></extra>"
        )

        fig.add_trace(trace)

    fig = apply_common_layout(
        fig,
        f"Age vs. nWBV — {mode_label}",
    )

    fig.add_annotation(
        text=(
            "Gray = full cohort context · "
            "group hue = active filtered cohort · "
            "larger + dark outline = selected subjects"
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=1.08,
        showarrow=False,
        align="left",
        font=dict(
            size=10,
            color="#667085",
        ),
    )

    fig.update_layout(
        dragmode="select",
        clickmode="event+select",
        uirevision=(
            f"cohort-scatter-"
            f"{observation_mode}-"
            f"{cohort_revision}"
        ),
        selectionrevision=(
            f"cohort-selection-{cohort_revision}"
        ),
        height=460,
        legend=dict(
            title="Cohort state / group",
        ),
    )

    return fig


def _selected_subject_dataframe(
    filtered_visits,
    selected_subjects,
):
    if not selected_subjects:
        return filtered_visits.iloc[0:0].copy()

    return (
        filtered_visits[
            filtered_visits["Subject ID"]
            .isin(selected_subjects)
        ]
        .sort_values(
            ["Subject ID", "YearsFromBaseline", "Visit"]
        )
        .copy()
    )


def create_subject_trajectory(
    filtered_visits,
    selected_subjects,
    variable,
):
    plot_df = _selected_subject_dataframe(
        filtered_visits,
        selected_subjects,
    )

    if plot_df.empty:
        return blank_figure(
            "Click a scatterplot point, lasso up to five subjects, "
            "or use the Subject selector."
        )

    variable_config = {
        "nWBV": {
            "title": "nWBV Trajectories",
            "y_label": "Normalized whole-brain volume (nWBV)",
            "hover_format": ".4f",
        },
        "MMSE": {
            "title": "MMSE Trajectories",
            "y_label": "MMSE score",
            "hover_format": ".0f",
        },
        "CDR": {
            "title": "CDR Trajectories",
            "y_label": "Clinical Dementia Rating (CDR)",
            "hover_format": ".1f",
        },
    }

    cfg = variable_config[variable]

    fig = go.Figure()

    ordered_subjects = [
        subject
        for subject in selected_subjects
        if subject in set(plot_df["Subject ID"])
    ]

    for idx, subject_id in enumerate(
        ordered_subjects[:MAX_SELECTED_SUBJECTS]
    ):
        subject_df = (
            plot_df[
                plot_df["Subject ID"] == subject_id
            ]
            .sort_values("YearsFromBaseline")
        )

        if subject_df.empty:
            continue

        group = subject_df["Group"].iloc[0]

        line_dash = SUBJECT_LINE_DASHES[
            idx % len(SUBJECT_LINE_DASHES)
        ]
        marker_symbol = SUBJECT_MARKERS[
            idx % len(SUBJECT_MARKERS)
        ]

        fig.add_trace(
            go.Scatter(
                x=subject_df["YearsFromBaseline"],
                y=subject_df[variable],
                mode="lines+markers",
                name=subject_id,
                line=dict(
                    color=GROUP_COLORS.get(group),
                    dash=line_dash,
                    width=1.5 if variable == "CDR" else 2.2,
                ),
                marker=dict(
                    color=GROUP_COLORS.get(group),
                    symbol=marker_symbol,
                    size=8,
                    line=dict(
                        color="#1f2937",
                        width=1.0,
                    ),
                ),
                connectgaps=False,
                customdata=np.stack(
                    [
                        subject_df["Visit"],
                        subject_df["Age"],
                        subject_df["MMSE"].fillna(np.nan),
                        subject_df["CDR"],
                        subject_df["nWBV"],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"<b>{subject_id}</b>"
                    f"<br>Group={group}"
                    "<br>Visit=%{customdata[0]}"
                    "<br>Years=%{x:.2f}"
                    "<br>Age=%{customdata[1]}"
                    "<br>nWBV=%{customdata[4]:.4f}"
                    "<br>MMSE=%{customdata[2]}"
                    "<br>CDR=%{customdata[3]}"
                    "<extra></extra>"
                ),
            )
        )

    fig = apply_common_layout(
        fig,
        cfg["title"],
        legend_title="Selected subjects",
    )

    fig.update_xaxes(
        title="Years from Baseline"
    )

    fig.update_yaxes(
        title=cfg["y_label"]
    )

    if variable == "MMSE":
        fig.update_yaxes(
            range=[0, 30],
            dtick=5,
        )

    if variable == "CDR":
        fig.update_yaxes(
            tickmode="array",
            tickvals=[0, 0.5, 1, 2],
            ticktext=["0", "0.5", "1", "2"],
            range=[-0.1, 2.1],
        )

    selection_revision = "-".join(
        sorted(selected_subjects)
    ) or "none"

    fig.update_layout(
        uirevision=f"trajectory-{variable}-{selection_revision}",
        height=390,
        hovermode="closest",
        hoverlabel=dict(
            align="left",
            bgcolor="#ffffff",
            bordercolor="#98a2b3",
            font=dict(size=12, color="#101828"),
            namelength=-1,
        ),
        legend=dict(
            title="Selected subjects",
            font=dict(size=10),
            itemsizing="constant",
            itemclick="toggle",
            groupclick="toggleitem",
        ),
    )

    return fig


def create_group_distribution(
    filtered_visits,
    metric,
    selected_subjects=None,
    cohort_revision="cohort",
    grouping_mode="diagnostic",
):
    """
    Prototype-style distribution:
    one Plotly box trace per category with all subject observations shown.
    """

    selected_subjects = selected_subjects or []
    selected_set = set(selected_subjects)

    metric_config = {
        "nWBV": {
            "label": "Normalized whole-brain volume (nWBV)",
            "mode": "Baseline",
            "decimals": 4,
        },
        "MMSE": {
            "label": "MMSE score",
            "mode": "Baseline",
            "decimals": 1,
        },
        "Delta_nWBV": {
            "label": "Change in nWBV",
            "mode": "Latest follow-up",
            "decimals": 4,
        },
        "Delta_MMSE": {
            "label": "Change in MMSE",
            "mode": "Latest follow-up",
            "decimals": 1,
        },
        "eTIV": {
            "label": "Estimated total intracranial volume (eTIV)",
            "mode": "Baseline",
            "decimals": 2,
        },
    }

    cfg = metric_config[metric]

    if metric.startswith("Delta_"):
        source_df = get_latest_rows(filtered_visits).copy()
    else:
        source_df = filtered_visits[
            filtered_visits["MR Delay"].eq(0)
        ].copy()

    source_df = source_df.dropna(subset=[metric])

    if source_df.empty:
        if (
            not metric.startswith("Delta_")
            and not filtered_visits["MR Delay"].eq(0).any()
        ):
            return blank_figure(
                "Baseline (Visit 1) is excluded by the active filters."
            )

        return blank_figure(
            "No observations match the current filters."
        )

    if grouping_mode == "selection":
        if not selected_set:
            return blank_figure(
                "Brush or click subjects to compare selected vs remaining cohort."
            )

        source_df["ComparisonGroup"] = np.where(
            source_df["Subject ID"].isin(selected_set),
            "Selected",
            "Remaining filtered cohort",
        )

        grouping_column = "ComparisonGroup"
        visible_groups = [
            group
            for group in ["Selected", "Remaining filtered cohort"]
            if group in source_df[grouping_column].unique()
        ]
        color_lookup = {
            "Selected": "#344054",
            "Remaining filtered cohort": "#cfd4dc",
        }
        x_title = "Selection comparison"

    else:
        grouping_column = "Group"
        visible_groups = [
            group
            for group in GROUP_ORDER
            if group in source_df[grouping_column].unique()
        ]
        color_lookup = GROUP_COLORS
        x_title = "Diagnostic group"

    fig = go.Figure()

    for group in visible_groups:
        group_df = (
            source_df[
                source_df[grouping_column] == group
            ]
            .sort_values("Subject ID")
            .reset_index(drop=True)
        )

        if group_df.empty:
            continue

        color = color_lookup[group]

        q1 = float(group_df[metric].quantile(0.25))
        median = float(group_df[metric].median())
        q3 = float(group_df[metric].quantile(0.75))
        vmin = float(group_df[metric].min())
        vmax = float(group_df[metric].max())
        n_subjects = int(
            group_df["Subject ID"].nunique()
        )

        customdata = np.column_stack(
            [
                group_df["Subject ID"].astype(str),
                group_df["Visit"].astype(str),
                group_df["YearsFromBaseline"].astype(float),
                group_df["Group"].astype(str),
            ]
        )

        fig.add_trace(
            go.Box(
                x=[group] * len(group_df),
                y=group_df[metric],
                name=group,
                boxpoints="all",
                jitter=0.28,
                pointpos=0,
                marker=dict(
                    color=color,
                    opacity=0.72,
                    size=6.5,
                    line=dict(
                        color="#ffffff",
                        width=0.6,
                    ),
                ),
                line=dict(
                    color=color,
                    width=1.8,
                ),
                fillcolor=color,
                opacity=0.24,
                customdata=customdata,
                notched=False,
                showlegend=False,
                hovertemplate=(
                    f"{x_title}=%{{x}}"
                    f"<br>{cfg['label']}=%{{y}}"
                    "<br>Subject ID=%{customdata[0]}"
                    "<br>Visit=%{customdata[1]}"
                    "<br>Years from baseline=%{customdata[2]:.2f}"
                    "<br>Diagnostic group=%{customdata[3]}"
                    "<extra></extra>"
                ),
            )
        )

        # Selected-subject overlay.
        # Box traces do not support per-point marker.line.width arrays,
        # so selected observations are emphasized with a scatter layer.
        selected_group_df = group_df[
            group_df["Subject ID"].isin(selected_set)
        ].copy()

        if not selected_group_df.empty:
            selected_customdata = np.column_stack(
                [
                    selected_group_df["Subject ID"].astype(str),
                    selected_group_df["Visit"].astype(str),
                    selected_group_df["YearsFromBaseline"].astype(float),
                    selected_group_df["Group"].astype(str),
                ]
            )

            fig.add_trace(
                go.Scatter(
                    x=[group] * len(selected_group_df),
                    y=selected_group_df[metric],
                    mode="markers",
                    marker=dict(
                        color=color,
                        size=10,
                        opacity=1.0,
                        symbol="circle",
                        line=dict(
                            color="#1f2937",
                            width=1.8,
                        ),
                    ),
                    customdata=selected_customdata,
                    hovertemplate=(
                        f"{x_title}=%{{x}}"
                        f"<br>{cfg['label']}=%{{y}}"
                        "<br>Subject ID=%{customdata[0]}"
                        "<br>Visit=%{customdata[1]}"
                        "<br>Years from baseline=%{customdata[2]:.2f}"
                        "<br>Diagnostic group=%{customdata[3]}"
                        "<extra>Selected</extra>"
                    ),
                    showlegend=False,
                )
            )

        # Transparent median hotspot: keeps the prototype appearance
        # while exposing the exact distribution summary on hover.
        decimals = cfg["decimals"]

        # Median summary marker.
        # The y-position is the exact median of the same rows used by the box.
        # A compact horizontal tick visually reinforces the box median,
        # while the open diamond remains an easy hover target.
        fig.add_trace(
            go.Scatter(
                x=[group],
                y=[median],
                mode="markers",
                marker=dict(
                    size=18,
                    symbol="line-ew",
                    color="#1f2937",
                    line=dict(
                        color="#1f2937",
                        width=2.5,
                    ),
                    opacity=0.95,
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=[group],
                y=[median],
                mode="markers",
                marker=dict(
                    size=9,
                    symbol="diamond-open",
                    color="#1f2937",
                    line=dict(
                        color="#1f2937",
                        width=1.8,
                    ),
                    opacity=1.0,
                ),
                customdata=[
                    [
                        n_subjects,
                        q1,
                        median,
                        q3,
                        vmin,
                        vmax,
                    ]
                ],
                hovertemplate=(
                    f"{x_title}=%{{x}}"
                    "<br>n subjects=%{customdata[0]}"
                    f"<br>Q1=%{{customdata[1]:.{decimals}f}}"
                    f"<br><b>Median=%{{customdata[2]:.{decimals}f}}</b>"
                    f"<br>Q3=%{{customdata[3]:.{decimals}f}}"
                    f"<br>Min=%{{customdata[4]:.{decimals}f}}"
                    f"<br>Max=%{{customdata[5]:.{decimals}f}}"
                    "<extra>Median summary</extra>"
                ),
                showlegend=False,
            )
        )

    metric_short = {
        "nWBV": "nWBV",
        "MMSE": "MMSE",
        "Delta_nWBV": "ΔnWBV",
        "Delta_MMSE": "ΔMMSE",
        "eTIV": "eTIV",
    }[metric]

    if grouping_mode == "selection":
        title = f"{metric_short} — Selected vs Remaining"
    elif metric.startswith("Delta_"):
        title = f"{metric_short} — Latest Follow-up by Diagnostic Group"
    else:
        title = f"{metric_short} — Baseline by Diagnostic Group"

    fig = apply_common_layout(
        fig,
        "",
    )

    fig.update_layout(
        boxmode="overlay",
        height=400,
        showlegend=False,
        hovermode="closest",
        margin=dict(
            l=65,
            r=28,
            t=92,
            b=58,
        ),
        title=dict(
            text=title,
            x=0.02,
            xanchor="left",
            y=0.96,
            yanchor="top",
            font=dict(size=18),
        ),
        uirevision=(
            f"distribution-{metric}-"
            f"{grouping_mode}-{cohort_revision}"
        ),
        selectionrevision=(
            f"distribution-selection-{cohort_revision}"
        ),
    )

    fig.update_xaxes(
        title=x_title,
        categoryorder="array",
        categoryarray=visible_groups,
    )

    fig.update_yaxes(
        title=cfg["label"],
    )

    if metric == "MMSE":
        fig.update_yaxes(
            range=[0, 30]
        )

    if metric.startswith("Delta_"):
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_width=1,
        )

    fig.add_annotation(
        text="Points = subjects · dark center tick = median · ◇ hover for distribution summary",
        xref="paper",
        yref="paper",
        x=1,
        y=1.035,
        showarrow=False,
        xanchor="right",
        font=dict(
            size=10,
            color="#667085",
        ),
    )

    return fig


# =========================================================
# DETAILS TABLE
# =========================================================

DETAIL_COLUMNS = [
    "Subject ID",
    "MRI ID",
    "Group",
    "Visit",
    "YearsFromBaseline",
    "Age",
    "M/F",
    "EDUC",
    "SES",
    "MMSE",
    "CDR",
    "nWBV",
    "Delta_nWBV",
    "Delta_MMSE",
    "eTIV",
]


def make_details_records(
    filtered_visits,
    selected_subjects,
):
    if not selected_subjects:
        return []

    detail_df = (
        filtered_visits[
            filtered_visits["Subject ID"]
            .isin(selected_subjects)
        ][DETAIL_COLUMNS]
        .sort_values(
            ["Subject ID", "YearsFromBaseline", "Visit"]
        )
        .copy()
    )

    detail_df["YearsFromBaseline"] = (
        detail_df["YearsFromBaseline"].round(2)
    )
    detail_df["nWBV"] = (
        detail_df["nWBV"].round(4)
    )
    detail_df["Delta_nWBV"] = (
        detail_df["Delta_nWBV"].round(4)
    )
    detail_df["Delta_MMSE"] = (
        detail_df["Delta_MMSE"].round(1)
    )
    detail_df["eTIV"] = (
        detail_df["eTIV"].round(2)
    )
    detail_df["MMSE"] = (
        detail_df["MMSE"].round(0)
    )
    detail_df["CDR"] = (
        detail_df["CDR"].round(1)
    )

    return detail_df.to_dict("records")


# =========================================================
# FILTER DEFAULTS
# =========================================================

AGE_MIN = int(df["Age"].min())
AGE_MAX = int(df["Age"].max())

EDUC_MIN = int(df["EDUC"].min())
EDUC_MAX = int(df["EDUC"].max())

VISIT_MIN = int(df["Visit"].min())
VISIT_MAX = int(df["Visit"].max())

SES_OPTIONS = [
    {"label": f"SES {value}", "value": float(value)}
    for value in sorted(
        df["SES"].dropna().unique().tolist()
    )
]
SES_OPTIONS.append(
    {"label": "Unknown", "value": "Unknown"}
)

ALL_SES_VALUES = [
    option["value"]
    for option in SES_OPTIONS
]

SUBJECT_OPTIONS = [
    {
        "label": (
            f"{subject_id} — "
            f"{df.loc[df['Subject ID'] == subject_id, 'Group'].iloc[0]}"
        ),
        "value": subject_id,
    }
    for subject_id in sorted(
        df["Subject ID"].unique()
    )
]


# =========================================================
# DASH APP
# =========================================================

app = Dash(
    __name__,
    title="NeuroTrajectory",
)

server = app.server


def filter_card(label, component):
    return html.Div(
        [
            html.Div(
                label,
                className="filter-label",
            ),
            component,
        ],
        className="filter-item",
    )


app.layout = html.Div(
    className="app-shell",
    children=[
        dcc.Store(
            id="interaction-message-store",
            data="",
        ),

        html.Header(
            className="app-header",
            children=[
                html.Div(
                    className="header-copy",
                    children=[
                        html.H1(
                            "NeuroTrajectory",
                            className="app-title",
                        ),
                        html.Div(
                            (
                                "Interactive Visual Analytics for Exploring "
                                "Longitudinal Brain Atrophy and Cognitive "
                                "Decline in Aging and Dementia"
                            ),
                            className="app-tagline",
                        ),
                        html.P(
                            (
                                "Explore relationships among brain volume, "
                                "cognitive measures, dementia severity, and "
                                "participant characteristics across repeated "
                                "OASIS-2 visits."
                            ),
                            className="app-subtitle",
                        ),
                    ],
                ),
                html.Div(
                    [
                        html.Div(
                            "Exploratory visual analytics",
                            className="header-badge",
                        ),
                        html.Div(
                            [
                                html.Strong("For exploratory analysis only"),
                                " — not a diagnostic tool.",
                            ],
                            className="header-note",
                        ),
                    ],
                    className="header-meta",
                ),
            ],
        ),

        html.Section(
            className="orientation-panel",
            children=[
                html.Div(
                    [
                        html.Div(
                            "Workflow",
                            className="orientation-label",
                        ),
                        html.Div(
                            "Filter → Explore → Select → Compare → Inspect trajectories",
                            className="workflow-text",
                        ),
                        html.Div(
                            [
                                html.Strong("Years from Baseline"),
                                (
                                    " = MR Delay ÷ 365.25, representing actual "
                                    "elapsed time between visits. Visit numbers "
                                    "are not assumed to be equally spaced."
                                ),
                            ],
                            className="time-abstraction-note",
                        ),
                    ],
                    className="workflow-block",
                ),
                html.Details(
                    [
                        html.Summary("Measures & definitions"),
                        html.Div(
                            [
                                html.Div([html.Strong("nWBV"), " — Normalized Whole-Brain Volume"]),
                                html.Div([html.Strong("eTIV"), " — Estimated Total Intracranial Volume"]),
                                html.Div([html.Strong("MMSE"), " — Mini-Mental State Examination"]),
                                html.Div([html.Strong("CDR"), " — Clinical Dementia Rating"]),
                                html.Div([html.Strong("SES"), " — Socioeconomic Status"]),
                                html.Div([
                                    html.Strong("Years from Baseline"),
                                    " — derived as MR Delay ÷ 365.25 to represent actual elapsed time since baseline",
                                ]),
                                html.Div([
                                    html.Strong("Converted"),
                                    " — participants initially nondemented who were later classified as demented during follow-up",
                                ]),
                            ],
                            className="definition-grid",
                        ),
                    ],
                    className="measure-help",
                ),
            ],
        ),

        html.Div(
            id="active-filter-summary",
            className="active-filter-summary",
        ),

        html.Div(
            id="cohort-summary-statistics",
            className="cohort-summary-statistics",
        ),

        html.Section(
            className="filter-panel",
            children=[
                filter_card(
                    "Diagnostic group",
                    dcc.Checklist(
                        id="group-filter",
                        options=[
                            {
                                "label": group,
                                "value": group,
                            }
                            for group in GROUP_ORDER
                        ],
                        value=GROUP_ORDER,
                        inline=True,
                        className="inline-checklist",
                    ),
                ),

                filter_card(
                    "Sex",
                    dcc.Checklist(
                        id="sex-filter",
                        options=[
                            {"label": "Female", "value": "F"},
                            {"label": "Male", "value": "M"},
                        ],
                        value=["F", "M"],
                        inline=True,
                        className="inline-checklist",
                    ),
                ),

                filter_card(
                    "Age range",
                    dcc.RangeSlider(
                        id="age-filter",
                        min=AGE_MIN,
                        max=AGE_MAX,
                        value=[AGE_MIN, AGE_MAX],
                        marks={
                            AGE_MIN: str(AGE_MIN),
                            AGE_MAX: str(AGE_MAX),
                        },
                        tooltip={
                            "placement": "bottom",
                            "always_visible": False,
                        },
                    ),
                ),

                filter_card(
                    "Visit range",
                    dcc.RangeSlider(
                        id="visit-filter",
                        min=VISIT_MIN,
                        max=VISIT_MAX,
                        step=1,
                        value=[VISIT_MIN, VISIT_MAX],
                        marks={
                            visit: str(visit)
                            for visit in range(
                                VISIT_MIN,
                                VISIT_MAX + 1,
                            )
                        },
                        tooltip={
                            "placement": "bottom",
                            "always_visible": False,
                        },
                    ),
                ),

                filter_card(
                    "Education range",
                    dcc.RangeSlider(
                        id="education-filter",
                        min=EDUC_MIN,
                        max=EDUC_MAX,
                        value=[EDUC_MIN, EDUC_MAX],
                        marks={
                            EDUC_MIN: str(EDUC_MIN),
                            EDUC_MAX: str(EDUC_MAX),
                        },
                        tooltip={
                            "placement": "bottom",
                            "always_visible": False,
                        },
                    ),
                ),

                html.Div(
                    className="filter-item",
                    children=[
                        html.Div(
                            "SES",
                            className="filter-label",
                        ),
                        dcc.Dropdown(
                            id="ses-filter",
                            options=SES_OPTIONS,
                            value=ALL_SES_VALUES,
                            multi=True,
                            clearable=False,
                        ),
                        html.Div(
                            id="ses-note",
                            className="filter-note",
                        ),
                    ],
                ),

                html.Div(
                    [
                        html.Button(
                            "Reset dashboard",
                            id="reset-filters",
                            n_clicks=0,
                            className="reset-button",
                        )
                    ],
                    className="filter-action",
                ),
            ],
        ),

        html.Section(
            className="status-row status-row-streamlined",
            children=[
                html.Div(
                    [
                        html.Div(
                            "Scatter observations",
                            className="control-caption",
                        ),
                        dcc.RadioItems(
                            id="scatter-mode",
                            options=[
                                {
                                    "label": "All visits",
                                    "value": "all",
                                },
                                {
                                    "label": "Baseline only",
                                    "value": "baseline",
                                },
                            ],
                            value="all",
                            inline=True,
                        ),
                    ],
                    className="status-card status-control scatter-control",
                ),
                html.Div(
                    [
                        html.Div(
                            className="subject-control-header",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            "Selected subjects (max 5)",
                                            className="control-caption",
                                        ),
                                        html.Div(
                                            "Click/lasso marks to link views",
                                            className="linked-caption",
                                        ),
                                    ]
                                ),
                                html.Button(
                                    "Clear selection",
                                    id="clear-selection",
                                    n_clicks=0,
                                    className="clear-selection-button",
                                ),
                            ],
                        ),
                        dcc.Dropdown(
                            id="subject-selector",
                            options=SUBJECT_OPTIONS,
                            value=[],
                            multi=True,
                            placeholder=(
                                "Click/lasso the scatterplot or choose subjects"
                            ),
                        ),
                    ],
                    className="status-card subject-control",
                ),
            ],
        ),

        html.Div(
            id="comparison-state-strip",
            className="comparison-state-strip",
        ),

        html.Div(
            className="interaction-row",
            children=[
                html.Div(
                    id="interaction-message",
                    className="interaction-message",
                ),
                html.Div(
                    "Drag a box to select subjects; use the toolbar for lasso selection.",
                    className="brush-hint",
                ),
            ],
        ),

        html.Div(
            className="trajectory-focus-bar",
            children=[
                html.Div(
                    [
                        html.Div(
                            "Trajectory focus",
                            className="panel-label",
                        ),
                        html.Div(
                            (
                                "Use this control to reliably isolate one "
                                "selected subject or restore all selected subjects."
                            ),
                            className="trajectory-focus-help",
                        ),
                    ]
                ),
                dcc.Dropdown(
                    id="trajectory-focus-subject",
                    options=[
                        {
                            "label": "All selected subjects",
                            "value": "__all__",
                        }
                    ],
                    value="__all__",
                    clearable=False,
                    className="trajectory-focus-dropdown",
                ),
            ],
        ),

        html.Main(
            className="dashboard-grid",
            children=[
                html.Section(
                    className="panel panel-wide",
                    children=[
                        dcc.Graph(
                            id="cohort-scatter",
                            config={
                                "displaylogo": False,
                                "scrollZoom": True,
                                "modeBarButtonsToAdd": [
                                    "select2d",
                                    "lasso2d",
                                ],
                            },
                        ),
                    ],
                ),

                html.Section(
                    className="panel",
                    children=[
                        dcc.Graph(
                            id="nwbv-trajectory",
                            config={
                                "displaylogo": False,
                            },
                        ),
                    ],
                ),

                html.Section(
                    className="panel",
                    children=[
                        html.Div(
                            className="panel-toolbar",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            "Group distribution",
                                            className="panel-label",
                                        ),
                                        dcc.RadioItems(
                                            id="distribution-grouping",
                                            options=[
                                                {
                                                    "label": "Diagnostic group",
                                                    "value": "diagnostic",
                                                },
                                                {
                                                    "label": "Selected vs remaining filtered cohort",
                                                    "value": "selection",
                                                },
                                            ],
                                            value="diagnostic",
                                            inline=True,
                                            className="distribution-grouping",
                                        ),
                                        html.Div(
                                            "Remaining cohort always respects the active global filters.",
                                            className="distribution-help",
                                        ),
                                    ]
                                ),
                                dcc.Dropdown(
                                    id="distribution-metric",
                                    options=[
                                        {
                                            "label": "nWBV",
                                            "value": "nWBV",
                                        },
                                        {
                                            "label": "MMSE",
                                            "value": "MMSE",
                                        },
                                        {
                                            "label": "ΔnWBV",
                                            "value": "Delta_nWBV",
                                        },
                                        {
                                            "label": "ΔMMSE",
                                            "value": "Delta_MMSE",
                                        },
                                        {
                                            "label": "eTIV",
                                            "value": "eTIV",
                                        },
                                    ],
                                    value="nWBV",
                                    clearable=False,
                                    className="metric-dropdown",
                                ),
                            ],
                        ),
                        dcc.Graph(
                            id="group-distribution",
                            config={
                                "displaylogo": False,
                                "scrollZoom": True,
                                "modeBarButtonsToAdd": [
                                    "select2d",
                                    "lasso2d",
                                ],
                            },
                        ),
                    ],
                ),

                html.Section(
                    className="panel",
                    children=[
                        dcc.Graph(
                            id="mmse-trajectory",
                            config={
                                "displaylogo": False,
                            },
                        ),
                    ],
                ),

                html.Section(
                    className="panel",
                    children=[
                        dcc.Graph(
                            id="cdr-trajectory",
                            config={
                                "displaylogo": False,
                            },
                        ),
                    ],
                ),

                html.Section(
                    className="panel panel-full",
                    children=[
                        html.Div(
                            className="details-header",
                            children=[
                                html.Div(
                                    "Selected subject / visit details",
                                    className="panel-label",
                                ),
                                html.Div(
                                    id="selection-note",
                                    className="selection-note",
                                ),
                            ],
                        ),
                        dash_table.DataTable(
                            id="details-table",
                            columns=[
                                {
                                    "name": {
                                        "Subject ID": "Subject ID",
                                        "MRI ID": "MRI ID",
                                        "Group": "Group",
                                        "Visit": "Visit",
                                        "YearsFromBaseline": "Years from baseline",
                                        "Age": "Age",
                                        "M/F": "Sex",
                                        "EDUC": "EDUC",
                                        "SES": "SES",
                                        "MMSE": "MMSE",
                                        "CDR": "CDR",
                                        "nWBV": "nWBV",
                                        "Delta_nWBV": "ΔnWBV",
                                        "Delta_MMSE": "ΔMMSE",
                                        "eTIV": "eTIV",
                                    }.get(column, column),
                                    "id": column,
                                }
                                for column in DETAIL_COLUMNS
                            ],
                            data=[],
                            page_size=10,
                            sort_action="native",
                            filter_action="native",
                            style_table={
                                "overflowX": "auto",
                            },
                            style_cell={
                                "fontFamily": (
                                    "Inter, system-ui, sans-serif"
                                ),
                                "fontSize": 12,
                                "padding": "8px",
                                "textAlign": "left",
                                "whiteSpace": "nowrap",
                            },
                            style_header={
                                "fontWeight": "700",
                            },
                            style_data_conditional=[
                                {
                                    "if": {
                                        "filter_query": "{Subject ID} != ''",
                                    },
                                    "backgroundColor": "#ffffff",
                                },
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# =========================================================
# CALLBACKS
# =========================================================

@callback(
    Output("group-filter", "value"),
    Output("sex-filter", "value"),
    Output("age-filter", "value"),
    Output("visit-filter", "value"),
    Output("education-filter", "value"),
    Output("ses-filter", "value"),
    Output("scatter-mode", "value"),
    Output("distribution-metric", "value"),
    Output("distribution-grouping", "value"),
    Input("reset-filters", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    """Restore the dashboard's presentation-safe default analytical state."""
    return (
        GROUP_ORDER,
        ["F", "M"],
        [AGE_MIN, AGE_MAX],
        [VISIT_MIN, VISIT_MAX],
        [EDUC_MIN, EDUC_MAX],
        ALL_SES_VALUES,
        "all",
        "nWBV",
        "diagnostic",
    )


@callback(
    Output("subject-selector", "options"),
    Input("group-filter", "value"),
    Input("sex-filter", "value"),
    Input("age-filter", "value"),
    Input("visit-filter", "value"),
    Input("education-filter", "value"),
    Input("ses-filter", "value"),
    Input("subject-selector", "value"),
)
def update_subject_options(
    groups,
    sexes,
    age_range,
    visit_range,
    education_range,
    ses_values,
    selected_subjects,
):
    """
    Restrict the manual subject selector to the filtered cohort.

    When five subjects are already selected, all other subject
    options are disabled. Existing selected subjects remain enabled
    so the user can remove them.
    """
    filtered = apply_filters(
        df,
        groups,
        sexes,
        age_range,
        education_range,
        ses_values,
        visit_range,
    )

    subjects = subjects_surviving_filters(
        filtered
    )

    selected_subjects = selected_subjects or []
    selected_set = set(selected_subjects)

    cap_reached = (
        len(selected_set) >= MAX_SELECTED_SUBJECTS
    )

    return [
        {
            "label": (
                f"{subject_id} — "
                f"{df.loc[df['Subject ID'] == subject_id, 'Group'].iloc[0]}"
            ),
            "value": subject_id,
            "disabled": (
                cap_reached
                and subject_id not in selected_set
            ),
        }
        for subject_id in subjects
    ]


@callback(
    Output("subject-selector", "value"),
    Output("interaction-message-store", "data"),
    Input("cohort-scatter", "selectedData"),
    Input("cohort-scatter", "clickData"),
    Input("group-distribution", "selectedData"),
    Input("group-distribution", "clickData"),
    Input("clear-selection", "n_clicks"),
    Input("group-filter", "value"),
    Input("sex-filter", "value"),
    Input("age-filter", "value"),
    Input("visit-filter", "value"),
    Input("education-filter", "value"),
    Input("ses-filter", "value"),
    Input("reset-filters", "n_clicks"),
    State("subject-selector", "value"),
    prevent_initial_call=True,
)
def update_subject_selection(
    scatter_selected,
    scatter_clicked,
    distribution_selected,
    distribution_clicked,
    clear_clicks,
    groups,
    sexes,
    age_range,
    visit_range,
    education_range,
    ses_values,
    reset_clicks,
    current_selection,
):
    """
    Stable linked selection.

    Plotly may emit selectedData=None or selectedData={"points": []}
    when a graph redraws after a valid brush selection. Those reset
    events are ignored so linked trajectories do not disappear.
    """

    current_selection = current_selection or []

    trigger = (
        ctx.triggered[0]["prop_id"]
        if ctx.triggered
        else ""
    )

    filtered = apply_filters(
        df,
        groups,
        sexes,
        age_range,
        education_range,
        ses_values,
        visit_range,
    )

    allowed_subjects = set(
        filtered["Subject ID"].unique()
    )

    def clean_subjects(subjects):
        cleaned = []

        for subject_id in subjects or []:
            if (
                subject_id in allowed_subjects
                and subject_id not in cleaned
            ):
                cleaned.append(subject_id)

        return cleaned[:MAX_SELECTED_SUBJECTS]

    def subject_ids_from_points(payload):
        if (
            not payload
            or not payload.get("points")
        ):
            return None, False

        subject_ids = []

        for point in payload["points"]:
            customdata = point.get("customdata")

            if not customdata:
                continue

            subject_id = customdata[0]

            if (
                subject_id in allowed_subjects
                and subject_id not in subject_ids
            ):
                subject_ids.append(subject_id)

        if not subject_ids:
            return None, False

        truncated = (
            len(subject_ids) > MAX_SELECTED_SUBJECTS
        )

        return (
            subject_ids[:MAX_SELECTED_SUBJECTS],
            truncated,
        )

    if trigger == "reset-filters.n_clicks":
        return [], "Dashboard reset to the full cohort."

    if trigger == "clear-selection.n_clicks":
        return [], "Selection cleared."

    if trigger == "cohort-scatter.selectedData":
        subject_ids, truncated = subject_ids_from_points(
            scatter_selected
        )

        if subject_ids is None:
            return no_update, no_update

        message = (
            "Selection truncated to first 5 subjects."
            if truncated
            else (
                f"{len(subject_ids)} subject"
                f"{'s' if len(subject_ids) != 1 else ''} "
                "selected from scatter."
            )
        )

        return subject_ids, message

    if trigger == "group-distribution.selectedData":
        subject_ids, truncated = subject_ids_from_points(
            distribution_selected
        )

        if subject_ids is None:
            return no_update, no_update

        message = (
            "Selection truncated to first 5 subjects."
            if truncated
            else (
                f"{len(subject_ids)} subject"
                f"{'s' if len(subject_ids) != 1 else ''} "
                "selected from distribution."
            )
        )

        return subject_ids, message

    click_payload = None
    source_name = None

    if trigger == "cohort-scatter.clickData":
        click_payload = scatter_clicked
        source_name = "scatter"
    elif trigger == "group-distribution.clickData":
        click_payload = distribution_clicked
        source_name = "distribution"

    if click_payload and click_payload.get("points"):
        customdata = click_payload["points"][0].get("customdata")

        if customdata:
            subject_id = customdata[0]

            # Distribution-summary hover hotspots are not subjects.
            if not isinstance(subject_id, str):
                return no_update, no_update

            updated = clean_subjects(current_selection)

            if subject_id in updated:
                updated = [
                    value
                    for value in updated
                    if value != subject_id
                ]
                return (
                    updated,
                    f"{subject_id} removed from selection.",
                )

            if subject_id not in allowed_subjects:
                return (
                    no_update,
                    "That subject is outside the active global filter.",
                )

            if len(updated) >= MAX_SELECTED_SUBJECTS:
                return (
                    no_update,
                    "Maximum of 5 selected subjects reached.",
                )

            updated.append(subject_id)

            return (
                updated,
                f"{subject_id} selected from {source_name}.",
            )

    pruned = clean_subjects(current_selection)

    if pruned != current_selection:
        removed = [
            subject_id
            for subject_id in current_selection
            if subject_id not in pruned
        ]

        return (
            pruned,
            (
                "Filters removed from selection: "
                + ", ".join(removed)
            ),
        )

    return no_update, no_update


@callback(
    Output("active-filter-summary", "children"),
    Input("group-filter", "value"),
    Input("sex-filter", "value"),
    Input("age-filter", "value"),
    Input("visit-filter", "value"),
    Input("education-filter", "value"),
    Input("ses-filter", "value"),
)
def update_active_filter_summary(
    groups,
    sexes,
    age_range,
    visit_range,
    education_range,
    ses_values,
):
    filtered = apply_filters(
        df,
        groups,
        sexes,
        age_range,
        education_range,
        ses_values,
        visit_range,
    )

    group_text = (
        "All diagnoses"
        if set(groups or []) == set(GROUP_ORDER)
        else ", ".join(groups or []) or "No diagnoses"
    )

    sex_set = set(sexes or [])
    if sex_set == {"F", "M"}:
        sex_text = "All sexes"
    elif sex_set == {"F"}:
        sex_text = "Female"
    elif sex_set == {"M"}:
        sex_text = "Male"
    else:
        sex_text = "No sex selected"

    unknown_ses = "Unknown SES included" if "Unknown" in (ses_values or []) else "Unknown SES excluded"

    return html.Div(
        [
            html.Strong("Active filters: "),
            html.Span(
                f"{group_text} · {sex_text} · Age {age_range[0]}–{age_range[1]} · "
                f"Visits {visit_range[0]}–{visit_range[1]} · EDUC {education_range[0]}–{education_range[1]} · "
                f"{unknown_ses}"
            ),
        ]
    )


@callback(
    Output("cohort-summary-statistics", "children"),
    Input("group-filter", "value"),
    Input("sex-filter", "value"),
    Input("age-filter", "value"),
    Input("visit-filter", "value"),
    Input("education-filter", "value"),
    Input("ses-filter", "value"),
)
def update_cohort_summary_statistics(
    groups,
    sexes,
    age_range,
    visit_range,
    education_range,
    ses_values,
):
    filtered = apply_filters(
        df,
        groups,
        sexes,
        age_range,
        education_range,
        ses_values,
        visit_range,
    )

    subject_count = int(
        filtered["Subject ID"].nunique()
    )
    visit_count = int(len(filtered))

    subject_groups = (
        filtered[
            ["Subject ID", "Group"]
        ]
        .drop_duplicates(
            subset=["Subject ID"]
        )
    )

    group_counts = {
        group: int(
            (
                subject_groups["Group"] == group
            ).sum()
        )
        for group in GROUP_ORDER
    }

    def format_median(column, decimals=1):
        values = filtered[column].dropna()

        if values.empty:
            return "—"

        median_value = float(values.median())
        return f"{median_value:.{decimals}f}"

    metrics = [
        (
            "Subjects",
            f"{subject_count:,}",
            "Unique participants",
        ),
        (
            "Visit records",
            f"{visit_count:,}",
            "Filtered observations",
        ),
        (
            "Median nWBV",
            format_median("nWBV", 3),
            "Across filtered visits",
        ),
        (
            "Median MMSE",
            format_median("MMSE", 1),
            "Across filtered visits",
        ),
        (
            "Median age",
            format_median("Age", 1),
            "Years · filtered visits",
        ),
        (
            "Nondemented",
            f"{group_counts.get('Nondemented', 0):,}",
            "Unique subjects",
        ),
        (
            "Converted",
            f"{group_counts.get('Converted', 0):,}",
            "Unique subjects",
        ),
        (
            "Demented",
            f"{group_counts.get('Demented', 0):,}",
            "Unique subjects",
        ),
    ]

    return [
        html.Div(
            [
                html.Div(
                    label,
                    className="summary-stat-label",
                ),
                html.Div(
                    value,
                    className="summary-stat-value",
                ),
                html.Div(
                    note,
                    className="summary-stat-note",
                ),
            ],
            className="summary-stat-card",
        )
        for label, value, note in metrics
    ]


@callback(
    Output("ses-note", "children"),
    Input("ses-filter", "value"),
)
def update_ses_note(ses_values):
    ses_values = ses_values or []

    if "Unknown" in ses_values:
        return "Unknown SES included in cohort"

    return "Unknown SES excluded from cohort"


@callback(
    Output("comparison-state-strip", "children"),
    Input("group-filter", "value"),
    Input("sex-filter", "value"),
    Input("age-filter", "value"),
    Input("visit-filter", "value"),
    Input("education-filter", "value"),
    Input("ses-filter", "value"),
    Input("subject-selector", "value"),
)
def update_comparison_state_strip(
    groups,
    sexes,
    age_range,
    visit_range,
    education_range,
    ses_values,
    selected_subjects,
):
    filtered = apply_filters(
        df,
        groups,
        sexes,
        age_range,
        education_range,
        ses_values,
        visit_range,
    )

    full_count = df["Subject ID"].nunique()
    filtered_ids = set(
        filtered["Subject ID"].unique()
    )
    filtered_count = len(filtered_ids)

    valid_selected = [
        subject_id
        for subject_id in (selected_subjects or [])
        if subject_id in filtered_ids
    ]

    selected_count = len(valid_selected)
    remaining_count = max(
        filtered_count - selected_count,
        0,
    )

    return [
        html.Div(
            [
                html.Div(
                    "Full cohort",
                    className="state-label",
                ),
                html.Div(
                    f"{full_count} subjects",
                    className="state-value",
                ),
                html.Div(
                    "Reference context",
                    className="state-role",
                ),
            ],
            className="state-card state-full",
        ),

        html.Div(
            "→",
            className="state-arrow",
        ),

        html.Div(
            [
                html.Div(
                    "Filtered cohort",
                    className="state-label",
                ),
                html.Div(
                    f"{filtered_count} subjects",
                    className="state-value",
                ),
                html.Div(
                    "Active population",
                    className="state-role",
                ),
            ],
            className="state-card state-filtered",
        ),

        html.Div(
            "→",
            className="state-arrow",
        ),

        html.Div(
            [
                html.Div(
                    "Selected subjects",
                    className="state-label",
                ),
                html.Div(
                    f"{selected_count} subjects",
                    className="state-value",
                ),
                html.Div(
                    (
                        f"{remaining_count} remaining"
                        if selected_count
                        else "None selected"
                    ),
                    className="state-role",
                ),
            ],
            className="state-card state-selected",
        ),
    ]


@callback(
    Output("trajectory-focus-subject", "options"),
    Output("trajectory-focus-subject", "value"),
    Input("subject-selector", "value"),
    State("trajectory-focus-subject", "value"),
)
def update_trajectory_focus_options(
    selected_subjects,
    current_focus,
):
    selected_subjects = selected_subjects or []

    options = [
        {
            "label": "All selected subjects",
            "value": "__all__",
        }
    ]

    options.extend(
        {
            "label": subject_id,
            "value": subject_id,
        }
        for subject_id in selected_subjects
    )

    if (
        current_focus != "__all__"
        and current_focus in selected_subjects
    ):
        return options, current_focus

    return options, "__all__"


@callback(
    Output("interaction-message", "children"),
    Input("interaction-message-store", "data"),
)
def show_interaction_message(message):
    if not message:
        return ""

    return message


@callback(
    Output("cohort-scatter", "figure"),
    Output("nwbv-trajectory", "figure"),
    Output("mmse-trajectory", "figure"),
    Output("cdr-trajectory", "figure"),
    Output("group-distribution", "figure"),
    Output("details-table", "data"),
    Output("selection-note", "children"),
    Input("group-filter", "value"),
    Input("sex-filter", "value"),
    Input("age-filter", "value"),
    Input("visit-filter", "value"),
    Input("education-filter", "value"),
    Input("ses-filter", "value"),
    Input("scatter-mode", "value"),
    Input("distribution-metric", "value"),
    Input("distribution-grouping", "value"),
    Input("subject-selector", "value"),
    Input("trajectory-focus-subject", "value"),
)
def update_dashboard(
    groups,
    sexes,
    age_range,
    visit_range,
    education_range,
    ses_values,
    scatter_mode,
    distribution_metric,
    distribution_grouping,
    selected_subjects,
    trajectory_focus_subject,
):
    filtered = apply_filters(
        df,
        groups,
        sexes,
        age_range,
        education_range,
        ses_values,
        visit_range,
    )

    selected_subjects = (
        selected_subjects or []
    )[:MAX_SELECTED_SUBJECTS]

    cohort_revision = (
        f"{len(filtered)}-"
        f"{filtered['Subject ID'].nunique()}-"
        f"{'-'.join(sorted(filtered['Subject ID'].unique())[:8])}"
    )

    surviving_subjects = set(
        filtered["Subject ID"].unique()
    )

    selected_subjects = [
        subject
        for subject in selected_subjects
        if subject in surviving_subjects
    ]

    scatter = create_age_nwbv_scatter(
        filtered,
        observation_mode=scatter_mode,
        selected_subjects=selected_subjects,
        cohort_revision=cohort_revision,
        full_visits=df,
    )

    # Step 5 global-filter semantics:
    # all linked subject views use only rows that survive
    # the active global filters, including Visit range.
    selected_history = filtered[
        filtered["Subject ID"].isin(selected_subjects)
    ].copy()

    if (
        trajectory_focus_subject
        and trajectory_focus_subject != "__all__"
        and trajectory_focus_subject in selected_subjects
    ):
        trajectory_subjects = [
            trajectory_focus_subject
        ]
    else:
        trajectory_subjects = selected_subjects

    nwbv_fig = create_subject_trajectory(
        selected_history,
        trajectory_subjects,
        "nWBV",
    )

    mmse_fig = create_subject_trajectory(
        selected_history,
        trajectory_subjects,
        "MMSE",
    )

    cdr_fig = create_subject_trajectory(
        selected_history,
        trajectory_subjects,
        "CDR",
    )

    distribution_fig = create_group_distribution(
        filtered,
        distribution_metric,
        selected_subjects=selected_subjects,
        cohort_revision=cohort_revision,
        grouping_mode=distribution_grouping,
    )

    records = make_details_records(
        selected_history,
        selected_subjects,
    )

    if selected_subjects:
        if len(selected_subjects) >= MAX_SELECTED_SUBJECTS:
            selection_note = (
                "Linked selection — 5 selected (maximum): "
                + ", ".join(selected_subjects)
            )
        else:
            selection_note = (
                f"Linked selection — {len(selected_subjects)} selected: "
                + ", ".join(selected_subjects)
            )
    else:
        selection_note = (
            "Linked selection — no subjects selected."
        )

    return (
        scatter,
        nwbv_fig,
        mmse_fig,
        cdr_fig,
        distribution_fig,
        records,
        selection_note,
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=False)
