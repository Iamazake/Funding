import type { AnchorHTMLAttributes, MouseEvent } from "react";

interface AppLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> { to: string; onNavigate: (path: string) => void; }

export function AppLink({ to, onNavigate, onClick, ...props }: AppLinkProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onNavigate(to);
  };
  return <a href={to} onClick={handleClick} {...props} />;
}
