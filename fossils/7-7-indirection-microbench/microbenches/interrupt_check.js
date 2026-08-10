// Hot loop stressing the interrupt-check slot and bytecode dispatch. Both are
// affected by the value-mirror opts (perf 1/n, perf 6/n): the loop back-edge
// reads the interrupt flag on every iteration, and under NO_OPTS that read
// costs two loads instead of one.

function bench() {
  const N = 500_000_000;
  let s = 0;
  for (let i = 0; i < N; i++) {
    s = s + 1;
  }
  return s;
}

const r = bench();
if (r !== 500_000_000) {
  throw new Error("bad result: " + r);
}
