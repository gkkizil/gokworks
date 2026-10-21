# Ortak Python yardımcıları

- `settings.py`: atomik JSON ayar okuma/kaydı. Kullanıcının mevcut ayar dosyası
  konumu ve anahtarları korunur; Qt ayar deposu bunu kullanır.
- `theme.py`, `text.py`, `window_geometry.py`: arayüzden bağımsız renk/yazı,
  metin ve geometri yardımcıları. Mevcut vektör çizim protokolü renklerini buradan alır.
- `icons.py`, `typography.py`: eski bağımsız K/R denemesinin Tk yardımcıları.
  Güncel GOKWORKS arayüzü bunları içe aktarmaz; ana EXE Tk paketlerini dışlar.
- `package_check.py`: Qt öz denetimine yönlenen uyumluluk giriş noktası.

Güncel Qt tema, ikon, navigasyon, iş yönetimi ve ortak widget'lar `gui_qt/`
altındadır. Gömülü logolar depo kökündeki `assets/` klasöründedir.
