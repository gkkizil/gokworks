# Menü akıcılığı — 13 Ekim 2026

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

BOM araması, liste–ürün ağacı geçişi ve değişmeyen ekranların yeniden çizimi iyileştirildi. Parça adı, konfigürasyon ve dosya yolu arama için bir kez hazırlanıyor. Eşdeğer arama sorguları tabloyu yeniden kurmuyor; aynı boyut, seçim ve tema tekrar uygulanmıyor. Yeni taramada önbellek temizleniyor; tema ve ölçek değiştiğinde açık ve saklanan sayfalar güncelleniyor.

## Önce / sonra

Başlangıç: `7b965da`. Aynı Linux ortamında Python 3.13.5, Tk 8.6.16 ve Xvfb üzerinde gerçek Tk penceresi kullanıldı. BOM verisi 10.000 örnek parça ve 10.000 ağaç düğümünden oluşuyor. Windows ve SolidWorks çalıştırılmadı.

| İşlem | Önce | Sonra |
| --- | ---: | ---: |
| BOM arama geri çağrısı, medyan | 6,56 ms | 0,59 ms |
| BOM arama geri çağrısı, en yüksek örnek | 13,17 ms | 2,43 ms |
| Parça listesi / ürün ağacı geçişi, medyan | 4,27 ms | 1,75 ms |
| Önceden açılmış PDF / BOM sayfaları arası geçiş, medyan | 6,00 ms | 4,38 ms |
| Eşdeğer sorguda tabloyu yeniden kurma | 1 | 0 |
| Boyut değişmeden 20 yerleşim çağrısında durum etiketi güncellemesi | 20 | 0 |
| Aynı çağrılarda parça tablosu sütun ayarı | 60 | 0 |

Arama ölçümü beş turda `imalat-000`, `İMALAT-000`, `imalat-009`, `olmayan` ve boş sorguyu içerir. İlk iki sorgu aynı sonucu verir. Arama süresi metin değişikliğinin eşzamanlı geri çağrısını ölçer; ekran çizimi sonraki adımda tamamlanır. Sekme ve sayfa ölçümleri `update_idletasks()` ile çizimi de içerir. Bunlar belirli iş yükündeki ölçümlerdir; tüm aramalarda aynı hızlanmayı garanti etmez.

Ayrı genel arayüz ölçümünde PDF, DXF/DWG, K/R, ISO ve geometrik tolerans sayfalarının hazır geçiş medyanı 3,16 → 3,78 ms oldu; bu senaryoda hızlanma ölçülmedi. Sayfaların ilk oluşturulması hâlâ yaklaşık 80–160 ms sürüyor. [Ham önce/sonra sonuçları](test-results/menu-latency.json) genel ölçümü de içerir.

## Kontroller

15 hedefli GUI kontrolü geçti: BOM tarama/iptal/Excel aktarımı, Türkçe karakterli arama, seçim korunması, yeni taramada arama önbelleğinin yenilenmesi, sayfa ön yükleme, hızlı menü tıklamaları, açık/koyu tema ve ölçek değişimi. İlk çalışmadaki iki yeni test hatası, yanlış konumdaki doğrulama ve Tcl renk nesnesinin metinle karşılaştırılmasından kaynaklandı; testler düzeltildi ve ilgili üç kontrol tekrar geçti. Tüm test paketi çalıştırılmadı.

Ölçümü yeniden çalıştırmak için proje kökünde, Tk bağımlılıkları ve sanal ekran hazırken:

```bash
DISPLAY=:99 python docs/report-tools/benchmark_bom_navigation.py /tmp/bom-navigation.json
DISPLAY=:99 python docs/report-tools/benchmark_gui_events.py . /tmp/gui-navigation.json
```

İki ölçüm aynı ekranda sırayla çalıştırılmalıdır.
