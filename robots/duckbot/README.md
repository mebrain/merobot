# Duckbot

Duckbot is the duck-style biped currently being developed in this repository.
Its simulation uses MuJoCo; standing policies use Stable-Baselines3 PPO.

- [Structure](robot_structure.md), using the [shared notation](../../standard/structure_notation.md).
- [Simulation notes](NOTES.md), including assumptions and outstanding measurements.
- [Parts](parts/) and [sensors](sensors.json).
- `generate_mjcf.py` generates `duckbot.xml` from the part definitions and the layout encoded in the script. It does not parse the structure document.
- `render_views.py` renders the model to `images/duckbot_views.png`.
- `train_stand.py` trains, plays, and evaluates standing policies.

From the repository root in PowerShell, using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe robots/duckbot/generate_mjcf.py
.\.venv\Scripts\python.exe robots/duckbot/render_views.py
.\.venv\Scripts\python.exe robots/duckbot/train_stand.py --steps 3000000
.\.venv\Scripts\python.exe robots/duckbot/train_stand.py --play robots/duckbot/runs/stand/<run>
.\.venv\Scripts\python.exe robots/duckbot/train_stand.py --analyze robots/duckbot/runs/stand/<run>
```

Model inputs and generated outputs are resolved relative to this robot directory.
The `--play` and `--analyze` arguments are paths relative to the current working directory.
Training outputs and local images are kept in ignored `runs/` and `images/` directories.
