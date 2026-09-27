"""
Solo Leveling — Real Life System
A Streamlit habit tracker styled after the "Solo Leveling" RPG-life-tracker
concept, with data persisted to a GitHub repo via the GitHub Contents API.
"""

import base64
import json
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
st.set_page_config(page_title="Solo Leveling — Real Life System", page_icon="⚔️", layout="wide")

GITHUB_API = "https://api.github.com"
DEFAULT_DATA_PATH = "habit_tracker_data.json"

SKILLS = ["Writing", "Financial", "Learning", "Video Editing", "Health", "Creativity"]
XP_PER_LEVEL = 500
HP_MAX_DEFAULT = 1000

DARK_BG = "#0b0e17"
ACCENT = "#5fd3e0"
CARD_BG = "#161b28"


def default_data():
    return {
        "player": {
            "name": "Sung Jin-woo",
            "title": "The Shadow Monarch",
            "level": 1,
            "coins": 0,
            "hp": HP_MAX_DEFAULT,
            "hp_max": HP_MAX_DEFAULT,
            "avatar_b64": None,
        },
        "skills": {s: {"xp": 0, "level": 1} for s in SKILLS},
        "activities": [],  # list of {ts, skill, kind, amount, note}
    }


# --------------------------------------------------------------------------
# GitHub storage
# --------------------------------------------------------------------------
def gh_headers(token):
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}


def load_from_github(owner, repo, path, token, branch):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=gh_headers(token), params={"ref": branch}, timeout=15)
    if r.status_code == 200:
        payload = r.json()
        decoded = base64.b64decode(payload["content"]).decode("utf-8")
        return json.loads(decoded), payload["sha"]
    if r.status_code == 404:
        return None, None
    raise RuntimeError(f"GitHub load failed ({r.status_code}): {r.text}")


def save_to_github(owner, repo, path, token, branch, data, sha, message):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    content_str = json.dumps(data, indent=2)
    b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": b64, "branch": branch}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=gh_headers(token), json=payload, timeout=15)
    if r.status_code in (200, 201):
        return r.json()["content"]["sha"]
    raise RuntimeError(f"GitHub save failed ({r.status_code}): {r.text}")


# --------------------------------------------------------------------------
# Game logic helpers
# --------------------------------------------------------------------------
def apply_activity(data, skill, kind, amount, note):
    """kind: 'xp_gain' | 'hp_loss' | 'hp_gain'"""
    ts = datetime.now().isoformat(timespec="seconds")
    entry = {"ts": ts, "skill": skill, "kind": kind, "amount": amount, "note": note}
    data["activities"].insert(0, entry)

    if kind == "xp_gain":
        sk = data["skills"][skill]
        sk["xp"] += amount
        while sk["xp"] >= XP_PER_LEVEL:
            sk["xp"] -= XP_PER_LEVEL
            sk["level"] += 1
            data["player"]["coins"] += 10
        # overall level = sum of skill levels / len, rounded
        total_levels = sum(s["level"] for s in data["skills"].values())
        data["player"]["level"] = max(1, total_levels // len(data["skills"]))
    elif kind == "hp_loss":
        data["player"]["hp"] = max(0, data["player"]["hp"] - amount)
    elif kind == "hp_gain":
        data["player"]["hp"] = min(data["player"]["hp_max"], data["player"]["hp"] + amount)

    return data


def hearts_bar(hp, hp_max, n=10):
    filled = round((hp / hp_max) * n) if hp_max else 0
    return "❤️" * filled + "🖤" * (n - filled)


def build_radar(data):
    cats = SKILLS + [SKILLS[0]]
    vals = [data["skills"][s]["level"] for s in SKILLS]
    vals += [vals[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals, theta=cats, fill="toself",
        line=dict(color=ACCENT), fillcolor="rgba(95,211,224,0.25)",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=CARD_BG,
            radialaxis=dict(visible=True, color="#8b93a7", gridcolor="#2a3040"),
            angularaxis=dict(color="#e5e8ef", gridcolor="#2a3040"),
        ),
        showlegend=False,
        paper_bgcolor=CARD_BG,
        font=dict(color="#e5e8ef"),
        margin=dict(l=40, r=40, t=30, b=30),
        height=380,
    )
    return fig


def build_calendar_heatmap(data, weeks_back=6):
    today = datetime.now().date()
    start = today - timedelta(days=today.weekday() + 7 * (weeks_back - 1))
    counts = {}
    for a in data["activities"]:
        d = datetime.fromisoformat(a["ts"]).date()
        counts[d] = counts.get(d, 0) + 1

    days = ["M", "T", "W", "T", "F", "S", "S"]
    z, labels, week_labels = [], [], []
    for w in range(weeks_back):
        week_start = start + timedelta(days=7 * w)
        row = []
        for d in range(7):
            day = week_start + timedelta(days=d)
            row.append(counts.get(day, 0))
        z.append(row)
        iso_week = week_start.isocalendar()[1]
        week_labels.append(f"w-{iso_week}")

    fig = go.Figure(data=go.Heatmap(
        z=z, x=days, y=week_labels,
        colorscale=[[0, CARD_BG], [1, ACCENT]],
        showscale=False, xgap=4, ygap=4,
    ))
    fig.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color="#e5e8ef"),
        margin=dict(l=10, r=10, t=10, b=10), height=260,
        yaxis=dict(autorange="reversed"),
    )
    return fig


# --------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------
st.markdown(f"""
<style>
.stApp {{ background-color: {DARK_BG}; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {CARD_BG};
    border-radius: 14px;
    border: 1px solid #232a3a;
}}
h1, h2, h3 {{ color: #f2f4f8; }}
.small-muted {{ color: #8b93a7; font-size: 0.85rem; }}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Session state init
# --------------------------------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = default_data()
if "sha" not in st.session_state:
    st.session_state.sha = None
if "gh_status" not in st.session_state:
    st.session_state.gh_status = "Not connected"

# --------------------------------------------------------------------------
# Sidebar — GitHub connection + add activity
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ GitHub Sync")

    secrets_token = st.secrets.get("GITHUB_TOKEN", "") if hasattr(st, "secrets") else ""
    secrets_owner = st.secrets.get("GITHUB_OWNER", "") if hasattr(st, "secrets") else ""
    secrets_repo = st.secrets.get("GITHUB_REPO", "") if hasattr(st, "secrets") else ""

    owner = st.text_input("Repo owner", value=secrets_owner, placeholder="your-github-username")
    repo = st.text_input("Repo name", value=secrets_repo, placeholder="habit-tracker-data")
    branch = st.text_input("Branch", value="main")
    path = st.text_input("Data file path", value=DEFAULT_DATA_PATH)
    token = st.text_input(
        "GitHub token", value=secrets_token, type="password",
        help="A fine-grained PAT with Contents read/write on this repo. "
             "Better: put it in .streamlit/secrets.toml as GITHUB_TOKEN so it never appears here.",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("⬇️ Load", use_container_width=True, disabled=not (owner and repo and token)):
            try:
                loaded, sha = load_from_github(owner, repo, path, token, branch)
                if loaded is None:
                    st.session_state.gh_status = "No file yet — will create on first save."
                else:
                    st.session_state.data = loaded
                    st.session_state.sha = sha
                    st.session_state.gh_status = "Loaded ✅"
            except Exception as e:
                st.session_state.gh_status = f"Error: {e}"
    with col_b:
        if st.button("⬆️ Save", use_container_width=True, disabled=not (owner and repo and token)):
            try:
                sha = save_to_github(
                    owner, repo, path, token, branch,
                    st.session_state.data, st.session_state.sha,
                    message=f"Update habit tracker — {datetime.now().isoformat(timespec='seconds')}",
                )
                st.session_state.sha = sha
                st.session_state.gh_status = "Saved ✅"
            except Exception as e:
                st.session_state.gh_status = f"Error: {e}"

    st.caption(st.session_state.gh_status)
    st.divider()

    st.header("➕ Log Activity")
    with st.form("add_activity"):
        skill = st.selectbox("Skill", SKILLS)
        kind_label = st.radio("Effect", ["Gain XP (good habit)", "Lose HP (bad habit)", "Restore HP"])
        amount = st.number_input("Amount", min_value=1, max_value=500, value=5)
        note = st.text_input("Note", placeholder="e.g. Workout, Smoking, Read 20 pages")
        submitted = st.form_submit_button("Log it", use_container_width=True)
        if submitted:
            kind = {"Gain XP (good habit)": "xp_gain",
                    "Lose HP (bad habit)": "hp_loss",
                    "Restore HP": "hp_gain"}[kind_label]
            st.session_state.data = apply_activity(st.session_state.data, skill, kind, amount, note or skill)
            st.success("Logged. Remember to Save to GitHub ⬆️")

    st.divider()
    with st.expander("Avatar"):
        up = st.file_uploader("Upload avatar image", type=["png", "jpg", "jpeg"])
        if up is not None:
            st.session_state.data["player"]["avatar_b64"] = base64.b64encode(up.read()).decode("utf-8")
            st.success("Avatar updated — Save to GitHub to persist it.")
        name = st.text_input("Character name", value=st.session_state.data["player"]["name"])
        if name != st.session_state.data["player"]["name"]:
            st.session_state.data["player"]["name"] = name

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.markdown("<h1 style='text-align:center;'>SOLO LEVELING</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;color:#8b93a7;'>REAL-LIFE SYSTEM</h3>", unsafe_allow_html=True)
st.write("")

data = st.session_state.data
player = data["player"]

# --------------------------------------------------------------------------
# Row 1 — Avatar / Radar / Calendar
# --------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)

with c1.container(border=True):
    st.subheader("1. Avatar")
    if player.get("avatar_b64"):
        st.image(base64.b64decode(player["avatar_b64"]), use_container_width=True)
    else:
        st.markdown("<div style='text-align:center;font-size:80px;'>🧑‍💼</div>", unsafe_allow_html=True)
    st.markdown(f"**{player['name']}** · Level {player['level']} · {player['coins']} Coins")
    st.markdown(f"HP: {hearts_bar(player['hp'], player['hp_max'])}  {player['hp']} / {player['hp_max']}")

with c2.container(border=True):
    st.subheader("2. Your Stats")
    st.plotly_chart(build_radar(data), use_container_width=True, config={"displayModeBar": False})

with c3.container(border=True):
    st.subheader("3. Your Progress")
    st.plotly_chart(build_calendar_heatmap(data), use_container_width=True, config={"displayModeBar": False})

st.write("")

# --------------------------------------------------------------------------
# Row 2 — Skill Points / Activities
# --------------------------------------------------------------------------
d1, d2 = st.columns(2)

with d1.container(border=True):
    st.subheader("4. Skill Points")
    for s in SKILLS:
        sk = data["skills"][s]
        pct = sk["xp"] / XP_PER_LEVEL
        st.markdown(f"**{s}** — LV {sk['level']}")
        st.progress(min(1.0, pct), text=f"{sk['xp']} / {XP_PER_LEVEL} XP")

with d2.container(border=True):
    st.subheader("5. Activities")
    if not data["activities"]:
        st.caption("Nothing logged yet — add one from the sidebar.")
    for a in data["activities"][:15]:
        ts = datetime.fromisoformat(a["ts"])
        when = ts.strftime("%b %d, %I:%M %p")
        if a["kind"] == "xp_gain":
            st.markdown(f"🟢 **{when}** — {a['note']} → +{a['amount']} XP ({a['skill']})")
        elif a["kind"] == "hp_loss":
            st.markdown(f"🔴 **{when}** — {a['note']} → -{a['amount']} HP")
        else:
            st.markdown(f"💚 **{when}** — {a['note']} → +{a['amount']} HP")

st.divider()
st.caption(
    "Data lives only in this session until you click **Save** in the sidebar — "
    "that commits habit_tracker_data.json to your GitHub repo."
)
