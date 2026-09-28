# [Solo Leveling — Real Life System (Streamlit)](https://y-level-up.streamlit.app)

A habit tracker styled after the "Solo Leveling / Life RPG" concept:
an avatar card, a skill radar chart, a weekly activity heatmap, skill
XP bars, and an activity log — with data saved straight to a GitHub
repo, so it persists across sessions and devices.

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Create a place on GitHub to store your data

1. Make a small repo (public or private), e.g. `habit-tracker-data`.
2. Create a GitHub **fine-grained personal access token**:
   Settings → Developer settings → Personal access tokens → Fine-grained tokens.
   - Repository access: only the repo above.
   - Permissions: **Contents → Read and write**.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
   and fill in `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`.
   (Alternatively, leave secrets.toml empty and paste the token into the
   sidebar each time — it's only kept in memory for that session.)

`.streamlit/secrets.toml` is already the standard place Streamlit reads
secrets from — **don't commit it**, add it to `.gitignore`.

## 3. Run

```bash
streamlit run app.py
```

## 4. Use it

- **Sidebar → Load**: pulls `habit_tracker_data.json` from your repo (or
  starts fresh if it doesn't exist yet).
- **Sidebar → Log Activity**: pick a skill, choose "Gain XP" for a good
  habit or "Lose HP" for a bad one, add a note, and log it. Skills level
  up every 500 XP; your overall character level is the average skill
  level; HP represents a health/energy pool that bad habits drain and
  good ones (or "Restore HP") refill.
- **Sidebar → Save**: commits the updated JSON back to your GitHub repo.
  Do this after logging activities you want to keep — nothing is
  persisted automatically.
- **Avatar**: upload any image in the sidebar to replace the default icon.

## 5. Deploying (optional)

To run this from anywhere (e.g. your phone), deploy it on
[Streamlit Community Cloud](https://streamlit.io/cloud) pointing at a
repo containing this app, and add the same three keys under
**App settings → Secrets** in the dashboard instead of a local file.

## Data model

Everything lives in one JSON file (`habit_tracker_data.json` by default)
committed to your GitHub repo:

```json
{
  "player": {"name": "...", "level": 1, "coins": 0, "hp": 1000, "hp_max": 1000, "avatar_b64": null},
  "skills": {"Writing": {"xp": 0, "level": 1}, "...": {}},
  "activities": [{"ts": "...", "skill": "...", "kind": "xp_gain", "amount": 5, "note": "Workout"}]
}
```

Feel free to edit `SKILLS` in `app.py` to match whatever stats you
actually want to track.
