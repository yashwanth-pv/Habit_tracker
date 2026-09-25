# The System 🗡️

A Solo-Leveling-inspired self-improvement tracker built with Streamlit. No database —
your **GitHub repo is the save file**. Every quest completion, level-up, and stat
allocation is committed straight to a JSON file in a repo you own via the GitHub API.

## Features

- Hunter status window: Level, Rank (E → S), XP bar, 5 core stats (STR/VIT/AGI/INT/PER)
- Daily quests with streaks, XP rewards, and stat rewards
- Level-up system with allocatable stat points
- **Penalty Zone**: missing a daily quest resets its streak and docks XP the next day
- Add your own custom quests
- Full quest log / history
- Zero external database — state lives in `data/save.json` inside your GitHub repo

## How the storage works

`github_storage.py` reads and writes a single JSON file in a repo you specify, using
the GitHub [Contents API](https://docs.github.com/en/rest/repos/contents):

- On load: `GET /repos/{repo}/contents/{path}` — decodes the base64 JSON.
- On every change: `PUT /repos/{repo}/contents/{path}` — commits the updated JSON
  (using the previous `sha` so GitHub treats it as an update, not a new file).
- If the file doesn't exist yet, it's created automatically on first run.

This means your quest history is literally a git commit history — you can see every
change in the repo's commit log.

## Setup

### 1. Create a repo for your save data

You can reuse the same repo you deploy the app from, or use a separate private repo
just for data. Either way, decide on a path, e.g. `data/save.json`.

### 2. Create a GitHub Personal Access Token

1. GitHub → Settings → Developer settings → **Fine-grained personal access tokens**
2. **Generate new token**, scope it to the one repo you chose above
3. Under **Repository permissions**, set **Contents: Read and write**
4. Generate and copy the token (you won't see it again)

### 3. Configure secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

```toml
GITHUB_TOKEN  = "github_pat_..."
GITHUB_REPO   = "your-username/your-repo"
GITHUB_PATH   = "data/save.json"
GITHUB_BRANCH = "main"
```

`.streamlit/secrets.toml` is already in `.gitignore` — **never commit your real
token**.

### 4. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 5. Deploy on Streamlit Community Cloud

1. Push this project to a GitHub repo (the app code itself — can be the same repo
   as your data, or a different one)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → pick the
   repo and `app.py` as the entrypoint
3. In **App settings → Secrets**, paste the same four keys/values from step 3
4. Deploy — the app will read/write `GITHUB_PATH` in `GITHUB_REPO` on every action

## Project structure

```
app.py                  # Streamlit UI — status window, quests, log
system_logic.py         # Pure game logic: XP curve, ranks, leveling, penalties
github_storage.py        # GitHub Contents API read/write helpers
requirements.txt
.streamlit/secrets.toml.example
```

## Customizing

- **Starter quests**: edit `default_quests()` in `system_logic.py`
- **XP curve**: edit `xp_to_next_level()` (currently `100 * 1.12^(level-1)`)
- **Rank thresholds**: edit the `thresholds` list in `rank_for_level()`
- **Penalty severity**: edit `apply_daily_penalty()` (currently 25% of a quest's XP)
- **Look and feel**: the CSS block at the top of `app.py`

## Notes

- This app has no login system — it's a single-player save file per repo. If you
  want multiple users, point each person at their own `GITHUB_PATH` or repo.
- The GitHub API has rate limits (5,000 requests/hour for an authenticated PAT),
  which is far more than a personal daily-quest tracker will ever hit.
