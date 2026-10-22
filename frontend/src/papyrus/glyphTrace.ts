// Recover a centreline from the exact locally rasterised glyph. The resulting
// order field follows curves and branches; it is not a horizontal reveal mask.
// Pure pixel processing, no network, dependencies or personal text storage.
export function traceGlyph(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
) {
  const n = width * height,
    mask = new Uint8Array(n),
    thin = new Uint8Array(n);
  for (let i = 0; i < n; i++) mask[i] = thin[i] = rgba[i * 4 + 3] > 80 ? 1 : 0;
  const around = [
    -width,
    1 - width,
    1,
    width + 1,
    width,
    width - 1,
    -1,
    -width - 1,
  ];
  let changed = true,
    rounds = 0;
  while (changed && rounds++ < 64) {
    changed = false;
    for (let pass = 0; pass < 2; pass++) {
      const remove = [];
      for (let y = 1; y < height - 1; y++)
        for (let x = 1; x < width - 1; x++) {
          const i = y * width + x;
          if (!thin[i]) continue;
          const p = around.map((d) => thin[i + d]),
            count = p.reduce((a, b) => a + b, 0);
          if (count < 2 || count > 6) continue;
          let transitions = 0;
          for (let k = 0; k < 8; k++)
            if (!p[k] && p[(k + 1) % 8]) transitions++;
          if (transitions !== 1) continue;
          if (
            pass === 0
              ? p[0] * p[2] * p[4] || p[2] * p[4] * p[6]
              : p[0] * p[2] * p[6] || p[0] * p[4] * p[6]
          )
            continue;
          remove.push(i);
        }
      if (remove.length) changed = true;
      for (const i of remove) thin[i] = 0;
    }
  }
  const neighbours = (i: number) =>
    around
      .map((d) => i + d)
      .filter(
        (j) =>
          j >= 0 &&
          j < n &&
          Math.abs((j % width) - (i % width)) <= 1 &&
          thin[j],
      );
  const nodes = [];
  for (let i = 0; i < n; i++) if (thin[i]) nodes.push(i);
  // Connected stems first, then detached dots/accents. At a branch the nearest
  // direction is continued before the remaining pen strokes are traversed.
  const seen = new Uint8Array(n),
    components: number[][] = [];
  for (const i of nodes) {
    if (seen[i]) continue;
    const stack = [i],
      component = [];
    seen[i] = 1;
    while (stack.length) {
      const j = stack.pop()!;
      component.push(j);
      for (const k of neighbours(j))
        if (!seen[k]) {
          seen[k] = 1;
          stack.push(k);
        }
    }
    components.push(component);
  }
  components.sort((a, b) => b.length - a.length);
  const visited = new Uint8Array(n),
    sequence = [];
  for (const component of components) {
    const ends = component.filter((i) => neighbours(i).length === 1);
    const start = (ends.length ? ends : component)
      .slice()
      .sort(
        (a, b) =>
          Math.floor(a / width) - Math.floor(b / width) ||
          (a % width) - (b % width),
      )[0];
    const stack: [number, number][] = [[start, -width]];
    while (stack.length) {
      const [i, direction] = stack.pop()!;
      if (visited[i]) continue;
      visited[i] = 1;
      sequence.push(i);
      const next = neighbours(i).filter((j) => !visited[j]);
      next.sort((a, b) => {
        const score = (j: number) => {
          const dx = (j % width) - (i % width),
            dy = Math.floor(j / width) - Math.floor(i / width),
            py = Math.round(direction / width),
            px = direction - py * width;
          return dx * px + dy * py;
        };
        return score(a) - score(b);
      });
      for (const j of next) stack.push([j, j - i]);
    }
  }
  const owner = new Int32Array(n).fill(-1),
    distance = new Uint16Array(n).fill(65535),
    queue = new Int32Array(n);
  let head = 0,
    tail = 0;
  sequence.forEach((i, rank) => {
    owner[i] = rank;
    distance[i] = 0;
    queue[tail++] = i;
  });
  while (head < tail) {
    const i = queue[head++];
    for (const d of [-width, 1, width, -1]) {
      const j = i + d;
      if (
        j < 0 ||
        j >= n ||
        Math.abs((j % width) - (i % width)) > 1 ||
        distance[j] !== 65535
      )
        continue;
      distance[j] = distance[i] + 1;
      owner[j] = owner[i];
      queue[tail++] = j;
    }
  }
  // A second distance field gives each stroke a very small, paper-bound corona.
  const inkDistance = new Uint16Array(n).fill(65535);
  head = tail = 0;
  for (let i = 0; i < n; i++)
    if (mask[i]) {
      inkDistance[i] = 0;
      queue[tail++] = i;
    }
  while (head < tail) {
    const i = queue[head++];
    if (inkDistance[i] >= 18) continue;
    for (const d of [-width, 1, width, -1]) {
      const j = i + d;
      if (
        j < 0 ||
        j >= n ||
        Math.abs((j % width) - (i % width)) > 1 ||
        inkDistance[j] !== 65535
      )
        continue;
      inkDistance[j] = inkDistance[i] + 1;
      queue[tail++] = j;
    }
  }
  const result = new Uint8ClampedArray(n * 4);
  for (let i = 0; i < n; i++)
    if (owner[i] >= 0 && inkDistance[i] < 18) {
      result[i * 4] = Math.round(
        255 * (0.025 + (0.95 * owner[i]) / Math.max(1, sequence.length - 1)),
      );
      result[i * 4 + 1] = Math.round(255 * Math.exp(-inkDistance[i] * 0.22));
      result[i * 4 + 2] = rgba[i * 4 + 3];
      result[i * 4 + 3] = 255;
    }
  return {
    pixels: result,
    points: sequence.map((i) => [i % width, Math.floor(i / width)]),
    components: components.length,
  };
}
