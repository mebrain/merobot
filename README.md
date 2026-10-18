# merobot

Robot designs, reusable hardware references, and a shared structure notation.

- [Standard](standard/structure_notation.md): draft notation for parts, sensors, rigid links, and joints.
- [Duckbot](robots/duckbot/README.md): the biped currently being developed, with its simulation and training tools.
- [Headbot](robots/headbot/README.md): head assembly meshes, previously called Smallskull.
- [Components](components/): shared board and servo reference models.

Each robot keeps its own parts, sensors, model, and notes under `robots/<name>/`.
Local `runs/` and `images/` directories and training logs are ignored by Git.
