"""Train merobot to stand upright with PPO (Stable-Baselines3, CPU).

The policy runs at 50 Hz. Every step it reads what the real robot can measure:
  - imu_body gyro and accelerometer (with MPU6050-like noise, see sensors.json)
  - position and speed of the 10 driven servo joints
  - its own previous action and the servo targets currently commanded
and outputs a desired angle for each of the 10 servos (around the zero pose).
The desired angles are smoothed and speed-limited before they reach the servos,
like a real servo command stream, so the policy cannot learn to buzz.

Usage (run with the project venv: .venv/Scripts/python.exe):
    python train_stand.py                      # train, saves to runs/stand/<time>/
    python train_stand.py --steps 5000000      # train longer
    python train_stand.py --play runs/stand/<time>    # watch a trained policy in the viewer
    python train_stand.py --analyze runs/stand/<time> # how long it stands, how smooth it is
"""

import argparse
import time
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np

ROOT = Path(__file__).parent
MODEL = ROOT / "merobot.xml"

CONTROL_HZ = 50
EPISODE_SECONDS = 10
ACTION_SCALE = 0.26         # rad: action +-1 -> target +-15 deg around the zero pose
TARGET_SMOOTHING = 0.5      # each step the target moves this fraction toward the desired angle
SERVO_MAX_SPEED = 4.4       # rad/s: STS3215 7.4V no-load speed (parts/sts3215.json) ...
MAX_TARGET_STEP = SERVO_MAX_SPEED / 50  # ... so a target may move at most ~5 deg per 20 ms step
MAX_TILT_DEG = 40           # episode ends when the body tilts further than this
MAX_DROP = 0.08             # m: ... or drops further than this below its start height
JOINT_POS_NOISE = 0.002     # rad (encoder: 0.0015 rad per step)
JOINT_VEL_NOISE = 0.05      # rad/s


class StandEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, push_newtons=0.0, seed=None):
        self.model = mujoco.MjModel.from_xml_path(str(MODEL))
        self.data = mujoco.MjData(self.model)
        self.frame_skip = round(1 / (CONTROL_HZ * self.model.opt.timestep))
        self.max_steps = EPISODE_SECONDS * CONTROL_HZ
        self.push_newtons = push_newtons
        self.rng = np.random.default_rng(seed)

        m = self.model
        self.body = m.body("box_body").id
        self.servos = [m.actuator(i).name for i in range(m.nu)]
        self.qadr = np.array([m.joint(n).qposadr[0] for n in self.servos])
        self.dadr = np.array([m.joint(n).dofadr[0] for n in self.servos])
        self.gyro = m.sensor("imu_body_gyro")
        self.accel = m.sensor("imu_body_accel")
        self.gyro_noise = float(self.gyro.noise[0])
        self.accel_noise = float(self.accel.noise[0])
        self.floor = m.geom("floor").id
        self.base_friction = m.geom_friction[self.floor].copy()

        mujoco.mj_forward(m, self.data)
        self.start_height = float(self.data.xpos[self.body][2])

        n = m.nu
        self.action_space = gym.spaces.Box(-1.0, 1.0, (n,), np.float32)
        obs_dim = 3 + 3 + n + n + n + n
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, (obs_dim,), np.float32)
        self.last_action = np.zeros(n)
        self.target = np.zeros(n)

    # -- helpers ---------------------------------------------------------------
    def _tilt(self):
        up_z = self.data.xmat[self.body][8]   # body z-axis . world z
        return float(np.arccos(np.clip(up_z, -1, 1)))

    def _obs(self):
        d, r = self.data, self.rng
        gyro = d.sensordata[self.gyro.adr[0]:self.gyro.adr[0] + 3] + r.normal(0, self.gyro_noise, 3)
        accel = d.sensordata[self.accel.adr[0]:self.accel.adr[0] + 3] + r.normal(0, self.accel_noise, 3)
        qpos = d.qpos[self.qadr] + r.normal(0, JOINT_POS_NOISE, len(self.qadr))
        qvel = d.qvel[self.dadr] + r.normal(0, JOINT_VEL_NOISE, len(self.dadr))
        return np.concatenate([gyro, accel / 9.81, qpos, qvel * 0.1, self.last_action,
                               self.target / ACTION_SCALE]).astype(np.float32)

    # -- gym API -----------------------------------------------------------------
    def reset(self, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        m, d, r = self.model, self.data, self.rng
        mujoco.mj_resetData(m, d)
        d.qpos[self.qadr] += r.uniform(-0.05, 0.05, len(self.qadr))
        m.geom_friction[self.floor] = self.base_friction * r.uniform(0.6, 1.2)
        self.last_action = np.zeros(m.nu)
        self.target = np.zeros(m.nu)
        self.steps = 0
        self.next_push = r.uniform(1.0, 3.0)
        mujoco.mj_forward(m, d)
        return self._obs(), {}

    def step(self, action):
        m, d, r = self.model, self.data, self.rng
        action = np.clip(action, -1, 1)
        # Smooth the desired angles, then limit how far each target may move this step.
        desired = ACTION_SCALE * action
        move = np.clip(TARGET_SMOOTHING * (desired - self.target), -MAX_TARGET_STEP, MAX_TARGET_STEP)
        self.target = self.target + move
        d.ctrl[:] = self.target

        # Optional random shove on the body (lasts one control step), to learn to recover.
        if self.push_newtons and d.time >= self.next_push:
            direction = r.normal(size=2)
            d.xfrc_applied[self.body, :2] = self.push_newtons * direction / np.linalg.norm(direction)
            self.next_push = d.time + r.uniform(2.0, 4.0)
        for _ in range(self.frame_skip):
            mujoco.mj_step(m, d)
        d.xfrc_applied[self.body, :3] = 0
        self.steps += 1

        tilt = self._tilt()
        height = float(d.xpos[self.body][2])
        body_angvel = d.qvel[3:6]
        joint_vel = d.qvel[self.dadr]
        effort = d.actuator_force
        reward = (
            1.0                                                        # alive
            + 1.0 * np.exp(-(tilt / 0.2) ** 2)                         # upright
            + 0.5 * np.exp(-((height - self.start_height) / 0.03) ** 2)  # at standing height
            - 0.1 * np.mean(d.qpos[self.qadr] ** 2)                    # near the zero pose
            - 0.05 * float(np.sum((action - self.last_action) ** 2))   # calm servo commands
            - 0.005 * float(joint_vel @ joint_vel)                     # joints not rushing around
            - 0.02 * float(effort @ effort)                            # low servo effort
            - 0.05 * float(body_angvel @ body_angvel)                  # body not wobbling
        )
        self.last_action = action

        fell = tilt > np.radians(MAX_TILT_DEG) or height < self.start_height - MAX_DROP
        terminated = bool(fell)
        truncated = self.steps >= self.max_steps
        return self._obs(), float(reward), terminated, truncated, {"tilt_deg": np.degrees(tilt)}


def make_env(rank, push):
    def _init():
        return StandEnv(push_newtons=push, seed=rank)
    return _init


def train(args):
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor, VecNormalize

    out = ROOT / "runs" / "stand" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    env = VecNormalize(VecMonitor(SubprocVecEnv([make_env(i, args.push) for i in range(args.envs)])),
                       norm_obs=True, norm_reward=True, clip_obs=10.0)
    model = PPO(
        "MlpPolicy", env,
        n_steps=256, batch_size=4096, n_epochs=5, learning_rate=3e-4,
        gamma=0.99, gae_lambda=0.95, clip_range=0.2, ent_coef=0.0,
        policy_kwargs={"net_arch": [256, 256], "log_std_init": -1.0},
        tensorboard_log=str(out), verbose=1, device="cpu",
    )
    model.learn(total_timesteps=args.steps)
    model.save(out / "policy")
    env.save(str(out / "vecnormalize.pkl"))
    print(f"saved to {out}")


def load_policy(run, push=0.0, seed=0):
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

    run = Path(run)
    venv = VecNormalize.load(str(run / "vecnormalize.pkl"),
                             DummyVecEnv([lambda: StandEnv(push_newtons=push, seed=seed)]))
    venv.training = False
    venv.norm_reward = False
    return PPO.load(run / "policy", device="cpu"), venv


def play(args):
    import mujoco.viewer

    policy, venv = load_policy(args.play, args.push)
    env = venv.venv.envs[0]

    obs = venv.reset()
    steps = 0
    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        while viewer.is_running():
            start = time.perf_counter()
            action, _ = policy.predict(obs, deterministic=True)
            obs, _, done, info = venv.step(action)
            steps += 1
            if done[0]:
                # The env resets itself, so count the steps here rather than reading the sim time.
                how = "time limit reached" if steps >= env.max_steps else "fell over"
                print(f"episode ended after {steps / CONTROL_HZ:.1f} s: {how}, restarting")
                steps = 0
            viewer.sync()
            time.sleep(max(0.0, 1 / CONTROL_HZ - (time.perf_counter() - start)))


def analyze(args):
    """Report how long the policy stands, and how calm or jerky its servo commands are."""
    for push in (0.0, 5.0, 10.0):
        policy, venv = load_policy(args.analyze, push, seed=123)
        obs, lengths = venv.reset(), []
        for _ in range(20):
            n = 0
            while True:
                obs, _, done, _ = venv.step(policy.predict(obs, deterministic=True)[0])
                n += 1
                if done[0]:
                    break
            lengths.append(n / CONTROL_HZ)
        lengths = np.array(lengths)
        print(f"push {push:4.0f} N: stood the full {EPISODE_SECONDS} s in {np.sum(lengths >= EPISODE_SECONDS)}/20, "
              f"mean {lengths.mean():.1f} s, worst {lengths.min():.1f} s")

    policy, venv = load_policy(args.analyze, seed=7)
    env = venv.venv.envs[0]
    obs, targets, actions, joint_vel, body_vel = venv.reset(), [], [], [], []
    for _ in range(400):
        action = policy.predict(obs, deterministic=True)[0]
        obs, _, done, _ = venv.step(action)
        if done[0]:
            break
        actions.append(np.clip(action[0], -1, 1))
        targets.append(env.target.copy())
        joint_vel.append(env.data.qvel[env.dadr].copy())
        body_vel.append(env.data.qvel[3:6].copy())
    targets, actions = np.array(targets)[50:], np.array(actions)[50:]
    step = np.abs(np.diff(targets, axis=0))
    flips = (np.diff(np.sign(np.diff(targets, axis=0)), axis=0) != 0).mean()
    print(f"servo target change per step: mean {np.degrees(step.mean()):.2f} deg, max {np.degrees(step.max()):.2f} deg")
    print(f"target direction reversals:   {flips * 100:.0f} % of steps")
    print(f"actions at their limit:       {(np.abs(actions) >= 0.99).mean() * 100:.0f} %")
    print(f"joint speed rms:              {np.degrees(np.sqrt((np.array(joint_vel)[50:] ** 2).mean())):.1f} deg/s")
    print(f"body wobble rms:              {np.degrees(np.sqrt((np.array(body_vel)[50:] ** 2).sum(1).mean())):.1f} deg/s")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--steps", type=int, default=3_000_000)
    p.add_argument("--envs", type=int, default=16)
    p.add_argument("--push", type=float, default=0.0, help="random shove on the body, newtons (0 = off)")
    p.add_argument("--play", help="run folder of a trained policy to watch")
    p.add_argument("--analyze", help="run folder of a trained policy to evaluate")
    args = p.parse_args()
    if args.analyze:
        analyze(args)
    elif args.play:
        play(args)
    else:
        train(args)
