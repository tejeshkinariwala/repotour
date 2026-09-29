// Small math helpers.
// Kept free of any other imports.
export function add(a: number, b: number): number {
  return a + b;
}

export async function slowAdd(a: number, b: number) {
  return add(a, b);
}

export function* counter(limit: number) {
  for (let i = 0; i < limit; i++) yield i;
}

function _scale(x: number): number {
  return x * 2;
}

export const double = (x: number): number => _scale(x);

const triple = async (x: number) => x * 3;

export const half = function (x: number) {
  return x / 2;
};

export { triple };
