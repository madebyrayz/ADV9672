# Phase 0: reproduction of Boxer (2012)

Input: Wikimedia `Holbein-ambassadors.jpg`, 1084 x 1069 px, sha1 0543318124d91bf44070b07ae991faf1a98c4134.
Panel 2095 x 2070 mm. Convention: dx right of the right edge, dy above the bottom edge, dz off the wall.

| quantity | ours | Boxer | diff | unit |
|---|---|---|---|---|
| D (jaw through S) | 1824.453 | 1824.450 | +0.003 | mm |
| d (aspect = 1) | 257.882 | 257.880 | +0.002 | mm |
| jaw angle in painting | 25.085 | 25.100 | -0.015 | deg |
| trapezoid dx | 776.953 | 776.900 | +0.053 | mm |
| trapezoid dy | 1035.000 | 1035.000 | +0.000 | mm |
| trapezoid dz | 257.882 | 257.900 | -0.018 | mm |
| restored skull width | 142.139 | 142.000 | +0.139 | mm |
| restored skull height | 142.139 | 142.000 | +0.139 | mm |
| restored box centre x | 21.652 | 21.650 | +0.002 | mm |
| restored box centre y | -783.000 | -783.000 | -0.000 | mm |
| restored jaw angle | -0.000 | 0.000 | -0.000 | deg |
| perspective R | 1806.136 |  |  | mm |
| perspective alpha (from normal) | 81.874 |  |  | deg |
| perspective dx | 740.502 | 740.500 | +0.002 | mm |
| perspective dz | 255.293 | 255.300 | -0.007 | mm |
| perspective jaw angle | 0.000 | 0.000 | +0.000 | deg |
| perspective aspect | 1.000 | 1.000 | +0.000 |  |
| R implied by brief (hypot) | 1842.589 |  |  | mm |
| alpha implied by brief | 81.955 |  |  | deg |
| R from algebraic identity | 1806.136 | 1806.136 | -0.000 | mm |
| alpha from algebraic identity | 81.874 | 81.874 | -0.000 | deg |
| max |trapezoid - perspective| under identity | 0.000 | 0.000 | +0.000 | mm |
| max |trapezoid - perspective| under brief relation | 63.726 |  |  | mm |

Images: `restored_painting_inverse_trapezoid.jpg`, `restored_skull_inverse_trapezoid.png`, `restored_skull_perspective.png`, `comparison_restored_skull.jpg` (ours beside Boxer's OptimalSkull.jpg).