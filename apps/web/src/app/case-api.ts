export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
      return String(payload.detail[0].msg);
    }
  } catch {
    return `${response.status} ${response.statusText}`;
  }

  return "Request failed.";
}
