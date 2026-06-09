import { describe, expect, it, vi } from 'vitest';
import { createSettingsDataLoader, loadSettingsData, type SettingsDataApi } from './settingsData';

const ok = (data: Record<string, unknown> = {}) => ({
  success: true,
  message: 'ok',
  data,
  timestamp: '2026-06-09T00:00:00Z',
});

const createApi = (): SettingsDataApi => ({
  initializeSettings: vi.fn(async () => ok({ message: 'initialized' })),
  getSettingsSchema: vi.fn(async () =>
    ok({
      sections: [
        {
          section: 'platform',
          title: 'Platform',
          description: 'Platform settings',
          fields: [],
        },
      ],
    })
  ),
  getSettings: vi.fn(async () =>
    ok({
      sections: [
        {
          section: 'platform',
          settings: [
            {
              key: 'coming_soon_enabled',
              value_type: 'boolean',
              default_value: false,
              value: 'true',
            },
          ],
        },
      ],
    })
  ),
});

describe('settings data loader', () => {
  it('initializes settings before fetching schema and values', async () => {
    const api = createApi();
    const calls: string[] = [];
    vi.mocked(api.initializeSettings).mockImplementation(async () => {
      calls.push('initialize');
      return ok({ message: 'initialized' });
    });
    vi.mocked(api.getSettingsSchema).mockImplementation(async () => {
      calls.push('schema');
      return ok({ sections: [] });
    });
    vi.mocked(api.getSettings).mockImplementation(async () => {
      calls.push('settings');
      return ok({ sections: [] });
    });

    await loadSettingsData(api);

    expect(calls[0]).toBe('initialize');
    expect(calls.slice(1).sort()).toEqual(['schema', 'settings']);
  });

  it('parses persisted Coming Soon state from saved settings', async () => {
    const api = createApi();

    const loaded = await loadSettingsData(api);

    expect(loaded.formValues.platform.coming_soon_enabled).toBe(true);
  });

  it('deduplicates concurrent initialization requests', async () => {
    const api = createApi();
    let resolveInitialize: (value: Awaited<ReturnType<SettingsDataApi['initializeSettings']>>) => void;
    vi.mocked(api.initializeSettings).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveInitialize = resolve;
        })
    );

    const loader = createSettingsDataLoader(api);
    const first = loader();
    const second = loader();
    resolveInitialize!(ok({ message: 'initialized' }));

    await Promise.all([first, second]);

    expect(api.initializeSettings).toHaveBeenCalledTimes(1);
    expect(api.getSettings).toHaveBeenCalledTimes(1);
  });

  it('surfaces GET settings failures', async () => {
    const api = createApi();
    vi.mocked(api.getSettings).mockResolvedValue({
      success: false,
      message: 'database scan failed',
      timestamp: '2026-06-09T00:00:00Z',
    });

    await expect(loadSettingsData(api)).rejects.toThrow('database scan failed');
  });

  it('allows retry after a failed load', async () => {
    const api = createApi();
    vi.mocked(api.getSettings)
      .mockResolvedValueOnce({
        success: false,
        message: 'temporary failure',
        timestamp: '2026-06-09T00:00:00Z',
      })
      .mockResolvedValueOnce(ok({ sections: [] }));

    const loader = createSettingsDataLoader(api);
    await expect(loader()).rejects.toThrow('temporary failure');
    await expect(loader()).resolves.toMatchObject({ formValues: {} });

    expect(api.initializeSettings).toHaveBeenCalledTimes(2);
    expect(api.getSettings).toHaveBeenCalledTimes(2);
  });
});
