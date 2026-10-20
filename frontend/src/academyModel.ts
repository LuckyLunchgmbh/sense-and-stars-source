import type { AcademyCourse } from "./types";

export const ACADEMY_LEVELS = {
  foundation: "Grundlagen",
  deepening: "Vertiefung",
  practice: "Praxis",
};

export const LEARNING_PATHS = [
  {
    id: "start",
    title: "Ich möchte sicher einsteigen",
    description:
      "Die Sprache verstehen und ein erstes Horoskop zusammenführen.",
    courses: [
      "grundlagen",
      "zeichen",
      "planeten",
      "haeuser",
      "aspekte",
      "radixsynthese",
    ],
  },
  {
    id: "deepen",
    title: "Ich möchte tiefer deuten",
    description: "Zeitqualität und unterschiedliche Deutungsschulen erkunden.",
    courses: [
      "transite",
      "psychologisch-evolutionaer",
      "mondknoten-asteroiden",
      "hellenistisch",
      "jyotish",
    ],
  },
  {
    id: "consult",
    title: "Ich möchte Beratung üben",
    description:
      "Wahrnehmung, Gespräch und Rückmeldung an fiktiven Fällen verbinden.",
    courses: [
      "beratung-feldarbeit",
      "radixsynthese",
      "psychologisch-evolutionaer",
    ],
  },
];

export function filterCourses(
  courses: AcademyCourse[],
  query: string,
  level: string,
  path: string,
) {
  const selected = LEARNING_PATHS.find((item) => item.id === path);
  const search = query.trim().toLocaleLowerCase("de");
  return courses.filter(
    (course) =>
      (!level || course.level === level) &&
      (!selected || selected.courses.includes(course.id)) &&
      `${course.title} ${course.summary} ${course.tradition} ${course.search_text || ""}`
        .toLocaleLowerCase("de")
        .includes(search),
  );
}

// These stages describe accumulated learning activity, never a qualification.
export function learningStage(points: number) {
  if (points >= 3000) return "Drangeblieben";
  if (points >= 1200) return "Wissen verknüpft";
  if (points >= 400) return "Regelmäßig geübt";
  if (points >= 100) return "Erste Erfahrungen";
  return "Auf Entdeckungsreise";
}

export function quizReady(
  questions: { id: string; options: string[] }[],
  answers: Record<string, number>,
) {
  return (
    questions.length > 0 &&
    questions.every(
      (q) =>
        Number.isInteger(answers[q.id]) &&
        answers[q.id] >= 0 &&
        answers[q.id] < q.options.length,
    )
  );
}

export function dueReviews<T extends { due_at: string }>(
  reviews: T[],
  now = Date.now(),
) {
  return reviews.filter((review) => Date.parse(review.due_at) <= now);
}
