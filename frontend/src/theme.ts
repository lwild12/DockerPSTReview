import { createTheme, type MantineColorsTuple } from "@mantine/core";

const indigo: MantineColorsTuple = [
  "#eef1fd",
  "#dde2fa",
  "#b8c1f2",
  "#909ee9",
  "#6f80e2",
  "#5a6cde",
  "#4f62dc",
  "#4053c3",
  "#3849af",
  "#2b3c9b",
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
  headings: {
    fontWeight: "600",
  },
  shadows: {
    xs: "0 1px 2px rgba(15, 23, 42, 0.06)",
    sm: "0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.06)",
    md: "0 4px 10px rgba(15, 23, 42, 0.08)",
  },
  components: {
    Card: {
      defaultProps: {
        withBorder: true,
        radius: "md",
      },
    },
    Paper: {
      defaultProps: {
        radius: "md",
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
  },
});
