"""The three-minute pitch, shared by the deck notes and the printable script.

Words between ** are key phrases, printed in bold for delivery.
"""

SCRIPT = [
    ("Cover", "I'm Wee Zhern Ray, and this is **KASCO**, the Kalimantan SAF Supply Chain Optimiser, delivering **explainable, data-driven decision intelligence** for Airbus Challenge 3."),
    ("The problem", "Aviation is a **hard-to-abate** sector on the road to **net zero**, yet **sustainable aviation fuel** was only about 0.6 percent of jet fuel in 2025. The bottleneck is the **feedstock-to-flight value chain**. In Kalimantan, the challenge inputs spread biomass over 80 sites, and four airports each need 300 kilotonnes. One large refinery costs USD 765 million, so this is a **high-stakes capital allocation** decision before engineering starts. Airbus itself was reported studying biomass logistics in Indonesia with IPB University."),
    ("Our solution", "KASCO is an **end-to-end optimisation platform** from biomass through depots and refineries to airports. A **high-performance Rust engine**, compiled to **WebAssembly**, runs **mixed-integer optimisation** in the browser, using **Lagrangian bounds** and **exact min-cost flow**. Planners get **scenario intelligence** and **solver-grounded explanations**. There is **no black box**: the solver uses no language model, and every result passes an **independent audit**."),
    ("Live MVP", "This is the live, **working MVP**. You get an **interactive geospatial network**: click any site or route, switch scenarios, rerun the solver in seconds, and ask why a refinery was chosen. An optional **Claude Sonnet 5.5 analyst** answers plain-English questions from solver data. It is **human-in-the-loop**: if a question is unclear or outside the model, it refuses rather than guesses."),
    ("Modelled impact", "On the official inputs, the **base case** costs USD 890 million a year, with six large refineries and 23 depot modules delivering **100 percent demand fulfilment** across 1,200 kilotonnes. That is **USD 61 to 77 million** below two simple heuristics. For **honest evaluation**, a strong k-means benchmark given the same fleet reaches our network, so the real value is the **optimality proof** and the fleet choice in each scenario. HiGHS, an **independent solver**, reached the same cost, and we prove a **0.75 percent optimality gap** on candidate sites."),
    ("Real-world relevance", "Regional studies support **waste-based residues** as a SAF feedstock, and palm residues are named for Kalimantan. Two honest limits: official demand is about twelve times today's real jet use here, so this is a **hub-scale** plan, and the 80 sites are modelling inputs. KASCO also surfaces **capacity thresholds**: past 1,304 kilotonnes a seventh plant is needed, and one more kilotonne adds about USD 30 million."),
    ("About me", "I'm a third-year Chemical Engineering student at NUS, minoring in Hydrogen and Low Carbon Technologies, with a specialisation in Safety and Sustainability, working where the **energy transition** meets **applied optimisation**."),
    ("Future direction", "KASCO is a prototype, with a **scalable roadmap**. Next comes **secure hosted access** to the analyst. Then **real-world validation** with logistics and feedstock data, plus **robust optimisation under uncertainty**. The **B2B opportunity** spans SAF producers, airlines, fuel distributors, airports, consultancies and planning agencies. Thank you."),
]


def plain(text: str) -> str:
    return text.replace("**", "")
