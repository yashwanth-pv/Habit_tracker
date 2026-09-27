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

SKILLS = ["Workout", "Reading", "Sleep"]
XP_PER_LEVEL = 500
HP_MAX_DEFAULT = 1000

# The specific routine you want tracked under "Workout" — shown as a
# reference checklist so you know what counts as one logged session.
WORKOUT_ROUTINE = {
    "frequency": "3 times every other day",
    "items": [
        "12 push ups",
        "25 crunches",
        "20 lunges (10/leg)",
        "25 squats",
        "50 jumping jacks",
        "60-second wall sit",
    ],
}

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


def square_bar(value, max_value, n=10):
    """Segmented block meter like the reference screenshot's skill bars."""
    filled = round((value / max_value) * n) if max_value else 0
    filled = max(0, min(n, filled))
    return "▰" * filled + "▱" * (n - filled)


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
section[data-testid="stSidebar"] {{ background-color: {CARD_BG}; }}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {CARD_BG};
    border-radius: 14px;
    border: 1px solid #232a3a;
}}

.system-title {{
    font-family: Georgia, 'Times New Roman', serif;
    font-weight: 700;
    text-align: center;
    font-size: 3rem;
    color: #f2f4f8;
    margin-bottom: 0;
}}
.system-subtitle {{
    text-align: center;
    letter-spacing: 3px;
    color: #e5e8ef;
    font-size: 1.1rem;
    margin-top: 0;
}}
.system-logo {{
    text-align: center;
    color: #8b93a7;
    letter-spacing: 2px;
    font-size: 0.8rem;
    text-transform: uppercase;
}}

.small-muted {{ color: #8b93a7; font-size: 0.85rem; }}
.avatar-frame {{ text-align: center; font-size: 90px; }}

.skill-row {{ letter-spacing: 1px; }}
.skill-bar {{ color: {ACCENT}; letter-spacing: 2px; }}

.activity-line {{ color: #8b93a7; font-size: 0.85rem; margin-bottom: -4px; }}
.activity-note {{ color: #e5e8ef; font-size: 0.95rem; margin-bottom: 0; }}
.activity-delta-pos {{ color: #4ade80; font-weight: 600; }}
.activity-delta-neg {{ color: #f87171; font-weight: 600; }}
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

    if secrets_token:
        # Token comes from .streamlit/secrets.toml — never rendered into any widget.
        st.caption("🔒 GitHub token loaded from secrets.toml")
        token = secrets_token
    else:
        # No secrets.toml found — let the user paste one for this session only.
        # type="password" masks it on screen; it is kept only in memory and is
        # never written back into the widget's displayed value.
        token_input = st.text_input(
            "GitHub token", value="", type="password",
            placeholder="paste token for this session",
            help="A fine-grained PAT with Contents read/write on this repo. "
                 "For a token that's never typed here at all, put it in "
                 ".streamlit/secrets.toml as GITHUB_TOKEN instead.",
        )
        token = token_input

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
    with st.expander("📋 Workout routine (reference)"):
        st.caption(WORKOUT_ROUTINE["frequency"])
        for item in WORKOUT_ROUTINE["items"]:
            st.markdown(f"- {item}")
    with st.form("add_activity"):
        skill = st.selectbox("Activity", SKILLS)
        kind_label = st.radio("Effect", ["Gain XP (good habit)", "Lose HP (bad habit)", "Restore HP"])
        amount = st.number_input("Amount", min_value=1, max_value=500, value=5)
        note = st.text_input("Note", placeholder="e.g. Full workout routine, Read 20 pages, 7hrs sleep")
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
st.markdown("<div class='system-logo'>⧉ Life RPG</div>", unsafe_allow_html=True)
st.markdown("<p class='system-title'>SOLO LEVELING</p>", unsafe_allow_html=True)
st.markdown("<p class='system-subtitle'>REAL-LIFE SYSTEM</p>", unsafe_allow_html=True)
st.write("")

data = st.session_state.data
player = data["player"]

# --------------------------------------------------------------------------
# Row 1 — Avatar / Radar / Calendar
# --------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)

with c1.container(border=True):
    st.subheader("1. Create Avatar")
    if player.get("avatar_b64"):
        st.image(base64.b64decode(player["avatar_b64"]), use_container_width=True)
    else:
        st.markdown("<div class='avatar-frame'>🧑‍💼</div>", unsafe_allow_html=True)
    st.markdown(
        f"<span class='small-muted'>{player['name']} · Level {player['level']} · {player['coins']} Coins</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<span class='skill-bar'>{hearts_bar(player['hp'], player['hp_max'])}</span> "
        f"<span class='small-muted'>{player['hp']} / {player['hp_max']}</span>",
        unsafe_allow_html=True,
    )

with c2.container(border=True):
    st.subheader("2. See your Stats")
    st.plotly_chart(build_radar(data), use_container_width=True, config={"displayModeBar": False})

with c3.container(border=True):
    st.subheader("3. Track your Progress")
    st.plotly_chart(build_calendar_heatmap(data), use_container_width=True, config={"displayModeBar": False})

st.write("")

# --------------------------------------------------------------------------
# Row 2 — Skill Points / Activities
# --------------------------------------------------------------------------
d1, d2 = st.columns(2)

with d1.container(border=True):
    st.subheader("4. Select Skill to Level Up")
    for s in SKILLS:
        sk = data["skills"][s]
        bar = square_bar(sk["xp"], XP_PER_LEVEL)
        st.markdown(
            f"<div class='skill-row'>{s}<br>"
            f"<span class='skill-bar'>{bar}</span> "
            f"<span class='small-muted'>{sk['xp']} / {XP_PER_LEVEL} &nbsp;·&nbsp; LV {sk['level']}</span>"
            f"</div><br>",
            unsafe_allow_html=True,
        )

with d2.container(border=True):
    st.subheader("5. Gain XP and Level Up")
    if not data["activities"]:
        st.caption("Nothing logged yet — add one from the sidebar.")
    for a in data["activities"][:15]:
        ts = datetime.fromisoformat(a["ts"])
        today = datetime.now().date()
        day_label = "Today" if ts.date() == today else (
            "Yesterday" if ts.date() == today - timedelta(days=1) else ts.strftime("%b %d")
        )
        when = f"@{day_label} {ts.strftime('%I:%M %p').lstrip('0')}"

        if a["kind"] == "xp_gain":
            verb, delta, cls = "You have gained", f"+ {a['amount']} EXP!", "activity-delta-pos"
        elif a["kind"] == "hp_loss":
            verb, delta, cls = "You lost a battle and lost", f"- {a['amount']} HP!", "activity-delta-neg"
        else:
            verb, delta, cls = "You restored", f"+ {a['amount']} HP!", "activity-delta-pos"

        st.markdown(
            f"<div class='activity-line'>→| {when}</div>"
            f"<div class='activity-note'>{verb} {a['amount']} {'HP' if 'HP' in delta else 'EXP'}! → {a['note']}</div>"
            f"<div class='{cls}'>{delta}</div><br>",
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "Data lives only in this session until you click **Save** in the sidebar — "
    "that commits habit_tracker_data.json to your GitHub repo."
)
