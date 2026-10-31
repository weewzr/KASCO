# KASCO submission content

## Submission title

KASCO — Kalimantan SAF Supply Chain Optimiser

## Project materials

Live prototype: https://weewzr.github.io/airbustrack3ray/

GitHub repository: https://github.com/weewzr/airbustrack3ray

Technical report: https://weewzr.github.io/airbustrack3ray/reports/KASCO_Technical_Report.pdf

Presentation: https://weewzr.github.io/airbustrack3ray/reports/KASCO_Pitch.pptx

Cover image: https://weewzr.github.io/airbustrack3ray/reports/KASCO_Cover.jpg

## Summary (138 words)

KASCO is a working prototype for planning a Sustainable Aviation Fuel supply chain across Kalimantan, built for Airbus Challenge 3. Using the official challenge data, it connects 80 biomass sites to depots, refineries and four international airports. A Rust optimisation engine, running in the browser through WebAssembly, selects facility sites and sizes, routes every tonne and proves how close each network is to the best possible on candidate sites. Planners explore an interactive map, rerun scenarios and ask explainable, solver-grounded questions, and the assistant refuses what the model cannot support. The base case meets all 1,200 kt of demand at USD 890.1M a year, within a proven 0.75% gap, and USD 61M to 77M below two simple heuristic layouts. HiGHS independently reached the same cost. KASCO helps a planner test decisions and find their limits before committing capital.

## Short prototype description (438 characters)

KASCO is a working prototype that optimises a Sustainable Aviation Fuel supply chain across Kalimantan on the official Airbus Challenge 3 data. A Rust solver running in the browser picks depot and refinery sites, routes biomass and SAF to four airports, and reports a proven gap. Users explore an interactive map, rerun scenarios and get explainable, solver-grounded answers. Base case: USD 890.1M a year, with all 1,200 kt of demand met.

## Three-minute pitch script (450 words, about 180 seconds at 150 words a minute)

**Slide 1.** I'm Wee Zhern Ray, and this is KASCO, the Kalimantan SAF Supply Chain Optimiser, delivering explainable, data-driven decision intelligence for Airbus Challenge 3.

**Slide 2.** Aviation is a hard-to-abate sector on the road to net zero, yet sustainable aviation fuel was only about 0.6 percent of jet fuel in 2025. The bottleneck is the feedstock-to-flight value chain. In Kalimantan, the challenge inputs spread biomass over 80 sites, and four airports each need 300 kilotonnes. One large refinery costs USD 765 million, so this is a high-stakes capital allocation decision before engineering starts. Airbus itself was reported studying biomass logistics in Indonesia with IPB University.

**Slide 3.** KASCO is an end-to-end optimisation platform from biomass through depots and refineries to airports. A high-performance Rust engine, compiled to WebAssembly, runs mixed-integer optimisation in the browser, using Lagrangian bounds and exact min-cost flow. Planners get scenario intelligence and solver-grounded explanations. There is no black box: it uses no language model, so it cannot invent a number, and every result passes an independent audit.

**Slide 4.** This is the live, working MVP. You get an interactive geospatial network: click any site or route, switch scenarios, rerun the solver in seconds, and ask why a refinery was chosen. It is human-in-the-loop: if a question is unclear or outside the model, it refuses rather than guesses.

**Slide 5.** On the official inputs, the base case costs USD 890 million a year, with six large refineries and 23 depot modules delivering 100 percent demand fulfilment across 1,200 kilotonnes. That is USD 61 to 77 million below two simple heuristics. For honest evaluation, a strong k-means benchmark given the same fleet reaches our network, so the real value is the optimality proof and the fleet choice in each scenario. HiGHS, an independent solver, reached the same cost, and we prove a 0.75 percent optimality gap on candidate sites.

**Slide 6.** Regional studies support waste-based residues as a SAF feedstock, and palm residues are named for Kalimantan. Two honest limits: official demand is about twelve times today's real jet use here, so this is a hub-scale plan, and the 80 sites are modelling inputs. KASCO also surfaces capacity thresholds: past 1,304 kilotonnes a seventh plant is needed, and one more kilotonne adds about USD 30 million.

**Slide 7.** I'm a third-year Chemical Engineering student at NUS, minoring in Hydrogen and Low Carbon Technologies, with a specialisation in Safety and Sustainability, working where the energy transition meets applied optimisation.

**Slide 8.** KASCO is a prototype today, with a scalable roadmap. Next comes a secure LLM layer, with the solver still in charge of every number. Then real-world validation with logistics and feedstock data, plus robust optimisation under uncertainty. The B2B opportunity spans SAF producers, airlines, fuel distributors, airports, consultancies and planning agencies. Thank you.
