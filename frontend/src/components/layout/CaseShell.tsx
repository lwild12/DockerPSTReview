import { AppShell, Burger, Divider, NavLink, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconArrowLeft,
  IconEyeOff,
  IconFileExport,
  IconForms,
  IconHistory,
  IconHome2,
  IconListCheck,
  IconMail,
  IconUpload,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { getCase } from "../../api/cases";
import { AppHeader } from "./AppHeader";

const NAV_ITEMS = [
  { label: "Documents", path: "documents", icon: IconMail },
  { label: "Review Sets", path: "review-sets", icon: IconListCheck },
  { label: "Import", path: "import", icon: IconUpload },
  { label: "Coding Fields", path: "coding-fields", icon: IconForms },
  { label: "Redaction Log", path: "redaction-log", icon: IconEyeOff },
  { label: "Export", path: "export", icon: IconFileExport },
  { label: "Audit Log", path: "audit-log", icon: IconHistory },
];

export function CaseShell() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const location = useLocation();
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true);

  const { data: caseData } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
    enabled: caseId !== "",
  });

  const overviewPath = `/cases/${caseId}`;
  const overviewActive = location.pathname === overviewPath;

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 240,
        breakpoint: "sm",
        collapsed: { mobile: !mobileOpened, desktop: !desktopOpened },
      }}
      padding="lg"
    >
      <AppShell.Header>
        <AppHeader
          leftSection={
            <>
              <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" />
              <Burger
                opened={desktopOpened}
                onClick={toggleDesktop}
                visibleFrom="sm"
                size="sm"
              />
            </>
          }
        />
      </AppShell.Header>
      <AppShell.Navbar p="sm">
        <Stack gap={4}>
          <NavLink
            component={Link}
            to="/cases"
            label="All cases"
            leftSection={<IconArrowLeft size={16} />}
          />
          <Divider my="xs" />
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="xs" truncate>
            {caseData?.name ?? "Case"}
          </Text>
          <NavLink
            component={Link}
            to={overviewPath}
            label="Overview"
            leftSection={<IconHome2 size={16} />}
            active={overviewActive}
            variant="filled"
          />
          {NAV_ITEMS.map((item) => {
            const to = `${overviewPath}/${item.path}`;
            const active = location.pathname.startsWith(to);
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                component={Link}
                to={to}
                label={item.label}
                leftSection={<Icon size={16} />}
                active={active}
                variant="filled"
              />
            );
          })}
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
