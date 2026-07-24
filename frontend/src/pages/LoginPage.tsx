import {
  Alert,
  Anchor,
  Button,
  Divider,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

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
    <Stack align="center" justify="center" mih="100vh">
      <Paper withBorder shadow="md" p="xl" w={380}>
        <Title order={2} mb="lg">
          PST Document Review
        </Title>
        <form onSubmit={handleSubmit}>
          <Stack>
            {error && (
              <Alert color="red" title="Login failed">
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
            <Button type="submit" loading={submitting} fullWidth>
              Sign in
            </Button>
            <Text size="sm" ta="center">
              Need an account? <Anchor component={Link} to="/register">Register</Anchor>
            </Text>
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
  );
}
