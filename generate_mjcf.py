"""Generate the merobot MuJoCo model (merobot.xml) from the part files.

Reads parts/*.json for meshes, sizes, masses and servo specs, and sensors.json
for the sensors. The robot layout (which part sits where, which servo drives
which joint) mirrors robot_structure.md and is written out in ORIENT, layout()
and TREE below.

World frame: x = our right (looking at the robot from the front),
y = away from us (the robot faces -y, toward us), z = up. Units in this file: mm.

Usage:
    python generate_mjcf.py          # writes merobot.xml
"""

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
PARTS = ROOT / "parts"
OUT = ROOT / "merobot.xml"

# ---------------------------------------------------------------------------
# Assumptions not (yet) in the part files
# ---------------------------------------------------------------------------
SERVO_VARIANT = "7.4V"           # sts3215.json: variant_in_use is still null
SHAFT_FROM_SERVO_END = 11.0      # mm from the servo's end at the holder's open end (estimate)
GAP = 5.0                        # mm clearance between parts next to a joint
BOX_SIZE = (125.0, 50.0, 70.0)   # head_box / box_body: width (= servo 3 + servo 4), depth, height (estimate)
PLACEHOLDER_MASS_G = {"head_box": 80.0, "box_body": 150.0}
KP = 20.0                        # position gain, N*m/rad (not calibrated)
ARMATURE = 0.012                 # reflected rotor inertia, kg*m^2: coreless rotor ~1e-7 x gear ratio 345^2 (estimate)
SERVO_TIMECONST = 0.02           # s: servo responds to a new target with this lag (first-order, estimate)
FRICTIONLOSS = 0.05              # N*m (estimate)
JOINT_RANGE_DEG = 90.0
IMU_BANDWIDTH_HZ = 44.0          # MPU6050 low-pass filter setting assumed for the noise level below


def load(name):
    return json.loads((PARTS / f"{name}.json").read_text(encoding="utf-8"))


SENSORS = json.loads((ROOT / "sensors.json").read_text(encoding="utf-8"))["sensors"]
SERVO = load("servo")
STS = load("sts3215")
FOOT = load("foot")
HOLDER = SERVO["holder"]
ROD = SERVO["connecting_rod"]

# ---------------------------------------------------------------------------
# Servo unit frame: origin on the shaft axis, mid-way between the two wheels.
#   X = shaft axis (mesh x), Z = toward the socket face (mesh z), Y = Z x X.
# ---------------------------------------------------------------------------
cav = HOLDER["servo_cavity"]["servo_box_estimate_mm"]
SHAFT_MESH = np.array([
    (cav["min"][0] + cav["max"][0]) / 2,
    (cav["min"][1] + cav["max"][1]) / 2,
    cav["min"][2] + SHAFT_FROM_SERVO_END,
])
HOLDER_MIN = np.array(HOLDER["bounds_mm"]["min"]) - SHAFT_MESH
HOLDER_MAX = np.array(HOLDER["bounds_mm"]["max"]) - SHAFT_MESH
SERVO_BOX_CENTER = (np.array(cav["min"]) + np.array(cav["max"])) / 2 - SHAFT_MESH
SERVO_BOX_HALF = (np.array(cav["max"]) - np.array(cav["min"])) / 2

sockets = HOLDER["rod_sockets"]
ROD_X = (sockets["x_centers_mm"][1] - sockets["x_centers_mm"][0]) / 2   # rods sit at X = +-ROD_X
ROD_REACH = ROD["wheel_axis_to_mating_face_mm"]                         # shaft -> next part's face
# Rod mesh: point at the centre of the disc (wheel axis), on the rod's mid-plane.
ROD_DISC_MESH = np.array([45.74, 19.3, 67.65])

# Foot mesh: centre of its socket pairs on the top face.
FOOT_ATTACH_MESH = np.array([
    np.mean(FOOT["rod_sockets"]["x_centers_mm"]),
    np.mean(FOOT["rod_sockets"]["y_centers_mm"]),
    FOOT["bounds_mm"]["max"][2],
])

AXES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}


def orientation(shaft, socket):
    """Rotation matrix whose columns are the world directions of unit X, Y, Z."""
    x, z = np.array(AXES[shaft], float), np.array(AXES[socket], float)
    return np.column_stack([x, np.cross(z, x), z])


def world_extent(R):
    """World-frame (min, max) of a servo unit's holder, relative to its shaft point."""
    corners = np.array([[a, b, c] for a in (HOLDER_MIN[0], HOLDER_MAX[0])
                        for b in (HOLDER_MIN[1], HOLDER_MAX[1]) for c in (HOLDER_MIN[2], HOLDER_MAX[2])])
    w = corners @ R.T
    return w.min(0), w.max(0)


def quat(R):
    """Rotation matrix -> MuJoCo quaternion (w x y z)."""
    m = R
    t = np.trace(m)
    if t > 0:
        s = np.sqrt(t + 1) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    else:
        i = int(np.argmax(np.diag(m)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = np.sqrt(1 + m[i, i] - m[j, j] - m[k, k]) * 2
        q = [0.0] * 4
        q[0] = (m[k, j] - m[j, k]) / s
        q[i + 1] = 0.25 * s
        q[j + 1] = (m[j, i] + m[i, j]) / s
        q[k + 1] = (m[k, i] + m[i, k]) / s
    q = np.array(q)
    return q / np.linalg.norm(q)


# ---------------------------------------------------------------------------
# Robot layout (mirrors robot_structure.md)
#
# Servo orientation: "shaft" = world direction of the shaft axis,
#                    "socket" = world direction the holder's socket face points.
# ---------------------------------------------------------------------------
ORIENT = {
    1:  ("+z", "+x"),   # rotor points up, turns the head_box
    2:  ("+x", "+z"),   # swings back/forward, rods go down into box_body
    3:  ("-z", "+x"),   # horizontal, rotor points down
    4:  ("-z", "-x"),
    6:  ("-y", "+z"),   # vertical, rotor points forward: tilts servo 5 left/right
    7:  ("-y", "+z"),
    5:  ("-y", "+x"),   # horizontal, fixed to the front of servo 9
    8:  ("-y", "-x"),
    9:  ("+x", "+z"),   # vertical, swings servo 11 back/forward
    10: ("+x", "+z"),
    11: ("+x", "+z"),   # vertical, swings the foot back/forward
    12: ("+x", "+z"),
}
R = {sid: orientation(*o) for sid, o in ORIENT.items()}
EXT = {sid: world_extent(r) for sid, r in R.items()}


def layout():
    """World positions (mm) at zero pose: servo shaft points and box/foot centres."""
    W, D, H = BOX_SIZE
    P = {"box_body": np.array([0.0, 0.0, 0.0])}
    body_top, body_bottom = H / 2, -H / 2

    # Neck: servo 2 drives the body through its rods; servo 1 sits flush on servo 2.
    P[2] = np.array([0.0, 0.0, body_top + ROD_REACH])
    lo1, hi1 = EXT[1]
    s2_top = P[2][2] + EXT[2][1][2]
    P[1] = np.array([-(lo1[0] + hi1[0]) / 2, 0.0, s2_top - lo1[2]])
    P["head_box"] = np.array([0.0, 0.0, P[1][2] + hi1[2] + GAP + H / 2])

    for side, (hip, mid, out, upper, lower) in {-1: (3, 6, 5, 9, 11), +1: (4, 7, 8, 10, 12)}.items():
        # Hip servo under the body, its outer edge flush with the body side.
        lo, hi = EXT[hip]
        x = side * W / 2 - (hi[0] if side > 0 else lo[0])
        P[hip] = np.array([x, 0.0, body_bottom - hi[2]])
        # Middle servo hangs under the hip servo, centred on its (vertical) shaft.
        lo_m, hi_m = EXT[mid]
        P[mid] = np.array([P[hip][0], 0.0, P[hip][2] + EXT[hip][0][2] - GAP - hi_m[2]])
        # Outer hip servo beside the middle servo, bottoms level.
        lo_o, hi_o = EXT[out]
        mid_edge = P[mid][0] + (lo_m[0] if side < 0 else hi_m[0])
        x = mid_edge - GAP - hi_o[0] if side < 0 else mid_edge + GAP - lo_o[0]
        P[out] = np.array([x, 0.0, P[mid][2] + lo_m[2] - lo_o[2]])
        # Upper leg servo: outer hip servo is fixed to its front, tops aligned.
        lo_u, hi_u = EXT[upper]
        out_center_x = P[out][0] + (lo_o[0] + hi_o[0]) / 2
        P[upper] = np.array([
            out_center_x - (lo_u[0] + hi_u[0]) / 2,
            P[out][1] + hi_o[1] - lo_u[1],
            P[out][2] + hi_o[2] - hi_u[2],
        ])
        # Lower leg servo: its socket face sits ROD_REACH below the upper servo's shaft.
        P[lower] = P[upper] + np.array([0.0, 0.0, -ROD_REACH - EXT[lower][1][2]])
        # Foot: its top face sits ROD_REACH below the lower servo's shaft.
        P[f"foot_{'left' if side < 0 else 'right'}"] = P[lower] + np.array([0.0, 0.0, -ROD_REACH])
    return P


# Kinematic tree: (body, parent, joint driven by servo / None, joint anchor servo, axis)
TREE = [
    ("servo2", "box_body", 2),
    ("servo1", "servo2", None),
    ("head_box", "servo1", 1),
    ("servo3", "box_body", None),
    ("servo6", "servo3", 3),
    ("servo5", "servo6", 6),
    ("servo9", "servo5", None),
    ("servo11", "servo9", 9),
    ("foot_left", "servo11", 11),
    ("servo4", "box_body", None),
    ("servo7", "servo4", 4),
    ("servo8", "servo7", 7),
    ("servo10", "servo8", None),
    ("servo12", "servo10", 10),
    ("foot_right", "servo12", 12),
]
# Joints driven through connecting rods: rods are bolted to the driving servo's wheels
# and plug into the part on the other side (they belong to that part's body).
RODS = {2: "box_body", 9: "servo11", 10: "servo12", 11: "foot_left", 12: "foot_right"}


def fmt(v, digits=5):
    return " ".join(f"{x:.{digits}g}" if abs(x) > 1e-9 else "0" for x in v)


def build():
    P = layout()
    # Lift the robot so the feet stand on the floor.
    foot_bottom = P["foot_left"][2] + (FOOT["bounds_mm"]["min"][2] - FOOT_ATTACH_MESH[2])
    lift = np.array([0.0, 0.0, -foot_bottom + 0.5])
    origin = {k: v + lift for k, v in P.items()}
    origin = {(f"servo{k}" if isinstance(k, int) else k): v for k, v in origin.items()}

    geoms = {name: [] for name in origin}
    mm = 0.001

    def servo_geoms(sid):
        name, r, q = f"servo{sid}", R[sid], fmt(quat(R[sid]))
        geoms[name].append(
            f'<geom name="{name}_holder" type="mesh" mesh="servo_holder" class="visual" '
            f'pos="{fmt(-(r @ SHAFT_MESH) * mm)}" quat="{q}" mass="{HOLDER["mass_g"] / 1000}"/>')
        geoms[name].append(
            f'<geom name="{name}_sts3215" type="box" material="servo" class="visual" '
            f'pos="{fmt(r @ SERVO_BOX_CENTER * mm)}" quat="{q}" size="{fmt(SERVO_BOX_HALF * mm)}" mass="{STS["mass_g"] / 1000}"/>')
        for s in (+1, -1):  # wheel discs
            geoms[name].append(
                f'<geom type="cylinder" class="rotor" pos="{fmt(r @ np.array([s * (SERVO_BOX_HALF[0] + 1), 0, 0]) * mm)}" '
                f'zaxis="{fmt(r[:, 0])}"/>')

    for sid in R:
        servo_geoms(sid)

    for name in ("head_box", "box_body"):
        geoms[name].append(
            f'<geom name="{name}" type="box" material="box" class="visual" size="{fmt(np.array(BOX_SIZE) / 2 * mm)}" '
            f'mass="{PLACEHOLDER_MASS_G[name] / 1000}"/>')

    for name in ("foot_left", "foot_right"):
        geoms[name].append(
            f'<geom name="{name}" type="mesh" mesh="foot" material="foot" pos="{fmt(-FOOT_ATTACH_MESH * mm)}" '
            f'mass="{FOOT["mass_g"] / 1000}"/>')

    # Connecting rods (two per servo, one on each wheel).
    for sid, owner in RODS.items():
        r, shaft = R[sid], origin[f"servo{sid}"]
        for s in (+1, -1):
            flip = np.diag([s, s, 1.0])        # 180 deg about Z for the rod on the -X side
            rr = r @ flip
            pos = shaft + r @ np.array([s * ROD_X, 0, 0]) - rr @ ROD_DISC_MESH - origin[owner]
            geoms[owner].append(
                f'<geom name="rod_servo{sid}_{"a" if s > 0 else "b"}" type="mesh" mesh="connecting_rod" material="rod" '
                f'class="visual" pos="{fmt(pos * mm)}" quat="{fmt(quat(rr))}" mass="{ROD["mass_g"] / 1000}"/>')

    # IMU sites: one per IMU in sensors.json, on the part it is mounted on.
    sensor_xml = []
    for sensor in SENSORS:
        if sensor["type"] == "imu":
            body = sensor["mounted_on"]
            pos = np.array(sensor["mount"]["position_mm"] or (0.0, 0.0, 0.0))  # default: centre of the part
            geoms[body].append(f'<site name="{sensor["name"]}" pos="{fmt(pos * mm)}" size="0.006" rgba="0 .8 1 1"/>')
            # MuJoCo stores sensor noise but does not apply it; training code adds it.
            sqrt_bw = np.sqrt(IMU_BANDWIDTH_HZ)
            gyro = sensor["measures"]["gyroscope"]
            accel = sensor["measures"]["accelerometer"]
            gyro_noise = np.radians(gyro["noise_density_deg_s_per_sqrt_hz"]) * sqrt_bw        # rad/s
            accel_noise = accel["noise_density_ug_per_sqrt_hz"] * 1e-6 * 9.81 * sqrt_bw     # m/s^2
            sensor_xml.append(f'    <gyro name="{sensor["name"]}_gyro" site="{sensor["name"]}" noise="{gyro_noise:.2g}"/>')
            sensor_xml.append(f'    <accelerometer name="{sensor["name"]}_accel" site="{sensor["name"]}" noise="{accel_noise:.2g}"/>')
        elif sensor["type"] == "servo_internal":
            for d in sorted(d for _, _, d in TREE if d is not None):
                sensor_xml.append(f'    <jointpos name="servo{d}_pos" joint="servo{d}"/>')
                sensor_xml.append(f'    <jointvel name="servo{d}_vel" joint="servo{d}"/>')
                sensor_xml.append(f'    <actuatorfrc name="servo{d}_load" actuator="servo{d}"/>')

    joint_of = {}
    for body, parent, driver in TREE:
        if driver is not None:
            anchor = origin[f"servo{driver}"] - origin[body]
            axis = R[driver][:, 0]
            joint_of[body] = (f'<joint name="servo{driver}" pos="{fmt(anchor * mm)}" axis="{fmt(axis)}"/>', driver)

    children = {}
    for body, parent, _ in TREE:
        children.setdefault(parent, []).append(body)

    def emit(body, parent, indent):
        pad = "  " * indent
        pos = origin[body] - (origin[parent] if parent else 0)
        out = [f'{pad}<body name="{body}" pos="{fmt(pos * mm)}">']
        if parent is None:
            out.append(f"{pad}  <freejoint name=\"root\"/>")  # the body is free to move in the world
        if body in joint_of:
            out.append(f"{pad}  {joint_of[body][0]}")
        out += [f"{pad}  {g}" for g in geoms[body]]
        for child in children.get(body, []):
            out += emit(child, body, indent + 1)
        out.append(f"{pad}</body>")
        return out

    variant = STS["variants"][SERVO_VARIANT]
    stall = variant["stall_torque_nm"]
    damping = stall / variant["no_load_speed_rad_s"]
    drivers = [d for _, _, d in TREE if d is not None]

    bodies = "\n".join(emit("box_body", None, 2))
    actuators = "\n".join(f'    <position name="servo{d}" joint="servo{d}"/>' for d in sorted(drivers))
    return f"""<!--
  merobot - generated by generate_mjcf.py from parts/*.json and robot_structure.md. Do not edit by hand.

  World frame: x = our right (looking at the robot from the front), y = away from us
  (the robot faces -y), z = up. Each joint is named after the servo that drives it.
  Servo model: STS3215 {SERVO_VARIANT} (stall {stall} N*m, damping {damping:.3f} = stall torque / no-load speed,
  armature {ARMATURE} kg*m^2, response lag {SERVO_TIMECONST} s).
  box_body has a freejoint: the robot stands on the floor and can fall.
-->
<mujoco model="merobot">
  <compiler angle="degree" meshdir="parts" inertiafromgeom="true"/>
  <option timestep="0.002" integrator="implicitfast"/>

  <visual>
    <global offwidth="1600" offheight="1200"/>
    <headlight ambient=".35 .35 .35" diffuse=".5 .5 .5"/>
  </visual>

  <default>
    <geom contype="0" conaffinity="1"/>  <!-- parts touch the floor, not each other -->
    <joint type="hinge" range="-{JOINT_RANGE_DEG} {JOINT_RANGE_DEG}" damping="{damping:.4f}" armature="{ARMATURE}" frictionloss="{FRICTIONLOSS}"/>
    <position kp="{KP}" ctrlrange="-1.57 1.57" forcerange="-{stall} {stall}" timeconst="{SERVO_TIMECONST}"/>
    <default class="visual">
      <geom material="pla"/>
    </default>
    <default class="rotor">
      <geom size="0.008 0.001" material="rotor" mass="0" conaffinity="0"/>
    </default>
  </default>

  <asset>
    <mesh name="servo_holder" file="{HOLDER['mesh']}" scale="0.001 0.001 0.001" inertia="convex"/>
    <mesh name="connecting_rod" file="{ROD['mesh']}" scale="0.001 0.001 0.001" inertia="convex"/>
    <mesh name="foot" file="{FOOT['mesh']}" scale="0.001 0.001 0.001" inertia="convex"/>
    <texture type="skybox" builtin="gradient" rgb1=".55 .6 .68" rgb2=".15 .17 .2" width="512" height="512"/>
    <texture name="grid" type="2d" builtin="checker" rgb1=".2 .25 .3" rgb2=".25 .3 .35" width="300" height="300" mark="edge" markrgb=".4 .45 .5"/>
    <material name="grid" texture="grid" texrepeat="8 8" reflectance=".1"/>
    <material name="pla" rgba=".72 .75 .8 1"/>
    <material name="servo" rgba=".12 .12 .14 1"/>
    <material name="box" rgba=".55 .6 .66 1"/>
    <material name="rod" rgba=".95 .55 .15 1"/>
    <material name="foot" rgba=".95 .45 .1 1"/>
    <material name="rotor" rgba=".95 .95 .95 1"/>
  </asset>

  <worldbody>
    <light pos="0.3 -0.6 0.8" dir="-0.3 0.6 -0.8" diffuse=".8 .8 .8"/>
    <light pos="-0.4 0.3 0.6" dir="0.4 -0.3 -0.6" diffuse=".3 .3 .3"/>
    <geom name="floor" type="plane" size="0.6 0.6 0.01" material="grid" contype="1" conaffinity="1"/>
{bodies}
  </worldbody>

  <actuator>
{actuators}
  </actuator>

  <!-- From sensors.json. Noise values are standard deviations; MuJoCo does not apply them itself. -->
  <sensor>
{chr(10).join(sensor_xml)}
  </sensor>
</mujoco>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
