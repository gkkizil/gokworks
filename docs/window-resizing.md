# Pencere boyutlandırma — 16 Ekim 2026

Küçültme ve büyütme sırasında açık olmayan sekiz çalışma alanı da pencereyle beraber esniyor, bütün alt kontrolleri yeniden boyutlanıyordu. Menü geçişleri için saklanan sayfaların aynı zamanda yeniden boyutlandırılması, görünmeyen içerikte gereksiz çizim işi oluşturuyordu.

Artık bütün sayfalar tek bir görünüm alanının gerçek alt pencereleri. Yalnız açık sayfa bu alanın genişlik ve yüksekliğini izliyor. Diğer sayfalar son boyutlarında, yerel pencereleri kaldırılmadan altta saklanıyor. Böylece hazır menü geçişi korunuyor; küçük pencerenin kenarlarından eski büyük sayfaların görünmesi de fiziksel üst pencerenin kırpmasıyla engelleniyor. Sayfa yeniden açıldığında mevcut pencere boyutuna uyarlanıyor, girilmiş değerler korunuyor.

Yerleşim istekleri 16 ms aralıklı tek bir bekleyen çağrıya birleştiriliyor. Her olayda yeniden başlatılan 35 ms bekleme kaldırıldı: sürükleme devam ederken de yerleşim güncelleniyor. Cıvata, ağırlık, ISO ve tolerans çizimleri aynı akışı kullanıyor; arama araçları yalnız dar/geniş düzen eşiği değiştiğinde yeniden yerleştiriliyor. Bu aralık, 60 FPS garantisi değildir.

İlk pencere boyutu ve minimum sınırlar DPI ölçeğine ve kullanılabilir alana göre hesaplanıyor. Windows'ta pencerenin bulunduğu monitörün görev çubuğu dışındaki çalışma alanı okunuyor; başlık ve çerçeve için pay bırakılıyor. Kısa pencerelerde yan menü sıklaşıyor, PDF/DXF/K/R başlıklarının yardımcı satırları gizlenerek asıl çalışma alanına yer açılıyor. İsimlendirmedeki gizli hata düğmesinin DPI değişiminde yeniden belirmesi de düzeltildi.

## Ölçüm

Aynı [betik](report-tools/benchmark_window_resize.py), `f8e96a8` başlangıcında ve değişikliklerden sonra birer kez çalıştırıldı. Normal açılışta dokuz sayfa hazırlandı; PDF ve ağırlık ekranlarında 1000×690–1440×900 arasında 16 boyut değişimi, her adımda gerçek Tk `update()` çağrısıyla ölçüldü. Python 3.13, Tk 8.6 ve CustomTkinter 6.0 kullanıldı. Linux/Xvfb'de font yükleme kısıtı nedeniyle iki ölçümde de `circle_shapes` çizimi kullanıldı.

| Ölçüm | Önce | Sonra |
| --- | ---: | ---: |
| PDF boyut değişimi, ortanca | 90,48 ms | 19,04 ms |
| PDF boyut değişimi, en yüksek | 120,25 ms | 33,18 ms |
| Ağırlık boyut değişimi, ortanca | 82,86 ms | 32,75 ms |
| Ağırlık boyut değişimi, en yüksek | 104,87 ms | 41,65 ms |
| Görünmeyen sayfalardaki boyutlandırma olayı, her 16 adımda | 128 | 0 |

Hazır menü geçişleri de mevcut gezinme betiğiyle kontrol edildi: sekiz tıklamanın ortancası 25,83 ms, en yükseği 34,30 ms; açılış sonrasında yeni sayfa oluşturulmadı. Bu ölçümler birer turdur; Windows kare hızı, fareyle gerçek büyütme animasyonu veya SolidWorks ölçülmedi. [Ham kayıt](test-results/window-resize.json).

## Kontrol

İlgili kontroller; görünmeyen sayfalarda boyutlandırma olmaması, sayfaların kaldırılmadan saklanması, sürekli sürüklemede yerleşimin ilerlemesi, ön yükleme, hata sonrası ekran dönüşü, sekmeler, tema, kullanıcı değerlerinin korunması ve 1000×690–1920×1080 ile %100/%125/%150 ölçeklerini kapsıyor. Tüm test paketi çalıştırılmadı.

Yerleşim kontrolündeki eski 48 piksel K/R sekme beklentisi, başlangıç kodunda zaten kullanılan 42 mantıksal piksele düzeltildi. Çalışma alanı, alanların erişilebilirliği ve tablo yüksekliği denetimleri korundu.

```bash
DISPLAY=:99 python docs/report-tools/benchmark_window_resize.py /tmp/window-resize.json
```
