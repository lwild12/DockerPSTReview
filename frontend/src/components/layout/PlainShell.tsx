import { AppShell } from "@mantine/core";
import { Outlet } from "react-router-dom";

import { AppHeader } from "./AppHeader";

export function PlainShell() {
  return (
    <AppShell header={{ height: 56 }} padding="lg">
      <AppShell.Header>
        <AppHeader />
      </AppShell.Header>
      <AppShell.Main className="app-shell-main">
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
