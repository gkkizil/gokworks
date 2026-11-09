# Kolay kullanım görünümü — 9 Kasım 2026

Amaç: profesyonel olmayan kullanıcıya mevcut teknik ekranı dayatmadan,
ölçü/hareket/sonuç üzerinden hesap yapma olanağı vermek.

## Davranış

- İlk açılış varsayılanı Kolay kullanım; seçilen görünüm arayüz tercihi olarak
  saklanır. Proje dosya şeması değişmez.
- Ölçüler: üç temel ölçü ve ölçekli olmadığı açıkça belirtilen silindir rehberi.
  Piston çapının gövde dış çapı olmadığı açıklanır.
- Hareketler: var olan fazların adları ve türleri korunur. Hareket mesafesi,
  tamamlanma süresi ve karşı koyan kuvvet girilir. Beklemede süre/kuvvet,
  boşta yalnız süre bulunur. Düzenlenmeyen hız tabanlı fazlar hız tabanlı kalır.
- Kuvvet: kN veya ton-kuvvet. 1 tonf = 9806.65 N. Görüntüleme değişimi
  fiziksel kuvveti ve bekleyen düzenlemeyi korur; geçersiz girişte kısmi dönüşüm yoktur.
- Sonuç: altı ihtiyacın değeri ve anlamı; bütün kritik/uyarı bildirimleri ve
  PDF/Excel erişimi. Yetersiz pompa ve varsayımsal ısı sonuçları açıkça belirtilir.
- İleri–bekle–geri örneği mevcut ölçü ve teknik ayarları korur. Geri alma yalnız
  hareketleri geri getirir; sonradan değiştirilen ölçüleri geri almaz.
- Pompa önerisi düğmesi nominal deplasmanı değiştirir; basınç sınırını veya
  verimleri kendiliğinden artırmaz. Sonuçlar yeniden hesaplanır.
- Ayrıntılı görünüm tüm mevcut özellikleri korur. Çok silindirli veya 12 fazı
  aşan projeler otomatik olarak ayrıntılı açılır; kolay görünüm projeyi düzleştirmez.

## Sınırlar

Bu çalışma uzmanlık veya üretici doğrulamasının yerine geçmez. Kütleyi
bilmenin gerçek itme/çekme kuvvetini her mekanizmada belirlemediği açıklanır.
Çekirdek, üretici veri durumu, mühendislik kabulleri ve proje şeması korunur.
Basit görünümde düzenlenmeyen arka plan ayarları açıklamada görünür tutulur ve
ayrıntılı ekrandan incelenebilir. Kritik uyarılar gizlenmez.

## Doğrulama

Birleşik koşu: **127 test geçti**; hidrolik hesap/rapor testleri, mevcut ayrıntılı
UI testleri, yeni kolay giriş testleri ve sayfa/gezinme regresyonları.

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests/hydraulic_unit modules/hydraulic_unit/tests tests/test_lazy_pages_gui.py tests/test_page_transition.py -q
QT_QPA_PLATFORM=offscreen python main.py --self-check /tmp/hydraulic-novice-startup.json
```

Görsel kontrol: 1366×900 koyu temada üç adım; 1024×700 açık temada ölçü girişi.
Görüntüler bu çalışmada `/tmp/hydraulic-novice-final-measure.png`,
`...-motions.png`, `...-results.png`, `...-small.png` altında üretildi ve incelendi.
Bu ekran görüntüleri Windows native veya tam erişilebilirlik sertifikası değildir.

Kod değişiklikleri: `beginner.py` (Qt'siz dönüştürme/örnek hareket),
`beginner_view.py` (kolay giriş), `ui.py` (görünüm seçimi ve mevcut servislere bağlama).
`tests/test_beginner_ui.py` ve kök `tests/hydraulic_unit/test_beginner_adapter.py`
eklendi. Mevcut UI testleri ayrıntılı görünümü açıkça seçerek çalışır.
