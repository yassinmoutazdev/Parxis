import { describe, it, expect } from 'vitest'

describe('Smoke Test', () => {
  it('should pass basic test', () => {
    expect(1 + 1).toBe(2)
  })

  it('should handle async tests', async () => {
    const result = await Promise.resolve('test')
    expect(result).toBe('test')
  })
})