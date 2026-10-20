# Hızlı Cıvata Tork Hesabı

Mevcut GOKWORKS PySide6 uygulamasında **Mühendislik Hesapları → Hızlı tork hesabı**.
Bağımsız hesap motoru `rules.py`; yeni bağımlılık veya SolidWorks gerektirmez.

- M3–M36, normal/ince adım; 4.8, 5.8, 8.8, 10.9, 12.9.
- Kuru K=0,20, hafif yağlı K=0,15; elle K girişi ve varsayılan %70 ön yük.
- Tahmini tork N·m, ön yük kN, tek tuşla pano ve kayıtlı seçimler.
- Canlı bağlantı kesiti: cıvata, somun, taralı iki parça, sıkma momenti ve hedef
  ön yük okları. Çap/adım ve hesap değerleri çizim üzerinde güncellenir.

Kesit şematik ve ölçeksizdir. Baş/somun ölçüsü, delik ve parça kalınlığı
atanmaz; bağlantı kapasitesi veya üretim resmi anlamına gelmez.

[Hesap formülleri, ISO dayanım temeli ve sınırlar](../docs/bolt-torque.md).

Gerçek Qt ekranları:

- [Koyu tema · M10×1,5 / 8.8 / %70](examples/torque-dark.png)
- [Küçük pencere · 1024×700](examples/torque-small.png)
- [Açık tema · ince diş / elle K](examples/torque-light.png)

Ekranlar `docs/report-tools/capture_bolt_torque_gui.py` ile alınır;
[sayısal girdiler/sonuçlar](examples/captures.json) ayrıca saklanır.
Paket kontrolü yeni modülü açar, kuru/yağlı sonuçları ve kopyalamayı doğrular.
Bu ekleme kendiliğinden EXE üretmez.
