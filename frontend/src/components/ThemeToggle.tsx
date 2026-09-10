import { useTheme } from "../lib/theme";
import { Select } from "./ui";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Select
      aria-label="Colour theme"
      value={theme}
      onChange={setTheme}
      options={[
        { value: "system", label: "◐ System" },
        { value: "light", label: "☀ Light" },
        { value: "dark", label: "☾ Dark" },
      ]}
      style={{ width: "auto" }}
    />
  );
}
