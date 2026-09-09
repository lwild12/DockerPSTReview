import { Stack, Text, ThemeIcon } from "@mantine/core";
import type { IconProps } from "@tabler/icons-react";
import type { ComponentType, ReactNode } from "react";

type TablerIcon = ComponentType<IconProps>;

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: TablerIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Stack align="center" gap="xs" py={60}>
      <ThemeIcon size={48} radius="xl" variant="light" color="gray">
        <Icon size={24} stroke={1.5} />
      </ThemeIcon>
      <Text fw={600}>{title}</Text>
      {description && (
        <Text size="sm" c="dimmed" maw={360} ta="center">
          {description}
        </Text>
      )}
      {action}
    </Stack>
  );
}
