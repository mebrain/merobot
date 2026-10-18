# 5x5 Mechanical Standard

_Draft notes. All dimensions are in millimetres._

## Connecting bars

- All parts connect using square bars (rods) with a **5 × 5 mm** cross-section.
- Use **2 mm screws** throughout.
- A rod's first screw point must be centred **exactly 2.5 mm from its end**.
- Valid screw-point centres along the rod are **2.5, 5, 7.5, 10 mm, and so on**: a 2.5 mm grid measured from that end.

## Holders and rod spacing

- In a complex holder, keep **5 mm between adjacent 5 mm rods**.
- Draft interpretation: this is the clear gap between nominal rod edges, giving a **10 mm centre-to-centre pitch**. Confirm this interpretation before treating the draft as final.
- Rod sockets must accept a 5 mm square rod, with an opening between **5.0 and 5.3 mm** across.
- Keep the nominal rod positions fixed. Any extra socket clearance extends **left to right** horizontally and **top to bottom** vertically; do not centre the extra clearance around the rod.

Example with 5.3 mm sockets and a nominal 5 mm gap:

| Feature | Horizontal extent |
|---|---|
| First nominal rod | 0 to 5 mm |
| First socket | 0 to 5.3 mm |
| Second nominal rod | 10 to 15 mm |
| Second socket | 10 to 15.3 mm |

The extra 0.3 mm projects to the right. The next socket starts **4.7 mm after the right edge of the first socket**, at 10 mm on the original grid. Apply the same rule vertically, extending the clearance downward.

## Panel screw holes

- Place the screw-hole centre **2.5 mm from the relevant panel edge**.
- The screw opening must be **2 mm wide**.

## Printing and hole geometry

- Minimize the need for printing supports.
- Use **teardrop-shaped holes** to reduce support requirements, oriented for the intended print direction.
- Square rod sockets must still accommodate the specified 5 × 5 mm bar. Any teardrop relief must preserve that fit; its exact profile remains to be defined.
- Wherever possible, make holes pass **all the way through** the object.
- If a hole must stop inside the object, the preferred depth is **5 mm**.
