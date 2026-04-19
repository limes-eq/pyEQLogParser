from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, send_from_directory
from eqlogparser.config import Config
from eqlogparser.log_processor import process_file
from eqlogparser.record_manager import RecordManager
from eqlogparser.player_manager import PlayerManager
from eqlogparser.data_manager import DataManager
from eqlogparser.fight_analyzer import detect_fights, aggregate_fights, build_timelines, Fight

def _template_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "web", "templates")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


app = Flask(__name__, template_folder=_template_dir())

_current_fights: list[Fight] = []


@app.route("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


def _tkinter_browse(title: str, filetypes: list) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return path or ""


@app.route("/api/browse")
def browse():
    path = _tkinter_browse(
        "Select EverQuest log file",
        [("Log files", "*.txt *.log"), ("All files", "*.*")],
    )
    return jsonify({"path": path})


@app.route("/api/browse-spells")
def browse_spells():
    path = _tkinter_browse(
        "Select spells_us.txt",
        [("Spell data", "spells_us.txt"), ("Text files", "*.txt"), ("All files", "*.*")],
    )
    return jsonify({"path": path})


@app.route("/api/spell-file", methods=["POST"])
def set_spell_file():
    data = request.get_json(force=True)
    path = (data.get("path") or "").strip()
    if not path or not os.path.exists(path):
        return jsonify({"error": f"File not found: {path}"}), 400
    try:
        DataManager.instance().load_spell_file(path)
        count = len(DataManager.instance()._spells_by_name)
        return jsonify({"ok": True, "spells_loaded": count, "path": path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/spell-file-path")
def get_spell_file_path():
    from eqlogparser.data_manager import _DEFAULT_SPELL_FILE
    current = DataManager.instance()._current_spell_file or _DEFAULT_SPELL_FILE
    return jsonify({"path": current, "loaded": len(DataManager.instance()._spells_by_name)})


@app.route("/api/parse", methods=["POST"])
def parse_log():
    global _current_fights
    data = request.get_json(force=True)
    import time as _time
    path = (data.get("path") or "").strip()
    player = (data.get("player") or "").strip()
    time_filter = data.get("time_filter", "all")
    _FILTER_HOURS = {"1h": 1, "24h": 24, "3d": 72, "7d": 168, "14d": 336}
    since = _time.time() - _FILTER_HOURS[time_filter] * 3600 if time_filter in _FILTER_HOURS else 0.0

    if not path or not os.path.exists(path):
        return jsonify({"error": f"File not found: {path}"}), 400

    if not player:
        import re
        m = re.match(r"eqlog_([^_]+)_", os.path.basename(path), re.IGNORECASE)
        if m:
            player = m.group(1)

    Config.player_name = player

    from eqlogparser.parsing import damage_line_parser
    RecordManager._instance = None
    PlayerManager._instance = None
    damage_line_parser.reset()
    # DataManager holds the spell DB — reset records but keep the loaded spell file
    DataManager.instance().reset_combat_state()

    process_file(path, since=since)
    rm = RecordManager.instance()
    _current_fights = detect_fights(rm)

    return jsonify({
        "fights": [_summarize(f) for f in _current_fights],
        "count": len(_current_fights),
    })


@app.route("/api/fights")
def list_fights():
    return jsonify([_summarize(f) for f in _current_fights])


@app.route("/api/detail", methods=["POST"])
def get_detail():
    data = request.get_json(force=True)
    ids = set(data.get("ids", []))
    selected = [f for f in _current_fights if f.id in ids]
    if not selected:
        return jsonify({"error": "No fights selected"}), 404
    return jsonify(aggregate_fights(selected))


@app.route("/api/timeline", methods=["POST"])
def get_timeline():
    data = request.get_json(force=True)
    ids = set(data.get("ids", []))
    selected = [f for f in _current_fights if f.id in ids]
    if not selected:
        return jsonify({"error": "No fights selected"}), 404
    return jsonify(build_timelines(selected))


def _summarize(f: Fight) -> dict:
    return {
        "id": f.id,
        "mob": f.mob,
        "start_time": f.start_time,
        "duration": round(f.duration),
        "total_damage": f.total_damage,
        "dps": round(f.total_damage / f.duration, 1),
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
