<p align="center">
  <img src="assets/icon.png" width="160" alt="TDCaro">
</p>

<h1 align="center">TDCaro</h1>

<p align="center">
  Game Caro (Gomoku – nối 5) đấu với máy, có 4 mức độ AI từ <b>Dễ</b> đến <b>Cực khó</b>.<br>
  Đồ án môn Trí tuệ Nhân tạo – viết bằng Python + pygame-ce.
</p>

<p align="center">
  <a href="https://duydev1205.github.io/TDCaro/"><b>▶ Chơi ngay trên trình duyệt</b></a> ·
  <a href="https://github.com/DuyDev1205/TDCaro/releases/latest"><b>⬇ Tải bản mới nhất (Windows .exe / macOS .dmg)</b></a>
</p>

---

## Tính năng

- **Chơi online 1 vs 1**: một người tạo phòng (mã 6 ký tự), người kia nhập mã để vào — chơi được giữa bản máy tính và bản web
- **Bản web**: chơi ngay trên trình duyệt, không cần cài đặt (GitHub Pages)

- **Luật chơi**: *Chặn 2 đầu* (mặc định — dãy 5 bị quân đối thủ chặn cả hai đầu không thắng, mép bàn không tính là chặn) hoặc *Tự do*; AI mức Bình thường/Khó/Cực khó hiểu luật này
- **4 mức độ AI**: Dễ · Bình thường · Khó · Cực khó (xem chi tiết bên dưới)
- Bàn cờ từ 5×5 đến **20×20** (chọn nhanh 9 · 13 · 15 · 19 · 20, hoặc `←/→` / cuộn chuột), chọn người đi trước
- Tỉ số cả phiên, **đặt lại** bằng nút *Đặt lại* hoặc phím `R`
- 4 giao diện: Midnight Neon, Gỗ Cổ Điển, Đại Dương, Hoa Anh Đào
- Hiệu ứng đặt quân, đường thắng, pháo giấy; âm thanh
- **Nhạc nền lo-fi**: 3 bài chill tự soạn bằng code — *Mưa đêm*, *Cà phê sáng*, *Hoàng hôn* (`tools/make_music.py`), phát ngẫu nhiên
- **Đi lại** (Undo), **Gợi ý** nước đi, lịch sử nước đi, đồng hồ, tỉ số
- **Toàn màn hình** (F11 / Alt+Enter hoặc nút trên màn hình)
- AI chạy trên luồng riêng → giao diện không bị đơ
- **Tự động cập nhật**: game tự kiểm tra bản mới trên GitHub Releases và cập nhật bằng một cú bấm
- Tự tạo **shortcut TDCaro** trên Desktop và Start Menu (Windows) khi mở lần đầu và sau mỗi lần cập nhật

## Cài đặt

| Hệ điều hành | Tệp | Ghi chú |
|---|---|---|
| Windows 10/11 | `TDCaro-vX.Y.Z-Windows.exe` | Chạy trực tiếp. Nếu SmartScreen cảnh báo: *More info → Run anyway* |
| macOS (M1/M2/M3…) | `TDCaro-vX.Y.Z-macOS-AppleSilicon.dmg` | Mở .dmg, kéo **TDCaro** vào Applications |
| macOS (Intel) | `TDCaro-vX.Y.Z-macOS-Intel.dmg` | như trên |

> **macOS:** ứng dụng chưa được ký bởi Apple, lần đầu mở hãy **chuột phải → Open**.
> Nếu báo "app is damaged", chạy: `xattr -cr "/Applications/TDCaro.app"`

## Phím tắt

| Phím | Chức năng |
|---|---|
| `Space` / `Enter` | Bắt đầu / ván mới |
| `←` `→` / cuộn chuột | Đổi kích thước bàn 5–20 (menu) |
| `D` | Đổi độ khó (menu) |
| `L` | Đổi luật: chặn 2 đầu / tự do (menu) |
| `F` | Đổi người đi trước (menu) |
| `U` / `Ctrl+Z` | Đi lại |
| `H` | Gợi ý |
| `T` | Đổi giao diện |
| `M` | Bật/tắt âm thanh |
| `R` | Đặt lại tỉ số |
| `B` | Bật/tắt nhạc nền |
| `K` | Chuyển bài nhạc |
| `F11` / `Alt+Enter` | Bật/tắt toàn màn hình |
| `Esc` | Về menu / thoát toàn màn hình / thoát |

## Các mức độ AI

| Mức | Thuật toán |
|---|---|
| **Dễ** | Thuật toán **gốc** của đồ án (`best_move` / `stupid_score`): tham lam 1 nước, chấm điểm tấn công + phòng thủ theo các cửa sổ 5 ô. |
| **Bình thường** | Vẫn dùng hàm chấm điểm gốc, thêm **luật ưu tiên** (thắng ngay › chặn 5 › tạo bốn mở › chặn ba mở), khai cuộc ở tâm và kiểm tra để không đi nước khiến đối thủ có chuỗi "bốn" ép thắng (VCF). |
| **Khó** | Đánh giá theo **mẫu hình** (năm, bốn mở, bốn, ba mở, ba, hai…), tìm chuỗi ép thắng **VCF**, lọc nước nguy hiểm, **Minimax + cắt tỉa Alpha-Beta** sâu ~6 nước với beam search. |
| **Cực khó** | Như Khó nhưng tìm VCF sâu hơn (cả của mình lẫn của người chơi), beam rộng hơn, **đào sâu dần** (iterative deepening) tới 12 nước, **bảng chuyển vị Zobrist**. Suy nghĩ ~2,2 giây/nước (Khó: ~0,8 giây). |

Mã nguồn AI gốc nằm nguyên vẹn trong [`src/Finals.py`](src/Finals.py); các mức mới nằm trong [`src/ai_engine_v2.py`](src/ai_engine_v2.py).

### So sánh sức mạnh (AI đấu AI, bàn 15×15)

| Trận (đổi lượt đi trước mỗi ván) | Số ván | Thắng | Thua | Hòa |
|---|:-:|:-:|:-:|:-:|
| Bình thường vs Dễ | 10 | 2 | 0 | 8 |
| Khó vs Dễ | 20 | 16 | 4 | 0 |
| Khó vs Bình thường | 20 | 16 | 4 | 0 |
| Cực khó vs Dễ | 20 | 17 | 2 | 1 |
| Cực khó vs Bình thường | 20 | 17 | 3 | 0 |
| **Cực khó vs Khó** | 20 | **13** | 7 | 0 |

> Caro luật tự do có lợi thế lớn cho người đi trước, nên ngay cả mức yếu hơn đôi khi vẫn thắng khi được đi trước.

Chạy lại: `python tools/benchmark.py 10 15`

## Chạy từ mã nguồn

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python src/Finals.py
```

Soạn lại nhạc nền (cần thêm `pip install numpy soundfile`, chỉ cho công cụ này): `python tools/make_music.py`

## Build

- **Windows:** chạy `packaging\build_exe.bat` → `dist/TDCaro.exe`
- **macOS:** `pyinstaller packaging/TDCaro_mac.spec` → `dist/TDCaro.app`
- **Web:** `pip install pygbag` rồi `python tools/build_web.py` → `build/web_app/build/web/` (thêm `--serve` để chạy thử ở http://localhost:8000)
- **Tự động:** push một tag dạng `v1.2.3` → GitHub Actions build `.exe` + `.dmg` đăng lên Releases, và build bản web đăng lên GitHub Pages.

## Chơi online

| Phần | Chi tiết |
|---|---|
| Server | [`server/server.js`](server/server.js) — Node.js + `ws`, giữ trạng thái ván (chống gian lận), kiểm tra lượt, luật chặn 2 đầu / tự do |
| Địa chỉ | `wss://vlxd.tail24e2ba.ts.net:10000` (VPS `vlxd`, thư mục `~/_gitclone/tdcaro`, dịch vụ `tdcaro.service`) |
| Client | [`src/online.py`](src/online.py) — máy tính dùng `websocket-client`, web dùng WebSocket của trình duyệt |
| Rớt mạng | Tự kết nối lại và về đúng phòng; quá 60 giây không quay lại thì xử thua |
| Chơi lại | Cả 2 bấm *Chơi lại* → ván mới, đổi người đi trước |

- Đổi server: biến môi trường `TDCARO_SERVER=wss://...` (máy tính) hoặc thêm `?server=wss://...` vào link (web).
- Chạy server ở máy: `cd server && npm install && npm start` (cổng 8388) · kiểm thử: `npm test`
- Cập nhật server trên VPS: `ssh vlxd 'sh ~/_gitclone/tdcaro/server/deploy.sh'`

## Cấu trúc

```
src/
  Finals.py           Giao diện pygame-ce + AI gốc (mức Dễ) — chạy file này
  ai_engine_v2.py     AI nâng cao (Bình thường / Khó / Cực khó)
  updater.py          Tự động cập nhật qua GitHub Releases
  online.py           Kết nối chơi online
  shortcuts.py        Tạo shortcut Desktop / Start Menu (Windows)
server/               Server phòng chơi online (Node.js + WebSocket) + test + systemd
web/                  Điểm vào + mẫu trang cho bản web (pygbag)
assets/               Icon, nhạc nền, phông chữ Be Vietnam Pro (OFL)
packaging/            Cấu hình PyInstaller (Windows / macOS) + build_exe.bat
tools/
  benchmark.py        Cho các mức AI đấu nhau
  set_version.py      Ghi số phiên bản (dùng trong CI)
  build_web.py        Build bản web
  make_music.py       Soạn nhạc nền
.github/workflows/    CI build & release (.exe + .dmg) và bản web (GitHub Pages)
```
