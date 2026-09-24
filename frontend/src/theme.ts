import { createTheme, type MantineColorsTuple } from "@mantine/core";

const indigo: MantineColorsTuple = [
  "#eef1fd",
  "#dde2fa",
  "#b8c1f2",
  "#8f9cea",
  "#6e7de3",
  "#5868df",
  "#4a5add",
  "#3d4cc4",
  "#3542af",
  "#28359b",
];

export const theme = createTheme({
  primaryColor: "indigo",
  primaryShade: { light: 6, dark: 5 },
  colors: {
    indigo,
  },
  defaultRadius: "md",
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  fontFamilyMonospace:
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
  headings: {
    fontWeight: "650",
    sizes: {
      h1: { lineHeight: "1.2" },
      h2: { lineHeight: "1.25" },
      h3: { lineHeight: "1.3" },
    },
  },
  shadows: {
    xs: "0 1px 2px rgba(15, 23, 42, 0.06)",
    sm: "0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.06)",
    md: "0 4px 12px rgba(15, 23, 42, 0.08)",
    lg: "0 8px 24px rgba(15, 23, 42, 0.12)",
    xl: "0 16px 40px rgba(15, 23, 42, 0.16)",
  },
  components: {
    Card: {
      defaultProps: {
        withBorder: true,
        radius: "lg",
      },
    },
    Paper: {
      defaultProps: {
        radius: "lg",
      },
    },
    Modal: {
      defaultProps: {
        radius: "lg",
        shadow: "xl",
        centered: true,
        overlayProps: { backgroundOpacity: 0.45, blur: 2 },
      },
    },
    Table: {
      defaultProps: {
        verticalSpacing: "sm",
        highlightOnHover: true,
      },
    },
    Badge: {
      defaultProps: {
        radius: "sm",
      },
    },
    Button: {
      defaultProps: {
        radius: "md",
      },
      styles: {
        root: { fontWeight: 550 },
      },
    },
    ActionIcon: {
      defaultProps: {
        radius: "md",
      },
    },
    Menu: {
      defaultProps: {
        radius: "md",
        shadow: "md",
      },
    },
    NavLink: {
      styles: {
        root: {
          borderRadius: "var(--mantine-radius-md)",
        },
        label: {
          fontWeight: 500,
        },
      },
    },
    Tooltip: {
      defaultProps: {
        radius: "sm",
        withArrow: true,
      },
    },
  },
});
