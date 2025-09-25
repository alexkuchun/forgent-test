import * as React from "react";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "ghost" | "destructive";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant = "default", ...props }, ref) => {
    const base =
      "btn inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 disabled:opacity-50";
    const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
      default:
        "bg-slate-800 text-slate-100 hover:bg-slate-700 focus:ring-slate-600",
      primary: "bg-blue-600 text-white hover:bg-blue-500 focus:ring-blue-500",
      ghost:
        "bg-transparent hover:bg-slate-800/50 text-slate-100 focus:ring-slate-600",
      destructive: "!bg-red-600 text-white hover:!bg-red-500 focus:ring-red-600",
    };
    return (
      <button
        ref={ref}
        className={`${base} ${variants[variant]} ${className}`}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
