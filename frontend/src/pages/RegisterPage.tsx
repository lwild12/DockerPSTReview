import {
  Alert,
  Anchor,
  Box,
  Button,
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

import { getRegistrationEnabled, register } from "../api/auth";
import { ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";

function AuthLayout({ children }: { children: React.ReactNode }) {
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
        <ThemeIcon
          size={52}
          radius="lg"
          variant="gradient"
          gradient={{ from: "indigo.6", to: "indigo.4", deg: 135 }}
        >
          <IconMailSearch size={28} stroke={1.75} />
        </ThemeIcon>
        {children}
      </Stack>
    </Box>
  );
}

export function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { data: registrationEnabled, isLoading: checkingRegistration } = useQuery({
    queryKey: ["registration-enabled"],
    queryFn: getRegistrationEnabled,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, fullName);
      await login(email, password);
      navigate("/cases");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError("That email is already registered, or the password is too weak.");
      } else if (err instanceof ApiError && err.status === 403) {
        setError("Registration is currently disabled.");
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!checkingRegistration && registrationEnabled === false) {
    return (
      <AuthLayout>
        <Paper withBorder shadow="lg" p="xl" w="100%">
          <Title order={2} mb="lg" ta="center">
            Registration disabled
          </Title>
          <Text size="sm" c="dimmed" mb="md">
            New accounts aren't being accepted right now. Ask a case admin to add you, or check
            back later.
          </Text>
          <Anchor component={Link} to="/login" size="sm">
            ← Back to sign in
          </Anchor>
        </Paper>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Title order={2} ta="center">
        Create your account
      </Title>
      <Paper withBorder shadow="lg" p="xl" w="100%">
        <form onSubmit={handleSubmit}>
          <Stack>
            {error && (
              <Alert color="red" title="Couldn't create account" radius="md">
                {error}
              </Alert>
            )}
            <TextInput
              label="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.currentTarget.value)}
            />
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
              Register
            </Button>
            <Text size="sm" ta="center">
              Already have an account? <Anchor component={Link} to="/login">Sign in</Anchor>
            </Text>
          </Stack>
        </form>
      </Paper>
    </AuthLayout>
  );
}
