# Manuel K / R atama sonrası son doğrulama

**189 test geçti; 0 başarısız, 0 atlanan. 44 gerçek Tk GUI testi.** Yeni manuel
özellik için 15 test: 4 sayısal/girdi, 6 COM uygulama, 5 gerçek GUI testi.

- [Arşiv: Tam konsol kaydı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/manual-k-radius/test-run.log)
- [Test özeti ve test edilen kaynakların SHA-256 değerleri](test-summary.json)
- [Gerçek manuel GUI görüntülerinin boyut ve SHA-256 kayıtları](screenshots.json)
- [Kullanım](../../manual-k-radius.md)

Kullanıcı örneği `2 mm → K=0,274, R=2 mm` doğrulandı. Eşleşen parçada
K=0.274 ve R=0.002 metre yazılıyor; diğer kalınlıklardaki parçalar için
ModifyDefinition/Save3 çağrılmıyor. Montaj örnekleri tekilleştirme, alt montaj,
referans konfigürasyonu, önizleme, geri alma, CSV, yeniden açılışta tercihler ve
küçük pencerede forma kaydırarak erişme gerçek kod akışıyla sınandı.

Tk ve hesap kodu gerçekten çalıştırıldı; SolidWorks COM test nesneleriyle
teyit edildi. Gerçek Windows/SolidWorks montajı bu ortamda çalıştırılmadı.
Önceki 174 testlik K/R raporu `../k-radius/`, 140 testlik GUI raporu `../`
altında tarihsel kayıt olarak korunur.

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
  .venv/bin/python -m unittest discover -s tests -v
```
