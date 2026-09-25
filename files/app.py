"""
The System — a Solo-Leveling-style self-improvement tracker.
Data is persisted to a JSON file in a GitHub repo via the Contents API,
so the app has no database of its own: your GitHub repo IS the save file.
"""

import datetime as dt

import streamlit as st

import github_storage as gh
import system_logic as sl

st.set_page_config(page_title="The System", page_icon="🗡️", layout="wide")

# ----------------------------------------------------------------------------
# Styling — dark "status window" look
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at 50% 0%, #0d1830 0%, #05070f 60%); }
    h1, h2, h3, h4 { color: #7ee3ff !important; letter-spacing: 1px; }
    .system-box {
        border: 1px solid #2e8fd6;
        background: linear-gradient(180deg, rgba(15,30,60,0.85), rgba(5,10,25,0.9));
        border-radius: 6px;
        padding: 18px 22px;
        box-shadow: 0 0 18px rgba(46,143,214,0.25) inset, 0 0 8px rgba(46,143,214,0.15);
        margin-bottom: 14px;
    }
    .stat-row { display:flex; justify-content:space-between; font-family: monospace;
        font-size: 15px; color:#d7f0ff; padding: 2px 0; }
    .rank-badge { font-size: 26px; font-weight:800; color:#ffd166;
        text-shadow: 0 0 10px rgba(255,209,102,0.6); }
    .quest-done { color:#7effa0 !important; text-decoration: line-through; opacity:0.7; }
    div[data-testid="stMetricValue"] { color:#7ee3ff; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Connection check
# ----------------------------------------------------------------------------
ok, msg = gh.connection_ok()
if not ok:
    st.error(
        "**Can't reach the System's data store.**\n\n"
        f"{msg}\n\n"
        "Add `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_PATH` (and optionally "
        "`GITHUB_BRANCH`) to your Streamlit secrets — see `.streamlit/secrets.toml.example` "
        "and the README."
    )
    st.stop()

# ----------------------------------------------------------------------------
# Load state (once per session; cached in st.session_state after that)
# ----------------------------------------------------------------------------
if "state" not in st.session_state:
    default_state = {
        "player": sl.new_player(),
        "quests": sl.default_quests(),
        "log": [],
        "last_seen": sl.today_str(),
    }
    with st.spinner("Connecting to the System..."):
        st.session_state.state = gh.load_state(default_state)

state = st.session_state.state
player = state["player"]
quests = state["quests"]


def persist(message: str):
    """Save current state back to GitHub and keep the sha in sync."""
    new_sha = gh.save_state(state, message=message)
    state["_sha"] = new_sha


def log_events(events: list[str]):
    for e in events:
        state["log"].insert(0, {"date": dt.datetime.now().isoformat(timespec="seconds"), "text": e})
    state["log"] = state["log"][:200]


# ----------------------------------------------------------------------------
# New-day check: apply penalties for quests missed the previous day
# ----------------------------------------------------------------------------
if state.get("last_seen") != sl.today_str():
    penalty_events = sl.apply_daily_penalty(player, quests)
    state["last_seen"] = sl.today_str()
    if penalty_events:
        log_events(penalty_events)
    persist("System: daily rollover" + (" + penalties" if penalty_events else ""))
    if penalty_events:
        st.toast("⚠️ Penalty Zone triggered for missed quests", icon="⚠️")

# ----------------------------------------------------------------------------
# Header / Status Window
# ----------------------------------------------------------------------------
st.title("🗡️ THE SYSTEM")

with st.container():
    st.markdown('<div class="system-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        st.markdown(f"### {player['name']}")
        st.caption(player.get("title", "Awakened"))
        with st.expander("Edit name / title"):
            new_name = st.text_input("Name", value=player["name"])
            new_title = st.text_input("Title", value=player.get("title", "Awakened"))
            if st.button("Save profile"):
                player["name"], player["title"] = new_name, new_title
                persist("System: update profile")
                st.rerun()

    with col2:
        rank = sl.rank_for_level(player["level"])
        st.markdown(f"<div class='rank-badge'>{rank}-RANK</div>", unsafe_allow_html=True)
        st.metric("Level", player["level"])

    with col3:
        need = sl.xp_to_next_level(player["level"])
        st.write(f"XP: **{player['xp']} / {need}**")
        st.progress(min(player["xp"] / need, 1.0))
        if player["stat_points"] > 0:
            st.warning(f"🔺 {player['stat_points']} unspent stat point(s) available")

    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Stats panel
# ----------------------------------------------------------------------------
st.markdown('<div class="system-box">', unsafe_allow_html=True)
st.subheader("Status")

stat_cols = st.columns(5)
for i, (stat, value) in enumerate(player["stats"].items()):
    with stat_cols[i]:
        st.metric(sl.STAT_LABELS.get(stat, stat), value)

if player["stat_points"] > 0:
    alloc_col, btn_col = st.columns([3, 1])
    with alloc_col:
        chosen_stat = st.selectbox(
            "Allocate a stat point",
            options=list(player["stats"].keys()),
            format_func=lambda s: sl.STAT_LABELS.get(s, s),
            key="alloc_select",
        )
    with btn_col:
        st.write("")
        st.write("")
        if st.button(f"Apply ({player['stat_points']} left)"):
            if sl.allocate_stat_point(player, chosen_stat):
                log_events([f"+1 {sl.STAT_LABELS.get(chosen_stat, chosen_stat)} (manual allocation)"])
                persist("System: allocate stat point")
                st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Daily Quests
# ----------------------------------------------------------------------------
st.markdown('<div class="system-box">', unsafe_allow_html=True)
st.subheader("📜 Daily Quest")

daily = [q for q in quests if q["category"] == "daily"]
custom = [q for q in quests if q["category"] == "custom"]

any_change = False
for quest in daily + custom:
    done = sl.is_completed_today(quest)
    c1, c2, c3 = st.columns([0.5, 5, 1.5])
    with c1:
        checked = st.checkbox("", value=done, key=f"chk_{quest['id']}", disabled=done)
    with c2:
        label_class = "quest-done" if done else ""
        st.markdown(
            f"<span class='{label_class}'><b>{quest['name']}</b> — {quest['description']} "
            f"<i>(+{quest['xp']} XP, streak {quest['streak']})</i></span>",
            unsafe_allow_html=True,
        )
    with c3:
        st.caption("✅ Done today" if done else "Pending")

    if checked and not done:
        events = sl.complete_quest(player, quest)
        log_events(events)
        any_change = True
        for e in events:
            if e.startswith("LEVEL UP"):
                st.balloons()
        st.toast(f"Quest complete: {quest['name']}", icon="✅")

if any_change:
    persist("System: quest completed")
    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Add a custom quest
# ----------------------------------------------------------------------------
with st.expander("➕ Add a custom quest"):
    with st.form("add_quest_form", clear_on_submit=True):
        q_name = st.text_input("Quest name")
        q_desc = st.text_input("Description")
        q_xp = st.number_input("XP reward", min_value=5, max_value=500, value=20, step=5)
        q_stat = st.selectbox(
            "Stat rewarded",
            options=[""] + list(player["stats"].keys()),
            format_func=lambda s: "None" if s == "" else sl.STAT_LABELS.get(s, s),
        )
        submitted = st.form_submit_button("Add Quest")
        if submitted and q_name:
            sl.add_custom_quest(quests, q_name, q_desc, int(q_xp), q_stat)
            persist("System: add custom quest")
            st.success(f"Quest added: {q_name}")
            st.rerun()

# ----------------------------------------------------------------------------
# Quest log / history
# ----------------------------------------------------------------------------
with st.expander("📖 Quest Log", expanded=False):
    if not state["log"]:
        st.caption("No events yet. Complete a quest to begin your record.")
    for entry in state["log"][:50]:
        st.write(f"`{entry['date']}` — {entry['text']}")

st.caption(
    "Data is stored in your connected GitHub repository as the single source of truth. "
    "Every completed quest, penalty, and level-up is committed automatically."
)
