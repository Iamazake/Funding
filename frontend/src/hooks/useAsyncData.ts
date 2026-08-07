import { useCallback, useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: null; error: string };

export function useAsyncData<T>(loader: () => Promise<T>) {
  const [reloadToken, setReloadToken] = useState(0);
  const [state, setState] = useState<AsyncState<T>>({ status: "loading", data: null, error: null });

  useEffect(() => {
    let active = true;
    setState({ status: "loading", data: null, error: null });
    loader()
      .then((data) => { if (active) setState({ status: "success", data, error: null }); })
      .catch((error: unknown) => { if (active) setState({ status: "error", data: null, error: error instanceof Error ? error.message : "Não foi possível carregar os dados." }); });
    return () => { active = false; };
  }, [loader, reloadToken]);

  const reload = useCallback(() => setReloadToken((value) => value + 1), []);
  return { state, reload };
}
