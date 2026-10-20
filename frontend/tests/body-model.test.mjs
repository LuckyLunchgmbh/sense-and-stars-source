import assert from "node:assert/strict";
import test from "node:test";
import { BODY_CENTERS, bodyModel, centerForPlanet } from "../src/bodyModel.ts";
const planet = (name) => ({
  name,
  longitude: 42,
  sign: "Stier",
  degree: 12,
  house: 2,
  retrograde: false,
});
const chart = {
  planets: [planet("Venus"), planet("Mars"), planet("Sun"), planet("Chiron")],
  aspects: [
    { planet1: "Venus", planet2: "Mars", aspect: "Trigon", orb: 1.25 },
    { planet1: "Sun", planet2: "Mars", aspect: "Konjunktion", orb: 3 },
    { planet1: "Venus", planet2: "Chiron", aspect: "Quadrat", orb: 2 },
    { planet1: "Venus", planet2: "Mercury", aspect: "Sextil", orb: 1 },
  ],
};
test("body teaching model has exactly seven named centers and a deterministic assignment", () => {
  assert.equal(BODY_CENTERS.length, 7);
  assert.equal(new Set(BODY_CENTERS.map((center) => center.id)).size, 7);
  assert.equal(centerForPlanet("Venus"), "heart");
  assert.equal(centerForPlanet("Moon"), "sacral");
  assert.equal(centerForPlanet("Chiron"), undefined);
});
test("body view preserves the supplied planet data without inventing strengths", () => {
  const original = JSON.stringify(chart),
    model = bodyModel(chart);
  assert.deepEqual(
    model.centers.find((center) => center.id === "heart").factors,
    [chart.planets[0]],
  );
  assert.deepEqual(model.unassigned, [chart.planets[3]]);
  assert.equal(JSON.stringify(chart), original);
  assert.equal("strength" in model.centers[0], false);
});
test("body connections only mirror supplied aspects between present assigned planets", () => {
  const model = bodyModel(chart);
  assert.equal(model.links.length, 2);
  assert.equal(model.links[0].aspect, "Trigon");
  assert.equal(model.links[0].orb, 1.25);
  assert.equal(model.links[0].from, "heart");
  assert.equal(model.links[0].to, "solar");
  assert.equal(model.links[1].from, model.links[1].to);
});
test("a chart without factors produces no simulated connections", () => {
  const model = bodyModel({ planets: [], aspects: [] });
  assert.equal(model.links.length, 0);
  assert.equal(model.centers.flatMap((center) => center.factors).length, 0);
});
test("actual German backend names keep all ten planets and their aspects", () => {
  const actual = {
    planets: ["Sonne", "Mond", "Merkur", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptun", "Pluto"].map(planet),
    aspects: [{planet1:"Merkur",planet2:"Neptun",aspect:"Trigon",orb:2.1}],
  };
  const model = bodyModel(actual);
  assert.equal(model.centers.flatMap(c => c.factors).length, 10);
  assert.equal(model.unassigned.length, 0);
  assert.equal(model.centers.find(c => c.id === "throat").factors[0].name,"Merkur");
  assert.equal(model.links[0].from,"throat");
  assert.equal(model.links[0].to,"crown");
  assert.equal(model.links[0].planet1,"Merkur");
});
