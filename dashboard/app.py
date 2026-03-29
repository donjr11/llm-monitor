# dashboard/app.py
# Plotly Dash dashboard using dash-bootstrap-components
# Professional dark theme with Bootstrap layout

import dash
from dash import dcc, html, dash_table, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import requests

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

API_BASE    = "http://127.0.0.1:8000"
API_TIMEOUT = 8

PROFILE_OPTIONS = [
    {"label": "💻 Coding / Dev",         "value": "coding"},
    {"label": "🧠 Reasoning / Analysis", "value": "reasoning"},
    {"label": "📄 RAG Long Context",      "value": "rag_long_context"},
    {"label": "💰 Minimum Cost",          "value": "minimum_cost"},
    {"label": "🤖 Enterprise Agents",     "value": "enterprise_agents"},
]

# ─────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────

def fetch_models():
    try:
        r = requests.get(f"{API_BASE}/models", timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json().get("models", [])
    except Exception as e:
        print(f"[ERROR] fetch_models: {e}")
        return []


def fetch_new_models():
    try:
        r = requests.get(f"{API_BASE}/models/new", timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json().get("models", [])
    except Exception:
        return []


def fetch_recommendation(profile, commercial=False, method="ahp_topsis", top_n=5):
    try:
        r = requests.get(
            f"{API_BASE}/recommend",
            params={"profile": profile, "commercial": str(commercial).lower(),
                    "method": method, "top_n": top_n},
            timeout=API_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] fetch_recommendation: {e}")
        return {}


def get_best_value_models(models):
    result = []
    for m in models:
        intel = m.get("intelligence_score") or 0
        price = m.get("price_input") or 0
        if intel > 75 and 0 < price < 0.5:
            result.append({
                "name":         m.get("name", ""),
                "provider":     m.get("provider", ""),
                "intelligence": intel,
                "price":        price,
                "ratio":        round(intel / (price + 0.001), 1),
            })
    return sorted(result, key=lambda x: x["ratio"], reverse=True)[:5]


# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG, dbc.icons.BOOTSTRAP],
    title="LLM Monitor — Epineon AI",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# ─────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────

app.layout = dbc.Container(
    fluid=True,
    style={"padding": "0"},
    children=[

        # ── NAVBAR ──
        dbc.Navbar(
            dbc.Container([
                html.A(
                    dbc.Row([
                        dbc.Col(html.Span("🔭", style={"fontSize": "1.4rem"})),
                        dbc.Col(dbc.NavbarBrand(
                            "LLM Monitoring System",
                            style={"fontWeight": "700", "fontSize": "1.1rem"},
                        )),
                    ], align="center", className="g-2"),
                    href="#", style={"textDecoration": "none"},
                ),
                dbc.Row([
                    dbc.Col(html.Div(id="nav-stats")),
                ], align="center"),
            ]),
            color="dark", dark=True,
            style={"borderBottom": "1px solid #2a2d3e", "padding": "0 16px"},
        ),

        # ── BODY ──
        dbc.Container(
            style={"padding": "28px 16px", "maxWidth": "1400px"},
            children=[

                # ── PAGE TITLE ──
                dbc.Row(dbc.Col(html.Div([
                    html.H1("Enterprise LLM Intelligence Dashboard",
                            className="h3 fw-bold mb-1"),
                    html.P(
                        "AHP+TOPSIS scoring · 3 data sources · Real-time recommendations",
                        className="text-muted small",
                    ),
                ]), className="mb-4")),

                # ── STATS CARDS ──
                html.Div(id="stats-cards", className="mb-4"),

                # ── NEW MODELS + BEST VALUE ──
                dbc.Row([
                    dbc.Col(html.Div(id="new-models-banner"), md=6),
                    dbc.Col(html.Div(id="best-value-section"), md=6),
                ], className="mb-4"),

                # ── CONTROLS ──
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label(
                                    "Enterprise Profile",
                                    className="text-muted small fw-bold text-uppercase mb-2",
                                ),
                                dcc.Dropdown(
                                    id="profile-dropdown",
                                    options=PROFILE_OPTIONS,
                                    value="coding",
                                    clearable=False,
                                    style={"color": "#000"},
                                ),
                            ], md=3),
                            dbc.Col([
                                html.Label(
                                    "Scoring Method",
                                    className="text-muted small fw-bold text-uppercase mb-2",
                                ),
                                dbc.RadioItems(
                                    id="method-selector",
                                    options=[
                                        {"label": " AHP + TOPSIS (derived weights)",
                                         "value": "ahp_topsis"},
                                        {"label": " TOPSIS (manual weights)",
                                         "value": "topsis"},
                                    ],
                                    value="ahp_topsis",
                                    inline=False,
                                ),
                            ], md=4),
                            dbc.Col([
                                html.Label(
                                    "License Filter",
                                    className="text-muted small fw-bold text-uppercase mb-2",
                                ),
                                dbc.Checklist(
                                    id="commercial-filter",
                                    options=[{"label": " Commercial use only",
                                              "value": "commercial"}],
                                    value=[],
                                ),
                            ], md=3),
                        ], align="center"),
                        # Method badge on its own row below
                        dbc.Row([
                            dbc.Col(
                                html.Div(id="method-badge", className="mt-3"),
                                md=12,
                            ),
                        ]),
                    ]),
                    className="mb-4",
                ),

                # ── GENERATE REPORT ──
                dbc.Row(
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dbc.Row([
                                    dbc.Col(
                                        html.Div([
                                            html.Span("📄 ", style={"fontSize": "1.1rem"}),
                                            html.Strong("Digest Report"),
                                            html.Span(
                                                " — Snapshot current rankings and movements to a Markdown file",
                                                className="text-muted small ms-1",
                                            ),
                                        ]),
                                        className="d-flex align-items-center",
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "📄 Generate Markdown Report",
                                            id="generate-report-btn",
                                            color="primary",
                                            outline=True,
                                            size="sm",
                                            n_clicks=0,
                                            className="float-end",
                                        ),
                                        className="d-flex justify-content-end align-items-center",
                                        xs=12, md=4,
                                    ),
                                ], align="center"),
                                className="py-2",
                            ),
                        ),
                        className="mb-2",
                    ),
                ),
                html.Div(id="report-output", className="mb-4"),

                # ── TOP 5 CARDS ──
                dbc.Row(dbc.Col([
                    html.H5("🏆 Top 5 Recommendations", className="fw-bold mb-3"),
                    html.Div(id="recommendation-cards"),
                ]), className="mb-4"),

                # ── CHARTS ROW ──
                dbc.Row([
                    dbc.Col(
                        dbc.Card(dbc.CardBody([
                            html.H6("📊 TOPSIS Score Ranking",
                                    className="fw-bold mb-1"),
                            html.P("Top 15 models by selected profile",
                                   className="text-muted small mb-2"),
                            dcc.Graph(id="score-chart",
                                      config={"displayModeBar": False}),
                        ])),
                        md=6, className="mb-4",
                    ),
                    dbc.Col(
                        dbc.Card(dbc.CardBody([
                            html.H6("💡 Intelligence vs Cost",
                                    className="fw-bold mb-1"),
                            html.P("Bubble size = context window · Color = source",
                                   className="text-muted small mb-2"),
                            dcc.Graph(id="scatter-chart",
                                      config={"displayModeBar": False}),
                        ])),
                        md=6, className="mb-4",
                    ),
                ]),

                # ── LEADERBOARD ──
                dbc.Card(
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.H5("📋 Full Model Leaderboard",
                                        className="fw-bold mb-0"),
                                html.P("Sortable · Filterable · All sources",
                                       className="text-muted small"),
                            ], md=6),
                            dbc.Col(
                                dbc.Row([
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="source-filter",
                                            options=[
                                                {"label": "All Sources",         "value": "all"},
                                                {"label": "HuggingFace",         "value": "huggingface"},
                                                {"label": "Artificial Analysis", "value": "artificial_analysis"},
                                                {"label": "LLM Stats",           "value": "llm_stats"},
                                            ],
                                            value="all", clearable=False,
                                            style={"color": "#000"},
                                        ), md=6,
                                    ),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="license-filter",
                                            options=[
                                                {"label": "All Licenses", "value": "all"},
                                                {"label": "Apache",       "value": "apache"},
                                                {"label": "MIT",          "value": "mit"},
                                                {"label": "Proprietary",  "value": "proprietary"},
                                            ],
                                            value="all", clearable=False,
                                            style={"color": "#000"},
                                        ), md=6,
                                    ),
                                ]),
                                md=6,
                            ),
                        ], className="mb-3", align="center"),
                        html.Div(id="leaderboard-table"),
                    ]),
                    className="mb-4",
                ),

                # ── FOOTER ──
                html.Hr(),
                html.P(
                    "LLM Monitoring System v1.0 · Epineon AI PFE 2026 · "
                    "AHP+TOPSIS (MCDM) · Sources: HuggingFace, Artificial Analysis, LLM Stats",
                    className="text-muted text-center small py-2",
                ),
            ],
        ),

        dcc.Interval(id="interval", interval=60_000, n_intervals=0),
    ],
)


# ─────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────

@callback(
    Output("nav-stats", "children"),
    Input("interval", "n_intervals"),
)
def update_nav(_):
    models    = fetch_models()
    new_count = len(fetch_new_models())
    return dbc.Row([
        dbc.Col(html.Span(f"🗄️ {len(models)} Models",
                          className="text-info small fw-bold")),
        dbc.Col(html.Span(f"🆕 {new_count} New",
                          className="text-success small fw-bold")),
        dbc.Col(html.Span("● LIVE",
                          className="text-success small fw-bold")),
    ], className="g-3")


@callback(
    Output("stats-cards", "children"),
    Input("interval", "n_intervals"),
)
def update_stats(_):
    models    = fetch_models()
    new_count = len(fetch_new_models())
    sources   = {}
    providers = set()
    for m in models:
        sources[m.get("source", "")] = sources.get(m.get("source", ""), 0) + 1
        if m.get("provider"):
            providers.add(m["provider"])

    cards_data = [
        ("🗄️", "Total Models",    str(len(models)),                          "primary"),
        ("🆕", "New This Run",    str(new_count),                             "success"),
        ("🏢", "Providers",       str(len(providers)),                        "info"),
        ("📡", "HuggingFace",     str(sources.get("huggingface", 0)),         "primary"),
        ("🔬", "Artif. Analysis", str(sources.get("artificial_analysis", 0)), "warning"),
        ("📈", "LLM Stats",       str(sources.get("llm_stats", 0)),           "secondary"),
    ]

    cols = []
    for icon, label, value, color in cards_data:
        cols.append(
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div(icon, style={"fontSize": "1.5rem",
                                              "marginBottom": "4px"}),
                        html.H3(value, className=f"text-{color} fw-bold mb-0"),
                        html.P(label, className="text-muted small mb-0"),
                    ], className="text-center py-3"),
                ], className=f"border-{color} border-top border-3"),
                xs=6, sm=4, md=2, className="mb-3",
            )
        )

    return dbc.Row(cols)


@callback(
    Output("new-models-banner", "children"),
    Input("interval", "n_intervals"),
)
def update_new_models(_):
    new_models = fetch_new_models()
    if not new_models:
        return html.Div()

    badges = [
        dbc.Badge(
            f"✨ {m['name']}",
            color="success", pill=True,
            className="me-1 mb-1",
            style={"fontSize": "0.75rem"},
        )
        for m in new_models[:10]
    ]

    return dbc.Card(
        dbc.CardBody([
            html.H6(f"🆕 {len(new_models)} New Models Detected",
                    className="text-success fw-bold mb-2"),
            html.Div(badges),
        ]),
        className="border-success border-start border-4 mb-0 h-100",
    )


@callback(
    Output("best-value-section", "children"),
    Input("interval", "n_intervals"),
)
def update_best_value(_):
    models = fetch_models()
    if not models:
        return html.Div()

    best = get_best_value_models(models)
    if not best:
        return html.Div()

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    rows = []
    for i, m in enumerate(best):
        rows.append(
            html.Tr([
                html.Td(medals[i] if i < len(medals) else "",
                        className="small"),
                html.Td(m["name"],  className="small fw-bold"),
                html.Td(f"{m['intelligence']:.0f}",
                        className="small text-info text-center"),
                html.Td(f"${m['price']:.3f}",
                        className="small text-success text-center"),
                html.Td(f"{m['ratio']:.0f}x",
                        className="small text-warning fw-bold text-center"),
            ])
        )

    return dbc.Card(
        dbc.CardBody([
            html.H6("💎 Best Value Models", className="text-warning fw-bold mb-1"),
            html.P("High intelligence · Low cost",
                   className="text-muted small mb-2"),
            dbc.Table(
                [
                    html.Thead(html.Tr([
                        html.Th(""),
                        html.Th("Model",  className="small"),
                        html.Th("Intel",  className="small text-center"),
                        html.Th("Price",  className="small text-center"),
                        html.Th("Value",  className="small text-center"),
                    ])),
                    html.Tbody(rows),
                ],
                dark=True, hover=True, size="sm", className="mb-0",
            ),
        ]),
        className="border-warning border-start border-4 mb-0 h-100",
    )


@callback(
    [Output("recommendation-cards", "children"),
     Output("score-chart",          "figure"),
     Output("scatter-chart",        "figure"),
     Output("method-badge",         "children")],
    [Input("profile-dropdown",  "value"),
     Input("commercial-filter", "value"),
     Input("method-selector",   "value")],
)
def update_recommendations(profile, commercial_filter, method):
    commercial = "commercial" in (commercial_filter or [])
    data       = fetch_recommendation(profile, commercial, method, top_n=5)
    empty_fig  = make_empty_fig("No data available")

    if not data or "results" not in data:
        return (
            dbc.Alert("No recommendation data available.", color="warning"),
            empty_fig, empty_fig, html.Div(),
        )

    # ── Method badge ──
    cr     = data.get("consistency_ratio")
    cr_str = f" · CR={cr:.4f} ✅" if cr and cr < 0.10 else ""
    badge  = dbc.Badge(
        f"{'AHP+TOPSIS' if method == 'ahp_topsis' else 'TOPSIS'}{cr_str}",
        color="success" if method == "ahp_topsis" else "secondary",
        pill=True, className="fs-6 px-3 py-2",
    )

    # ── Top 5 recommendation cards ──
    colors = ["warning", "secondary", "danger", "primary", "info"]
    labels = ["1st 🥇", "2nd 🥈", "3rd 🥉", "4th", "5th"]
    cols   = []

    for r in data["results"]:
        idx   = r["rank"] - 1
        color = colors[idx] if idx < len(colors) else "primary"
        label = labels[idx] if idx < len(labels) else f"#{r['rank']}"
        score = r["score"]
        m     = r["metrics"]

        cols.append(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        dbc.Row([
                            dbc.Col(dbc.Badge(label, color=color, pill=True)),
                            dbc.Col(
                                html.Small(m.get("license", ""),
                                           className="text-muted float-end"),
                                className="text-end",
                            ),
                        ]),
                    ),
                    dbc.CardBody([
                        html.H6(r["name"], className="fw-bold mb-0"),
                        html.P(r.get("provider", ""),
                               className="text-muted small mb-2"),

                        # Score + progress bar
                        html.Div([
                            dbc.Row([
                                dbc.Col(html.Small("Score",
                                                   className="text-muted")),
                                dbc.Col(html.Small(
                                    f"{score:.4f}",
                                    className=f"text-{color} fw-bold float-end",
                                )),
                            ]),
                            dbc.Progress(
                                value=score * 100,
                                color=color,
                                style={"height": "6px"},
                                className="mb-2",
                            ),
                        ]),

                        # D+ D- badges
                        html.Div([
                            dbc.Badge(f"D+ {r['d_plus']:.4f}",
                                      color="danger",  className="me-1 small"),
                            dbc.Badge(f"D- {r['d_minus']:.4f}",
                                      color="success", className="small"),
                        ], className="mb-2"),

                        # Metric pills
                        html.Div([
                            pill(f"🧠 {m.get('intelligence') or 'N/A'}/100"),
                            pill(f"💰 ${m.get('price_input') or 'N/A'}/M"),
                            pill(f"⚡ {m.get('speed_tps') or 'N/A'}t/s"),
                            pill(f"⏱️ {m.get('ttft_ms') or 'N/A'}ms"),
                        ], className="mb-2"),

                        html.Small(r["justification"],
                                   className="text-muted fst-italic"),
                    ]),
                ], className=f"border-{color} border-top border-3 h-100"),
                xs=12, sm=6, md=4, lg=True, className="mb-3",
            )
        )

    cards_div = dbc.Row(cols)

    # ── Bar chart — top 15 ──
    all_scored = data.get("all_scored", [])[:15]
    names  = [m["name"]  for m in all_scored]
    scores = [m["score"] for m in all_scored]
    bcolors = [
        "#fbbf24" if i == 0 else
        "#94a3b8" if i == 1 else
        "#b45309" if i == 2 else
        "#3b82f6"
        for i in range(len(names))
    ]

    bar_fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker=dict(color=bcolors),
        text=[f"{s:.3f}" for s in scores],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{y}</b><br>Score: %{x:.4f}<extra></extra>",
    ))
    bar_fig.update_layout(
        paper_bgcolor="#222", plot_bgcolor="#1a1a2e",
        font_color="#e0e0e0",
        margin=dict(l=8, r=50, t=8, b=8),
        height=400,
        xaxis=dict(range=[0, 1.15], gridcolor="#2a2d3e",
                   showgrid=True, tickfont=dict(size=10)),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        bargap=0.35,
    )

    # ── Scatter chart ──
    all_models = fetch_models()
    sm = [m for m in all_models
          if m.get("intelligence_score") and m.get("price_input")]

    src_color = {
        "huggingface":         "#3b82f6",
        "artificial_analysis": "#f59e0b",
        "llm_stats":           "#06b6d4",
    }

    scatter_fig = go.Figure(go.Scatter(
        x=[m["price_input"]         for m in sm],
        y=[m["intelligence_score"]  for m in sm],
        mode="markers",
        marker=dict(
            size=[max(8, min(28, (m.get("context_window") or 4096) / 10000))
                  for m in sm],
            color=[src_color.get(m.get("source", ""), "#94a3b8") for m in sm],
            opacity=0.85,
            line=dict(color="#2a2d3e", width=1),
        ),
        text=[m["name"] for m in sm],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Intelligence: %{y:.1f}<br>"
            "Price: $%{x:.3f}/1M<extra></extra>"
        ),
    ))
    scatter_fig.update_layout(
        paper_bgcolor="#222", plot_bgcolor="#1a1a2e",
        font_color="#e0e0e0",
        margin=dict(l=8, r=8, t=8, b=8),
        height=400,
        xaxis=dict(title="Price Input ($/1M tokens)",
                   gridcolor="#2a2d3e", showgrid=True,
                   tickfont=dict(size=10)),
        yaxis=dict(title="Intelligence Score",
                   gridcolor="#2a2d3e", showgrid=True,
                   tickfont=dict(size=10)),
    )

    return cards_div, bar_fig, scatter_fig, badge


@callback(
    Output("leaderboard-table", "children"),
    [Input("source-filter",    "value"),
     Input("license-filter",   "value"),
     Input("profile-dropdown", "value")],
)
def update_leaderboard(source_filter, license_filter, _):
    models = fetch_models()
    if not models:
        return dbc.Alert("No models found.", color="warning")

    if source_filter != "all":
        models = [m for m in models if m.get("source") == source_filter]
    if license_filter != "all":
        models = [m for m in models if m.get("license_type") == license_filter]

    rows = [{
        "Model":        m.get("name", ""),
        "Provider":     m.get("provider", ""),
        "Source":       m.get("source", ""),
        "License":      m.get("license_type") or "",
        "Intelligence": m.get("intelligence_score", ""),
        "Price In":     m.get("price_input", ""),
        "Price Out":    m.get("price_output", ""),
        "Speed t/s":    m.get("speed_tps", ""),
        "TTFT ms":      m.get("ttft_ms", ""),
        "Context":      m.get("context_window", ""),
        "New":          "🆕" if m.get("is_new") else "—",
    } for m in models]

    df = pd.DataFrame(rows)

    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        sort_action="native",
        filter_action="native",
        page_size=15,
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#1a1d27",
            "color":           "#e0e0e0",
            "fontWeight":      "600",
            "border":          "1px solid #2a2d3e",
            "padding":         "10px 12px",
            "fontSize":        "0.78rem",
            "textTransform":   "uppercase",
            "letterSpacing":   "0.04em",
        },
        style_cell={
            "backgroundColor": "#111827",
            "color":           "#e0e0e0",
            "border":          "1px solid #2a2d3e",
            "padding":         "9px 12px",
            "fontSize":        "0.82rem",
            "textAlign":       "left",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"},
             "backgroundColor": "#1a2236"},
            {"if": {"filter_query": '{New} = "🆕"'},
             "backgroundColor": "#052e16",
             "color":           "#4ade80"},
        ],
    )


@callback(
    Output("report-output", "children"),
    Input("generate-report-btn", "n_clicks"),
    prevent_initial_call=True,
)
def generate_report(n_clicks):
    if not n_clicks:
        return html.Div()
    try:
        r = requests.get(f"{API_BASE}/report/generate", timeout=60)
        r.raise_for_status()
        data     = r.json()
        filepath = data.get("file") or data.get("filename") or data.get("path") or "report"
        return dbc.Alert(
            [html.Strong("✅ Report generated — "), html.Code(filepath)],
            color="success", dismissable=True, className="py-2",
        )
    except Exception as e:
        return dbc.Alert(
            f"❌ Report generation failed: {e}",
            color="danger", dismissable=True, className="py-2",
        )


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def pill(text):
    return dbc.Badge(text, color="dark", className="me-1 mb-1 small")


def make_empty_fig(msg):
    fig = go.Figure()
    fig.add_annotation(
        text=msg, xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=13, color="#94a3b8"),
    )
    fig.update_layout(
        paper_bgcolor="#222", plot_bgcolor="#1a1a2e",
        margin=dict(l=8, r=8, t=8, b=8), height=300,
    )
    return fig


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=8050)