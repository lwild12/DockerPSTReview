import { Anchor, Badge, Button, Checkbox, Container, Group, Stack, Table, Text, Title } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listAdminUsers, getSystemSettings, updateAdminUser, updateSystemSettings } from "../api/admin";
import { useAuth } from "../hooks/useAuth";

export function AdminPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: listAdminUsers,
  });

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: getSystemSettings,
  });

  const updateUserMutation = useMutation({
    mutationFn: ({
      userId,
      payload,
    }: {
      userId: string;
      payload: { is_active?: boolean; is_superuser?: boolean };
    }) => updateAdminUser(userId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const updateSettingsMutation = useMutation({
    mutationFn: (payload: { enable_api_docs?: boolean; cookie_secure?: boolean }) =>
      updateSystemSettings(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-settings"] }),
  });

  return (
    <Container size="lg" py="xl">
      <Anchor component={Link} to="/cases" size="sm">
        ← Back to cases
      </Anchor>
      <Title order={2} mt="sm" mb="lg">
        Admin
      </Title>

      <Title order={4} mb="sm">
        Users
      </Title>
      {usersLoading && <Text>Loading...</Text>}
      {users && (
        <Table striped highlightOnHover mb="xl">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Email</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users.map((u) => {
              const isSelf = u.id === user?.id;
              return (
                <Table.Tr key={u.id}>
                  <Table.Td>{u.email}</Table.Td>
                  <Table.Td>{u.full_name || <Text c="dimmed">—</Text>}</Table.Td>
                  <Table.Td>
                    <Badge color={u.is_active ? "green" : "gray"} size="sm">
                      {u.is_active ? "active" : "deactivated"}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={u.is_superuser ? "violet" : "gray"} size="sm" variant="light">
                      {u.is_superuser ? "superuser" : "user"}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs" justify="flex-end">
                      <Button
                        size="xs"
                        variant="subtle"
                        disabled={isSelf}
                        title={isSelf ? "You can't change your own account" : undefined}
                        onClick={() =>
                          updateUserMutation.mutate({
                            userId: u.id,
                            payload: { is_active: !u.is_active },
                          })
                        }
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                      <Button
                        size="xs"
                        variant="subtle"
                        disabled={isSelf}
                        title={isSelf ? "You can't change your own account" : undefined}
                        onClick={() =>
                          updateUserMutation.mutate({
                            userId: u.id,
                            payload: { is_superuser: !u.is_superuser },
                          })
                        }
                      >
                        {u.is_superuser ? "Demote" : "Promote"}
                      </Button>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <Title order={4} mb="sm">
        System settings
      </Title>
      {settingsLoading && <Text>Loading...</Text>}
      {settings && (
        <Stack gap="sm" maw={520}>
          <Checkbox
            label="Enable API docs (Swagger UI at /docs, ReDoc at /redoc)"
            description="Applies immediately — no restart needed."
            checked={settings.enable_api_docs}
            onChange={(e) =>
              updateSettingsMutation.mutate({ enable_api_docs: e.currentTarget.checked })
            }
          />
          <Checkbox
            label="Require secure (HTTPS-only) cookies"
            description="Takes effect after restarting the backend — leave off for plain-HTTP installs."
            checked={settings.cookie_secure}
            onChange={(e) =>
              updateSettingsMutation.mutate({ cookie_secure: e.currentTarget.checked })
            }
          />
        </Stack>
      )}
    </Container>
  );
}
