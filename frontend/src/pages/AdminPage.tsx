import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  Code,
  Container,
  Group,
  PasswordInput,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  listAdminUsers,
  getSystemSettings,
  updateAdminUser,
  updateSystemSettings,
  type SystemSettings,
} from "../api/admin";
import { useAuth } from "../hooks/useAuth";

function OidcSettings({ settings }: { settings: SystemSettings }) {
  const queryClient = useQueryClient();
  const [issuerUrl, setIssuerUrl] = useState(settings.oidc_issuer_url);
  const [clientId, setClientId] = useState(settings.oidc_client_id);
  const [clientSecret, setClientSecret] = useState("");
  const [displayName, setDisplayName] = useState(settings.oidc_display_name);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (initialized) return;
    setIssuerUrl(settings.oidc_issuer_url);
    setClientId(settings.oidc_client_id);
    setDisplayName(settings.oidc_display_name);
    setInitialized(true);
  }, [settings, initialized]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateSystemSettings({
        oidc_issuer_url: issuerUrl,
        oidc_client_id: clientId,
        oidc_display_name: displayName,
        ...(clientSecret ? { oidc_client_secret: clientSecret } : {}),
      }),
    onSuccess: () => {
      setClientSecret("");
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
    },
  });

  const toggleEnabledMutation = useMutation({
    mutationFn: (enabled: boolean) => updateSystemSettings({ oidc_enabled: enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-settings"] }),
  });

  const callbackUrl =
    typeof window !== "undefined" ? `${window.location.origin}/api/auth/oidc/callback` : "";

  return (
    <Stack gap="sm" maw={520}>
      <Text size="sm" c="dimmed">
        Register this redirect URI with your identity provider:
      </Text>
      <Code block fz="xs">
        {callbackUrl}
      </Code>
      <TextInput
        label="Issuer URL"
        placeholder="https://your-idp.example.com"
        value={issuerUrl}
        onChange={(e) => setIssuerUrl(e.currentTarget.value)}
      />
      <TextInput
        label="Client ID"
        value={clientId}
        onChange={(e) => setClientId(e.currentTarget.value)}
      />
      <PasswordInput
        label="Client secret"
        placeholder={settings.oidc_client_secret_set ? "•••••••• (configured — leave blank to keep)" : "Not set"}
        value={clientSecret}
        onChange={(e) => setClientSecret(e.currentTarget.value)}
      />
      <TextInput
        label="Button label"
        description='Shown on the login page as "Sign in with ..."'
        value={displayName}
        onChange={(e) => setDisplayName(e.currentTarget.value)}
      />
      <Button
        variant="light"
        loading={saveMutation.isPending}
        onClick={() => saveMutation.mutate()}
      >
        Save OIDC settings
      </Button>
      {saveMutation.isError && (
        <Text c="red" size="sm">
          Couldn't save — check the values and try again.
        </Text>
      )}
      <Checkbox
        label="Enable OIDC login"
        description="Requires an issuer URL, client ID, and client secret to already be saved."
        checked={settings.oidc_enabled}
        onChange={(e) => toggleEnabledMutation.mutate(e.currentTarget.checked)}
      />
      {toggleEnabledMutation.isError && (
        <Text c="red" size="sm">
          Couldn't enable OIDC — make sure the issuer URL, client ID, and client secret are all
          saved first.
        </Text>
      )}
    </Stack>
  );
}

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

      <Title order={4} mt="xl" mb="sm">
        OIDC login
      </Title>
      {settings && <OidcSettings settings={settings} />}
    </Container>
  );
}
