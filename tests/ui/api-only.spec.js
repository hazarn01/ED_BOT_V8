// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('EDBotv8 API-Only Tests (No Browser)', () => {
  test('health endpoint responds correctly', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data).toHaveProperty('status');
    expect(data.status).toBe('healthy');
  });

  test('query endpoint handles STEMI protocol', async ({ request }) => {
    const response = await request.post('/api/v1/query', {
      data: {
        query: 'what is the STEMI protocol'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    expect(data).toHaveProperty('response');
    expect(data).toHaveProperty('query_type');
    expect(data.query_type.toLowerCase()).toBe('protocol');
    expect(data.response.length).toBeGreaterThan(10);
  });

  test('query endpoint handles contact lookup', async ({ request }) => {
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

  test('query endpoint validates medical queries', async ({ request }) => {
    const testCases = [
      { query: 'show me the blood transfusion form', expectedType: 'form' },
      { query: 'what is the epinephrine dose for cardiac arrest', expectedType: 'dosage' },
      // Note: Some queries may be classified as 'unknown' - this tests a known working type
      { query: 'what is the hypoglycemia treatment protocol', expectedType: 'protocol' }
    ];

    for (const testCase of testCases) {
      const response = await request.post('/api/v1/query', {
        data: { query: testCase.query }
      });
      
      expect(response.status()).toBe(200);
      const data = await response.json();
      
      expect(data.query_type.toLowerCase()).toBe(testCase.expectedType);
      expect(data).toHaveProperty('response');
      expect(data.response.length).toBeGreaterThan(5);
    }
  });

  test('API handles malformed requests gracefully', async ({ request }) => {
    // Test empty query
    const emptyResponse = await request.post('/api/v1/query', {
      data: { query: '' }
    });
    
    expect([400, 422]).toContain(emptyResponse.status());
    
    // Test missing query field
    const missingFieldResponse = await request.post('/api/v1/query', {
      data: {}
    });
    
    expect([400, 422]).toContain(missingFieldResponse.status());
  });
});