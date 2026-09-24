import {
  ActionIcon,
  Avatar,
  Group,
  Menu,
  Text,
  ThemeIcon,
  useMantineColorScheme,
} from "@mantine/core";
import { IconLogout, IconMailSearch, IconMoon, IconSettings, IconSun } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

export function AppHeader({ leftSection }: { leftSection?: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { colorScheme, setColorScheme } = useMantineColorScheme();

  return (
    <Group
      h="100%"
      px="md"
      justify="space-between"
      wrap="nowrap"
      style={{
        borderBottom: "1px solid var(--mantine-color-default-border)",
        backdropFilter: "blur(8px)",
      }}
    >
      <Group gap="sm" wrap="nowrap">
        {leftSection}
        <Link
          to="/cases"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            textDecoration: "none",
            color: "inherit",
          }}
        >
          <ThemeIcon
            size={30}
            radius="md"
            variant="gradient"
            gradient={{ from: "indigo.6", to: "indigo.4", deg: 135 }}
          >
            <IconMailSearch size={18} stroke={2} />
          </ThemeIcon>
          <Text fw={700} size="md" lh={1}>
            PST Review
          </Text>
        </Link>
      </Group>
      <Group gap="xs" wrap="nowrap">
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={() => setColorScheme(colorScheme === "dark" ? "light" : "dark")}
          aria-label="Toggle color scheme"
        >
          {colorScheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
        </ActionIcon>
        <Menu position="bottom-end" width={200}>
          <Menu.Target>
            <ActionIcon variant="subtle" color="gray" radius="xl" size="lg">
              <Avatar size={28} radius="xl" color="indigo">
                {user?.email ? user.email[0].toUpperCase() : "?"}
              </Avatar>
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Label>{user?.email}</Menu.Label>
            {user?.is_superuser && (
              <Menu.Item component={Link} to="/admin" leftSection={<IconSettings size={14} />}>
                Admin
              </Menu.Item>
            )}
            <Menu.Item
              color="red"
              leftSection={<IconLogout size={14} />}
              onClick={() => {
                logout().catch(() => {});
                navigate("/login");
              }}
            >
              Sign out
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </Group>
    </Group>
  );
}
