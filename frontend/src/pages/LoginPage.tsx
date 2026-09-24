import {
  Alert,
  Anchor,
  Box,
  Button,
  Divider,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { IconMailSearch } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getRegistrationEnabled } from "../api/auth";
import { getOidcPublicConfig, oidcLoginUrl } from "../api/oidc";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: oidcConfig } = useQuery({
    queryKey: ["oidc-public-config"],
    queryFn: getOidcPublicConfig,
  });

  const { data: registrationEnabled } = useQuery({
    queryKey: ["registration-enabled"],
    queryFn: getRegistrationEnabled,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/cases");
    } catch {
      setError("Invalid email or password");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box
      mih="100vh"
      className="auth-page-bg"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem 1rem",
      }}
    >
      <Stack align="center" gap="xl" w={380} maw="100%">
        <Stack align="center" gap={6}>
          <ThemeIcon
            size={52}
            radius="lg"
            variant="gradient"
            gradient={{ from: "indigo.6", to: "indigo.4", deg: 135 }}
          >
            <IconMailSearch size={28} stroke={1.75} />
          </ThemeIcon>
          <Title order={2} ta="center">
            PST Document Review
          </Title>
          <Text size="sm" c="dimmed" ta="center">
            Sign in to continue to your cases
          </Text>
        </Stack>
        <Paper withBorder shadow="lg" p="xl" w="100%">
          <form onSubmit={handleSubmit}>
            <Stack>
              {error && (
                <Alert color="red" title="Login failed" radius="md">
                  {error}
                </Alert>
              )}
              <TextInput
                label="Email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
              />
              <PasswordInput
                label="Password"
                required
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
              />
              <Button type="submit" loading={submitting} fullWidth mt="xs">
                Sign in
              </Button>
              {registrationEnabled !== false && (
                <Text size="sm" ta="center">
                  Need an account? <Anchor component={Link} to="/register">Register</Anchor>
                </Text>
              )}
            </Stack>
          </form>
          {oidcConfig?.enabled && (
            <>
              <Divider label="or" labelPosition="center" my="md" />
              <Button component="a" href={oidcLoginUrl()} variant="outline" fullWidth>
                Sign in with {oidcConfig.display_name}
              </Button>
            </>
          )}
        </Paper>
      </Stack>
    </Box>
  );
}
