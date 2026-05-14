# Scheme Log

Notes on how the SMS classification scheme evolved across batches. Each section is dated and summarizes what changed and why.

# 2026-04-18

First batch: papers 1-10. Initialized the scheme from scratch.

- Added 4 facets: `Environmental impact focus`, `Lifecycle stage`, `System locus`, and `Management and intervention levers`.
- Added 15 starting categories covering carbon, energy, and material burdens; the main lifecycle stages; the facility/hardware/software/user loci; and the measurement/control/design/incentive levers.
- All batch keywords fit into the initial categories, so there were no unresolved keywords.
- A few papers landed in multiple places. Paper 3 spans upstream design, runtime operations, and material burdens because its digital twin combines liquid cooling, virtual prototyping, and construction waste. Paper 7 is a position paper that touches several intervention levers at once. Paper 9 sits in both carbon and material impact categories because its keywords jointly emphasize emissions, e-waste, and resource use rather than energy alone.
- Recorded that 4 facets were enough for the initial scheme, while the operational stage and measurement categories might need splitting as finer-grained topics arrived.

# 2026-04-18

Second batch: papers 11-20. No structural changes this round, just broadening.

- Added example keywords across most categories (`lifecycle carbon emissions`, `greenhouse gas emissions`, `energy productivity metrics`, `hardware recycling`, `device reuse`, `renewable energy integration`, `AI workloads`, `code optimization`, `geographic scheduling`, `waste heat reuse`, `policy guidance`, etc.).
- Broadened `End-of-life and residual materials` to cover hardware recycling and device reuse, `Software, workloads, and data flows` to cover code and AI workloads, and `Operational governance and user practices` to include policy actors.
- All keywords fit existing categories. Paper 14 spans facility, hardware, and software loci (two-stage mechanism on an HPC cluster). Paper 17 hits every lifecycle stage because it models both embodied and operational emissions and prescribes circular-economy interventions. Paper 19 covers hardware, end-of-life, and whole-system because it argues device reuse via smartphones as compute substrate. Paper 18 lands in both runtime control and incentives because of its normative framing around code optimization.
- Flagged two sub-themes worth watching without splitting yet: renewable/grid integration (papers 11, 16, 17) and waste heat recovery (paper 12, with papers 21 and 23 likely to follow). Carbon and operational-stage coverage are near-universal, as expected under RQ1.

# 2026-04-21

Third batch: papers 21-30. Water and broad-impact framings finally had enough evidence to separate out.

- Added `Water use and hydrological impacts` under `Environmental impact focus` for water-centric sustainability papers, and `Aggregate environmental impacts` for broad or explicitly multi-impact framings that don't name a dominant burden.
- Updated descriptions and example keywords throughout to absorb new evidence (`decarbonization`, `energy reuse`, `supercomputer design`, `district heating`, `groundwater cooling`, `energy-system integration`, `benchmark dataset`, `environmental forecasting`, `workload shifting`, `thermosyphon cooling`, `environmental awareness`).
- Water keywords (`water use`, `water-efficient cooling`, `water usage effectiveness`, `aquifer thermal impacts`) went into the new water category. Broad-impact terms (`environmental impacts`, `sustainable design`, `sustainable HPC`) went into the new aggregate category.
- Papers 25, 27, and 29 needed the new categories before they could be placed. Paper 22 spans facility, software, and governance plus runtime, infrastructure, and strategic levers because the review synthesizes workload shifting, energy-system integration, and stakeholder action in one frame. Paper 26's three-model forecast treats energy demand, CO2 emissions, and e-waste together. Paper 27's LCA explicitly compares future supercomputer designs across stages. Paper 30 sits in both facility and software because geographic federation and scheduling are inseparable.
- Water is distinct enough to separate at the impact level, but waste-heat recovery and water-aware cooling still cluster as one engineering/intervention theme rather than needing their own branch. Renewable/grid integration remains cross-cutting rather than its own category.

# 2026-04-21

Fourth batch: papers 60, 71, 77, 188, 223, 239, 404, 406, 419, 421. No new facets or categories; everything fit.

- Added example keywords like `power demand shaping`, `hardware lifetime`, `water scarcity`, `data center planning`, `distributed generation`, `HPC software`, `vectorization`, `sustainability metrics`, `observability stack`, `water footprint modeling`, `adaptive scheduling`, and `carbon credits`.
- Broadened `End-of-life and residual materials` to cover aging-aware lifetime extension, `Facility, thermal, and energy infrastructure` to include onsite/distributed power, `Measurement, accounting, and visibility` to include observability tooling and water-footprint modeling, and `Infrastructure and cooling design` to include onsite generation and heat-reuse planning.
- Paper 60 spans measurement and runtime (vectorized code plus power-rate and footprint evaluation). Paper 71 covers upstream planning, operational heat recovery, measurement, and infrastructure because HRF/GSR are planning metrics grounded in facility behavior. Paper 188 pairs distributed generation with workload-aware power shaping. Paper 239 (CEEMS) is both an observability stack and a user-facing reporting interface. Paper 404 (ThirstyFLOPS) quantifies embodied and operational water. Paper 406 turns carbon and energy accounting into pricing signals. Paper 419 reduces embodied impacts through aging-aware scheduling, spanning material burdens, whole-system lifecycle, end-of-life, hardware, and runtime. Paper 421 couples embodied/operational carbon modeling with HPC-wide reporting.
- This batch reinforces existing themes — renewable/power-supply integration, observability as one measurement cluster, hardware lifetime as an existing material/lifecycle theme — rather than pushing for new structure.

# 2026-04-21

Fifth batch: papers 432, 435, 477, 688, 835, 838, 898, 928, 962, 979. Biodiversity showed up as a distinct impact.

- Added `Biodiversity and ecosystem impacts` under `Environmental impact focus` for papers that explicitly model biodiversity burdens across HPC lifecycles.
- Updated examples and some descriptions to absorb `dynamic power scaling`, `hardware reuse`, `server replacement`, `metal usage`, `supercomputer manufacturing`, `serverless computing`, `self-cooled data centers`, `hydrogen storage`, `biodiversity metrics`, `code portability`.
- `biodiversity impact`, `embodied biodiversity`, and `operational biodiversity` went into the new category. Metal-accounting terms like `abiotic resource depletion`, `metal usage`, and `lifecycle inventory` stayed in `Material, waste, and resource burdens`.
- Paper 432 (FABRIC) spans operational and whole-system lifecycle plus hardware and workload loci because it separates embodied and operational biodiversity while linking workload to lifecycle burdens. Paper 838's digital twin is paired with renewable, hydrogen, self-cooling, and waste-heat systems in a planned facility. Paper 898's replacement model explicitly trades embodied against operational carbon. Paper 835 stays under strategic framing because it compares hardware and consensus choices conceptually rather than proposing a concrete control mechanism.
- Hardware reuse and server replacement stay cross-cutting instead of earning their own longevity facet. Serverless and runtime optimization papers strengthen rather than split the existing workload and runtime clusters.

# 2026-04-22

Sixth batch: papers 1060, 2202, 2503, 2520, 2521, 2558, 2866, 2879, 3368, 3579. No new facets or categories.

- Added examples like `hybrid energy systems`, `renewable energy planning`, `green siting`, `replacement cycles`, `data center expansion`, `single-phase immersion cooling`, `scenario modeling`, `institutional carbon accounting`, `job-level analysis`, `provider-user mitigation`.
- Broadened `Upstream planning and procurement`, `Facility, thermal, and energy infrastructure`, and `Infrastructure and cooling design` to make siting-related planning decisions explicit. `air pollution` in paper 2520 stayed secondary to that paper's carbon framing and didn't justify a new impact category.
- Paper 1060 pairs forecasting with Grey Wolf optimization to size a hybrid-energy mix. Paper 2202 uses historical scenarios to compare replacement cycles, carbon, power, and green-siting trade-offs. Paper 2503's DRL scheduler couples job dispatch with center-level renewables and pricing. Paper 2558 inventories operational and embodied emissions and turns them into provider-user mitigation. Paper 2866's review combines CUE/WUE/REF/LCA with waste-heat and immersion-cooling deployment. Paper 2879's decision-support model covers procurement, construction, operation, and regional siting. Paper 3368 (CES) is a job-level metric intended to inform carbon-aware scheduling. Paper 3579 models replacement timing, data-center expansion, embodied carbon, grid intensity, and heat reuse jointly.
- The 4-facet scheme still absorbs scenario planning, institutional accounting, and immersion-cooling reviews without further branching. Job-level carbon-efficiency work still fits the measurement-plus-runtime split instead of needing a workload-metrics category.

# 2026-04-22

Seventh batch: papers 3601, 3706. Small wrap-up.

- Added examples like `heat pump deployment`, `thermodynamic modeling`, `environmental impact modeling`, `policy incentives`, `ecological sensitivity`. Structure unchanged.
- `low-GWP refrigerants` and `district heating` reinforced the facility and infrastructure branches. `global HPC analysis`, `environmental impact modeling`, and `policy incentives` fit the existing measurement and strategic-framing branches.
- Paper 3601 spans upstream planning and operational control because it's a thermodynamic feasibility study for recovering Frontier waste heat through heat pumps rather than a deployed system. Paper 3706 spans carbon, energy, and aggregate environmental impacts and also covers facility, governance, measurement, and strategic framing thanks to its global center-level emissions modeling paired with policy-incentive analysis.
- The full corpus still fits the 4-facet scheme. Heat-pump waste-heat recovery stays part of the infrastructure cluster; ecological-sensitivity modeling stays part of the aggregate-impact branch when coupled to carbon analysis.

# 2026-04-24

Fine adjustments to the scheme.

- Renamed facet `Environmental impact focus` to Environmental impacts.
- Deleted category `Aggregate environmental impacts`. This category was somewhat out of place compared to the others. All the papers had already been classified in some other category, except for paper 27. After reviewing the full text, it was classified in all categories. Updated the descriptions and rationale too.
- Deleted `Whole-system lifecycle` because it was a cross-stage summary label rather than a concrete lifecycle stage. Updated the facet rationale to state that cross-stage lifecycle coverage is represented through multi-category membership in the concrete stage categories.

# 2026-04-29

Phase-1 anchor cleanup. Rechecked the six heavily labeled environmental-impact papers and tightened one overbroad case.

- Removed paper 27 from `Water use and hydrological impacts` and `Biodiversity and ecosystem impacts` after the full-text check showed that water only appears as a cooling-medium design detail and biodiversity is not treated directly.

# 2026-04-30

Environmental-impact cleanup after rechecking the role of energy efficiency and paper 5.

- Removed `Energy and power efficiency` from `Environmental impacts`. Energy efficiency is now treated as an operational driver, midpoint, or intervention concern rather than an endpoint-style environmental impact category.
- Added paper 5 to `Water use and hydrological impacts`. Although its keyword row was previously energy-focused, the full text explicitly discusses HPC cooling water demand, water availability, treatment and discharge concerns, and an adiabatic dry-cooler design that reduces cooling-water use by about 88%.
- Coverage check after the deletion: all 62 papers still have at least one remaining environmental-impact category. Distribution is now carbon 54, materials/resource burdens 12, water 5, biodiversity 1.

# 2026-04-30

Lifecycle-stage cleanup after tracing the removal of `Whole-system lifecycle`.

- Restored concrete stage memberships that were lost when the cross-stage summary category was deleted. Added upstream tags for papers 404, 421, 432, 2558, and 2866; operational tags for papers 27, 898, 2879, and 3579; and end-of-life tags for papers 432, 2879, and 3579.
- Left weaker cases unchanged: papers 5, 6, 7, 14, 17, 19, 26, and 419 already have the defensible concrete stages supported by the current evidence, and paper 2866 remains upstream plus operational rather than end-of-life because the review discusses LCA and deployment challenges without a clear disposal-stage treatment.
- Coverage check after the repair: all 62 papers still have at least one lifecycle-stage category. Distribution is now upstream 20, operational 58, end-of-life 10; lifecycle-stage breadth is 41 papers with one stage, 16 with two stages, and 5 with all three.

# 2026-05-01

Scheme split for the SMS resubmission. The scheme is now limited to the four keyword-derived SMS facets, with methodology codings organized separately.

- Moved the previous scheme notes into this log and removed note fields from `scheme.json`.
- The four-facet scheme stays within Petersen's 3-5 facet guideline: Environmental impacts, Lifecycle stages, System locus, and Management and intervention levers.
- Environmental impacts contains only concrete endpoint-style impact types: carbon, material/resource burdens, water, and biodiversity. Energy and power efficiency remains outside the impact facet because it is a driver, midpoint, or operational-efficiency concern rather than an environmental impact category.
- Broad aggregate environmental framing is represented through membership in one or more specific impact categories rather than a separate summary category. Paper 5 remains covered under water impacts because its full text discusses cooling water demand, water availability and treatment concerns, and dry-cooler reductions in cooling-water use.
- Lifecycle stages contains only concrete stage categories. Cross-stage lifecycle reasoning is represented by multi-category membership across upstream, operational, and end-of-life stages, while lifecycle assessment as a measurement/accounting method remains captured under Management and intervention levers.
- The earlier lifecycle repair remains part of the scheme history: concrete stage memberships were restored for papers 27, 404, 421, 432, 898, 2558, 2866, 2879, and 3579 after the former `Whole-system lifecycle` label had hidden clear multi-stage evidence.
- Job- and system-level modeling still fits the existing measurement lever. Infrastructure planning, renewable integration, and waste-heat utilization remain cross-cutting themes rather than standalone scheme facets.
- `Research type`, `Methodological approach`, `Data source`, and `Assessment orientation` are organized in `others.csv` rather than in the SMS scheme.

# 2026-05-12

Category rename pass and removal of one System locus category.

- Dropped `Operational governance and user practices` from the System locus facet. The category described an intervention type (incentives, awareness, reporting, policy) rather than a physical or computational location, so it overlapped with the Management and intervention levers facet. Of its 15 papers, 12 already carried the `Incentives and strategic framing` lever; the remaining three (10, 239, 421) are measurement-oriented (user-centric carbon footprints, monitoring stack, footprint modeling) and were already tagged with the measurement lever. No paper lost its lever coverage. Five papers ended with an empty System locus cell (1, 4, 10, 28, 406), reflecting that their original locus assignment was governance-only; leaving the cell empty is preferred over inferring a physical locus without evidence.
- Renamed every category for brevity and consistency. Removed redundant trailing qualifiers (`and footprint`, `and residual materials`, `and visibility`), dropped action concepts smuggled into structural categories (`and procurement` from Compute hardware, `and control` from Operational use), and removed jargon (`hydrological`). Final names: Environmental impacts — Carbon emissions, Materials and waste, Water use, Biodiversity and ecosystems. Lifecycle stages — Production, Operational, End of Life. System locus — Facility and energy infrastructure, Compute hardware, Software and workloads. Management and intervention levers — Measurement and accounting, Workload and runtime optimization, Infrastructure design, Incentives and policy.
- Updated the `Compute hardware` description to drop the procurement clause, and the `System locus` rationale to reflect the three remaining loci.
- Reassigned the five papers (1, 4, 10, 28, 406) whose System locus cell was emptied by the governance removal. Full-text review showed each one genuinely spans multiple physical loci rather than fitting none. Paper 1 (Masciari & Napolitano survey) tagged at all three loci because Section 3.1 surveys facility innovations, hardware advances, and software optimization. Paper 4 (Fugaku Points) tagged at Software and workloads and Compute hardware because the user-facing knobs are set in job scripts but trigger hardware-level power control. Paper 10 (user-centric carbon footprints) tagged at Facility and energy infrastructure and Software and workloads because its formula combines facility-side PUE and energy mix with job-side core hours. Paper 28 (Physics World feature) tagged at Facility and energy infrastructure and Software and workloads because it discusses grid carbon intensity and code/data-transfer efficiency in parallel. Paper 406 (core hours and carbon credits) tagged at Software and workloads because the accounting mechanism acts on user job-placement decisions. Final System locus counts: Facility and energy infrastructure 43, Compute hardware 18, Software and workloads 30.
