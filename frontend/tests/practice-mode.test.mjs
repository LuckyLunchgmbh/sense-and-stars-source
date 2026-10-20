import assert from "node:assert/strict";
import test from "node:test";
import {
  parseWorkspaceRoute,
  workspaceRoute,
  clientMatchesWorkspace,
  isCurrentWorkspaceRequest,
} from "../src/practiceMode.ts";
test("workspace navigation keeps practice explicit across learning and person selection", () => {
  assert.deepEqual(parseWorkspaceRoute("practice/clients/42"), {
    practice: true,
    route: "clients/42",
  });
  assert.equal(workspaceRoute("learning", true), "practice/learning");
  assert.equal(workspaceRoute("astro", true), "practice/astro");
  assert.equal(workspaceRoute("clients", false), "clients");
});
test("leaving practice removes the prefix and never duplicates it", () => {
  assert.equal(workspaceRoute("practice/help", false), "help");
  assert.equal(workspaceRoute("practice/calendar", true), "practice/calendar");
  assert.deepEqual(parseWorkspaceRoute(""), { practice: false, route: "home" });
});

test("profile guard rejects real IDs in practice and test IDs in practice records", () => {
  assert.equal(clientMatchesWorkspace({ is_test: false }, true), false);
  assert.equal(clientMatchesWorkspace({ is_test: true }, false), false);
  assert.equal(clientMatchesWorkspace({ is_test: false }, false), true);
  assert.equal(clientMatchesWorkspace({ is_test: true }, true), true);
});
test("profile guard fails closed if the API omits the mode flag", () => {
  assert.equal(clientMatchesWorkspace({}, false), false);
  assert.equal(clientMatchesWorkspace({}, true), false);
});
test("a completed create keeps the original workspace instead of the current hash mode", () => {
  const originalPractice = true;
  const currentRoute = parseWorkspaceRoute("clients");
  assert.equal(currentRoute.practice, false);
  assert.equal(
    workspaceRoute("clients/81", originalPractice),
    "practice/clients/81",
  );
  assert.equal(workspaceRoute("clients/82", false), "clients/82");
});
test("late responses from closed dialogs or another route cannot control the current page", () => {
  assert.equal(
    isCurrentWorkspaceRequest("#practice/clients", "#practice/clients", true),
    true,
  );
  assert.equal(
    isCurrentWorkspaceRequest("#practice/clients", "#clients", true),
    false,
  );
  assert.equal(
    isCurrentWorkspaceRequest("#practice/clients", "#practice/calendar", true),
    false,
  );
  assert.equal(
    isCurrentWorkspaceRequest("#practice/clients", "#practice/clients", false),
    false,
  );
});
