import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  getApiBase,
  getToken,
  setToken,
  formatDateTime,
  formatDay,
  modelProvenanceLabel,
  errorDetail,
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

describe('errorDetail', () => {
  const fallback = 'An unexpected error occurred';

  it('should return fallback when body is not an object', () => {
    expect(errorDetail(null, fallback)).toBe(fallback);
    expect(errorDetail(undefined, fallback)).toBe(fallback);
    expect(errorDetail('string', fallback)).toBe(fallback);
    expect(errorDetail(123, fallback)).toBe(fallback);
  });

  it('should return fallback when body is an object without a detail property', () => {
    expect(errorDetail({}, fallback)).toBe(fallback);
    expect(errorDetail({ otherKey: 'value' }, fallback)).toBe(fallback);
  });

  it('should return the string detail when body.detail is a string', () => {
    expect(errorDetail({ detail: 'Specific error message' }, fallback)).toBe('Specific error message');
  });

  it('should format array of validation errors correctly', () => {
    const body = {
      detail: [
        {
          type: 'missing',
          loc: ['body', 'username'],
          msg: 'Field required',
          input: null
        },
        {
          type: 'string_too_short',
          loc: ['body', 'password'],
          msg: 'String should have at least 8 characters',
          input: '123'
        }
      ]
    };
    const expected = 'username: Field required. password: String should have at least 8 characters';
    expect(errorDetail(body, fallback)).toBe(expected);
  });

  it('should filter out "body" from loc array', () => {
    const body = {
      detail: [
        {
          loc: ['body', 'user', 'profile', 'age'],
          msg: 'Must be an integer'
        }
      ]
    };
    expect(errorDetail(body, fallback)).toBe('user · profile · age: Must be an integer');
  });

  it('should handle elements without loc', () => {
    const body = {
      detail: [
        {
          msg: 'General validation error'
        }
      ]
    };
    expect(errorDetail(body, fallback)).toBe('General validation error');
  });

  it('should handle malformed array elements gracefully', () => {
    const body = {
      detail: [
        null,
        'string instead of object',
        { missingMsg: true },
        { msg: 123 }, // msg is not a string
        { msg: 'Valid message' }
      ]
    };
    expect(errorDetail(body, fallback)).toBe('Valid message');
  });

  it('should return fallback if array parsing results in empty messages', () => {
    const body = {
      detail: [
        null,
        'string instead of object',
        { missingMsg: true }
      ]
    };
    expect(errorDetail(body, fallback)).toBe(fallback);
  });
});
