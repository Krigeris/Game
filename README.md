# Idle Game Prototype

This repository hosts a prototype for a Runescape-inspired idle game focused on gathering, production, and combat skills. The current build focuses on the **Woodcutting** skill and a UI shell for future expansion.

## Features
- Loading screen for creating or loading characters (JSON saves stored in `saves/`).
- Paneled UI: left activity selector, center activity details, right tabbed panels (inventory, stats, collection log, etc.), and a bottom activity summary.
- Woodcutting loop that gains XP every second based on your gather rate and periodically grants logs.
- Notification stack above the summary pane for XP and item rewards.
- Game data defined in JSON (`data/items.json`, `data/skills/woodcutting.json`) for easy editing.

## Running the prototype
```bash
python main.py
```

### Controls
- **Create & Start** on the loading screen to make a new character, or select an existing save and choose **Load Selected**.
- Choose **Woodcutting** in the activities pane, then select a tree to begin chopping.
- Use the tabs on the right to view inventory, stats, and your collection log.
- Click **Save Now** in the summary pane to write progress to your character file.

## Saving and files
- Saves live in `saves/<character>.json`.
- Items and skills are data-driven; extend them by editing the JSON files under `data/`.

## Branch reminder
To keep changes on the main branch:
```bash
git checkout main
# after your work
git add .
git commit -m "Your message"
git push origin main
```
