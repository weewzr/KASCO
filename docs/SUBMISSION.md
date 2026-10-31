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

## Three-minute pitch script (429 words, about 172 seconds at 150 words a minute)

**Slide 1.** I'm Wee Zhern Ray, and this is KASCO, the Kalimantan SAF Supply Chain Optimiser, built for Airbus Challenge 3.

**Slide 2.** Sustainable aviation fuel was only about 0.6 percent of jet fuel in 2025. In Kalimantan the challenge inputs give biomass spread over 80 sites and four airports needing 300 kilotonnes each. A large refinery costs USD 765 million, so a network planner must decide where capital goes before engineering starts. Airbus itself was reported studying biomass logistics and factory siting in Indonesia with IPB University.

**Slide 3.** KASCO follows material from biomass to depots, refineries and airports. A Rust solver compiled to WebAssembly picks sites and sizes in the browser and routes flows exactly. Planners can change assumptions, rerun the solver, and get explanations drawn from solver records. It uses no language model, so it cannot invent a number, and every result passes an independent audit.

**Slide 4.** This is a real screenshot of the working site, not a mock-up. You can click any site or route, switch scenarios, run the solver in the browser, and ask why a refinery was chosen. If a question is unclear or outside the model, it refuses rather than guesses.

**Slide 5.** The base case costs USD 890 million a year with six large refineries and 23 depot modules, meeting all 1,200 kilotonnes. That is USD 61 to 77 million a year below two simple heuristics. Honest caveat: a strong k-means benchmark given the same fleet reaches our network, so the real value is the proof, the fleet choice in each scenario, and the limits. HiGHS, a separate solver, reached the same cost, and we prove the gap at 0.75 percent on candidate sites.

**Slide 6.** Regional studies support residues as a SAF feedstock, and palm residues are named for Kalimantan. Indonesia's first mandate covers Jakarta and Bali departures only. Two honest limits: official demand is about twelve times today's real jet use here, so this is a hub-scale plan, and the 80 sites are modelling inputs. KASCO also exposes decision limits: past 1,304 kilotonnes a seventh plant is needed, and one more kilotonne adds about USD 30 million.

**Slide 7.** I'm a third-year Chemical Engineering student at NUS, minoring in Hydrogen and Low Carbon Technologies, with a specialisation in safety and sustainability.

**Slide 8.** KASCO is a prototype today. Next would come a secure language-model layer, with the solver still in charge of every number. Then road, port and feedstock data, robust optimisation and stakeholder validation. Likely users would be SAF producers, airlines, fuel distributors, airports, consultancies and planning agencies. This is an industrial planning tool, so there is no consumer story here. Thank you.
