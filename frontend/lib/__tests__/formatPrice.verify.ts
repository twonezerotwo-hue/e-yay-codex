/**
 * formatPrice sanity check doğrulama — `npx tsx lib/__tests__/formatPrice.verify.ts`
 * Test runner gerekmez; TypeScript derleme + console.assert ile çalışır.
 */
import { checkConfirmationSanity, parseNumeric } from "../formatPrice";

function assert(label: string, condition: boolean) {
  if (!condition) {
    console.error(`FAIL: ${label}`);
    process.exitCode = 1;
  } else {
    console.log(`PASS: ${label}`);
  }
}

// ── parseNumeric ──────────────────────────────────────────────────────────
assert("parseNumeric $61,000 → 61000", parseNumeric("$61,000") === 61000);
assert("parseNumeric $61 → 61",        parseNumeric("$61")     === 61);
assert("parseNumeric 99.78 → 99.78",   parseNumeric("99.78")   === 99.78);
assert("parseNumeric 4.32% → 4.32",    parseNumeric("4.32%")   === 4.32);
assert("parseNumeric 59109 → 59109",   parseNumeric("59109")   === 59109);
assert("parseNumeric — → null",        parseNumeric("—")       === null);

// ── DXY ──────────────────────────────────────────────────────────────────
{
  const r = checkConfirmationSanity("DXY dolar sıkılaşması yok (104 altında)", "99.78", "104");
  assert("DXY current_ok",        r.current.ok  === true);
  assert("DXY threshold_ok",      r.threshold.ok === true);
  assert("DXY final_status=ok",   r.final_status === "ok");
  assert("DXY current display",   r.current.displayValue === "99.8");
}

// "altında" (below) kelimesi xauusd olarak yanlış eşleşmemeli
{
  const r = checkConfirmationSanity("Brent direnç altında ($74,959 altında)", "92.69", "74959");
  assert("Brent current_ok (92.69 geçerli)",     r.current.ok   === true);
  assert("Brent threshold_invalid (74959 dışı)", r.threshold.ok === false);
  assert("Brent final=threshold_invalid",        r.final_status === "threshold_invalid");
}

// Brent threshold mantıklı (~74.96) ise
{
  const r = checkConfirmationSanity("Brent direnç altında", "92.69", "74.96");
  assert("Brent both ok (threshold=74.96)",  r.final_status === "ok");
}

// ── BTC ──────────────────────────────────────────────────────────────────
{
  const r = checkConfirmationSanity("BTC destek üstünde ($59,109 üzerinde)", "$62,705", "$59,109");
  assert("BTC current_ok",      r.current.ok   === true);
  assert("BTC threshold_ok",    r.threshold.ok === true);
  assert("BTC final=ok",        r.final_status === "ok");
  assert("BTC current display", r.current.displayValue === "$62,705");
}

// ── XAG / Gümüş ──────────────────────────────────────────────────────────
{
  const r = checkConfirmationSanity("Gümüş destek üstünde ($59,109 üzerinde)", "$68.60", "$59,109");
  assert("XAG current_ok  (68.60 geçerli)",    r.current.ok   === true);
  assert("XAG threshold_invalid (59109 dışı)", r.threshold.ok === false);
  assert("XAG final=threshold_invalid",        r.final_status === "threshold_invalid");
}

// ── Copper ───────────────────────────────────────────────────────────────
{
  const r = checkConfirmationSanity("Bakır destek üstünde", "$14,142", "$130,312,880");
  assert("Copper current_ok (14142/ton range)", r.current.ok   === true);
  assert("Copper threshold out_of_range",       r.threshold.ok === false);
  assert("Copper final=threshold_invalid",      r.final_status === "threshold_invalid");
}

// ── Yield Curve — spread semantiği ───────────────────────────────────────
{
  // 10.00% büyük ihtimalle 10Y yield; yield_spread range [-5,5] dışı
  const r = checkConfirmationSanity("Yield curve inversiyonu çözülüyor (10Y > 2Y)", "10.00%", "0");
  assert("Yield curve 10% current_invalid", r.current.ok  === false);
  assert("Yield curve final=current_invalid", r.final_status === "current_invalid");
}

{
  // +0.92% gerçek spread — geçerli
  const r2 = checkConfirmationSanity("Yield curve inversiyonu çözülüyor (10Y > 2Y)", "0.92%", "0");
  assert("Yield curve spread 0.92 current_ok", r2.current.ok  === true);
  assert("Yield curve final=ok",               r2.final_status === "ok");
}

// ── VIX ──────────────────────────────────────────────────────────────────
{
  const r = checkConfirmationSanity("VIX destek altında", "59109", "25");
  assert("VIX 59109 current_invalid",   r.current.ok  === false);
  assert("VIX final=current_invalid",   r.final_status === "current_invalid");
}

{
  const r2 = checkConfirmationSanity("VIX destek altında", "21.4", "25");
  assert("VIX 21.4 current_ok",    r2.current.ok  === true);
  assert("VIX final=ok",           r2.final_status === "ok");
}

console.log("\nTamamlandı.");
