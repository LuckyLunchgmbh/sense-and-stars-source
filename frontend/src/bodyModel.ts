import type { Chart, Planet } from "./types";

// Sense & Stars' explicit teaching convention, not an ephemeris-derived chakra measure.
export const BODY_MODEL_VERSION = "Sense & Stars-Symbolmodell 1.0";
export const BODY_CENTERS = [
  {
    id: "root",
    name: "Wurzel",
    theme: "Halt und Grenzen",
    planets: ["Saturn", "Pluto"],
    y: 354,
    question: "Was gibt mir Halt, wenn sich etwas verändert?",
  },
  {
    id: "sacral",
    name: "Sakral",
    theme: "Empfindung und Beweglichkeit",
    planets: ["Moon"],
    y: 313,
    question: "Was nehme ich wahr, bevor ich es deute?",
  },
  {
    id: "solar",
    name: "Solarplexus",
    theme: "Ausdruck und Handlung",
    planets: ["Sun", "Mars"],
    y: 269,
    question: "Was möchte ich bewusst zum Ausdruck bringen?",
  },
  {
    id: "heart",
    name: "Herz",
    theme: "Beziehung und Werte",
    planets: ["Venus"],
    y: 222,
    question: "Was fühlt sich in einer Beziehung stimmig an?",
  },
  {
    id: "throat",
    name: "Kehle",
    theme: "Sprache und Austausch",
    planets: ["Mercury"],
    y: 175,
    question: "Wie kann ich meine Wahrnehmung offen formulieren?",
  },
  {
    id: "third-eye",
    name: "Stirn",
    theme: "Perspektive und neue Bilder",
    planets: ["Uranus"],
    y: 124,
    question: "Welche andere Sichtweise könnte ebenfalls passen?",
  },
  {
    id: "crown",
    name: "Krone",
    theme: "Sinn und Vorstellung",
    planets: ["Jupiter", "Neptune"],
    y: 76,
    question: "Was gibt meinem Weg Bedeutung?",
  },
] as const;
export type BodyCenterId = (typeof BODY_CENTERS)[number]["id"];
export const PLANET_LABELS: Record<string, string> = {
  Sonne: "Sonne",
  Mond: "Mond",
  Merkur: "Merkur",
  Neptun: "Neptun",
  Sun: "Sonne",
  Moon: "Mond",
  Mercury: "Merkur",
  Venus: "Venus",
  Mars: "Mars",
  Jupiter: "Jupiter",
  Saturn: "Saturn",
  Uranus: "Uranus",
  Neptune: "Neptun",
  Pluto: "Pluto",
  TrueNode: "Mondknoten",
  Chiron: "Chiron",
};
const PLANET_ALIASES: Record<string, string> = {
  Sonne: "Sun",
  Mond: "Moon",
  Merkur: "Mercury",
  Neptun: "Neptune",
};
export function centerForPlanet(name: string): BodyCenterId | undefined {
  const canonical = PLANET_ALIASES[name] || name;
  return BODY_CENTERS.find((center) =>
    (center.planets as readonly string[]).includes(canonical),
  )?.id;
}
export function bodyModel(chart: Chart) {
  const centers = BODY_CENTERS.map((center) => ({
    ...center,
    factors: chart.planets.filter(
      (planet: Planet) => centerForPlanet(planet.name) === center.id,
    ),
  }));
  const links = chart.aspects.flatMap((aspect, index) => {
    const from = centerForPlanet(aspect.planet1),
      to = centerForPlanet(aspect.planet2);
    if (!from || !to) return [];
    if (
      !chart.planets.some((planet) => planet.name === aspect.planet1) ||
      !chart.planets.some((planet) => planet.name === aspect.planet2)
    )
      return [];
    return [{ ...aspect, id: index, from, to }];
  });
  return {
    centers,
    links,
    unassigned: chart.planets.filter((planet) => !centerForPlanet(planet.name)),
  };
}
