import { describe, expect, it } from 'vitest';
import { paraCentavos } from './api';

describe('paraCentavos', () => {
  it.each([
    ['45,90', 4590], ['45.90', 4590], ['45', 4500], ['0,5', 50], ['1.234,56', 123456],
    ['1.234', 123400], ['1.234.567,8', 123456780], ['  12,30 ', 1230], ['R$ 10,00', 1000],
  ])('%s vira %i centavos', (texto, centavos) => {
    expect(paraCentavos(texto)).toBe(centavos);
  });

  it.each(['', 'abc', '-5', '1,2,3', '12.345.6'])('%s é inválido', (texto) => {
    expect(Number.isNaN(paraCentavos(texto))).toBe(true);
  });
});
