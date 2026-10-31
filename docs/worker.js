// Runs the Rust engine off the main thread so the page stays responsive during a solve.
let ex = null;

async function init() {
  const bytes = await (await fetch("saf.wasm?v=4")).arrayBuffer();
  const { instance } = await WebAssembly.instantiate(bytes, { env: { js_now_ms: () => performance.now() } });
  ex = instance.exports;
}

function call(cmd, text) {
  const data = new TextEncoder().encode(text);
  const p = ex.alloc(data.length);
  new Uint8Array(ex.memory.buffer).set(data, p);
  const r = ex.call(cmd, p, data.length);
  ex.dealloc(p, data.length);
  const n = new DataView(ex.memory.buffer).getUint32(r, true);
  const out = new TextDecoder().decode(new Uint8Array(ex.memory.buffer, r + 4, n));
  ex.dealloc(r, n + 4);
  return out;
}

onmessage = async (e) => {
  const { id, cmd, body } = e.data;
  try {
    if (!ex) await init();
    postMessage({ id, ok: true, text: call(cmd, body) });
  } catch (err) {
    postMessage({ id, ok: false, error: String(err) });
  }
};
