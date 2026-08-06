import { useCallback, useEffect, useState } from "react";

export function useRouter() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = useCallback((nextPath: string, replace = false) => {
    const nextUrl = new URL(nextPath, window.location.origin);
    if (nextUrl.pathname === window.location.pathname && nextUrl.search === window.location.search) return;
    window.history[replace ? "replaceState" : "pushState"]({}, "", nextPath);
    setPath(nextUrl.pathname);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return { path, navigate };
}
