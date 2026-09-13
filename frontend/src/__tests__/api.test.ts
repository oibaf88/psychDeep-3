import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  getApiBase,
  getLegacyApiBaseOverride,
  clearLegacyApiBaseOverride,
  setApiBase,
  getToken,
  setToken,
  formatDateTime,
  formatDay,
  modelProvenanceLabel
} from '../api';

describe('api base functions', () => {
  const originalEnv = import.meta.env.VITE_API_BASE_URL;

  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    (import.meta.env as any).VITE_API_BASE_URL = originalEnv;
  });

  describe('getApiBase', () => {
    it('should return VITE_API_BASE_URL without trailing slash', () => {
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/');
      expect(getApiBase()).toBe('http://localhost:8000');
    });

    it('should return VITE_API_BASE_URL if it has no trailing slash', () => {
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
      expect(getApiBase()).toBe('http://localhost:8000');
    });

    it('should return empty string if VITE_API_BASE_URL is not set', () => {
      vi.stubEnv('VITE_API_BASE_URL', '');
      expect(getApiBase()).toBe('');
    });
  });

  describe('Legacy API Base Override', () => {
    it('should return legacy override from localStorage', () => {
      localStorage.setItem('psychapp_api_base', ' http://legacy.local ');
      expect(getLegacyApiBaseOverride()).toBe('http://legacy.local');
    });

    it('should return empty string if legacy override is not set', () => {
      expect(getLegacyApiBaseOverride()).toBe('');
    });

    it('should clear legacy override', () => {
      localStorage.setItem('psychapp_api_base', 'http://legacy.local');
      clearLegacyApiBaseOverride();
      expect(localStorage.getItem('psychapp_api_base')).toBeNull();
    });

    it('should clear legacy override when setApiBase is called', () => {
      localStorage.setItem('psychapp_api_base', 'http://legacy.local');
      setApiBase('http://new.local');
      expect(localStorage.getItem('psychapp_api_base')).toBeNull();
    });
  });

  describe('Token management', () => {
    it('should get token from localStorage', () => {
      localStorage.setItem('psychapp_token', 'my-token');
      expect(getToken()).toBe('my-token');
    });

    it('should return null if token is not set', () => {
      expect(getToken()).toBeNull();
    });

    it('should set token in localStorage', () => {
      setToken('new-token');
      expect(localStorage.getItem('psychapp_token')).toBe('new-token');
    });

    it('should remove token from localStorage when set to null', () => {
      localStorage.setItem('psychapp_token', 'my-token');
      setToken(null);
      expect(localStorage.getItem('psychapp_token')).toBeNull();
    });

    it('should remove token from localStorage when set to empty string', () => {
      localStorage.setItem('psychapp_token', 'my-token');
      setToken('');
      expect(localStorage.getItem('psychapp_token')).toBeNull();
    });
  });

  describe('formatDateTime', () => {
    it('should format date correctly', () => {
      expect(formatDateTime(null)).toBe('—');
      expect(formatDateTime('')).toBe('—');
      expect(formatDateTime('invalid-date')).toBe('—');
      expect(typeof formatDateTime('2023-01-01T12:00:00Z')).toBe('string');
      expect(formatDateTime('2023-01-01T12:00:00Z')).not.toBe('—');
    });
  });

  describe('formatDay', () => {
    it('should format day correctly', () => {
      expect(formatDay(null)).toBe('—');
      expect(formatDay('')).toBe('—');
      expect(formatDay('invalid-date')).toBe('invalid-date'); // As per implementation
      expect(typeof formatDay('2023-01-01')).toBe('string');
      expect(formatDay('2023-01-01')).not.toBe('—');
    });
  });

  describe('modelProvenanceLabel', () => {
    it('should return null if no provider or model', () => {
      expect(modelProvenanceLabel({})).toBeNull();
    });

    it('should return label for unknown provider', () => {
      expect(modelProvenanceLabel({ model: 'gpt-4' })).toBe('gpt-4');
    });

    it('should handle openai_compatible provider with base_url', () => {
      expect(modelProvenanceLabel({ provider: 'openai_compatible', model: 'llama-3', provider_base_url: 'http://my-server.com/api' })).toBe('llama-3 · servidor propio (my-server.com)');
    });

    it('should handle openai_compatible provider without base_url', () => {
      expect(modelProvenanceLabel({ provider: 'openai_compatible', model: 'llama-3' })).toBe('llama-3 · servidor propio');
    });

    it('should handle anthropic provider', () => {
      expect(modelProvenanceLabel({ provider: 'anthropic', model: 'claude-3' })).toBe('claude-3 · Claude / Anthropic');
    });
  });
});
