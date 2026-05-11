export type ApiRecord = Record<string, unknown>;

export const toApiRecord = (value: unknown): ApiRecord =>
  typeof value === 'object' && value !== null ? (value as ApiRecord) : {};

export const getEnvelopeData = (payload: unknown): ApiRecord => toApiRecord(toApiRecord(payload).data);

export const getEnvelopeValue = (payload: unknown, key: string): unknown => {
  const root = toApiRecord(payload);
  const data = getEnvelopeData(root);
  return key in data ? data[key] : root[key];
};

export const getEnvelopeList = <T = unknown>(
  payload: unknown,
  keys: readonly string[]
): T[] => {
  const root = toApiRecord(payload);
  const data = getEnvelopeData(root);

  for (const key of keys) {
    const nestedValue = data[key];
    if (Array.isArray(nestedValue)) {
      return nestedValue as T[];
    }

    const rootValue = root[key];
    if (Array.isArray(rootValue)) {
      return rootValue as T[];
    }
  }

  return [];
};

