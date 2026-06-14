"use client";

/**
 * Opsiyonel sesli okuma — Web Speech API (speechSynthesis, tr-TR).
 * Varsayılan kapalı (mute). Tarayıcı desteklemiyorsa veya konuşma
 * engellenirse sessiz kalır; hata fırlatmaz. Sadece UI katmanı.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export function useAgentVoice() {
  const [enabled, setEnabled] = useState(false);
  const [supported, setSupported] = useState(false);
  const enabledRef = useRef(false);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    return () => {
      try { window.speechSynthesis?.cancel(); } catch { /* sessiz */ }
    };
  }, []);

  const speak = useCallback((text: string) => {
    if (!enabledRef.current || !text) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "tr-TR";
      u.rate = 1.05;
      window.speechSynthesis.speak(u);
    } catch { /* otomatik izin yoksa sessiz kal */ }
  }, []);

  const toggle = useCallback(() => {
    setEnabled(prev => {
      const next = !prev;
      enabledRef.current = next;
      if (!next) { try { window.speechSynthesis?.cancel(); } catch { /* sessiz */ } }
      return next;
    });
  }, []);

  return { enabled, supported, speak, toggle };
}
