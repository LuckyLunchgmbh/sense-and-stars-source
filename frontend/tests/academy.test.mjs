import assert from "node:assert/strict";
import test from "node:test";
import {
  filterCourses,
  quizReady,
  dueReviews,
  learningStage,
} from "../src/academyModel.ts";
import { euroToCents, suggestedPrice } from "../src/pricing.ts";
test("free choice includes courses without progress and path reset restores every course", () => {
  const courses = [
    {
      id: "grundlagen",
      title: "Grundlagen",
      summary: "Start",
      tradition: "Westlich",
      level: "foundation",
      published_count: 8,
      completed_count: 0,
    },
    {
      id: "jyotish",
      title: "Jyotish",
      summary: "Siderischer Tierkreis",
      tradition: "Indisch",
      level: "deepening",
      published_count: 6,
      completed_count: 0,
    },
  ];
  assert.deepEqual(filterCourses(courses, "", "", ""), courses);
  assert.deepEqual(filterCourses(courses, "siderisch", "", ""), [courses[1]]);
  assert.deepEqual(filterCourses(courses, "", "", "deepen"), [courses[1]]);
  assert.deepEqual(filterCourses(courses, "", "foundation", ""), [courses[0]]);
});
test("quiz requires one valid option per question including index zero", () => {
  const quiz = [
    { id: "q1", options: ["A", "B"] },
    { id: "q2", options: ["A", "B"] },
  ];
  assert.equal(quizReady(quiz, { q1: 0, q2: 1 }), true);
  for (const answers of [
    { q1: 0 },
    { q1: 0, q2: -1 },
    { q1: 0, q2: 2 },
    { q1: 0, q2: 1.5 },
  ])
    assert.equal(quizReady(quiz, answers), false);
});
test("topic search finds a published lesson even when the course title is broader", () => {
  const course = {id: "planeten", title: "Planeten", summary: "Himmelskörper", tradition: "Westlich", search_text: "Saturn: Grenzen und Verantwortung"};
  assert.deepEqual(filterCourses([course], "Saturn", "", ""), [course]);
  assert.deepEqual(filterCourses([course], "unbekannt", "", ""), []);
});
test("repetitions are due only at or after their date", () => {
  const reviews = [
    { due_at: "2026-10-20T10:00:00Z" },
    { due_at: "2026-10-21T10:00:00Z" },
  ];
  assert.deepEqual(dueReviews(reviews, Date.parse("2026-10-20T10:00:00Z")), [
    reviews[0],
  ]);
  assert.equal(learningStage(0), "Auf Entdeckungsreise");
});
test("prices distinguish unset, free, exact cents and invalid inputs", () => {
  assert.equal(euroToCents(""), null);
  assert.equal(euroToCents("0"), 0);
  assert.equal(euroToCents("80,50"), 8050);
  assert.equal(euroToCents("10000.00"), 1000000);
  for (const input of ["1e2", "-10", "80.123", "NaN", "10000.01"])
    assert.throws(() => euroToCents(input));
});
test("price follows duration and commercial half-up cent rounding", () => {
  assert.equal(suggestedPrice(8000, 45), 6000);
  assert.equal(suggestedPrice(8000, 90), 12000);
  assert.equal(suggestedPrice(1, 30), 1);
  assert.equal(suggestedPrice(null, 90), 0);
  assert.equal(suggestedPrice(0, 90), 0);
});
