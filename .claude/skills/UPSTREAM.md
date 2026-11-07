# Kaynak

- Depo: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (MIT, `LICENSE`)
- Sürüm: commit `b7d5353`, `.claude/skills/` altındaki 7 skill:
  `ui-ux-pro-max`, `design`, `design-system`, `ui-styling`, `brand`,
  `banner-design`, `slides`. `ui-styling` kendi Apache-2.0 lisansıyla
  (`ui-styling/LICENSE.txt`), yazı tipleri OFL lisanslarıyla gelir.
- Yerel değişiklikler: betik yolları `${CLAUDE_PLUGIN_ROOT}` yerine proje
  köküne göre (`$(git rev-parse --show-toplevel)/.claude/skills/...`);
  `tests/` klasörleri alınmadı. Veri ve betikler değiştirilmedi.
- Dış bağlantı: yalnız `design` skill'inin logo/ikon/CIP görsel üretimi,
  ortamda `GEMINI_API_KEY`, `ATLASCLOUD_API_KEY` veya `MUAPI_API_KEY`
  verilirse ilgili servise bağlanır. Diğer betikler yereldir (`ui-styling`
  bileşen ekleme `npx shadcn` çalıştırır).
- Not: GOKWORKS bir PySide6 masaüstü uygulamasıdır; skill'lerin teknoloji
  önerileri çoğunlukla web içindir. Renk, kontrast, tipografi, form ve
  erişilebilirlik kuralları genel olarak kullanılır.
