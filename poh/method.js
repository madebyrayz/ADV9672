// Essay page. Built once per session (see showView in lab.js); figures open in the shared image viewer.
function renderMethod() {
  const b = M.boxer, p1 = M.phase1 && M.phase1.stats;
  const flat = p1 ? p1.scores_at_published["Boxer anamorphic.m"].resemblance.toFixed(3) : "0.997";
  const ratio = p1 ? Math.round(p1.resemblance.above_95pct.area_mm2 / p1.ellipse_area_mm2) : 24;
  const ratioP = p1 ? Math.round(p1.clip_skull.above_95pct.area_mm2 / p1.ellipse_area_mm2) : 604;
  const HERO = "anamorph/captures/20260910/best/0001__sharp_wiki_f30__flat__dx+740_dy+1035_dz+255__fov22__BEST-MATCH-flat-skull-resolved.jpg";

  // Numbered notes. cite(n) drops a superscript marker and records the use, so each note can
  // link back to every place it was cited from.
  const NOTES = [
    `Benjamin, W. (1968) &lsquo;The work of art in the age of mechanical reproduction&rsquo;, in Arendt, H. (ed.) <i>Illuminations</i>. Translated by H. Zohn. New York: Schocken Books, pp. 217&ndash;251. Originally published 1936.`,
    `Davis, D. (1995) &lsquo;The work of art in the age of digital reproduction (an evolving thesis: 1991&ndash;1995)&rsquo;, <i>Leonardo</i>, 28(5), pp. 381&ndash;386.`,
    `Boxer, A. (2012) &lsquo;Anamorphic Ambassadors&rsquo;, <i>Idols of the Cave</i>, May. Available at: <a href="https://idolsofthecave.com/cabinet/anamorphic-ambassadors-may-2012/" target="_blank" rel="noopener">idolsofthecave.com</a> (Accessed: 9 September 2026).`,
    `Mescheder, L., Dong, W., Li, S., Bai, X., Santos, M., Hu, P., Lecouat, B., Zhen, M., Delaunoy, A., Fang, T., Tsin, Y., Richter, S.R. and Koltun, V. (2025) &lsquo;Sharp monocular view synthesis in less than a second&rsquo;, <i>arXiv</i>:2512.10685. Available at: <a href="https://arxiv.org/abs/2512.10685" target="_blank" rel="noopener">arxiv.org/abs/2512.10685</a>.`,
    `Baudrillard, J. (1994) <i>Simulacra and simulation</i>. Translated by S.F. Glaser. Ann Arbor: University of Michigan Press. Originally published 1981.`,
    `Troika (n.d.) <i>Ghost Specimen</i>. Available at: <a href="https://troika.uk.com" target="_blank" rel="noopener">troika.uk.com</a> (Accessed: 9 September 2026).`,
    `Harlow, F.H. and Fromm, J.E. (1965) &lsquo;Computer experiments in fluid dynamics&rsquo;, <i>Scientific American</i>, 212(3), pp. 104&ndash;110.`,
    `Wyld, M. (1998) &lsquo;The restoration history of Holbein&rsquo;s Ambassadors&rsquo;, <i>National Gallery Technical Bulletin</i>, 19, pp. 4&ndash;25.`,
    `Foister, S., Roy, A. and Wyld, M. (1997) <i>Making and meaning: Holbein&rsquo;s Ambassadors</i>. London: National Gallery Publications, p. 53.`,
    `Radford, A., Kim, J.W., Hallacy, C., Ramesh, A., Goh, G., Agarwal, S., Sastry, G., Askell, A., Mishkin, P., Clark, J., Krueger, G. and Sutskever, I. (2021) &lsquo;Learning transferable visual models from natural language supervision&rsquo;, <i>Proceedings of the 38th International Conference on Machine Learning</i>, PMLR 139, pp. 8748&ndash;8763.`,
    `Kerbl, B., Kopanas, G., Leimk&uuml;hler, T. and Drettakis, G. (2023) &lsquo;3D Gaussian splatting for real-time radiance field rendering&rsquo;, <i>ACM Transactions on Graphics</i>, 42(4), pp. 1&ndash;14.`,
    `Pearce, T. (2024) &lsquo;Measuring Adolf Loos&rsquo; parallax: retroactive digital photogrammetry and the persistent off-screen&rsquo;, <i>ARENA Journal of Architectural Research</i>, 9(1): 5.`,
  ];
  const uses = {};
  const cite = (n) => {
    uses[n] = (uses[n] || 0) + 1;
    return `<sup class="fnref" id="fnref-${n}-${uses[n]}"><a href="#fn-${n}">${n}</a></sup>`;
  };
  const notesList = () => `<ol class="footnotes">` + NOTES.map((t, i) => {
    const n = i + 1, k = uses[n] || 0;
    const back = Array.from({ length: k }, (_, j) =>
      `<a class="fnback" href="#fnref-${n}-${j + 1}" aria-label="Back to reference ${n}">&#8617;${k > 1 ? `<sub>${j + 1}</sub>` : ""}</a>`).join(" ");
    return `<li id="fn-${n}"><span>${t}</span> ${back}</li>`;
  }).join("") + `</ol>`;

  const attr = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const plain = (s) => String(s).replace(/<[^>]+>/g, "");
  const F = (n, src, cap) => `<figure class="mfig" data-full="${attr(src)}" data-title="Fig. ${n}" data-cap="${attr(plain(cap))}">
    <img src="${attr(src)}" alt="${attr(plain(cap))}" loading="lazy" decoding="async" />
    <figcaption><b>Fig.&nbsp;${n}</b> ${cap}</figcaption></figure>`;

  document.getElementById("method").innerHTML = `
<header class="mhead">
  <div class="tags"><span class="badge badge-outline">Design research</span><span class="badge badge-outline">Computer vision</span><span class="badge badge-outline">Media theory</span></div>
  <h1>The Post-Original Holbein</h1>
  <h2 class="msub">A hallucinative facsimile of The Ambassadors</h2>
  <div class="mmeta">
    <span>10 September 2026</span>
    <a class="mtag" href="https://github.com/madebyrayz/ADV9672/tree/main/week-02-post-original-holbein" target="_blank" rel="noopener">ADV9672 · Week 02 · reflection artifact</a>
  </div>
  <figure class="mhead-fig">
    <img src="${HERO}" alt="Holbein's anamorphic skull seen from the viewing point that resolves it." />
    <figcaption>Caption 1: The lower section of <i>The Ambassadors</i> rendered from (740.5, 1035, 255.3) mm relative to the centroid of the original 207 × 209.5 cm artwork, the position at which the smear becomes a skull.</figcaption>
  </figure>
</header>

<section>
<p class="lede">To observe the skull depicted by Holbein, one must stand at a specific vantage point within the Renaissance collection at the National Gallery. This optimal viewing position can be accurately reconstructed from the panel through precise geometrical analysis, achieving millimeter-level accuracy as demonstrated by Idols of the Cave${cite(3)}. However, the objective of this study is to utilize a predictive regression model to perform reverse engineering of the position that most closely approximates the “imaginary position” from which Holbein was situated during the creation of the painting.</p>
</section>

<section>
<h2><span class="num">01</span>Coordination</h2>
<p>Walter Benjamin, writing in 1936, posited that while a reproduction can disseminate across any geographic location, it inherently lacks the capacity to convey the original's unique presence at a specific place and moment in time. He designated this phenomenon as <i>aura</i> and regarded it as being diminished or lost through mechanical reproduction processes${cite(1)}.</p>
<p>Holbein's <i>The Ambassadors</i> (1533) presents a compelling case study for analyzing the concept of aura. The depiction of the skull within the lower panel appears as a smudged image that becomes perceptible only from an oblique viewing angle to the right of the composition. A straightforward photograph of the painting fails to reliably reproduce the skull, because the perception of the skull does not solely reside in the mechanical transition from pigments to pixels. Instead, it emerges within the experiential context of the viewer’s perception at the precise “moment of originality”${cite(2)}. The <i>Ambassadors</i> exemplifies this ephemeral quality of the “here and now,” which necessitates specific spatial and perceptual coordinates during the act of viewing.</p>
<p>This analysis draws methodological inspiration from Alexander Booker’s approach, applying solely geometric analysis through an “inverse trapezoid” transformation${cite(3)}. This technique reconstructs the formation and assesses the extent to which an observer’s gaze can drift before the skull ceases to be perceptually resolvable. Additionally, the <a href="https://github.com/apple/ml-sharp" target="_blank" rel="noopener">SHARP</a> neural network—designed to convert a single photographic image into a metric 3D scene${cite(4)}—is employed to investigate the same perceptual phenomena from a computational perspective.</p>
</section>

<section>
<h2><span class="num">02</span>Simulation</h2>
<p>For Baudrillard, simulation is distinguished from pretense${cite(5)}. He employs an illustrative example that I find particularly enlightening: an individual feigning illness remains healthy; the pretense exists externally, and an examination can detect the falsehood. Conversely, a person engaging in simulation of illness produces genuine symptoms, rendering the examination unable to differentiate between reality and simulation. This conceptual experiment can be extended to our context to question what we actually perceive when we “see”—are we merely engaging in pretense, since we are essentially receiving light stimuli through the retina, or is the act of seeing itself a form of mental simulation mediated by neural processes within the brain?</p>
<p>Baudrillard larger claim extends this to representation itself. Once models are cheap, detailed and everywhere, the copy stops depending on an original and begins standing in for it. A model that has displaced its referent is referred to a <i>simulacrum</i>; the condition it produces is called <i>hyperreal</i>, meaning not false but no longer answerable to anything outside itself.</p>
<p>An anamorphosis is a rare object that keeps its outside: the correct viewing position is recoverable from the panel independently of any model, with a published uncertainty attached. The model can therefore be caught — and the interesting work is catching it precisely enough that the disagreement means something.</p>
<p>Douglas Davis argues that the aura does not die in the copy but relocates into the individual act of looking, wherever the image is met${cite(2)}. Between the three positions sits one testable question. If the moment of seeing has a location, can an instrument find it?</p>
<p>Another noteworthy observation is that the resolution of the image used in this experiment is 1084 x 1069 pixels, which constitutes a relatively limited pixel count for optimal performance in a regression model. Additionally, this raises concerns regarding the effective resolution reduction from the original physical artwork, which exists at an atomic scale. The artwork is scaled down to merely 1,158,796 pixels, equivalent to approximately 1.16 megapixels. This diminution of detail contributes to an additional layer of information loss, thereby impacting the overall dissimilarity measure. The subsequent step would involve evaluating the employment of the high-resolution version scanned by Google Art Project.</p>
${F(1, "anamorph/figures/method/resolution_ladder.png",
  "The source at three scales. Left, the 1084 × 1069 px Wikimedia file the study runs on; centre, the 3840 px Google Art Project scan at the same crop; right, the difference. Every metric in this study is computed on the left-hand column.")}
</section>

<section>
<h2><span class="num">03</span>Error and Bias</h2>
<p>In Troika's <i>Ghost Specimen</i>, the artists began with a pressed herbarium sheet depicting a flower that had been extinct for a century. Pressing captures one planar aspect of the organism while obliterating the other. When requested to reconstruct the entire plant, a generative image model produced the missing face based on the statistical frequencies of all other observed specimens, resulting in an image that combined the original pressed specimen with the artificially generated face, subsequently exhibited on a wall—thus concealing the model's “imperfection”${cite(6)}.</p>
<p>Another earlier precedent that informed this experiment is the visualization of fluid dynamics data generated by electromechanical plotters at Los Alamos Laboratories during the 1950s and 1960s, as documented in laboratory reports${cite(7)}. These outputs enabled scientists to analyze phenomena such as shockwaves and high-velocity collisions—conditions under which solids undergo deformation, liquefaction, or vaporization—without necessitating physical experimentation. The process involved generating a series of drawings through cumulative calculations, thereby creating and examining representations of phenomena and spatial configurations that were not physically realizable.</p>
<p>Both projects exemplify an interrogation of the boundary between the real and the artificial. When machines encounter incomplete or ambiguous information, they are programmed to generate plausible reconstructions—effectively hallucinating. This behavior inherently introduces biases embedded within the training data and algorithmic assumptions. For example, it raises questions regarding whether the model's architecture—such as the weighting schemes in deep learning frameworks—favors certain image types over others. Consequently, the notion of authorship and agency is challenged. In the context of this experiment, three agents—Holbein, the regression model, and myself—debate the apparent paradoxical existence of a shared agency within our differing perceptions of reality.</p>
</section>

<section>
<h2><span class="num">04</span>Premise</h2>
<p>Boxer's construction uses five points marked on the anamorphic skull, measured in millimetres from the panel's lower-left corner, plus two conditions on the restored image: the jaw line becomes horizontal, and the restored skull fits a square. Eye height is fixed at the panel's midline, which the painting's own perspective supports. With the panel at 2095 × 2070 mm after the restoration record${cite(8)}, the viewing point lands at Δx = 776.9 mm right of the panel's right edge, Δy = 1035 mm above its bottom edge, Δz = 257.9 mm off the wall, with a stated uncertainty of 20 × 4 mm. The National Gallery's own figure, obtained by dragging the image in a graphics program until the skull looked right, is (790, 1040, 120)${cite(9)}.</p>
${F(2, "anamorph/figures/method/tiepoints_plate.png",
  "Tie points. Boxer's five marked skull points on the source photograph, the jaw line at 25.1° whose extension meets eye level at S, the central axis, and the 8 × 8 grid that places S three units right of the panel edge.")}
<p>A Python port of Boxer's two <a href="https://idolsofthecave.com/cabinet/anamorphic-ambassadors-may-2012/" target="_blank" rel="noopener">MATLAB scripts</a> returns every published number to within 0.2 mm. The port also exposes how little the construction needs. The horizontal-jaw condition means only that the jaw line passes through S, which fixes D = ${b.D.toFixed(2)} mm in a single line; the square condition is a ratio, which fixes d = ${b.d.toFixed(2)} mm.</p>
<p>That transparency cuts both ways. The whole result rests on one judgement, that a painted jawbone is a straight line, and Boxer says so himself. The method is exact about a premise that is not, and nothing in the panel can settle it.</p>
<p>The port corrected this study's own brief rather than Boxer's. His two transforms are not approximations of one another; they are the same function. Perspective projection at distance R and angle α equals the inverse trapezoid with D = R / sin α and d = R cot α, identically. The 36 mm between his two published points is the orientation of the screen the image is thrown on, not an error. "The" viewing point is already a convention at the millimetre scale, before any model is involved.</p>
${F(3, "anamorph/figures/method/two_eyes.png",
  "The same image, two eyes. Boxer's trapezoid construction (S, O, D, d) beside the exact-perspective eye whose screen sits perpendicular to the line of sight. Both produce identical restored skulls.")}
</section>

<section>
<h2><span class="num">05</span>How wide is “it looks like a skull”?</h2>
<p>Before asking a model for the position, the flat painting was projected from 13 700 eye positions on a 10 × 5 mm grid at eye height, and each skull crop scored with CLIP, a network that rates how well an image matches a phrase${cite(10)}. "A human skull" scores above 0.99 almost everywhere. A skull stretched to twice its length is still a skull to the network, and the region within 5 % of the best score covers ${ratioP} times the area of Boxer's ellipse. A stricter score, image-to-image similarity against the resolved skull itself, still leaves a basin ${ratio} times that ellipse.</p>
<p>Perception puts the viewer somewhere in a large region of acceptable smears. Geometry puts him inside a few millimetres.</p>
<p>These are different kinds of answer, and the study keeps them apart rather than splitting the difference. It is also the quantitative form of Boxer's objection to the National Gallery's method: dragging until it looks right cannot be more precise than the tolerance of looking, and that tolerance turns out to be enormous.</p>
${F(4, M.phase1.figure,
  "Perceptual basin of the flat panel over (Δx, Δz) at Δy = 1035 mm: skull probability, resemblance to the resolved skull, symmetry, and Boxer's two geometric conditions, with the four published points and his 2σ ellipse.")}
</section>

<section>
<h2><span class="num">06</span>Invented Depth</h2>
<p>SHARP was given the same photograph. When an image carries no camera data the model assumes a 30 mm lens and reports depth in metres derived from that assumption. There was no lens in 1533, so every metre it returns descends from a default.</p>
<p>It did not reconstruct a panel. It reconstructed the room depicted in the painting: the floor advances, the curtain recedes, and 623 mm of relief appear across a surface 2095 mm wide that is physically flat. A plane fitted to the image border tilts twenty degrees, because the bottom border is the depicted floor.</p>
${F(5, "anamorph/captures/20260910/docs/0002__sharp_wiki_f30__sharp__dx-1048_dy+1033_dz+2040__fov54__02-photo-camera-depth-wireframe.jpg",
  "The invented room, made visible. Depth wireframe over the reconstruction from the photograph's own camera: a flat oak panel returned as a floor, a recess and a hanging curtain.")}
<p>Comparing metres to millimetres therefore requires deciding where the panel is, and that decision is a stated assumption rather than a hidden one. The primary bridge places a plane parallel to the photograph at the reconstructed depth of the skull and sets its width to 2095 mm; a global-median plane and the tilted border fit are carried as bounds. One SHARP metre then equals 1095 mm, the photograph's own camera stands 2.04 m from the wall, and the skull's known 915 mm width returns as 1036 mm per metre, a 6 % check. The bridge is unit-tested against a synthetic plane and written into every render. It is the weakest link in the study, and it is deliberately kept visible.</p>
${F(6, "anamorph/figures/method/section_plate.png",
  "Section at the skull's column: eye level, the skull box on the panel, the published eyes, and the reconstructed surface at the default lens. Rays from Boxer's O to the skull box cross the reconstructed floor before they reach the wall.")}
</section>

<section>
<h2><span class="num">07</span>Resection</h2>
<p>In photogrammetry, resection means recovering a camera's position from what it saw. The model's scene was photographed from 1421 positions on the same grid as the perceptual sweep, looking horizontally at the panel's centre as in Boxer's script, and from a 532-position orbit around the skull.</p>
<p>The scoring crop cannot be placed where the flat panel puts the skull, because that box comes back empty: the model's skull is not on the wall. The crop instead follows the projected 3D bounding box of the Gaussians belonging to the skull in the photograph${cite(11)}. At Boxer's O that box is 87 % empty.</p>
<p>Resemblance across the whole grid stays between 0.30 and 0.61, below what the flat panel scores even at the National Gallery's point, and its maximum sits 141 mm from Boxer's O, at (675, 1035, 160). Measured against the disagreement between the two human estimates (13 mm along the wall, 138 mm out from it), that is eight units off along the wall and less than one unit out from it. The number is not a station point. It is the least bad view of a streak lying on a receding floor.</p>
${F(7, "anamorph/figures/method/resection_plate.png",
  "Resection plate. The photograph as picture plane; below it in plan, Boxer's construction with S and O, rays from O through the skull's extent, the published points with the 2σ ellipse, the reconstructed surface along three image rows, the grid and orbit maxima, and the camera position the model assigns to the photograph itself.")}
</section>

<section>
<h2><span class="num">08</span>Phantom Lens</h2>
<p>Since every metre descends from a default, the default was swept from 5 to 200 mm. Depth is exactly linear in the assumed focal length and the lateral scale does not move: the model's metric guess is a depth guess only, and relief follows it, from 104 mm at 5 mm to 4.1 m at 200 mm. No lens brings the model's best position inside the ellipse.</p>
<p>What a short lens does is flatten the scene, and at 5 mm, from Boxer's exact-perspective point with a narrow field of view, the skull begins to read. That is suggestive and not proof: it is a single capture, the scoring crop misses it because the crop sits at the wrong depth, and a 5 mm equivalent lens is not a plausible camera. It does locate the obstacle. The lens prior is what stands between the model and the panel.</p>
${F(8, "anamorph/figures/depth_strip.png",
  "The same picture at thirteen assumed lenses, 5 to 200 mm. Bright is near. Nothing in the image changes; only the depth scale does, and with it every millimetre the model reports.")}
</section>

<section>
<h2><span class="num">09</span>Idolmorphosis</h2>
<p>Boxer ends by running his procedure backwards: a square image placed in the 142 mm box of the restored painting and forward-transformed with the same D and d lands exactly where Holbein's skull lies. The same was done here with the model's output: its best crop, its torn render from O, and its depth map of the skull region. Each becomes a 914 × 532 mm streak, saved at four pixels per millimetre for a 36-inch print, that resolves only from the exact-perspective point.</p>
<p>The depth map reads best from O: a machine's belief about where the skull is, stretched across the floor exactly where Holbein stretched the skull. Whether that is an artifact or a diagram is the question the print puts to a visitor who has to walk to it.</p>
${F(9, "anamorph/figures/phase5_pairs.jpg",
  "Idolmorphosis. Left, the streak composited into the painting; right, the same streak seen from Boxer's O, where it resolves back into its square. Sources top to bottom: best-pose crop, torn render from O, depth map of the skull region.")}
</section>

<section>
<h2><span class="num">10</span>The Outside</h2>
<p>The geometer's answer is the viewpoint saved in this instrument as the resolved skull: (740.5, 1035, 255.3) mm, R = 1806 mm, 81.9° from the wall normal, where the flat panel scores ${flat} and Boxer's construction reproduces to a hundredth of a millimetre. The model's answer is not slightly wrong. It answers a different question. Given a photograph with no lens it fills in a room, and once there is a room the floor carries the smear away from the wall the construction lives on.</p>
<p>This is the useful result, and it cuts against the theory it was meant to illustrate. Baudrillard's model does not pretend to see a skull; it produces the symptoms of a scene, and the symptoms are coherent enough to be measured. But they <i>were</i> measured, and they were found wanting at a specific coordinate. The hyperreal is supposed to have absorbed its outside. Here the outside held, not because the model is weak, but because the object was chosen so that a physical fact stayed recoverable.</p>
<p>The precession of simulacra is not a property of models. It is a property of situations in which nothing survives to check them, and those situations are made, not given.</p>
<p>Benjamin's aura did not stay in the panel and it did not pass to the model. It sits in the bridge: the list of assumptions that permit millimetres to be compared to metres. Davis is right that the moment of seeing survives reproduction, but here it survives as a coordinate someone has to argue for, and the argument is the artifact.</p>
</section>

<section>
<h2><span class="num">11</span>Objections</h2>
<p>Four objections, in descending order of how much they threaten the result.</p>
<ul>
<li><b>The judge is a network.</b> Resemblance is scored by CLIP, which carries its own biases and was trained on the same kind of internet imagery as the model under test. A network is being asked whether another network's output looks like a skull. This was accepted because a human judge is the thing under test, but it means every score in §05 and §07 compares two priors, not a perceptual fact.</li>
<li><b>The bridge is chosen, not derived.</b> Three defensible bridges disagree by up to 25 % in scale. All three were carried and the conclusion holds under all three, but a reader who rejects the primary bridge is entitled to reject the specific millimetre figures that depend on it.</li>
<li><b>Boxer's premise is unfalsifiable from the panel.</b> The construction assumes the painted jawbone is a straight line. Nothing in the object can confirm it. The ground truth is a very precise consequence of an imprecise reading.</li>
<li><b>The comparison is unfair by design, and that is the point.</b> SHARP was not built to solve anamorphosis; it was built to make plausible geometry from one photograph, and by that standard it succeeds. The test is not of competence. It is of what a model does with a question it cannot know it is being asked, and whether the answer arrives marked as a guess. It does not. It arrives in metres.</li>
</ul>
<p>None of the four touches the central observation, which depends on no metric at all: at the one position where the geometry resolves the skull, the model has nothing on the wall.</p>
</section>

<section>
<h2><span class="num">12</span>The Instrument</h2>
<p>The interface is not an illustration of this study; it is the apparatus the measurements were taken with, and every figure above can be reproduced from it. It holds one painting, several reconstructions of it, and three coordinate frames kept deliberately separate. <b>Lab</b> is the instrument, <b>Log</b> is its record, <b>Report</b> is its running summary.</p>

<h3>The three frames</h3>
<p>Every number in the app belongs to exactly one of these. Confusing them is the error the bridge exists to prevent.</p>
<table class="glossary">
<tr><th>Panel (mm)</th><td>The physical frame, and the one the argument is conducted in. Δx = millimetres right of the panel's right edge, Δy = above its bottom edge, Δz = out from the wall. The panel is 2095 × 2070 mm.</td></tr>
<tr><th>SHARP (m)</th><td>The model's own frame, in metres, x right, y down, z forward from the photograph's camera. These metres are not measurements; they are consequences of an assumed lens.</td></tr>
<tr><th>Bridge</th><td>The stated conversion between the two, as <i>mm per SHARP unit</i>. It is an assumption, it is recorded in every capture, and it is the single number most able to invalidate a comparison.</td></tr>
</table>

<h3>The controls</h3>
<table class="glossary">
<tr><th>Scene</th><td>One reconstruction: the photograph passed through SHARP at one assumed lens. <i>Reference</i> scenes are the thirteen lenses of the sweep; <i>Tests</i> are reconstructions made from views rendered inside the app. The badge shows the lens.</td></tr>
<tr><th>View</th><td>How the loaded scene is drawn, camera held fixed so the five are comparable. <i>Splat</i>: the 1.18 million Gaussians. <i>Mesh</i>: the depth map as a textured surface. <i>Wire</i>: the same depth as lines, which makes invented relief legible. <i>Flat</i>: the painting on a flat panel from the same camera, which is Boxer's model and the control condition. <i>Split</i>: splats against one of the others.</td></tr>
<tr><th>Viewpoints</th><td>Named eye positions on keys 0–5: the camera the model assigns to the photograph, the four published estimates, the reconstruction's own scoring maximum, and anything saved in session. Selecting one sets Δx, Δy, Δz and field of view together.</td></tr>
<tr><th>Trajectories</th><td>Camera paths between positions, so a claim about a region can be shown rather than sampled: the approach to O, sweeps along Δx and Δz, a descent, the orbit, a grazing pass. Record writes every frame plus an mp4 to the Log.</td></tr>
<tr><th>Overlays</th><td>Construction geometry drawn <i>into</i> the 3D scene rather than painted over it, so it occludes correctly and shows where the reconstruction sits relative to the panel: the 8 × 8 grid, skull box, station points, Boxer's S–O construction, sight lines, depth wireframe.</td></tr>
<tr><th>Capture</th><td>Writes the frame as a JPEG beside a JSON sidecar holding the pose in <i>both</i> frames, field of view, view mode, active overlays and bridge parameters. The filename repeats scene, view, pose, field and tag, so a capture stays identifiable detached from its sidecar. This is what makes a screenshot admissible as evidence.</td></tr>
<tr><th>Reconstruct</th><td>Renders the painting from the current camera and runs SHARP on that render, passing the render's true focal length. The result enters as a Test scene, bridged from the render camera rather than assumed, the one way to feed the model an image whose lens is known.</td></tr>
</table>

<h3>The numbers</h3>
<table class="glossary">
<tr><th>Δx Δy Δz</th><td>Current eye in panel millimetres. Boxer's O is (776.9, 1035, 257.9); the resolved-skull viewpoint is (740.5, 1035, 255.3).</td></tr>
<tr><th>az · el · d</th><td>Direction from eye to skull: azimuth from the wall normal, elevation, distance in mm. Grazing views, the ones the model prefers, show high azimuth and negative elevation.</td></tr>
<tr><th>fov</th><td>Field of view in degrees. Not cosmetic: it sets how much of the smear is in frame, and the 5 mm result in §08 depends on it.</td></tr>
<tr><th>R · α</th><td>Boxer's own two parameters, recomputed live: R the distance from eye to panel centre, α the angle from the wall normal. At his solution, R = 1806 mm, α = 81.9°.</td></tr>
<tr><th>f_px</th><td>The assumed focal length in pixels for this scene, the origin of every metre that follows.</td></tr>
<tr><th>Relief</th><td>Depth p95 minus p05 in panel millimetres: how much depth the model invented across a flat board. 623 mm at the 30 mm default.</td></tr>
<tr><th>mm per unit</th><td>The bridge, stated. 1095 at the default lens.</td></tr>
<tr><th>Grid peak · Offset</th><td>Best-scoring position on the resection grid, and its distance from Boxer's O. 141 mm at the default lens, the study's headline disagreement.</td></tr>
</table>
</section>

<section>
<h2>Notes</h2>
<ol class="notes">
<li>Source image: <code>Holbein-ambassadors.jpg</code>, 1084 × 1069 px, the Wikimedia file Boxer worked from. Panel dimensions after the 1996 restoration${cite(8)}.</li>
<li>All measurements, including those that failed, are recorded in <code>anamorph/findings.md</code>. Figures are drawn by <code>method_figures.py</code>; their drawing conventions follow the retroactive-photogrammetry plates in ${cite(12)}. The reproduction of Boxer's scripts is in <code>anamorph/boxer_repro/</code>.</li>
<li>Model weights and inference code: <a href="https://github.com/apple/ml-sharp" target="_blank" rel="noopener">github.com/apple/ml-sharp</a>. Every run in this study used the released checkpoint with no fine-tuning.</li>
<li>Source, measurements and this prototype: <a href="https://github.com/madebyrayz/ADV9672/tree/main/week-02-post-original-holbein" target="_blank" rel="noopener">github.com/madebyrayz/ADV9672</a>. Method, Log and Report run with no model installed; the Lab needs the SHARP checkpoint.</li>
</ol>
</section>

<section class="refs">
<h2>References</h2>
${notesList()}
<p class="text-muted text-xs">Source image: <code>Holbein-ambassadors.jpg</code>, 1084 × 1069 px, the Wikimedia file Boxer worked from. Further reading: Baltrušaitis, J. (1977) <i>Anamorphic art</i>, trans. W.J. Strachan; Kircher, A. (1646) <i>Ars magna lucis et umbrae</i>, the trapezoid construction Boxer inverts.</p>
</section>`;
}
