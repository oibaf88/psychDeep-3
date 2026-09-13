import { describe, it, expect } from 'vitest';
import { errorDetail } from './api';

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
