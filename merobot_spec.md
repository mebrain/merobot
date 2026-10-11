# merobot – Structure Notation Spec

How we write down the structure of the robot as text. The robot itself is described in [robot_structure.md](robot_structure.md).

_Draft. We are still working on this spec._

---

## 1. Parts

- The robot is made of **re-usable parts**. Each part type is specified once, in the `parts/` folder.
- **A cell holds the exact `name` of a part file**, e.g. `servo`, `foot`, `head_box`, `box_body`, so the table can be matched to `parts/<name>.json`.
- **A servo and its holder are one unit: `servo`** (`parts/servo.json`, marked `"servo_holder": true`). They are never written separately. The servo model inside it (`sts3215`) is referenced from that file and never appears in the table.
- **Every servo has a numerical ID** so it can be referenced, written in the cell as `servo <ID>`, e.g. `servo 5`.
  IDs are unique and numbered in reading order: top to bottom, and left to right within a row.
- **The height of a servo cell shows its orientation**, as seen from the front:
  - a servo standing **vertically, facing us**, is **two bars** (text lines) tall, with its label on the **lower** line;
  - a servo lying **horizontally** is **one bar** tall.

```
│     servo 5     │   ← horizontal
├────────⊙────────┤
│                 │
│     servo 9     │   ← vertical, facing us
```

- **Sensors are written inside the cell of the part they are mounted on**, as `{ sensor_name }`. The name matches an entry in `sensors.json`.

```
│           { imu_body }          │
│             box_body            │
```

## 2. The table

The structure is a Unicode box-drawing table, wrapped in a code block so it renders in a monospace font.

- **Each row is one level of the hierarchy**, read from top (head) to bottom (feet).
- **Columns are left to right as we see the robot from the front.** "Left" always means **our** left, looking at the robot.
- **Each cell holds one object only.** Links between objects are never cells.
- **A cell spans the full width** when it is a single object in the middle (head, body).
- **Physically separate objects in the same row get a gap between their cells**, e.g. the two legs:

```
│     servo 9     │   │     servo 10    │
```

## 3. Links

Links are drawn only on the borders between cells.

### Rigid link

The two cells share a border. A rigid link is marked on that border with **one of three symbols**:

| Symbol | Meaning |
|---|---|
| `⊙` | the upper object sits **in front of** the lower one |
| `⊗` | the upper object sits **behind** the lower one |
| `=` | the two objects are **aligned**, neither juts out to the front or back |

Left, right, up and down can be seen in the table itself. Only front and behind cannot, which is why every rigid link carries one of these symbols.

```
│     servo 5     │
├────────⊙────────┤
│                 │
│     servo 9     │
```

Servo 5 is fixed to the front of servo 9.

No symbol on a shared border means the two cells are not connected.

### Joint

Two objects connected by a joint are **separated**. The upper cell narrows into a stem that plugs into the lower cell:

```
│                 │
│     servo 11    │
└──────┐   ┌──────┘
       ↓   ↓
       ○   ○
┌──────┘   └──────┐
│      foot       │
```

**The joint type is written on the separator (the stem).**

**Arrows are only used on joint stems, never for a rigid link.** They show which object moves: they point from the servo that drives the joint toward the circles. The object on the other side of the circles is the one that swings. In the example, servo 11 drives the joint and the foot swings.

### Sideways joint (draft)

Two objects side by side in the same row can also be joined by a joint. The driving servo's border narrows into a short sideways stem; the arrow points from it toward the circle, and the object on the other side of the circle moves:

```
                    ┌─────────────┐
┌─────────────┐     │             │
│   servo 5   │ ○←──┤   servo 6   │
└─────────────┘     └─────────────┘
```

Servo 6 drives the joint and servo 5 moves. One circle: the rotator points forward (back–forward axis), so servo 5 tilts to the left and right.

## 4. Joint types

The joint type is shown by where the circles sit on the stem, as seen from the front:

| Separator | Rotation axis | Meaning |
|---|---|---|
| `○   ○`, circles replace the left and right bars of the stem | Left–right | The lower object swings back and forward |
| `│ ○ │`, circle at the top of the stem | Back–forward | The lower object tilts to the left and right |
| `↓ ○ ↓`, one circle between the arrows | Vertical: the rotor points along the arrows (`↓` down, `↑` up) | The driven object turns parallel to the ground |
| `│ ? │` | Not decided yet | It is a joint, but its type is still to be specified |

Swings back and forward (e.g. a foot):

```
│                 │
│     servo 11    │
└──────┐   ┌──────┘
       ↓   ↓
       ○   ○
┌──────┘   └──────┐
│      foot       │
```

Rotor points down, the servo below turns parallel to the ground:

```
│     servo 3     │
└──────┐   ┌──────┘
       ↓ ○ ↓
┌──────┘   └──────┐
│                 │
│     servo 6     │
```

## 5. Open points

- Sideways joint: the symbol for a **left–right axis** on a sideways stem.
