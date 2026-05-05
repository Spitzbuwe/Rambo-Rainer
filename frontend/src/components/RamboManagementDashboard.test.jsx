import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { RamboManagementDashboard } from './RamboManagementDashboard.jsx';

const API = 'http://test.rambo.local:9';

/** Mock-Daten (Tests + teilweise analog zur API-Form). */
const MOCK = {
  health: { status: 'healthy', server_id: 'backend/server.py ACTIVE' },
  summary: {
    success: true,
    rules_total: 5,
    count_active: 4,
    count_by_group: { behavior: 3, language: 2 },
  },
  status: {
    success: true,
    active_rules_count: 4,
    rule_history_entries: 10,
    rollback_available: true,
    builtin_presets: 5,
  },
  history: {
    success: true,
    entries: [
      { id: 'h1', action: 'rules_preset_applied', timestamp: '2025-04-18T09:50:00Z' },
      { id: 'h2', action: 'rule_meta_updated', timestamp: '2025-04-18T09:45:00Z' },
      { id: 'h3', action: 'rule_learned', timestamp: '2025-04-18T09:40:00Z' },
    ],
  },
  presets: {
    success: true,
    presets: [
      { id: 'strict', name: 'Strict' },
      { id: 'permissive', name: 'Permissive' },
    ],
  },
  backup: {
    success: true,
    created_at: '2025-04-18T09:00:00Z',
    backup_kind: 'rambo_rules_backup_light_v1',
  },
};

function jsonResponse(data, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: async () => data,
  });
}

function setupFetchAllSuccess() {
  globalThis.fetch = vi.fn((url, _opts) => {
    const u = String(url);
    if (u.includes('/api/health')) return jsonResponse(MOCK.health);
    if (u.includes('/api/rules/summary')) return jsonResponse(MOCK.summary);
    if (u.includes('/api/rules/status')) return jsonResponse(MOCK.status);
    if (u.includes('/api/rules/history')) return jsonResponse(MOCK.history);
    if (u.includes('/api/rules/presets')) return jsonResponse(MOCK.presets);
    if (u.includes('/api/rules/backup')) return jsonResponse(MOCK.backup);
    return jsonResponse({}, false, 404);
  });
}

describe('RamboManagementDashboard', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('rendert ohne Fehler', async () => {
    setupFetchAllSuccess();
    render(<RamboManagementDashboard apiBase={API} adminToken="test-admin" refreshIntervalMs={0} />);
    await waitFor(() => {
      expect(screen.getByText('Rambo Management')).toBeInTheDocument();
    });
  });

  it('zeigt Health-Status Online', async () => {
    setupFetchAllSuccess();
    render(<RamboManagementDashboard apiBase={API} adminToken="test-admin" refreshIntervalMs={0} />);
    expect(await screen.findByText('Online')).toBeInTheDocument();
  });

  it('zeigt Summary-Zahlen', async () => {
    setupFetchAllSuccess();
    render(<RamboManagementDashboard apiBase={API} adminToken="test-admin" refreshIntervalMs={0} />);
    const summaryCards = await screen.findAllByRole('region', { name: 'Policy Summary' });
    const summaryCard = summaryCards[0];
    expect(summaryCard.textContent).toMatch(/5/);
    expect(summaryCard.textContent).toMatch(/Regeln gesamt/);
    expect(summaryCard.textContent).toMatch(/2 Gruppen/);
  });

  it('listet History-Einträge auf', async () => {
    setupFetchAllSuccess();
    render(<RamboManagementDashboard apiBase={API} adminToken="test-admin" refreshIntervalMs={0} />);
    expect((await screen.findAllByText(/rules_preset_applied/))[0]).toBeInTheDocument();
    expect(screen.getAllByText(/rule_meta_updated/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/rule_learned/)[0]).toBeInTheDocument();
  });

  it('zeigt Preset-Namen', async () => {
    setupFetchAllSuccess();
    render(<RamboManagementDashboard apiBase={API} adminToken="test-admin" refreshIntervalMs={0} />);
    expect((await screen.findAllByText('Strict'))[0]).toBeInTheDocument();
    expect(screen.getAllByText('Permissive')[0]).toBeInTheDocument();
  });

  it('zeigt Error-State bei Fetch-Fehler', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('network')));
    render(<RamboManagementDashboard apiBase={API} adminToken="test-admin" refreshIntervalMs={0} />);
    expect(await screen.findByText('API nicht erreichbar')).toBeInTheDocument();
    expect(await screen.findByText('Offline')).toBeInTheDocument();
  });
});
