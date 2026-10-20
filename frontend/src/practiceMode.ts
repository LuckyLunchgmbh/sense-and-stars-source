export function parseWorkspaceRoute(route: string) {
  const practice = route.startsWith("practice/");
  return {
    practice,
    route: (practice ? route.slice("practice/".length) : route) || "home",
  };
}
export function workspaceRoute(route: string, practice: boolean) {
  return (practice ? "practice/" : "") + parseWorkspaceRoute(route).route;
}

// Missing or ambiguous flags fail closed; practice is never inferred from an ID.
export function clientMatchesWorkspace(
  client: { is_test?: boolean },
  practice = false,
) {
  return client.is_test === practice;
}
export function isCurrentWorkspaceRequest(
  originalHash: string,
  currentHash: string,
  mounted: boolean,
) {
  return mounted && originalHash === currentHash;
}
