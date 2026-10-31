//! Browser entry points. JSON goes in and out through linear memory, so the page needs
//! no glue library: it writes a string, calls `call`, and reads the reply.
use saf_engine::explain::answer;
use saf_engine::params::Params;
use saf_engine::solution::Solution;
use saf_engine::{baseline, run};
use serde_json::{json, Value};

#[no_mangle]
pub extern "C" fn alloc(n: usize) -> *mut u8 {
    let mut v = Vec::<u8>::with_capacity(n);
    let p = v.as_mut_ptr();
    std::mem::forget(v);
    p
}

/// # Safety
/// `p` and `n` must come from `alloc`.
#[no_mangle]
pub unsafe extern "C" fn dealloc(p: *mut u8, n: usize) {
    drop(Vec::from_raw_parts(p, 0, n));
}

fn dispatch(cmd: u32, body: &str) -> Value {
    match cmd {
        1 => {
            let p: Params = serde_json::from_str(body).unwrap_or_default();
            serde_json::to_value(run(&p)).unwrap()
        }
        2 => {
            let v: Value = serde_json::from_str(body).unwrap_or(Value::Null);
            let q = v["question"].as_str().unwrap_or("").to_string();
            let s: Solution = serde_json::from_value(v["solution"].clone()).unwrap_or_default();
            serde_json::to_value(answer(&q, &s)).unwrap()
        }
        3 => {
            let p: Params = serde_json::from_str(body).unwrap_or_default();
            let pack = |b: Option<Solution>| b.map(|s| json!({"objective": s.objective, "n_ref": s.kpis.n_refineries, "n_dep": s.kpis.n_depots, "message": s.message}));
            json!({"greedy": pack(baseline::greedy(&p)), "airport_first": pack(baseline::airport_first(&p))})
        }
        _ => json!({"error": "unknown command"}),
    }
}

/// Returns a pointer to a 4-byte little-endian length followed by that many bytes.
///
/// # Safety
/// `p` and `n` must describe a valid UTF-8 buffer from `alloc`.
#[no_mangle]
pub unsafe extern "C" fn call(cmd: u32, p: *const u8, n: usize) -> *mut u8 {
    let body = std::str::from_utf8(std::slice::from_raw_parts(p, n)).unwrap_or("{}");
    let text = dispatch(cmd, body).to_string();
    let mut out = Vec::with_capacity(text.len() + 4);
    out.extend_from_slice(&(text.len() as u32).to_le_bytes());
    out.extend_from_slice(text.as_bytes());
    let ptr = out.as_mut_ptr();
    std::mem::forget(out);
    ptr
}
