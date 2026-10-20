import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { isCurrentWorkspaceRequest, workspaceRoute } from "./practiceMode";
export function useData<T>(path: string | null, revision = 0) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    if (!path) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    api<T>(path)
      .then((value) => {
        if (alive) setData(value);
      })
      .catch((error) => {
        if (alive) setError(error.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, revision]);
  return { data, setData, loading, error };
}
export function useRoute() {
  const [route, setRoute] = useState(window.location.hash.slice(1) || "home");
  useEffect(() => {
    const handle = () => setRoute(window.location.hash.slice(1) || "home");
    window.addEventListener("hashchange", handle);
    return () => window.removeEventListener("hashchange", handle);
  }, []);
  return route;
}
export const go = (route: string, practice?: boolean) => {
  const inPractice = practice ?? window.location.hash.startsWith("#practice/");
  window.location.hash = workspaceRoute(route, inPractice);
  window.scrollTo({ top: 0, behavior: "instant" });
};

// Async mutations may finish after a dialog closes or another workspace opens.
export function useRequestScope() {
  const scope = useRef({ mounted: true, hash: window.location.hash });
  useEffect(() => {
    scope.current.mounted = true;
    return () => {
      scope.current.mounted = false;
    };
  }, []);
  return () =>
    isCurrentWorkspaceRequest(
      scope.current.hash,
      window.location.hash,
      scope.current.mounted,
    );
}
