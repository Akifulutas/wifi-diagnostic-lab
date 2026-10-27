# Wi-Fi Diagnostic Lab & Bufferbloat Localization Lab — Yol Haritası ve Gelişim Durumu

Son Güncelleme: **Ekim 2026**. Proje Sahibi: **Akif Ulutaş (RWTH Aachen University)**.  
Donanım Test Yatağı: **AVM FRITZ!Box 7530 AX + Apple MacBook Pro M1 Pro (macOS Darwin)**.

**Mevcut Durum:**  
- **Tamamlandı:** v0.1 ve v0.2 pilot analiz boru hattı, ham telemetri ayrıştırıcıları, 4 fazlı ölçüm motoru ve 4 SVG yayın grafiği.
- **Tamamlandı:** Gerçek ev ortamında (L1 Line-of-Sight vs L2 Drywall NLOS) fiziksel Wi-Fi 6 telemetri ölçümleri (`data/raw/live_home_runs/`).
- **Tamamlandı:** Bufferbloat Localization Lab (`bll`) Linux network namespace test yatağı, DuckDB analitik depolaması, diferansiyel yol cebiri ve sıfır etiket sızıntılı deterministic set-valued çıkarım motoru.
- **Doğrulandı:** 196 birim/kontrat testi + 286 E2E kabul testi (285 geçti, 1 Linux atlandı) ile %100 yerel CLI doğrulandı.

---

## 📌 Tamamlanan ve Planlanan Aşamalar

| Aşama | Durum | Somut Çıktı | Tamamlanma & Doğrulama Kanıtı |
|---|:---:|---|---|
| **v0.1 Altyapı** | **Tamamlandı** | CLI, mimari, veri sözlüğü, TOML/JSON şemaları | `wifi-lab doctor` ve temel kontrat testleri |
| **v0.2 Pilot** | **Tamamlandı** | 12 sentetik referans koşusu, hata muhasebesi, 4 SVG grafik | `wifi-lab analyze data/raw/pilot` boru hattı |
| **v1.0 Gerçek Ev Ölçümleri** | **Tamamlandı** | L1 vs L2 dual-vantage Wi-Fi 6 ölçümleri, airtime bloat tespiti | `data/raw/live_home_runs/` (377 probe kaydı) |
| **v1.1 BLL Çıkarım Motoru** | **Tamamlandı** | 6-düğümlü netns laboratuvarı, DuckDB RTT delta motoru, çekimserlik (abstention) | Sıfır etiket sızıntısı birim ve E2E testleri |
| **v2.0 Wi-Fi 7 / MLO (Gelecek)** | *Tasarım Aşamasında* | Çoklu link operasyonu (MLO, eMLSR), 6 GHz band geçişi simülasyonu | `wifi-lab mlo-sim` kuyruk simülatörü |

Donanım bekleme süresi bu saatlere dahil değil. Başvuru belgeleri paralel hazırlanır; 12 haftanın bitmesi beklenmez. Mevcut gerçek çıktı hangi aşamadaysa öyle anlatılır.

## Haftalık plan

| Hafta | Öğrenme | Uygulama | Haftanın çıktısı |
|---|---|---|---|
| 1 | LAN/WAN, katmanlar, throughput/RTT | OS/firmware/association kaydı; sunucu erişimi; TCP/DNS lab; JSON alanları | Donanım notu, bir lab ve parser başlangıcı |
| 2 | TCP/UDP, congestion; JSON/tablo | P01–P03: parser, birimler, kaynaklı örnekten figür | v0.1 analiz yolu |
| 3 | CSMA/CA/airtime, Wi-Fi 6; ilk makale | P04–P06: manifest, basit runner, ping/evreler | Bir koşunun ham kayıt ve doğru zaman eşlemesi |
| 4 | Tekrarlı deney, alternatif açıklamalar | P07: pilot, kontroller, iki figür, 2–3 sayfa not | v0.2; 12 planlı koşu ve açık hata sayımı |
| 5 | Otomasyon güvenilirliği | Timeout/cancel/parse hataları; config, veri sözlüğü, offline analiz | Hataları koruyan runner ve kritik kontroller |
| 6 | Dengeli sıra ve koşu düzeyi analiz | Ana çalışmanın ilk günü; kablolu referans imkânı | İlk gün, sapmalar ve kalite kontrolü |
| 7 | Median/IQR, ECDF, p95 ve bağımlı örnekler | İkinci gün; gün bazlı karşılaştırma | 40 planlı koşunun dökümü ve dört figür |
| 8 | Sonuç açıklama ve reproducibility | P08–P09 tamamlanması; ham veriden yeniden analiz | v1.0 çekirdek çalışma |
| 9 | WiSlow ve teşhis için kanıt | P10: gözlem/aday neden/eksik kanıt/sonraki test | Takip önerileri ve sınırları |
| 10 | MLO kanıt türleri; tek ek soru | P11: band veya UDP deneyi | Ek deney ve 6–8 kaynaklı sentez |
| 11 | Bilimsel yazım | P12: rapor, temiz ortamda offline tekrar | Rapor ve release adayı |
| 12 | İngilizce teknik anlatım | Beş dakikalık demo, sorular, tamamlanan katkıları anlatma | Portföy sürümü ve mülakat hazırlığı |

Genel hafta: 2 saat okuma/izleme, 4 saat kod/deney, 2 saat analiz, 1 saat belgeleme, 1 saat kontrol ve İngilizce anlatım. Öğrenirken mevcut Python deneyimini kullan. Ölçüm/rapor haftalarında dağılım değişebilir.

## Deney tasarımı

```text
Mac (Wi-Fi) ── FRITZ!Box 7530 AX ── Ethernet ── Yerel server
```

Önce 5 GHz, tek TCP stream; upload/download ayrı. Her koşu: 30 s idle + 3 s warm-up + 60 s measured load + 30 s recovery. Gerçek evre zamanları kaydedilecek.

- Pilot: 2 konum × 2 yön × 3 tekrar = **12 planlı yük koşusu**, tek gün.
- Ana çalışma: 2 konum × 2 yön × 5 tekrar × 2 gün = **40 planlı yük koşusu**.
- Kablolu referans mümkünse her yön için 5 ek koşu; ana 40'a dahil değil.

Idle/recovery her koşunun içinde; ayrı throughput hücreleri değil. Önceki 80 koşuluk planın yerine bu düzen kullanılır. Sayılar kesinlik garantisi değildir; pilot sonrası değişiklik ana ölçümden önce protokole yazılır. Bir koşudaki ping'ler bağımsız deney tekrarı sayılmaz.

Sunucu gelene kadar parser/protokol çalışmaları ilerler; yerel Wi-Fi throughput sonucu iddia edilmez. Loopback yazılım kontrolü sayılır. Donanım hazır olduğunda pilot tarihi yenilenir.

## Kaynak sırası

1. [Kurose 1.4–1.5](https://gaia.cs.umass.edu/kurose_ross/videos/1/): performans/katmanlar; metric ve topology notu.
2. [Kurose 3.3 ve 3.5–3.7](https://gaia.cs.umass.edu/kurose_ross/videos/3/): TCP/UDP/congestion; paket analizi.
3. [Wireshark labs](https://gaia.cs.umass.edu/kurose_ross/wireshark.php): DNS/ARP ve TCP; kendi açıklaman.
4. [Kurose 6.3](https://gaia.cs.umass.edu/kurose_ross/videos/6/) ve [802.11 alıştırmaları](https://gaia.cs.umass.edu/kurose_ross/videos/7/); [Cisco Wi-Fi 6](https://video.cisco.com/detail/video/6049407419001).
5. [Literature review](docs/literature-review.md): Wi-Fi 6 ölçümü ve WiSlow; ardından MLO trace/prototip çalışmaları.

Her öğrenme oturumundan bir lab, metric tanımı veya deney kararı çıksın. Kaynak/video sayısı tek başına teslim değildir.

## Sonraki kapsam

Çekirdek: TCP throughput, idle/loaded RTT, kayıt/analiz ve kontroller. Sonra bir band veya UDP deneyi. Testbed erişimine göre multi-client, mesh, native MLO veya VLP yeni protokolle ele alınır.

Tek istemcili speed test OFDMA/MU-MIMO faydasını kanıtlamaz. Tek AP mesh-backhaul deneyi oluşturmaz. Büyük ML modeli, driver, ns-3 ve dashboard için çekirdek çalışma tamamlandıktan sonra karar ver.

## Teslim kontrolü

- [ ] README mevcut uygulamayı doğru anlatıyor.
- [ ] Topology, actual association, sürüm/config ve endpoint/yön kayıtlı.
- [ ] Ham veri/provenance ve paylaşılan veri dönüşümleri açık.
- [ ] Başarısız denemeler korunmuş; planlanan/denenen/geçerli sayıları var.
- [ ] Grafikler aynı veriden üretiliyor; birim ve n açık.
- [ ] Gün/blok/koşu düzeyi analiz yapılmış; paketler tekrar sayılmamış.
- [ ] Olası neden ile kanıt ayrılmış; sonraki kontrol belirli.
- [ ] Kaynaklarda measurement/prototype/simulation ayrımı korunmuş.
- [ ] İngilizce rapor ve beş dakikalık anlatım hazır.

Bu liste tamamlanmış işler değildir. Uygulama sırası: [P01–P12](docs/implementation-backlog.md).
