// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('EDBotv8 Query Interface', () => {
  test('query API should handle medical queries', async ({ request }) => {
    // Test a medical protocol query
    const response = await request.post('/api/v1/query', {
      data: {
        query: 'what is the STEMI protocol'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    // Verify response structure
    expect(data).toHaveProperty('response');
    expect(data).toHaveProperty('query_type');
    expect(data).toHaveProperty('confidence');
    expect(data).toHaveProperty('sources');
    
    // Should be classified as PROTOCOL (API returns lowercase)
    expect(data.query_type.toLowerCase()).toBe('protocol');
    expect(data.confidence).toBeGreaterThan(0.7);
    expect(data.response.length).toBeGreaterThan(50);
  });

  test('query API should handle contact queries', async ({ request }) => {
    const response = await request.post('/api/v1/query', {
      data: {
        query: 'who is on call for cardiology'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data.query_type.toLowerCase()).toBe('contact');
    expect(data).toHaveProperty('response');
  });

  test('query API should handle form requests', async ({ request }) => {
    const response = await request.post('/api/v1/query', {
      data: {
        query: 'show me the blood transfusion form'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data.query_type.toLowerCase()).toBe('form');
    expect(data).toHaveProperty('response');
  });

  test('query API should handle dosage questions', async ({ request }) => {
    const response = await request.post('/api/v1/query', {
      data: {
        query: 'what is the epinephrine dose for cardiac arrest'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data.query_type.toLowerCase()).toBe('dosage');
    expect(data).toHaveProperty('response');
    expect(data.response).toContain('epinephrine');
  });
});