"""Render merobot.xml from several angles into images/merobot_views.png (servo IDs labelled).

Usage:
    python render_views.py
"""

from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
W, H = 700, 760


def main():
    m = mujoco.MjModel.from_xml_path(str(ROOT / "merobot.xml"))
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, H, W)
    font = ImageFont.truetype("arialbd.ttf", 16)
    big = ImageFont.truetype("arialbd.ttf", 20)
    center = (0, 0.02, 0.23)

    def shot(az, el, title, pose=None, labels=False, dist=0.95, lookat=center):
        mujoco.mj_resetData(m, d)
        for j, v in (pose or {}).items():
            d.qpos[m.joint(j).qposadr[0]] = np.radians(v)
        mujoco.mj_forward(m, d)
        cam = mujoco.MjvCamera()
        cam.azimuth, cam.elevation, cam.distance = az, el, dist
        cam.lookat[:] = lookat
        r.update_scene(d, cam)
        img = Image.fromarray(r.render())
        draw = ImageDraw.Draw(img)
        draw.text((14, 10), title, font=big, fill="white")
        if labels:
            # Label each servo at the centre of its visible pixels.
            r.enable_segmentation_rendering()
            r.update_scene(d, cam)
            seg = r.render()[:, :, 0]
            r.disable_segmentation_rendering()
            for b in range(1, m.nbody):
                name = m.body(b).name
                if not name.startswith("servo"):
                    continue
                geoms = [g for g in range(m.ngeom) if m.geom_bodyid[g] == b]
                ys, xs = np.nonzero(np.isin(seg, geoms))
                if len(xs) > 30:
                    draw.text((xs.mean(), ys.mean()), name[5:], font=font, fill="#ffe14d",
                              anchor="mm", stroke_width=3, stroke_fill="black")
        return np.array(img)

    pose = {"servo1": 40, "servo2": 15, "servo3": 20, "servo6": -12, "servo9": 35,
            "servo11": -30, "servo7": 12, "servo10": -25, "servo12": 20}
    tiles = [
        shot(90, 0, "front (servo IDs)", labels=True),
        shot(180, 0, "side, from our right (servo IDs)", labels=True),
        shot(125, -18, "3/4 view"),
        shot(125, -18, "joints moved", pose),
    ]
    grid = np.concatenate([np.concatenate(tiles[:2], 1), np.concatenate(tiles[2:], 1)], 0)
    out = ROOT / "images" / "merobot_views.png"
    Image.fromarray(grid).save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
