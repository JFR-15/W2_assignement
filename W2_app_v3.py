import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Does spending on education pay off?", page_icon="🎓", layout="wide")

API_URL = "https://api.worldbank.org/v2"

INDICATOR_CODES = {
    "SE.XPD.TOTL.GD.ZS": "spending_gdp",
    "SE.XPD.TOTL.GB.ZS": "spending_budget",
    "HD.HCI.LAYS": "learning_years",
    "SE.PRM.CMPT.ZS": "primary_completion",
    "SE.SEC.CMPT.LO.ZS": "lower_secondary_completion",
    "SI.POV.DDAY": "poverty_rate",
    "SE.ADT.LITR.ZS": "adult_literacy",
    "NY.GDP.PCAP.CD": "gdp_per_capita",
    "NY.GDP.PCAP.KD": "gdp_per_capita_constant",
    "SP.POP.TOTL": "population",
}

LABELS = {
    "country": "Country",
    "region": "Region",
    "year": "Year",
    "spending_gdp": "Education spending (% of GDP)",
    "spending_budget": "Education spending (% of government budget)",
    "spending_per_person": "Education spending per person (US$)",
    "learning_years": "Learning-adjusted years of school",
    "primary_completion": "Finished primary school (%)",
    "lower_secondary_completion": "Finished lower secondary school (%)",
    "poverty_rate": "Living on under $3 a day (%)",
    "adult_literacy": "Adults who can read (%)",
    "gdp_per_capita": "GDP per person (US$)",
    "gdp_per_capita_constant": "GDP per person (constant 2015 US$)",
    "gdp_growth": "GDP per person growth, 2010 to latest (% per year)",
    "early_spending": "Average education spending 2000–2009 (% of GDP)",
    "population": "Population",
}

SPENDING_MEASURES = {
    "spending_gdp": "Share of the economy (% of GDP) — how much effort a country puts in.",
    "spending_budget": "Share of the government budget — pushed up in countries with many children.",
    "spending_per_person": "Dollars per person — mostly reflects how rich a country is.",
}

SPENDING_OPTION_NAMES = {
    "spending_gdp": "% of GDP",
    "spending_budget": "% of government budget",
    "spending_per_person": "US$ per person",
}

OUTCOMES = ["poverty_rate", "learning_years", "gdp_per_capita"]

EXAMPLE_COUNTRIES = ["Vietnam", "South Africa"]

COUNTRY_NAMES = {
    "Viet Nam": "Vietnam",
    "Korea, Rep.": "South Korea",
    "Korea, Dem. People's Rep.": "North Korea",
    "Egypt, Arab Rep.": "Egypt",
    "Iran, Islamic Rep.": "Iran",
    "Yemen, Rep.": "Yemen",
    "Congo, Dem. Rep.": "DR Congo",
    "Congo, Rep.": "Congo",
    "Gambia, The": "Gambia",
    "Bahamas, The": "Bahamas",
    "Lao PDR": "Laos",
    "Turkiye": "Türkiye",
    "Russian Federation": "Russia",
    "Syrian Arab Republic": "Syria",
    "Kyrgyz Republic": "Kyrgyzstan",
    "Slovak Republic": "Slovakia",
    "Venezuela, RB": "Venezuela",
    "Micronesia, Fed. Sts.": "Micronesia",
    "Somalia, Fed. Rep.": "Somalia",
    "Hong Kong SAR, China": "Hong Kong",
    "Macao SAR, China": "Macao",
    "Cote d'Ivoire": "Côte d'Ivoire",
}

REGIONS = {
    "Sub-Saharan Africa": ("Sub-Saharan Africa", "#D55E00"),
    "South Asia": ("South Asia", "#E69F00"),
    "East Asia & Pacific": ("East Asia & Pacific", "#009E73"),
    "Latin America & Caribbean": ("Latin America & Caribbean", "#CC79A7"),
    "Middle East, North Africa, Afghanistan & Pakistan": ("Middle East & North Africa", "#0072B2"),
    "Europe & Central Asia": ("Europe & Central Asia", "#56B4E9"),
    "North America": ("North America", "#999999"),
}
REGION_COLORS = dict(REGIONS.values())

MIN_POVERTY_SURVEYS = 3
LATEST_POVERTY_YEAR = 2017
LATEST_LEARNING_YEAR = 2020
MIN_SPENDING_YEARS = 5

LINE_COLORS = {
    LABELS["primary_completion"]: "#56B4E9",
    LABELS["lower_secondary_completion"]: "#0072B2",
    LABELS["adult_literacy"]: "#009E73",
    LABELS["poverty_rate"]: "#D55E00",
    LABELS["spending_gdp"]: "#7B3294",
}

GDP_TICKS = [250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]


def fetch_world_bank(url, params):
    response = requests.get(url, params={"format": "json", **params}, timeout=30)
    payload = response.json()

    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        meta = payload[0] if isinstance(payload, list) and payload else payload
        messages = meta.get("message", []) if isinstance(meta, dict) else []
        text = messages[0].get("value") if messages else None
        raise RuntimeError(text or "Unexpected response from the World Bank API")
    return payload[0], payload[1]


@st.cache_data(ttl=86400)
def load_indicator(code):
    rows, page, total_pages = [], 1, 1
    while page <= total_pages:
        meta, batch = fetch_world_bank(
            f"{API_URL}/country/all/indicator/{code}",
            {"date": "1990:2025", "per_page": 20000, "page": page},
        )
        rows += batch
        total_pages = int(meta.get("pages", 1))
        page += 1

    indicator = pd.DataFrame(
        {
            "iso3": [row["countryiso3code"] for row in rows],
            "year": [int(row["date"]) for row in rows],
            "value": [row["value"] for row in rows],
        }
    )
    indicator["indicator"] = INDICATOR_CODES[code]
    return indicator.dropna(subset=["value"])


@st.cache_data(ttl=86400)
def load_countries():
    _, rows = fetch_world_bank(f"{API_URL}/country", {"per_page": 400})
    countries = pd.DataFrame(
        {
            "iso3": [row["id"] for row in rows],
            "country": [row["name"].strip() for row in rows],
            "region": [row["region"]["value"].strip() for row in rows],
        }
    )
    countries = countries[countries["region"] != "Aggregates"]
    countries["country"] = countries["country"].replace(COUNTRY_NAMES)
    countries["region"] = countries["region"].map(lambda r: REGIONS.get(r, (r, None))[0])
    return countries


@st.cache_data(ttl=86400)
def load_data(codes):
    long_table = pd.concat([load_indicator(code) for code in codes], ignore_index=True)
    wide_table = long_table.pivot_table(
        index=["iso3", "year"], columns="indicator", values="value"
    ).reset_index()
    wide_table.columns.name = None
    wide_table["spending_per_person"] = wide_table["spending_gdp"] * wide_table["gdp_per_capita"] / 100
    return wide_table.merge(load_countries(), on="iso3", how="inner")


try:
    with st.spinner("Loading World Bank data (first load takes a few seconds)..."):
        all_data = load_data(tuple(INDICATOR_CODES))
except (RuntimeError, requests.RequestException, ValueError) as err:
    st.error(f"Couldn't load data from the World Bank: {err}")
    st.caption("The API might be down or unreachable. Refresh the page in a minute.")
    st.stop()


def reliable_countries(data):
    recent = data[data["year"] >= 2000]
    poverty_checks = (
        recent.dropna(subset=["poverty_rate"])
        .groupby("country")
        .agg(surveys=("year", "count"), latest=("year", "max"))
    )
    learning_latest = recent.dropna(subset=["learning_years"]).groupby("country")["year"].max()
    spending_years = recent.dropna(subset=["spending_gdp"]).groupby("country")["year"].count()
    good_poverty = poverty_checks[
        (poverty_checks["surveys"] >= MIN_POVERTY_SURVEYS)
        & (poverty_checks["latest"] >= LATEST_POVERTY_YEAR)
    ].index
    good_learning = learning_latest[learning_latest >= LATEST_LEARNING_YEAR].index
    good_spending = spending_years[spending_years >= MIN_SPENDING_YEARS].index
    return good_poverty.intersection(good_learning).intersection(good_spending)


all_data = all_data[all_data["country"].isin(reliable_countries(all_data))]


with st.sidebar:
    st.header("Explore")
    spending_measure = st.radio(
        "Measure spending as",
        list(SPENDING_MEASURES),
        format_func=lambda column: SPENDING_OPTION_NAMES[column],
        help="\n\n".join(SPENDING_MEASURES.values()),
    )
    outcome = st.selectbox(
        "Result to compare against",
        OUTCOMES,
        format_func=lambda column: LABELS[column],
        help="Learning-adjusted years is used instead of completion rates, "
             "because it is comparable between different school systems.",
    )
    country_list = sorted(all_data["country"].unique())
    selected_country = st.selectbox(
        "Country to follow",
        country_list,
        index=country_list.index("Vietnam") if "Vietnam" in country_list else 0,
        help="Shown in the timeline and highlighted in the scatter plots.",
    )
    start_year, end_year = st.slider(
        "Years",
        min_value=int(all_data["year"].min()),
        max_value=int(all_data["year"].max()),
        value=(2000, int(all_data["year"].max())),
    )
    st.subheader("Scatter plots")
    focus_region = st.selectbox(
        "Focus on a region",
        ["All regions"] + list(REGION_COLORS),
        help="Colours one region and greys out the rest, so it's easier to see where it sits.",
    )
    size_by_population = st.checkbox(
        "Size dots by population", value=False,
        help="Bigger dots = more people. Off by default to keep the chart clean.",
    )
    st.divider()
    st.caption(
        f"Showing {all_data['country'].nunique()} countries with reliable data: "
        f"at least {MIN_POVERTY_SURVEYS} poverty surveys since 2000 (latest from {LATEST_POVERTY_YEAR} "
        f"or later), {MIN_SPENDING_YEARS}+ years of education spending data, and a learning score "
        f"from the World Bank's {LATEST_LEARNING_YEAR} Human Capital Index."
    )
    st.caption("Spending figures show what governments budget, not what reaches classrooms.")

data_in_range = all_data[all_data["year"].between(start_year, end_year)].copy()

if data_in_range.empty:
    st.info("No data for these years. Widen the year range in the sidebar.")
    st.stop()

latest_by_country = (
    data_in_range.sort_values("year").groupby(["country", "region"], as_index=False).last()
)
country_timeline = data_in_range[data_in_range["country"] == selected_country].sort_values("year")


st.title("Does spending on education pay off?")
st.markdown(
    "Do countries that spend more on education have less poverty, children who learn more, "
    "and faster-growing economies? Pick a spending measure and a result in the sidebar."
)


def first_and_last(frame, column):
    measured = frame[["year", column]].dropna()
    if measured.empty:
        return None
    first, last = measured.iloc[0], measured.iloc[-1]
    return {"first": first[column], "last": last[column],
            "first_year": int(first["year"]), "last_year": int(last["year"])}


def format_value(column, value):
    if column in ("spending_per_person", "gdp_per_capita"):
        return f"${value:,.0f}"
    if column == "learning_years":
        return f"{value:.1f} years"
    return f"{value:.1f}%"


def comparable(frame, x_column, y_column):
    pair = frame[[x_column, y_column]].dropna()
    if x_column == "spending_per_person":
        pair[x_column] = np.log10(pair[x_column])
    if y_column == "gdp_per_capita":
        pair[y_column] = np.log10(pair[y_column])
    return pair


compare_pair = comparable(latest_by_country, spending_measure, outcome)
correlation = compare_pair.corr().iloc[0, 1] if len(compare_pair) > 2 else float("nan")
spending = first_and_last(country_timeline, spending_measure)
poverty = first_and_last(country_timeline, "poverty_rate")
learning = first_and_last(country_timeline, "learning_years")


metric_1, metric_2, metric_3, metric_4 = st.columns(4)
if spending:
    metric_1.metric(
        f"{selected_country}: spending ({spending['last_year']})",
        format_value(spending_measure, spending["last"]),
        help=LABELS[spending_measure],
    )
else:
    metric_1.metric(f"{selected_country}: spending", "No data")
if poverty:
    metric_2.metric(
        f"{selected_country}: poverty ({poverty['last_year']})",
        f"{poverty['last']:.1f}%",
        delta=(f"{poverty['last'] - poverty['first']:+.1f} pts since {poverty['first_year']}"
               if poverty["first_year"] != poverty["last_year"] else None),
        delta_color="inverse",
    )
else:
    metric_2.metric(f"{selected_country}: poverty", "No data")
metric_3.metric(
    f"{selected_country}: learning-adjusted years" + (f" ({learning['last_year']})" if learning else ""),
    f"{learning['last']:.1f} years" if learning else "No data",
    help="Years in school, discounted by how much children actually learn. The best systems reach about 13.",
)
metric_4.metric(
    "Link: spending and result",
    f"{correlation:+.2f}",
    help="Correlation from -1 to 1 across all countries shown. Close to 0 means no clear link. "
         "Dollar amounts are compared on a log scale.",
)


def country_scatter(frame, x_column, y_column, hover_format, log_x=False, log_y=False):
    frame = frame.copy()
    if focus_region == "All regions":
        frame["dot_group"] = frame["region"]
        colors = REGION_COLORS
    else:
        frame["dot_group"] = np.where(frame["region"] == focus_region, focus_region, "Other regions")
        colors = {focus_region: REGION_COLORS[focus_region], "Other regions": "#D3D3D3"}
        frame = frame.sort_values("dot_group", key=lambda group: group == focus_region)

    fig = px.scatter(
        frame, x=x_column, y=y_column,
        color="dot_group", color_discrete_map=colors,
        size="population" if size_by_population else None, size_max=30,
        hover_name="country", log_x=log_x, log_y=log_y, labels=LABELS,
        hover_data={"dot_group": False, "region": True, "population": ":,.0f", **hover_format},
    )
    if not size_by_population:
        fig.update_traces(marker=dict(size=10))
    fig.update_traces(marker=dict(opacity=0.8, line=dict(width=0.8, color="white")))

    if len(frame) > 2:
        x_values = np.log10(frame[x_column]) if log_x else frame[x_column]
        y_values = np.log10(frame[y_column]) if log_y else frame[y_column]
        slope, intercept = np.polyfit(x_values, y_values, 1)
        trend_x = np.linspace(x_values.min(), x_values.max(), 50)
        trend_y = slope * trend_x + intercept
        fig.add_scatter(
            x=10 ** trend_x if log_x else trend_x,
            y=10 ** trend_y if log_y else trend_y.clip(min=0),
            mode="lines", name="Overall trend", line=dict(dash="dash", color="grey"), hoverinfo="skip",
        )

    labelled = frame[frame["country"].isin(EXAMPLE_COUNTRIES + [selected_country])]
    if not labelled.empty:
        fig.add_scatter(
            x=labelled[x_column], y=labelled[y_column],
            mode="markers+text", text=labelled["country"], textposition="top center",
            marker=dict(size=20, color="rgba(0,0,0,0)", line=dict(width=2.5, color="black")),
            textfont=dict(size=14, color="black"), name="Highlighted", hoverinfo="skip",
        )
    fig.update_layout(
        height=540, margin=dict(t=40, b=60), plot_bgcolor="white",
        legend=dict(orientation="h", y=1.08, x=0, title_text=""),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEEEEE")
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE")
    if log_x:
        fig.update_xaxes(tickvals=GDP_TICKS, ticktext=[f"${tick:,}" for tick in GDP_TICKS])
    if log_y:
        fig.update_yaxes(tickvals=GDP_TICKS, ticktext=[f"${tick:,}" for tick in GDP_TICKS])
    return fig


def growth_table(data):
    early_spending = (
        data[data["year"].between(2000, 2009)]
        .groupby(["country", "region"])["spending_gdp"].mean()
        .rename("early_spending").reset_index()
    )
    gdp = data.dropna(subset=["gdp_per_capita_constant"])
    start = gdp[gdp["year"] == 2010].set_index("country")["gdp_per_capita_constant"]
    end = gdp[gdp["year"] >= 2022].sort_values("year").groupby("country").last()
    yearly_growth = ((end["gdp_per_capita_constant"] / start) ** (1 / (end["year"] - 2010)) - 1) * 100
    population = data.dropna(subset=["population"]).sort_values("year").groupby("country")["population"].last()
    table = early_spending.merge(yearly_growth.rename("gdp_growth"), left_on="country", right_index=True)
    table = table.merge(population, left_on="country", right_index=True)
    return table.dropna(subset=["early_spending", "gdp_growth"])


tab_compare, tab_timeline, tab_growth = st.tabs(
    ["Compare countries", f"{selected_country} over time", "Spending and growth"]
)

with tab_compare:
    comparison = f"{LABELS[spending_measure]} vs {LABELS[outcome]}".replace("$", "\\$")
    st.markdown(f"**Do countries that spend more have better results?** "
                f"{comparison}, latest values {start_year}–{end_year}.")
    scatter_data = latest_by_country.dropna(subset=[spending_measure, outcome])
    if len(scatter_data) < 3:
        st.info("Not enough data for this combination. Learning scores exist for 2010, 2017, 2018 "
                "and 2020 only, so include 2020 in the year range.")
    else:
        fig = country_scatter(
            scatter_data, spending_measure, outcome,
            {spending_measure: ":,.1f", outcome: ":,.1f"},
            log_x=spending_measure == "spending_per_person",
            log_y=outcome == "gdp_per_capita",
        )
        st.plotly_chart(fig)
        st.caption(
            "Each dot is a country. Vietnam and South Africa are labelled as an example pair: "
            "similar corruption scores, very different spending and results. "
            f"{SPENDING_MEASURES[spending_measure]} This shows a pattern, not proof."
        )

with tab_timeline:
    st.markdown(f"**Did {selected_country}'s results improve as it spent more?**")
    percent_columns = ["primary_completion", "lower_secondary_completion", "adult_literacy", "poverty_rate"]
    results = country_timeline.melt(id_vars="year", value_vars=percent_columns,
                                    var_name="measure", value_name="value").dropna()
    results["panel"] = "Schooling and poverty (%)"
    budget = country_timeline.melt(id_vars="year", value_vars=["spending_gdp"],
                                   var_name="measure", value_name="value").dropna()
    budget["panel"] = "Education spending (% of GDP)"
    timeline_data = pd.concat([results, budget], ignore_index=True)
    timeline_data["measure"] = timeline_data["measure"].map(LABELS)

    if timeline_data.empty:
        st.info(f"No data for {selected_country} in these years. Try another country or a wider year range.")
    else:
        fig = px.line(
            timeline_data, x="year", y="value", color="measure", facet_row="panel",
            category_orders={"panel": ["Schooling and poverty (%)", "Education spending (% of GDP)"]},
            color_discrete_map=LINE_COLORS, markers=True,
            labels={"value": "", "year": "", "measure": ""}, facet_row_spacing=0.08,
        )
        fig.for_each_annotation(lambda note: note.update(text=note.text.split("=")[-1]))
        fig.update_traces(selector=dict(name=LABELS["poverty_rate"]), line=dict(width=4, dash="dash"))
        fig.update_yaxes(matches=None, rangemode="tozero", showgrid=True, gridcolor="#EEEEEE")
        fig.update_layout(height=620, margin=dict(t=40, b=60), plot_bgcolor="white",
                          legend=dict(orientation="h", y=1.08, x=0, title_text=""))
        st.plotly_chart(fig)
        st.caption("Top: schooling (blue, green) and poverty (red dashed). Bottom: education spending. "
                   "Dots are real measurements; lines connect them across missing years. "
                   "Completion rates depend on how each school system is organised, so use them "
                   "to follow one country over time, not to compare countries.")

with tab_growth:
    st.markdown("**Did countries that spent more on education in the 2000s grow faster afterwards?**")
    growth_data = growth_table(all_data)
    if len(growth_data) < 3:
        st.info("Not enough data to compare spending and growth.")
    else:
        fig = country_scatter(growth_data, "early_spending", "gdp_growth",
                              {"early_spending": ":.1f", "gdp_growth": ":.1f"})
        st.plotly_chart(fig)
        st.caption(
            "Spending is averaged over 2000–2009; growth is measured from 2010 to the latest year, "
            "adjusted for inflation. The gap in time is there because schooling can only affect "
            "the economy once students start working. This chart ignores the year slider."
        )


st.divider()
if "pinned_views" not in st.session_state:
    st.session_state.pinned_views = []

pin_column, clear_column, _ = st.columns([1, 1, 4])
if pin_column.button("📌 Pin this view", help="Save the current numbers to compare countries side by side."):
    st.session_state.pinned_views.append(
        {
            "Country": selected_country,
            "Years": f"{start_year}–{end_year}",
            "Spending measure": LABELS[spending_measure],
            "Spending (latest)": format_value(spending_measure, spending["last"]) if spending else None,
            "Poverty change (pts)": round(poverty["last"] - poverty["first"], 1) if poverty else None,
            "Learning-adjusted years": round(learning["last"], 1) if learning else None,
            "Result compared": LABELS[outcome],
            "Spending–result link": round(float(correlation), 2),
        }
    )
if clear_column.button("Clear pins"):
    st.session_state.pinned_views = []

if st.session_state.pinned_views:
    st.subheader("Pinned views")
    pinned_table = pd.DataFrame(st.session_state.pinned_views)
    st.dataframe(pinned_table, hide_index=True)
    st.download_button(
        "Download pinned views (CSV)",
        data=pinned_table.to_csv(index=False).encode("utf-8"),
        file_name="pinned_views.csv",
        mime="text/csv",
    )


download_table = data_in_range.drop(columns="iso3").rename(columns=LABELS)
st.download_button(
    "Download the data for these years (CSV)",
    data=download_table.to_csv(index=False).encode("utf-8"),
    file_name="education_spending.csv",
    mime="text/csv",
)
