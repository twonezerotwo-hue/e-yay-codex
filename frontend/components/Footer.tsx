"use client";

import { useLanguage } from "@/contexts/LanguageContext";

export default function Footer() {
  const { t } = useLanguage();
  return (
    <div className="py-3 border-t border-eyay-border text-center">
      <p className="text-xs text-eyay-faint">
        E-YAY BrainChain · PAPER_SAFE · NO_EXECUTION
        <span className="mx-2 text-eyay-border">·</span>
        {t.footer.text}
      </p>
    </div>
  );
}
