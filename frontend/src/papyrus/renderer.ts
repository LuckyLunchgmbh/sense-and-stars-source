import * as THREE from "three";
import { traceGlyph } from "./glyphTrace";

export type PapyrusPhase =
  "loading" | "sealed" | "opening" | "writing" | "reading";
export type LetterBlock = {
  text: string;
  kind: "title" | "salutation" | "sender" | "body";
};
export interface PapyrusElements {
  dialog: HTMLDialogElement;
  canvas: HTMLCanvasElement;
  scroller: HTMLDivElement;
  scrollSpace: HTMLDivElement;
  seal: HTMLButtonElement;
}
interface Options {
  elements: PapyrusElements;
  source: LetterBlock[];
  paperUrl: string;
  reduced: boolean;
  onPhase: (phase: PapyrusPhase) => void;
  onStatus: (message: string) => void;
  onEnd: (atEnd: boolean) => void;
  onReady: () => void;
  onFailure: () => void;
}
export interface PapyrusRenderer {
  open: () => void;
  reset: () => void;
  showAll: () => void;
  setReduced: (value: boolean) => void;
  dispose: () => void;
}
interface Glyph {
  char: string;
  x: number;
  y: number;
  width: number;
  size: number;
  font: string;
  index: number;
}
interface Stroke {
  canvas: HTMLCanvasElement;
  left: number;
  top: number;
  size: number;
  points: number;
}
type Shader = Parameters<THREE.MeshStandardMaterial["onBeforeCompile"]>[0];

// Each mount owns its renderer and temporary private text atlases. The component
// disposes it on account/version change or dismissal. Nothing is persisted.
export function createPapyrusRenderer(options: Options): PapyrusRenderer {
  const { elements, source } = options;
  const dialog = elements.dialog,
    input = elements.scroller,
    sealButton = elements.seal;
  const segmenter =
    typeof Intl.Segmenter === "function"
      ? new Intl.Segmenter("de", { granularity: "grapheme" })
      : null;
  const W = 1000,
    glyphs: Glyph[] = [],
    traceCache = new Map<string, Stroke>(),
    textures = new Set<THREE.Texture>();
  const temporaryPoint = new THREE.Vector3();
  const handFont =
    getComputedStyle(dialog).getPropertyValue("--papyrus-hand").trim() ||
    '"Apple Chancery", "Snell Roundhand", "Segoe Print", cursive';
  let renderer: THREE.WebGLRenderer,
    scene: THREE.Scene,
    camera: THREE.OrthographicCamera,
    paperGroup: THREE.Group,
    paperMesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
  let atlas: THREE.CanvasTexture,
    inkMap: THREE.CanvasTexture,
    idMap: THREE.CanvasTexture,
    strokeMap: THREE.CanvasTexture,
    paperMat: THREE.MeshStandardMaterial;
  let topRoll: THREE.Group,
    bottomRoll: THREE.Group,
    band: THREE.Group,
    wax: THREE.Group,
    groundShadow: THREE.Mesh;
  let image: HTMLImageElement,
    phase: PapyrusPhase = "loading",
    opened = 0,
    openStart = 0,
    scroll = 0,
    targetScroll = 0,
    progress = 0,
    allShown = false,
    last = 0,
    lastAdvance = 0;
  let scale = 0.72,
    flatH = 1000,
    totalH = 2200,
    cssW = 720,
    cssH = 720,
    raf = 0,
    textureScale = 1.5,
    shader: Shader | null = null;
  let baseCanvas: HTMLCanvasElement,
    inkCanvas: HTMLCanvasElement,
    idCanvas: HTMLCanvasElement,
    strokeCanvas: HTMLCanvasElement;
  let sheetGeometry: THREE.BufferGeometry,
    rollerTexture: THREE.CanvasTexture,
    grainTexture: THREE.CanvasTexture,
    endTexture: THREE.CanvasTexture;
  let topRadius = 24,
    bottomRadius = 75,
    frameCount = 0,
    layoutVersion = 0,
    disposed = false,
    reduced = options.reduced,
    atEnd = false,
    resizeTimer = 0;
  const timers = new Set<number>();
  const pending = new Set<(reason: Error) => void>();
  let geometryOpened = -1,
    geometryScroll = -1,
    geometryLayout = -1,
    geometryFrames = 0;
  const quiet = () => reduced;
  const clamp = (v: number, a: number, b: number) =>
    Math.max(a, Math.min(b, v));
  const smooth = (value: number) => {
    const t = clamp(value, 0, 1);
    return t * t * (3 - 2 * t);
  };
  function phaseTo(value: PapyrusPhase) {
    phase = value;
    dialog.dataset.phase = value;
    options.onPhase(value);
  }
  function status(message: string) {
    options.onStatus(message);
  }
  function canvas(width: number, height: number) {
    const c = document.createElement("canvas");
    c.width = width;
    c.height = height;
    return c;
  }
  function context(c: HTMLCanvasElement) {
    const ctx = c.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("Canvas unavailable");
    return ctx;
  }
  function texture(c: HTMLCanvasElement, color = true) {
    const t = new THREE.CanvasTexture(c);
    if (color) t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    textures.add(t);
    return t;
  }
  function release(t: THREE.Texture | undefined) {
    if (t) {
      t.dispose();
      textures.delete(t);
    }
  }
  async function deadline<T>(promise: PromiseLike<T>, ms: number): Promise<T> {
    let timer = 0;
    let cancel: (reason: Error) => void = () => {};
    try {
      return await Promise.race([
        promise,
        new Promise<never>((_, reject) => {
          cancel = reject;
          pending.add(cancel);
          timer = window.setTimeout(
            () => reject(new Error("Render timeout")),
            ms,
          );
          timers.add(timer);
        }),
      ]);
    } finally {
      clearTimeout(timer);
      timers.delete(timer);
      pending.delete(cancel);
    }
  }
  function glyphStroke(char: string) {
    const cached = traceCache.get(char);
    if (cached) return cached;
    const size = 96,
      pad = 22,
      font = `${size}px ${handFont}`;
    const measure = context(canvas(1, 1));
    measure.font = font;
    const m = measure.measureText(char);
    const left = Math.ceil(m.actualBoundingBoxLeft),
      ascent = Math.ceil(m.actualBoundingBoxAscent);
    const width = Math.max(
      1,
      Math.ceil(m.actualBoundingBoxLeft + m.actualBoundingBoxRight) + pad * 2,
    );
    const height = Math.max(
      1,
      Math.ceil(m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) +
        pad * 2,
    );
    const c = canvas(width, height),
      ctx = context(c);
    ctx.font = font;
    ctx.fillText(char, pad + left, pad + ascent);
    const traced = traceGlyph(
      ctx.getImageData(0, 0, width, height).data,
      width,
      height,
    );
    ctx.putImageData(new ImageData(traced.pixels, width, height), 0, 0);
    const result = {
      canvas: c,
      left: pad + left,
      top: pad + ascent,
      size,
      points: traced.points.length,
    };
    traceCache.set(char, result);
    return result;
  }

  function layoutLetter() {
    glyphs.length = 0;
    const measure = context(canvas(16, 16)),
      fontSize = 23 / scale,
      margin = 82 / Math.max(0.8, scale / 0.72);
    const contentW = W - margin * 2;
    let y = 90 / scale,
      ornamentY = 0;
    for (const block of source) {
      const size =
        block.kind === "title"
          ? 36 / scale
          : block.kind === "sender"
            ? 44 / scale
            : block.kind === "salutation"
              ? 27 / scale
              : fontSize;
      const lineHeight = size * (block.kind === "title" ? 1.38 : 1.85),
        font = `${size}px ${handFont}`;
      measure.font = font;
      if (block.kind === "title") y = 92 / scale;
      if (block.kind === "salutation") y += 27 / scale;
      if (block.kind === "sender") y += 8 / scale;
      let words = block.text.match(/\S+\s*|\s+/gu) || [],
        lines = [],
        line = "";
      for (const word of words) {
        if (
          measure.measureText(line + word.trimEnd()).width > contentW &&
          line
        ) {
          lines.push(line.trimEnd());
          line = word.trimStart();
        } else line += word;
      }
      if (line) lines.push(line.trimEnd());
      for (const text of lines) {
        const lineW = measure.measureText(text).width;
        let x = block.kind === "title" ? (W - lineW) / 2 : margin;
        let prefix = "";
        for (const { segment } of segmenter
          ? segmenter.segment(text)
          : Array.from(text, (segment) => ({ segment }))) {
          const gx = x + measure.measureText(prefix).width;
          prefix += segment;
          const width = measure.measureText(prefix).width - (gx - x);
          glyphs.push({
            char: segment,
            x: gx,
            y,
            width,
            size,
            font,
            index: glyphs.length + 1,
          });
        }
        y += lineHeight;
      }
      if (block.kind === "title") ornamentY = y - 13 / scale;
      y +=
        block.kind === "title"
          ? 44 / scale
          : block.kind === "salutation"
            ? 10 / scale
            : 21 / scale;
    }
    totalH = Math.max(flatH + 50, y + 95 / scale);
    textureScale = Math.min(
      1.5,
      (innerWidth < 600 ? 4096 : 6144) / totalH,
      renderer.capabilities.maxTextureSize / totalH,
    );
    if (textureScale / scale < 0.65) throw new Error("Texture capacity");
    for (const c of [baseCanvas, inkCanvas, idCanvas, strokeCanvas])
      if (c) {
        c.width = 1;
        c.height = 1;
      }
    baseCanvas = canvas(
      Math.max(1, Math.round(W * textureScale)),
      Math.max(1, Math.round(totalH * textureScale)),
    );
    inkCanvas = canvas(baseCanvas.width, baseCanvas.height);
    idCanvas = canvas(baseCanvas.width, baseCanvas.height);
    strokeCanvas = canvas(baseCanvas.width, baseCanvas.height);
    const bc = context(baseCanvas),
      ic = context(inkCanvas),
      ids = context(idCanvas),
      strokes = context(strokeCanvas);
    bc.scale(textureScale, textureScale);
    ic.scale(textureScale, textureScale);
    ids.scale(textureScale, textureScale);
    strokes.scale(textureScale, textureScale);
    // A single continuous sheet. Ink and grain use precisely the same UV coordinates.
    // Keep fibers and stains at their original proportions on a long sheet.
    const tileH = W * ((image.height * 0.66) / image.width),
      overlap = tileH * 0.18;
    for (let y = -overlap, part = 0; y < totalH; y += tileH - overlap, part++) {
      const tile = canvas(Math.ceil(W), Math.ceil(tileH)),
        tc = context(tile);
      if (part % 2) {
        tc.translate(0, tileH);
        tc.scale(1, -1);
      }
      tc.drawImage(
        image,
        0,
        image.height * 0.17,
        image.width,
        image.height * 0.66,
        0,
        0,
        W,
        tileH,
      );
      tc.setTransform(1, 0, 0, 1, 0, 0);
      tc.globalCompositeOperation = "destination-in";
      const fade = tc.createLinearGradient(0, 0, 0, tileH);
      fade.addColorStop(0, "#0000");
      fade.addColorStop(0.18, "#000");
      fade.addColorStop(1, "#000");
      tc.fillStyle = fade;
      tc.fillRect(0, 0, W, tileH);
      bc.drawImage(tile, 0, y, W, tileH);
    }
    bc.save();
    bc.globalCompositeOperation = "source-atop";
    for (let i = 0; i < totalH; i += 2.4) {
      bc.strokeStyle = `rgba(89,65,31,${0.018 + 0.018 * (0.5 + 0.5 * Math.sin(i * 1.37))})`;
      bc.lineWidth = 0.5;
      bc.beginPath();
      bc.moveTo(0, i);
      bc.lineTo(W, i + Math.sin(i) * 0.8);
      bc.stroke();
    }
    bc.restore();
    for (const g of glyphs) {
      ic.font = g.font;
      ic.fillStyle = "#3b2619";
      ic.fillText(g.char, g.x, g.y);
      if (!g.char.trim()) continue;
      const stroke = glyphStroke(g.char),
        ratio = g.size / stroke.size,
        x = g.x - stroke.left * ratio,
        y = g.y - stroke.top * ratio;
      strokes.drawImage(
        stroke.canvas,
        x,
        y,
        stroke.canvas.width * ratio,
        stroke.canvas.height * ratio,
      );
      const coded = canvas(stroke.canvas.width, stroke.canvas.height),
        cc = context(coded);
      cc.drawImage(stroke.canvas, 0, 0);
      cc.globalCompositeOperation = "source-in";
      cc.fillStyle = `rgb(${g.index % 256},${Math.floor(g.index / 256)},0)`;
      cc.fillRect(0, 0, coded.width, coded.height);
      ids.drawImage(coded, x, y, coded.width * ratio, coded.height * ratio);
    }
    // Ornament is ink on the same one-sided paper, not a screen-space overlay.
    ic.save();
    ic.strokeStyle = "#684722";
    ic.lineWidth = 0.9 / scale;
    ic.beginPath();
    ic.moveTo(W * 0.28, ornamentY);
    ic.lineTo(W / 2 - 31 / scale, ornamentY);
    ic.moveTo(W / 2 + 31 / scale, ornamentY);
    ic.lineTo(W * 0.72, ornamentY);
    ic.stroke();
    ic.font = `${35 / scale}px Georgia,serif`;
    ic.textAlign = "center";
    ic.textBaseline = "middle";
    ic.fillStyle = "#684722";
    ic.fillText("∞", W / 2, ornamentY);
    ic.restore();
    // ID zero is reserved for this permanent, non-burning ornament.
    release(atlas);
    release(inkMap);
    release(idMap);
    release(strokeMap);
    atlas = texture(baseCanvas);
    inkMap = texture(inkCanvas);
    idMap = texture(idCanvas, false);
    strokeMap = texture(strokeCanvas, false);
    idMap.minFilter = THREE.NearestFilter;
    idMap.magFilter = THREE.NearestFilter;
    idMap.generateMipmaps = false;
    if (paperMat) {
      paperMat.map = atlas;
      paperMat.needsUpdate = true;
    }
    elements.scrollSpace.style.height = `${totalH * scale}px`;
    dialog.dataset.glyphCount = String(glyphs.length);
    dialog.dataset.materialHeight = String(totalH);
    dialog.dataset.tracedGlyphs = String(traceCache.size);
    dialog.dataset.ornament = "two-lines-infinity";
    layoutVersion++;
  }

  function makePaperMaterial() {
    const mat = new THREE.MeshStandardMaterial({
      map: atlas,
      roughness: 0.96,
      metalness: 0,
      side: THREE.DoubleSide,
      alphaTest: 0.14,
      bumpMap: grainTexture,
      bumpScale: 0.35,
    });
    mat.onBeforeCompile = (s) => {
      s.uniforms.inkMap = { value: inkMap };
      s.uniforms.idMap = { value: idMap };
      s.uniforms.strokeMap = { value: strokeMap };
      s.uniforms.progress = { value: progress };
      s.uniforms.burnTime = { value: 0 };
      s.uniforms.burnStrength = { value: 0 };
      s.uniforms.paperPixels = {
        value: new THREE.Vector2(W * scale, totalH * scale),
      };
      s.uniforms.heartId = {
        value:
          glyphs.find((g) => /\p{Extended_Pictographic}/u.test(g.char))
            ?.index || -100,
      };
      s.fragmentShader =
        "uniform sampler2D inkMap;uniform sampler2D idMap;uniform sampler2D strokeMap;uniform float progress;uniform float burnTime;uniform float burnStrength;uniform vec2 paperPixels;uniform float heartId;\n" +
        s.fragmentShader;
      s.fragmentShader = s.fragmentShader.replace(
        "#include <map_fragment>",
        `#include <map_fragment>
      vec4 ink=texture2D(inkMap,vMapUv);vec4 encoded=texture2D(idMap,vMapUv);
      float letterId=floor(encoded.r*255.0+.5)+floor(encoded.g*255.0+.5)*256.0;
      // The reverse of the sheet is blank: writing is inside the rolled paper.
      float face=gl_FrontFacing?1.0:0.0;
      vec4 stroke=texture2D(strokeMap,vMapUv);
      float localProgress=progress-(letterId-1.0);
      float age=localProgress-stroke.r;
      float hasLetter=step(.5,letterId);
      float isInk=ink.a*face;
      float written=mix(1.0,smoothstep(-.016,.025,age),hasLetter);
      float flicker=.82+.18*sin(burnTime*29.0+stroke.r*84.0+letterId*1.7);
      float heat=exp(-abs(age)*6.8)*step(.0,localProgress)*step(localProgress,1.7)*hasLetter*face*flicker*burnStrength;
      float ember=exp(-max(age,0.0)*2.7)*step(.0,age)*hasLetter*face*burnStrength;
      // Short tongues originate on the active pen stroke. All samples are sheet
      // UVs, so scrolling cannot leave a screen-space trail or loose particle.
      float tongues=0.0;
      for(int k=1;k<=4;k++){
        float height=float(k)*3.0;
        float sway=sin(burnTime*16.0+vMapUv.x*1250.0+float(k)*1.3)*height*.16;
        vec2 seedUv=vMapUv+vec2(sway/paperPixels.x,-height/paperPixels.y);
        vec4 seed=texture2D(strokeMap,seedUv),code=texture2D(idMap,seedUv);
        float seedId=floor(code.r*255.0+.5)+floor(code.g*255.0+.5)*256.0;
        float seedAge=progress-(seedId-1.0)-seed.r;
        float tipNoise=.65+.35*sin(burnTime*23.0+seed.r*73.0+float(k)*2.4);
        tongues+=exp(-abs(seedAge)*6.5)*seed.b*seed.a*step(.5,seedId)*(1.0-float(k)/5.0)*tipNoise;
      }
      tongues*=face*burnStrength;
      vec3 baseInk=mix(vec3(.043,.024,.012),ink.rgb,1.0-step(.5,abs(letterId-heartId)));
      vec3 burnt=mix(baseInk,vec3(1.0,.19,.008),max(heat,ember*.22));
      float fiber=.9+.1*diffuseColor.r;
      diffuseColor.rgb=mix(diffuseColor.rgb,burnt,isInk*written*fiber);
      if(vMapUv.y<0.0||vMapUv.y>1.0)discard;
    `,
      );
      s.fragmentShader = s.fragmentShader.replace(
        "#include <emissivemap_fragment>",
        `#include <emissivemap_fragment>
      float corona=stroke.g*stroke.a*heat;
      totalEmissiveRadiance+=vec3(1.0,.08,.001)*corona*3.2;
      totalEmissiveRadiance+=vec3(1.0,.52,.12)*pow(heat,2.0)*isInk*7.0;
      totalEmissiveRadiance+=vec3(.72,.035,.001)*ember*isInk*.22;
      totalEmissiveRadiance+=vec3(1.0,.14,.002)*tongues*4.8;
    `,
      );
      shader = s;
    };
    return mat;
  }

  function makeSheet() {
    const nx = 56,
      ny = 380,
      positions = new Float32Array((nx + 1) * (ny + 1) * 3),
      uv = new Float32Array((nx + 1) * (ny + 1) * 2),
      indices = [];
    for (let y = 0; y < ny; y++)
      for (let x = 0; x < nx; x++) {
        let a = y * (nx + 1) + x,
          b = a + nx + 1;
        indices.push(a, b, a + 1, b, b + 1, a + 1);
      }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    geo.setIndex(indices);
    geo.userData = { nx, ny };
    return geo;
  }
  function deform(q: number, x: number, h: number, rT: number, rB: number) {
    let y, z;
    if (q < 0) {
      const a = -q / rT;
      y = h / 2 + (rT + 1.3) * 0.94 * Math.sin(a);
      z = rT - (rT + 1.3) * Math.cos(a);
    } else if (q > h) {
      const a = (q - h) / rB;
      y = -h / 2 - (rB + 1.3) * 0.96 * Math.sin(a);
      z = rB - (rB + 1.3) * Math.cos(a);
    } else {
      y = h / 2 - q;
      z = 1.5 * Math.sin(x * 0.018 + q * 0.008) + 1.2 * Math.sin(q * 0.027);
    }
    const edge = Math.pow(Math.abs(x) / (W / 2), 10);
    z += edge * (1.6 * Math.sin(q * 0.033) + 0.7 * Math.sin(q * 0.12));
    return temporaryPoint.set(x, y, z);
  }
  function updateSheet(h: number) {
    const { nx, ny } = sheetGeometry.userData,
      p = sheetGeometry.attributes.position,
      u = sheetGeometry.attributes.uv;
    const from = -topRadius * Math.PI * 1.1,
      to = h + bottomRadius * Math.PI * 1.1;
    for (let row = 0; row <= ny; row++) {
      const q = from + ((to - from) * row) / ny;
      for (let col = 0; col <= nx; col++) {
        const ix = row * (nx + 1) + col,
          x = (col / nx - 0.5) * W;
        const point = deform(q, x, h, topRadius, bottomRadius);
        p.setXYZ(ix, point.x, point.y, point.z);
        u.setXY(ix, col / nx, 1 - (scroll + q) / totalH);
      }
    }
    p.needsUpdate = true;
    u.needsUpdate = true;
    sheetGeometry.computeVertexNormals();
    sheetGeometry.computeBoundingSphere();
  }
  function makeRoll() {
    const group = new THREE.Group();
    const geometry = new THREE.CylinderGeometry(1, 1, W, 112, 12, false),
      points = geometry.attributes.position;
    for (let i = 0; i < points.count; i++) {
      const x = points.getX(i),
        z = points.getZ(i),
        a = Math.atan2(z, x),
        f =
          1 +
          0.011 * Math.sin(a * 7) +
          0.006 * Math.sin(a * 15 + points.getY(i) * 0.01);
      points.setXYZ(i, x * f, points.getY(i), z * f);
    }
    geometry.computeVertexNormals();
    const side = new THREE.MeshStandardMaterial({
      map: rollerTexture,
      bumpMap: grainTexture,
      bumpScale: 1.7,
      color: 0xffffff,
      roughness: 0.98,
    });
    const end = new THREE.MeshStandardMaterial({
      map: endTexture,
      roughness: 1,
      color: 0xffffff,
    });
    const body = new THREE.Mesh(geometry, [side, end, end]);
    body.rotation.order = "ZYX";
    body.rotation.z = Math.PI / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);
    group.userData.body = body;
    for (const direction of [-1, 1]) {
      const count = 2000,
        coords = new Float32Array(count * 3),
        g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(coords, 3));
      const line = new THREE.Line(
        g,
        new THREE.LineBasicMaterial({
          color: 0x8a6439,
          transparent: true,
          opacity: 0.75,
        }),
      );
      line.userData = { direction, count };
      line.position.x = direction * (W / 2 + 0.22);
      group.add(line);
    }
    return group;
  }
  function updateRoll(group: THREE.Group, r: number, y: number) {
    group.position.set(0, y, r);
    group.userData.body.scale.set(r * 0.985, 1, r * 0.985);
    group.userData.body.rotation.y =
      ((group === topRoll ? 1 : -1) * scroll) / Math.max(r, 1);
    for (const child of group.children) {
      if (!(child instanceof THREE.Line)) continue;
      const { count } = child.userData,
        p = child.geometry.attributes.position;
      const turns = (r - 7) / 1.35;
      for (let i = 0; i < count; i++) {
        const t = i / (count - 1),
          angle = t * turns * Math.PI * 2,
          rad = 7 + (r - 7) * t;
        const ripple =
          1 + 0.012 * Math.sin(angle * 3.1) + 0.006 * Math.sin(angle * 7.9);
        p.setXYZ(
          i,
          0,
          Math.sin(angle) * rad * 0.94 * ripple,
          Math.cos(angle) * rad * ripple,
        );
      }
      p.needsUpdate = true;
    }
  }
  function makeBand() {
    const group = new THREE.Group();
    for (let part = 0; part < 2; part++) {
      const nx = 14,
        ny = 96,
        positions = [],
        uv = [],
        indices = [];
      for (let row = 0; row <= ny; row++) {
        const theta = (part + row / ny) * Math.PI;
        for (let col = 0; col <= nx; col++) {
          const x = (col / nx - 0.5) * 118,
            wrinkle = Math.sin(col * 0.9 + theta * 4) * 1.4;
          positions.push(
            x,
            Math.sin(theta) * (89 + wrinkle),
            73 + Math.cos(theta) * (91 + wrinkle),
          );
          uv.push(col / nx, theta / Math.PI);
        }
      }
      for (let y = 0; y < ny; y++)
        for (let x = 0; x < nx; x++) {
          const a = y * (nx + 1) + x,
            b = a + nx + 1;
          indices.push(a, b, a + 1, b, b + 1, a + 1);
        }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(positions, 3),
      );
      geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
      geo.setIndex(indices);
      geo.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({
        color: 0x613a42,
        roughness: 0.87,
        side: THREE.DoubleSide,
        bumpMap: grainTexture,
        bumpScale: 1.3,
        transparent: true,
      });
      material.onBeforeCompile = (s) => {
        s.fragmentShader = s.fragmentShader.replace(
          "#include <color_fragment>",
          `#include <color_fragment>
      float weave=.94+.06*sin(vBumpMapUv.x*820.0)*sin(vBumpMapUv.y*1200.0);diffuseColor.rgb*=weave;
      float selvedge=smoothstep(.028,.055,vBumpMapUv.x)*(1.0-smoothstep(.945,.972,vBumpMapUv.x));diffuseColor.rgb*=mix(vec3(1.35,1.2,.92),vec3(1.0),selvedge);
    `,
        );
      };
      const mesh = new THREE.Mesh(geo, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
    }
    return group;
  }
  function makeWax() {
    const group = new THREE.Group(),
      shape = new THREE.Shape();
    for (let i = 0; i <= 80; i++) {
      const angle = (i / 80) * Math.PI * 2,
        r = 47 + 1.5 * Math.sin(angle * 7) + 1.2 * Math.sin(angle * 13);
      const x = Math.cos(angle) * r,
        y = Math.sin(angle) * r * 0.96;
      i ? shape.lineTo(x, y) : shape.moveTo(x, y);
    }
    const waxMat = new THREE.MeshPhysicalMaterial({
      color: 0x6f342c,
      roughness: 0.5,
      metalness: 0,
      clearcoat: 0.22,
      clearcoatRoughness: 0.6,
      transparent: true,
    });
    const mesh = new THREE.Mesh(
      new THREE.ExtrudeGeometry(shape, {
        depth: 8,
        bevelEnabled: true,
        bevelThickness: 2.3,
        bevelSize: 2.4,
        bevelSegments: 4,
        steps: 1,
      }),
      waxMat,
    );
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    group.add(mesh);
    const metal = new THREE.MeshStandardMaterial({
      color: 0xb88c50,
      metalness: 0.32,
      roughness: 0.57,
      transparent: true,
    });
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(35, 0.65, 8, 90),
      metal,
    );
    ring.position.z = 10.4;
    group.add(ring);
    class InfinityCurve extends THREE.Curve<THREE.Vector3> {
      constructor() {
        super();
      }
      getPoint(t: number, target = new THREE.Vector3()) {
        const a = t * Math.PI * 2,
          den = 1 + Math.sin(a) ** 2;
        return target.set(
          (27 * Math.cos(a)) / den,
          (14 * Math.sin(a * 2)) / den,
          10.2,
        );
      }
    }
    group.add(
      new THREE.Mesh(
        new THREE.TubeGeometry(new InfinityCurve(), 128, 0.9, 8, true),
        metal,
      ),
    );
    group.position.set(0, 0, 169);
    return group;
  }
  function prepareMaterials() {
    const c = canvas(512, 512),
      ctx = context(c);
    ctx.fillStyle = "#d4bd88";
    ctx.fillRect(0, 0, 512, 512);
    ctx.drawImage(
      image,
      image.width * 0.12,
      image.height * 0.15,
      image.width * 0.76,
      image.height * 0.7,
      0,
      0,
      512,
      512,
    );
    rollerTexture = texture(c);
    const bump = canvas(512, 512),
      b = context(bump);
    b.fillStyle = "#888";
    b.fillRect(0, 0, 512, 512);
    for (let y = 0; y < 512; y++) {
      let value = 128 + Math.sin(y * 3.8) * 20 + Math.sin(y * 0.26) * 12;
      b.fillStyle = `rgb(${value},${value},${value})`;
      b.fillRect(0, y, 512, 1);
    }
    for (let x = 0; x < 512; x += 3) {
      b.fillStyle = `rgba(205,205,205,${0.09 + 0.07 * Math.sin(x * 3)})`;
      b.fillRect(x, 0, 0.6, 512);
    }
    grainTexture = texture(bump, false);
    grainTexture.wrapS = grainTexture.wrapT = THREE.RepeatWrapping;
    grainTexture.repeat.set(4, 7);
    const cut = canvas(512, 512),
      e = context(cut);
    e.fillStyle = "#c6aa74";
    e.fillRect(0, 0, 512, 512);
    e.beginPath();
    for (let i = 0; i < 16000; i++) {
      const t = i / 15999,
        a = t * Math.PI * 2 * 35,
        r = 12 + t * 246,
        jitter = 1 + 0.009 * Math.sin(a * 4.3) + 0.004 * Math.sin(a * 12);
      const x = 255 + Math.cos(a) * r * jitter,
        y = 256 + Math.sin(a) * r * (0.98 + 0.015 * Math.sin(a * 2));
      i ? e.lineTo(x, y) : e.moveTo(x, y);
    }
    e.strokeStyle = "#73562b9c";
    e.lineWidth = 1.6;
    e.stroke();
    e.globalCompositeOperation = "screen";
    e.strokeStyle = "#ebddb344";
    e.lineWidth = 0.6;
    e.translate(0.8, -0.8);
    e.stroke();
    endTexture = texture(cut);
  }

  function measure() {
    cssW = Math.min(760, innerWidth - 54);
    scale = cssW / W;
    cssH = Math.min(810, innerHeight - 250);
    cssH = Math.max(220, cssH);
    flatH = cssH / scale;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    renderer.setSize(innerWidth, innerHeight);
    camera.left = -innerWidth / scale / 2;
    camera.right = -camera.left;
    camera.top = innerHeight / scale / 2;
    camera.bottom = -camera.top;
    camera.updateProjectionMatrix();
    input.style.width = `${cssW}px`;
    input.style.height = `${cssH}px`;
    input.style.top = "calc(50% - 8px)";
  }
  function project(point: THREE.Vector3) {
    return paperGroup.localToWorld(point.clone()).project(camera);
  }
  function positionSeal() {
    const p = project(
      new THREE.Vector3(wax.position.x, wax.position.y, wax.position.z + 12),
    );
    sealButton.style.left = `${(p.x * 0.5 + 0.5) * innerWidth}px`;
    sealButton.style.top = `${(-p.y * 0.5 + 0.5) * innerHeight}px`;
    sealButton.style.width =
      sealButton.style.height = `${98 * scale * (0.88 + 0.12 * opened)}px`;
  }
  function setOpened() {
    if (["writing", "reading"].includes(phase)) return;
    phaseTo(allShown ? "reading" : "writing");
    input.setAttribute("aria-hidden", "false");
    input.tabIndex = 0;
    input.focus({ preventScroll: true });
    status("Deine Rolle ist geöffnet. Zum Weiterlesen weiter entrollen.");
  }
  function showAll() {
    if (!["opening", "writing", "reading"].includes(phase)) return;
    allShown = true;
    progress = glyphs.length + 25;
    if (opened < 1) {
      opened = 1;
      setOpened();
    }
    phaseTo("reading");
    wake();
  }
  function open() {
    if (phase !== "sealed") return;
    phaseTo("opening");
    sealButton.disabled = true;
    openStart = performance.now();
    status("Das Siegel löst sich und die Papyrusrolle entfaltet sich.");
    if (quiet()) {
      opened = 1;
      setOpened();
      showAll();
    }
    wake();
  }
  function reset() {
    phaseTo("sealed");
    opened = 0;
    scroll = targetScroll = 0;
    input.scrollTop = 0;
    progress = 0;
    allShown = false;
    input.setAttribute("aria-hidden", "true");
    input.tabIndex = -1;
    sealButton.disabled = false;
    status("Eine versiegelte Papyrusrolle für dich.");
    wake();
  }

  function write(now: number, dt: number, h: number) {
    if (!["writing", "reading"].includes(phase)) return;
    const before = progress;
    if (!allShown) {
      // A continuous pen advances along the centreline of each glyph. Spaces take
      // less time, punctuation pauses. Only the unrolled reading face is written.
      let budget = dt;
      for (let i = 0; i < 40 && progress < glyphs.length && budget > 0; i++) {
        const g = glyphs[Math.floor(progress)];
        if (g.y > scroll + h - 12) break;
        if (g.y < scroll - 25) {
          progress = Math.floor(progress) + 1;
          continue;
        }
        const duration = !g.char.trim()
          ? 18
          : /[.,…!?]/u.test(g.char)
            ? 120
            : /[A-ZÄÖÜ]/u.test(g.char)
              ? 195
              : 112;
        const remaining = (1 - (progress - Math.floor(progress))) * duration,
          step = Math.min(budget, remaining);
        progress = Math.min(
          Math.floor(progress) + 1,
          progress + step / duration,
        );
        budget -= step;
        if (remaining - step < 0.001) progress = Math.round(progress);
      }
      if (progress >= glyphs.length) {
        allShown = true;
        phaseTo("reading");
      }
    }
    if (progress !== before) lastAdvance = now;
    if (shader) {
      shader.uniforms.progress.value = allShown ? glyphs.length + 25 : progress;
      shader.uniforms.burnTime.value = now / 1000;
      shader.uniforms.burnStrength.value =
        allShown || quiet()
          ? 0
          : Math.exp(-Math.max(0, now - lastAdvance - 120) / 170);
      shader.uniforms.paperPixels.value.set(W * scale, totalH * scale);
      shader.uniforms.inkMap.value = inkMap;
      shader.uniforms.idMap.value = idMap;
      shader.uniforms.strokeMap.value = strokeMap;
    }
    dialog.dataset.written = String(Math.floor(progress));
    dialog.dataset.burnProgress = progress.toFixed(4);
    dialog.dataset.fireAttachment = "glyph-centreline-shared-uv";
    dialog.dataset.printedFace = "front-only";
  }
  function render(now: number) {
    raf = 0;
    if (disposed) return;
    const dt = Math.min(50, last ? now - last : 16);
    last = now;
    if (phase === "opening") {
      opened = smooth((now - openStart - 250) / 2550);
      if (opened >= 1) setOpened();
    }
    const amount = quiet()
      ? targetScroll
      : scroll + (targetScroll - scroll) * 0.17;
    scroll = Math.abs(amount - targetScroll) < 0.02 ? targetScroll : amount;
    const p = clamp(scroll / (totalH - flatH), 0, 1),
      h = 18 + (flatH - 18) * opened;
    topRadius = opened * (22 + 37 * Math.sqrt(p)) + (1 - opened) * 44;
    bottomRadius = opened * (34 + 40 * Math.sqrt(1 - p)) + (1 - opened) * 77;
    paperGroup.scale.setScalar(0.87 + 0.13 * opened);
    paperGroup.rotation.set(
      (1 - opened) * 0.17,
      (1 - opened) * -0.17 + opened * 0.025,
      (1 - opened) * -0.045,
    );
    paperGroup.position.y = (opened * (8 + p * 17)) / scale;
    // A burning letter changes its material, not its shape. Reuse stationary
    // geometry and shadows instead of recomputing every vertex during writing.
    if (
      opened !== geometryOpened ||
      scroll !== geometryScroll ||
      layoutVersion !== geometryLayout
    ) {
      updateSheet(h);
      updateRoll(topRoll, topRadius, h / 2);
      updateRoll(bottomRoll, bottomRadius, -h / 2);
      geometryOpened = opened;
      geometryScroll = scroll;
      geometryLayout = layoutVersion;
      geometryFrames++;
      renderer.shadowMap.needsUpdate = true;
    }
    topRoll.visible = opened > 0.04;
    topRoll.scale.set(1, 0.94, 1);
    bottomRoll.scale.set(1, 0.96, 1);
    const peel = smooth(opened / 0.42);
    band.visible = peel < 1;
    wax.visible = opened < 0.34;
    band.children.forEach((child, i) => {
      const sign = i ? -1 : 1;
      child.position.set(sign * peel * 150, sign * peel * 145, -peel * 75);
      child.rotation.z = sign * peel * 0.45;
      (
        child as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>
      ).material.opacity = 1 - peel;
    });
    wax.scale.setScalar(1 + opened * 0.55);
    wax.rotation.z = -opened * 0.3;
    wax.children.forEach((child) => {
      if (child instanceof THREE.Mesh)
        (child.material as THREE.MeshStandardMaterial).opacity =
          1 - smooth(opened / 0.32);
    });
    write(now, dt, h);
    paperGroup.updateMatrixWorld(true);
    positionSeal();
    const end = p > 0.975 && (allShown || quiet());
    if (end !== atEnd) {
      atEnd = end;
      options.onEnd(end);
    }
    dialog.dataset.scrollFraction = p.toFixed(4);
    dialog.dataset.materialOffset = scroll.toFixed(2);
    dialog.dataset.textOffset = scroll.toFixed(2);
    dialog.dataset.layoutVersion = String(layoutVersion);
    dialog.dataset.geometryFrames = String(geometryFrames);
    renderer.render(scene, camera);
    frameCount++;
    dialog.dataset.frames = String(frameCount);
    const next = glyphs[Math.floor(progress)];
    const writingCanContinue =
      opened >= 1 && !allShown && next && next.y <= scroll + h - 12;
    if (
      phase === "opening" ||
      Math.abs(scroll - targetScroll) > 0.02 ||
      writingCanContinue ||
      (!allShown && now - lastAdvance < 1600)
    )
      wake();
  }
  function wake() {
    if (!disposed && !document.hidden && renderer && paperGroup && !raf)
      raf = requestAnimationFrame((now) => {
        try {
          render(now);
        } catch {
          fail();
        }
      });
  }
  function fail() {
    if (disposed) return;
    options.onFailure();
    dispose();
  }
  async function init() {
    renderer = new THREE.WebGLRenderer({
      canvas: elements.canvas,
      alpha: true,
      antialias: true,
      powerPreference: "default",
      preserveDrawingBuffer: false,
    });
    renderer.debug.onShaderError = () => {
      queueMicrotask(fail);
    };
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.96;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.autoUpdate = false;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    scene = new THREE.Scene();
    camera = new THREE.OrthographicCamera(-1000, 1000, 700, -700, 0.1, 8000);
    camera.position.set(0, 0, 3000);
    camera.lookAt(0, 0, 0);
    scene.add(new THREE.HemisphereLight(0xfff0d9, 0x463344, 2.3));
    const key = new THREE.DirectionalLight(0xffedce, 3.2);
    key.position.set(-850, 1050, 1700);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = key.shadow.camera.bottom = -2200;
    key.shadow.camera.right = key.shadow.camera.top = 2200;
    key.shadow.camera.near = 100;
    key.shadow.camera.far = 5000;
    key.shadow.normalBias = 1.8;
    key.shadow.bias = -0.0001;
    key.shadow.radius = 4;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xbfc6e5, 0.8);
    fill.position.set(1000, -150, 1100);
    scene.add(fill);
    groundShadow = new THREE.Mesh(
      new THREE.PlaneGeometry(9000, 9000),
      new THREE.ShadowMaterial({ opacity: 0.32 }),
    );
    groundShadow.position.z = -12;
    groundShadow.receiveShadow = true;
    scene.add(groundShadow);
    image = new Image();
    image.src = options.paperUrl;
    await deadline(image.decode(), 12000);
    if (disposed) return;
    await deadline(document.fonts.ready, 12000);
    if (disposed) return;
    measure();
    prepareMaterials();
    layoutLetter();
    paperGroup = new THREE.Group();
    scene.add(paperGroup);
    paperGroup.add(groundShadow);
    sheetGeometry = makeSheet();
    paperMat = makePaperMaterial();
    paperMesh = new THREE.Mesh(sheetGeometry, paperMat);
    paperMesh.castShadow = true;
    paperMesh.receiveShadow = true;
    paperMesh.customDepthMaterial = new THREE.MeshDepthMaterial({
      depthPacking: THREE.RGBADepthPacking,
      map: atlas,
      alphaTest: 0.14,
      side: THREE.DoubleSide,
    });
    paperGroup.add(paperMesh);
    topRoll = makeRoll();
    bottomRoll = makeRoll();
    paperGroup.add(topRoll, bottomRoll);
    band = makeBand();
    wax = makeWax();
    paperGroup.add(band, wax);
    dialog.dataset.renderer = "webgl-shared-paper-ink-uv";
    dialog.dataset.threeVersion = THREE.REVISION;
    reset();
    options.onReady();
  }

  function onScroll() {
    targetScroll = input.scrollTop / scale;
    wake();
  }
  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      if (disposed || !renderer || !image || !paperMesh) return;
      try {
        const fraction = targetScroll / Math.max(1, totalH - flatH);
        measure();
        layoutLetter();
        (paperMesh.customDepthMaterial as THREE.MeshDepthMaterial).map = atlas;
        targetScroll = clamp(fraction, 0, 1) * (totalH - flatH);
        input.scrollTop = targetScroll * scale;
        scroll = targetScroll;
        if (phase === "opening") {
          opened = 1;
          setOpened();
        }
        wake();
      } catch {
        fail();
      }
    }, 120);
  }
  function onVisibility() {
    if (document.hidden) {
      cancelAnimationFrame(raf);
      raf = 0;
    } else {
      last = 0;
      wake();
    }
  }
  function onContextLost(event: Event) {
    event.preventDefault();
    fail();
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(raf);
    raf = 0;
    clearTimeout(resizeTimer);
    for (const timer of timers) clearTimeout(timer);
    timers.clear();
    for (const cancel of pending) cancel(new Error("Render cancelled"));
    pending.clear();
    input.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", onResize);
    document.removeEventListener("visibilitychange", onVisibility);
    elements.canvas.removeEventListener("webglcontextlost", onContextLost);
    const geometries = new Set<THREE.BufferGeometry>(),
      materials = new Set<THREE.Material>();
    scene?.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
        geometries.add(object.geometry);
        for (const m of Array.isArray(object.material)
          ? object.material
          : [object.material])
          materials.add(m);
        if (object instanceof THREE.Mesh && object.customDepthMaterial)
          materials.add(object.customDepthMaterial);
      }
      if (object instanceof THREE.DirectionalLight) object.shadow.dispose();
    });
    for (const g of geometries) g.dispose();
    for (const m of materials) m.dispose();
    for (const t of textures) t.dispose();
    textures.clear();
    scene?.clear();
    renderer?.renderLists.dispose();
    renderer?.dispose();
    renderer?.forceContextLoss();
    for (const c of [
      baseCanvas,
      inkCanvas,
      idCanvas,
      strokeCanvas,
      ...Array.from(traceCache.values(), (entry) => entry.canvas),
    ])
      if (c) {
        c.width = 1;
        c.height = 1;
      }
    traceCache.clear();
    glyphs.length = 0;
    source.length = 0;
    shader = null;
    if (image) image.src = "";
    elements.canvas.width = 1;
    elements.canvas.height = 1;
  }
  input.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onResize);
  document.addEventListener("visibilitychange", onVisibility);
  elements.canvas.addEventListener("webglcontextlost", onContextLost);
  void init().catch(() => {
    if (!disposed) fail();
  });
  return {
    open,
    reset,
    showAll,
    setReduced(value) {
      reduced = value;
      if (value && ["opening", "writing", "reading"].includes(phase)) showAll();
      wake();
    },
    dispose,
  };
}
