import json
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path("data")
SAVE_DIR = Path("saves")
SAVE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SkillAction:
    id: str
    name: str
    item_id: str
    required_level: int
    action_value: float
    flavor: str


@dataclass
class SkillDefinition:
    id: str
    name: str
    description: str
    base_rate: float
    rate_per_level: float
    actions: List[SkillAction] = field(default_factory=list)

    def gather_rate(self, level: int) -> float:
        return self.base_rate + self.rate_per_level * max(level, 1)


class DataRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.items = self._load_items()
        self.skills = self._load_skills()

    def _load_items(self) -> Dict[str, Dict]:
        items_path = self.data_dir / "items.json"
        with items_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return {item["id"]: item for item in raw.get("items", [])}

    def _load_skills(self) -> Dict[str, SkillDefinition]:
        skills_dir = self.data_dir / "skills"
        skills = {}
        for path in skills_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            actions = [
                SkillAction(
                    id=a["id"],
                    name=a["name"],
                    item_id=a["item_id"],
                    required_level=a["required_level"],
                    action_value=a["action_value"],
                    flavor=a.get("flavor", ""),
                )
                for a in raw.get("actions", [])
            ]
            skills[raw["id"]] = SkillDefinition(
                id=raw["id"],
                name=raw["name"],
                description=raw.get("description", ""),
                base_rate=raw.get("base_rate", 1.0),
                rate_per_level=raw.get("rate_per_level", 0.2),
                actions=actions,
            )
        return skills


class SaveManager:
    def __init__(self, save_dir: Path):
        self.save_dir = save_dir

    def list_saves(self) -> List[str]:
        return [p.stem for p in self.save_dir.glob("*.json")]

    def save(self, player_name: str, state: Dict):
        path = self.save_dir / f"{player_name}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load(self, player_name: str) -> Optional[Dict]:
        path = self.save_dir / f"{player_name}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)


class NotificationManager:
    def __init__(self, frame: tk.Frame):
        self.frame = frame
        self.queue: List[str] = []
        self.active_labels: List[tk.Label] = []
        self.frame.config(height=180)
        self.frame.pack_propagate(False)

    def push(self, message: str):
        self.queue.append(message)
        self._process_queue()

    def _process_queue(self):
        if not self.queue:
            return
        if len(self.active_labels) >= 6:
            return
        message = self.queue.pop(0)
        label = tk.Label(
            self.frame,
            text=message,
            bg="#1f2937",
            fg="#f3f4f6",
            relief=tk.RIDGE,
            padx=8,
            pady=4,
            borderwidth=2,
        )
        label.update_idletasks()
        start_y = self.frame.winfo_height() - 10
        label.place(relx=0.5, y=start_y, anchor="s")
        self.active_labels.append(label)
        self._animate_label(label, 0)

    def _animate_label(self, label: tk.Label, step: int):
        if step >= 35:
            if label in self.active_labels:
                self.active_labels.remove(label)
            label.destroy()
            self._process_queue()
            return
        current_y = label.winfo_y()
        label.place_configure(y=current_y - 3)
        self.frame.after(40, lambda: self._animate_label(label, step + 1))


class IdleGameApp(tk.Tk):
    TICK_MS = 1000

    def __init__(self):
        super().__init__()
        self.title("Runescape-Inspired Idle Prototype")
        self.geometry("1200x800")
        self.configure(bg="#0f172a")

        self.data_repo = DataRepository(DATA_DIR)
        self.save_manager = SaveManager(SAVE_DIR)
        self.player_state: Optional[Dict] = None
        self.current_activity: Optional[Dict] = None
        self.progress_amount: float = 0.0
        self.active_skill: Optional[SkillDefinition] = None
        self.active_skill_ui: Dict[str, Dict[str, tk.Widget]] = {}
        self.active_tab: Optional[str] = None
        self.image_cache: Dict[str, tk.PhotoImage] = {}

        self.loading_frame: Optional[tk.Frame] = None
        self.main_frame: Optional[tk.Frame] = None

        self._build_loading_screen()

    # -------------------------- UI BUILDERS --------------------------
    def _build_loading_screen(self):
        if self.main_frame:
            self.main_frame.destroy()
        self.loading_frame = tk.Frame(self, bg="#0f172a", padx=20, pady=20)
        self.loading_frame.pack(expand=True, fill=tk.BOTH)

        tk.Label(
            self.loading_frame,
            text="Load Character",
            font=("Segoe UI", 24, "bold"),
            fg="#e5e7eb",
            bg="#0f172a",
        ).pack(pady=(0, 16))

        saves = self.save_manager.list_saves()
        self.save_listbox = tk.Listbox(self.loading_frame, height=6, bg="#111827", fg="#e5e7eb")
        for name in saves:
            self.save_listbox.insert(tk.END, name)
        self.save_listbox.pack(fill=tk.X, pady=6)

        tk.Label(
            self.loading_frame,
            text="New character name",
            fg="#cbd5e1",
            bg="#0f172a",
        ).pack(pady=(12, 4))
        self.name_entry = tk.Entry(self.loading_frame)
        self.name_entry.insert(0, "Adventurer")
        self.name_entry.pack(fill=tk.X)

        btn_frame = tk.Frame(self.loading_frame, bg="#0f172a")
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="Load Selected", command=self._load_selected).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Create & Start", command=self._create_new).pack(side=tk.LEFT, padx=6)

    def _build_game_shell(self):
        if self.loading_frame:
            self.loading_frame.destroy()
        self.main_frame = tk.Frame(self, bg="#0f172a")
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        # Grid weights
        self.main_frame.columnconfigure(0, weight=1, minsize=220)
        self.main_frame.columnconfigure(1, weight=2, minsize=520)
        self.main_frame.columnconfigure(2, weight=1, minsize=260)
        self.main_frame.rowconfigure(0, weight=5)
        self.main_frame.rowconfigure(1, weight=0, minsize=140)

        self.left_pane = tk.Frame(self.main_frame, bg="#111827", padx=10, pady=10)
        self.left_pane.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._build_left_activities()

        self.center_pane = tk.Frame(self.main_frame, bg="#0b1224", padx=10, pady=10)
        self.center_pane.grid(row=0, column=1, sticky="nsew")
        self._build_center_content()

        self.right_pane = tk.Frame(self.main_frame, bg="#111827", padx=10, pady=10)
        self.right_pane.grid(row=0, column=2, rowspan=2, sticky="nsew")
        self._build_right_tabs()

        self.summary_pane = tk.Frame(self.main_frame, bg="#0b132c", padx=12, pady=8, height=140)
        self.summary_pane.grid(row=1, column=1, sticky="nsew")
        self.summary_pane.grid_propagate(False)
        self._build_summary()

        self.notification_frame = tk.Frame(self.center_pane, bg="#0b1224")
        self.notification_frame.pack(side=tk.BOTTOM, anchor="s")
        self.notifications = NotificationManager(self.notification_frame)

    def _build_left_activities(self):
        tk.Label(
            self.left_pane,
            text="Activities",
            font=("Segoe UI", 16, "bold"),
            fg="#f8fafc",
            bg="#111827",
        ).pack(anchor="w")

        self.activities_list = tk.Listbox(self.left_pane, activestyle="dotbox", bg="#0f172a", fg="#e5e7eb")
        self.activities_list.pack(expand=True, fill=tk.BOTH, pady=8)

        for skill in self.data_repo.skills.values():
            self.activities_list.insert(tk.END, skill.name)
        self.activities_list.bind("<<ListboxSelect>>", self._on_activity_select)

    def _build_center_content(self):
        self.center_header = tk.Label(
            self.center_pane,
            text="Select an activity to begin",
            font=("Segoe UI", 14, "bold"),
            fg="#e2e8f0",
            bg="#0b1224",
        )
        self.center_header.pack(anchor="w")

        self.center_subheader = tk.Label(
            self.center_pane,
            text="",
            font=("Segoe UI", 10),
            fg="#cbd5e1",
            bg="#0b1224",
        )
        self.center_subheader.pack(anchor="w")

        self.center_body = tk.Frame(self.center_pane, bg="#0b1224")
        self.center_body.pack(expand=True, fill=tk.BOTH, pady=8)

    def _build_right_tabs(self):
        tabs = [
            "Inventory",
            "Stats",
            "Collection Log",
            "Equipment",
            "Settings",
            "Debug",
        ]
        self.tab_buttons: List[tk.Button] = []
        tab_frame = tk.Frame(self.right_pane, bg="#111827")
        tab_frame.pack(pady=(0, 10))
        for idx, label in enumerate(tabs):
            btn = tk.Button(
                tab_frame,
                text=label,
                width=12,
                command=lambda l=label: self._show_tab(l),
            )
            btn.grid(row=idx // 3, column=idx % 3, padx=4, pady=4)
            self.tab_buttons.append(btn)

        self.tab_content_frame = tk.Frame(self.right_pane, bg="#0f172a")
        self.tab_content_frame.pack(expand=True, fill=tk.BOTH)
        self._show_tab("Inventory")

    def _build_summary(self):
        self.summary_title = tk.Label(
            self.summary_pane,
            text="Current Activity: None",
            font=("Segoe UI", 12, "bold"),
            fg="#e5e7eb",
            bg="#0b132c",
        )
        self.summary_title.pack(anchor="w")

        self.summary_progress = tk.Label(
            self.summary_pane,
            text="Progress: 0% | XP gain: 0/s",
            fg="#cbd5e1",
            bg="#0b132c",
        )
        self.summary_progress.pack(anchor="w", pady=4)

        self.save_button = tk.Button(self.summary_pane, text="Save Now", command=self._manual_save)
        self.save_button.pack(anchor="e", pady=4)

    # -------------------------- GAME FLOW --------------------------
    def _on_activity_select(self, event):
        selection = self.activities_list.curselection()
        if not selection:
            return
        selected_name = self.activities_list.get(selection[0])
        skill = next((s for s in self.data_repo.skills.values() if s.name == selected_name), None)
        if skill:
            self._render_skill(skill)

    def _render_skill(self, skill: SkillDefinition):
        for child in self.center_body.winfo_children():
            child.destroy()
        self.active_skill = skill
        self.active_skill_ui = {}

        skill_state = self.player_state["skills"].get(skill.id, {"level": 1, "xp": 0})
        player_level = skill_state.get("level", 1)
        xp_display = self._format_number(skill_state.get("xp", 0))
        self.center_header.config(text=f"{skill.name}")
        self.center_subheader.config(text=f"Level {player_level} | XP {xp_display}")

        for action in skill.actions:
            state = tk.NORMAL if player_level >= action.required_level else tk.DISABLED
            frame = tk.Frame(self.center_body, bg="#111827", padx=10, pady=10)
            frame.pack(fill=tk.X, pady=6)

            item = self.data_repo.items.get(action.item_id, {})
            icon = self._get_image(item.get("image"))
            icon_label = tk.Label(frame, image=icon, bg="#111827")
            icon_label.image = icon
            icon_label.grid(row=0, column=0, rowspan=3, padx=(0, 10))

            tk.Label(
                frame,
                text=f"{action.name} ({item.get('name', '')})",
                fg="#f8fafc",
                bg="#111827",
                font=("Segoe UI", 12, "bold"),
            ).grid(row=0, column=1, sticky="w")

            details = f"Tier {item.get('tier', action.required_level)} | Value {self._format_number(item.get('value', 0))} | Req Lvl {action.required_level}"
            tk.Label(frame, text=details, fg="#cbd5e1", bg="#111827").grid(row=1, column=1, sticky="w")

            rate = skill.gather_rate(player_level)
            seconds = action.action_value / rate if rate else 0
            tk.Label(
                frame,
                text=f"Gather rate {self._format_number(rate)}/s | {seconds:.1f}s per log",
                fg="#9ca3af",
                bg="#111827",
            ).grid(row=2, column=1, sticky="w")

            btn = tk.Button(
                frame,
                text="Gather",
                state=state,
                command=lambda a=action, s=skill: self._start_activity(s, a),
                width=10,
            )
            btn.grid(row=0, column=2, rowspan=3, padx=(10, 0))
            self.active_skill_ui[action.id] = {"button": btn, "frame": frame, "rate_label": None}

    def _start_activity(self, skill: SkillDefinition, action: SkillAction):
        self.current_activity = {
            "skill": skill,
            "action": action,
            "progress": 0.0,
        }
        self.progress_amount = 0.0
        self.summary_title.config(text=f"Current Activity: {skill.name} - {action.name}")
        self._update_summary_progress()
        self.notifications.push(f"Started {action.name}")

    def _update_summary_progress(self):
        if not self.current_activity:
            self.summary_progress.config(text="Progress: 0% | XP gain: 0/s")
            return
        skill = self.current_activity["skill"]
        level = self.player_state["skills"][skill.id]["level"]
        rate = skill.gather_rate(level)
        action_value = self.current_activity["action"].action_value
        progress_pct = min(100, (self.progress_amount / action_value) * 100)
        self.summary_progress.config(
            text=f"Progress: {progress_pct:.1f}% | XP gain: {self._format_number(rate)}/s"
        )

    def _manual_save(self):
        if self.player_state:
            self.save_manager.save(self.player_state["name"], self.player_state)
            self.notifications.push("Game saved.")

    def _tick(self):
        if self.current_activity:
            skill: SkillDefinition = self.current_activity["skill"]
            action: SkillAction = self.current_activity["action"]
            skill_state = self.player_state["skills"].setdefault(
                skill.id, {"xp": 0.0, "level": 1, "actions": {}}
            )
            rate = skill.gather_rate(skill_state["level"])
            # XP gain per second equals gather rate.
            skill_state["xp"] += rate
            self._recalculate_level(skill.id)
            self.notifications.push(f"+{self._format_number(rate)} {skill.name} XP")

            self.progress_amount += rate
            if self.progress_amount >= action.action_value:
                self.progress_amount -= action.action_value
                self._grant_item(action.item_id, 1)
                actions_log = skill_state.setdefault("actions", {})
                actions_log[action.id] = actions_log.get(action.id, 0) + 1
                self.notifications.push(f"Gathered {self.data_repo.items[action.item_id]['name']}")
            self._update_summary_progress()
            self._refresh_active_skill_view()
        self._refresh_active_tab()
        self.after(self.TICK_MS, self._tick)

    def _grant_item(self, item_id: str, qty: int):
        inv = self.player_state.setdefault("inventory", {})
        inv[item_id] = inv.get(item_id, 0) + qty
        item_log = self.player_state.setdefault("collection_log", {}).setdefault("items", {})
        item_log[item_id] = item_log.get(item_id, 0) + qty

    def _recalculate_level(self, skill_id: str):
        skill_state = self.player_state["skills"].setdefault(skill_id, {"xp": 0.0, "level": 1})
        xp = skill_state["xp"]
        # Simple leveling curve for prototype.
        level = max(1, int(xp // 100) + 1)
        if level != skill_state["level"]:
            skill_state["level"] = level
            self.notifications.push(f"{self.data_repo.skills[skill_id].name} leveled to {level}!")
            if self.active_skill and self.active_skill.id == skill_id:
                self._refresh_active_skill_view()

    def _refresh_active_skill_view(self):
        if not self.active_skill:
            return
        skill = self.active_skill
        skill_state = self.player_state["skills"].get(skill.id, {"level": 1, "xp": 0})
        level = skill_state.get("level", 1)
        xp_display = self._format_number(skill_state.get("xp", 0))
        self.center_subheader.config(text=f"Level {level} | XP {xp_display}")
        rate = skill.gather_rate(level)
        for action in skill.actions:
            ui = self.active_skill_ui.get(action.id)
            if not ui:
                continue
            allowed = level >= action.required_level
            ui["button"].config(state=tk.NORMAL if allowed else tk.DISABLED)
            # Update time display row 2 column 1
            for widget in ui["frame"].grid_slaves(row=2, column=1):
                seconds = action.action_value / rate if rate else 0
                widget.config(text=f"Gather rate {self._format_number(rate)}/s | {seconds:.1f}s per log")

    def _show_tab(self, tab_name: str):
        self.active_tab = tab_name
        for child in self.tab_content_frame.winfo_children():
            child.destroy()

        if tab_name == "Inventory":
            self.inventory_frame = tk.Frame(self.tab_content_frame, bg="#0f172a")
            self.inventory_frame.pack(expand=True, fill=tk.BOTH)
            self._render_inventory_tab()
        elif tab_name == "Stats":
            self.stats_frame = tk.Frame(self.tab_content_frame, bg="#0f172a")
            self.stats_frame.pack(expand=True, fill=tk.BOTH)
            self._render_stats_tab()
        elif tab_name == "Collection Log":
            self.collection_frame = tk.Frame(self.tab_content_frame, bg="#0f172a")
            self.collection_frame.pack(expand=True, fill=tk.BOTH)
            self._render_collection_tab()
        else:
            msg = {
                "Equipment": "Equipment slots coming soon.",
                "Settings": "Settings will cover audio, UI, and accessibility.",
                "Debug": "Debug tools will enable live editing of items and recipes.",
            }.get(tab_name, "")
            tk.Label(
                self.tab_content_frame,
                text=msg,
                fg="#e5e7eb",
                bg="#0f172a",
                justify=tk.LEFT,
            ).pack(anchor="nw", padx=6, pady=6)

    def _render_inventory_tab(self):
        frame = self.inventory_frame
        for child in frame.winfo_children():
            child.destroy()
        inventory = self.player_state.get("inventory", {})
        if not inventory:
            tk.Label(frame, text="Inventory empty", fg="#e5e7eb", bg="#0f172a").pack(anchor="w", padx=8, pady=4)
            return
        columns = 4
        row = col = 0
        for item_id, qty in sorted(inventory.items()):
            item = self.data_repo.items.get(item_id, {"name": item_id})
            cell = tk.Frame(frame, width=96, height=96, bg="#111827", relief=tk.RIDGE, borderwidth=2)
            cell.grid(row=row, column=col, padx=6, pady=6)
            cell.grid_propagate(False)
            icon = self._get_image(item.get("image"))
            icon_label = tk.Label(cell, image=icon, bg="#111827")
            icon_label.image = icon
            icon_label.place(relx=0.5, rely=0.5, anchor="center")
            if qty > 1:
                tk.Label(
                    cell,
                    text=self._format_number(qty),
                    fg="#f9fafb",
                    bg="#111827",
                    font=("Segoe UI", 10, "bold"),
                ).place(relx=0.9, rely=0.1, anchor="ne")
            tk.Label(cell, text=item.get("name", item_id), fg="#e5e7eb", bg="#111827").place(relx=0.5, rely=0.95, anchor="s")
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def _render_stats_tab(self):
        self.stats_labels = {}
        for child in self.stats_frame.winfo_children():
            child.destroy()
        for idx, (skill_id, state) in enumerate(self.player_state.get("skills", {}).items()):
            skill = self.data_repo.skills.get(skill_id)
            if not skill:
                continue
            row_frame = tk.Frame(self.stats_frame, bg="#0f172a")
            row_frame.pack(anchor="w", pady=4, padx=6)
            tk.Label(row_frame, text=skill.name, fg="#f8fafc", bg="#0f172a", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
            lvl_label = tk.Label(row_frame, text="", fg="#cbd5e1", bg="#0f172a")
            lvl_label.grid(row=1, column=0, sticky="w")
            self.stats_labels[skill_id] = lvl_label
        self._update_stats_labels()

    def _render_collection_tab(self):
        frame = self.collection_frame
        for child in frame.winfo_children():
            child.destroy()
        tk.Label(frame, text="Collection Log", fg="#f8fafc", bg="#0f172a", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=6, pady=(0, 6))
        items_frame = tk.Frame(frame, bg="#0f172a")
        items_frame.pack(anchor="w")
        item_log = self.player_state.get("collection_log", {}).get("items", {})
        if not item_log:
            tk.Label(items_frame, text="No items collected yet.", fg="#e5e7eb", bg="#0f172a").pack(anchor="w")
        else:
            for item_id, qty in sorted(item_log.items()):
                item = self.data_repo.items.get(item_id, {"name": item_id})
                tk.Label(
                    items_frame,
                    text=f"{item.get('name', item_id)}: {self._format_number(qty)}",
                    fg="#e5e7eb",
                    bg="#0f172a",
                ).pack(anchor="w")
        actions_frame = tk.Frame(frame, bg="#0f172a")
        actions_frame.pack(anchor="w", pady=(8, 0))
        tk.Label(actions_frame, text="Actions", fg="#f8fafc", bg="#0f172a", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        any_actions = False
        for skill_id, skill_state in self.player_state.get("skills", {}).items():
            actions = skill_state.get("actions", {})
            if not actions:
                continue
            any_actions = True
            skill = self.data_repo.skills.get(skill_id)
            tk.Label(actions_frame, text=skill.name, fg="#e5e7eb", bg="#0f172a", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            for action_id, count in actions.items():
                tk.Label(
                    actions_frame,
                    text=f" - {action_id}: {self._format_number(count)} times",
                    fg="#cbd5e1",
                    bg="#0f172a",
                ).pack(anchor="w", padx=10)
        if not any_actions:
            tk.Label(actions_frame, text="No actions logged yet.", fg="#e5e7eb", bg="#0f172a").pack(anchor="w")

    def _update_stats_labels(self):
        for skill_id, label in getattr(self, "stats_labels", {}).items():
            state = self.player_state.get("skills", {}).get(skill_id, {"level": 1, "xp": 0})
            text = f"Level {state.get('level', 1)} | XP {self._format_number(state.get('xp', 0))}"
            label.config(text=text)

    def _refresh_active_tab(self):
        if self.active_tab == "Inventory":
            self._render_inventory_tab()
        elif self.active_tab == "Stats":
            self._update_stats_labels()
        elif self.active_tab == "Collection Log":
            self._render_collection_tab()

    def _get_image(self, path: Optional[str]) -> tk.PhotoImage:
        if not path:
            return tk.PhotoImage(width=64, height=64)
        if path in self.image_cache:
            return self.image_cache[path]
        file_path = Path(path)
        if not file_path.exists():
            placeholder = tk.PhotoImage(width=64, height=64)
            placeholder.put("#1f2937", to=(0, 0, 64, 64))
            self.image_cache[path] = placeholder
            return placeholder
        image = tk.PhotoImage(file=str(file_path))
        self.image_cache[path] = image
        return image

    @staticmethod
    def _format_number(value: float) -> str:
        suffixes = [
            (1_000_000_000_000, "T"),
            (1_000_000_000, "B"),
            (1_000_000, "M"),
            (1_000, "K"),
        ]
        abs_val = abs(value)
        for threshold, suffix in suffixes:
            if abs_val >= threshold:
                return f"{value / threshold:.2f}{suffix}"
        if abs_val < 1000 and value % 1 == 0:
            return f"{int(value)}"
        return f"{value:.2f}"

    # -------------------------- SAVE/LOAD --------------------------
    def _load_selected(self):
        selection = self.save_listbox.curselection()
        if not selection:
            return
        name = self.save_listbox.get(selection[0])
        loaded = self.save_manager.load(name)
        if loaded:
            self.player_state = loaded
            self._enter_game()

    def _create_new(self):
        name = self.name_entry.get().strip() or "Adventurer"
        self.player_state = {
            "name": name,
            "inventory": {},
            "skills": {sk: {"xp": 0.0, "level": 1, "actions": {}} for sk in self.data_repo.skills},
            "collection_log": {"items": {}, "skills": {}, "entities": {}},
        }
        self.save_manager.save(name, self.player_state)
        self._enter_game()

    def _enter_game(self):
        self._build_game_shell()
        self._tick()


def main():
    app = IdleGameApp()
    app.mainloop()


if __name__ == "__main__":
    main()
