# Báo cáo so sánh dữ liệu trạm thu phí

## Quy ước

- **A** = `tram_thu_phi.csv` của đồng nghiệp.
- **B** = `merged_toll_stations_final.csv` của mình.
- So sánh chính dựa trên **tọa độ** và **độ giống tên**.
- Một trạm được xem là khớp tốt nếu khoảng cách tọa độ giữa A và B **<= 120 m**.
- Trường hợp tên giống nhưng tọa độ xa được đưa vào nhóm **cần review**.

## Tổng quan kết quả

| Nhóm so sánh | Số lượng | Ý nghĩa |
|---|---:|---|
| Tổng trạm bên A | 105 | Dữ liệu đồng nghiệp cung cấp |
| Tổng trạm bên B | 99 | Dataset final hiện tại của mình |
| Khớp tốt theo tọa độ | 72 | Hai bên có cùng trạm, tọa độ gần nhau |
| Khớp theo tên, cần review tọa độ | 2 | Tên giống nhưng tọa độ cần kiểm tra lại |
| A có, B chưa có | 31 | Có thể là trạm mới/cần bổ sung vào dataset của mình |
| B có, A chưa có | 34 | Dataset của mình có thêm các trạm không có trong file đồng nghiệp |

## Nhận xét nhanh

- Hai bộ dữ liệu có phần giao nhau khá lớn: **72 trạm khớp tốt theo tọa độ**.
- File A có nhiều trường Google Maps trực tiếp như `google_maps_url`, `cid`, `google_name`, `address`.
- File B giàu thông tin pipeline hơn: có `id`, `source`, `confidence`, `osm_id`, `osm_name`, `final_status`, `tags`.
- Nhóm quan trọng nhất cần xem tiếp là **31 trạm A có nhưng B chưa có**, vì đây là nguồn bổ sung tiềm năng.
- Nhóm **34 trạm B có nhưng A chưa có** không nên xóa vội, vì nhiều trạm có thể đến từ VETC/ePass/manual/OSM hoặc nguồn crawl Google Maps trước đó.

## A có nhưng B chưa có

Đây là các trạm xuất hiện trong file đồng nghiệp nhưng chưa khớp với dataset final của mình theo ngưỡng tọa độ/tên.

| STT | Tên trạm bên A |
|---:|---|
| 1 | Trạm thu phí Thân Cửu Nghĩa |
| 2 | TRẠM THU PHÍ CAM THỊNH ( KHÁNH HÒA) |
| 3 | TRẠM THU PHÍ CAM RANH KM52 |
| 4 | TRẠM THU PHÍ CAM LÂM KM30 |
| 5 | TRẠM THU PHÍ DT741- BÌNH DƯƠNG |
| 6 | TRẠM THU PHÍ VĨNH PHÚ |
| 7 | TRẠM THU PHÍ HOÀNG MAI |
| 8 | TRẠM THU PHÍ QL279 ( BẮC GIANG LẠNG SƠN) |
| 9 | TRẠM THU PHÍ HÒA PHƯỚC |
| 10 | TRẠM THU PHÍ TAM NÔNG |
| 11 | TRẠM THU PHÍ AN SƯƠNG AN LẠC |
| 12 | Trạm thu phí Hải Hà |
| 13 | Trạm thu phí 279 BGLS |
| 14 | Trạm thu phí Cổ Chiên |
| 15 | Trạm thu phí Cai Chanh |
| 16 | Trạm thu phí Thuận Phú |
| 17 | Trạm thu phí Bù Nho |
| 18 | Trạm thu phí Thanh Lương |
| 19 | Trạm thu phí Tân Lập |
| 20 | Trạm thu phí BOT Thanh Nê |
| 21 | Trạm thu phí BOT Thanh Nê số 1 |
| 22 | Trạm Thu phí Cái Bè |
| 23 | Trạm thu phí QL 5B |
| 24 | Trạm Thu phí Quốc lộ 17B |
| 25 | Trạm Thu phí Sân bay Pleiku |
| 26 | Trạm Thu phí An Hiệp |
| 27 | Trạm Thu phí Diên Thọ |
| 28 | Trạm Thu Phí Đầm Hà |
| 29 | Trạm Thu phí Quốc lộ 37 |
| 30 | Trạm Thu phí Cầu Móng Sến |
| 31 | Trạm thu phí cao tốc bến lức - Long Thành (quốc lộ 51) |

**Đề xuất xử lý:** mở Google Maps hoặc kiểm tra tọa độ các trạm này. Nếu đúng là trạm thu phí thật, nên merge thêm vào dataset final.

## B có nhưng A chưa có

Đây là các trạm có trong dataset final của mình nhưng không khớp với file đồng nghiệp.

| STT | Tên trạm bên B |
|---:|---|
| 1 | Trạm Thu Phí BOT Quang Đức QL14 |
| 2 | Trạm Thu Phí Cao Tốc Hạ Long - Vân Đồn |
| 3 | Trạm Thu phí An Dân |
| 4 | Trạm Thu phí Phú Thọ (IC9) |
| 5 | Trạm Thu phí Bình Xuyên (IC3) |
| 6 | Trạm Thu phí Bắc Quảng Ngãi |
| 7 | Trạm Thu phí Cao Bồ |
| 8 | Trạm Thu phí Chu Lai |
| 9 | Trạm Thu phí Cầu Phú Hữu |
| 10 | Trạm Thu phí Cầu Phú Mỹ |
| 11 | Trạm Thu phí Cầu Thái Hà |
| 12 | Trạm Thu phí Hạ Hoà (IC11) |
| 13 | Trạm Thu phí Hồ Sơn |
| 14 | Trạm Thu phí Móng Cái |
| 15 | Trạm Thu phí Phong Thử |
| 16 | Trạm Thu phí Phù Ninh (IC8) |
| 17 | Trạm Thu phí Quán Hàu |
| 18 | Trạm Thu phí Quảng Ngãi |
| 19 | Trạm Thu phí Sông Lũy |
| 20 | Trạm Thu phí Thái Nguyên - Chợ Mới |
| 21 | Trạm Thu phí Túy Loan |
| 22 | Trạm Thu phí Việt Trì (IC7) |
| 23 | Trạm Thu phí Văn Quán (IC6) |
| 24 | Trạm Thu phí Ô Môn |
| 25 | Trạm Thu phí Điện Bàn |
| 26 | Trạm Thu phí Định An |
| 27 | Trạm Thu phí Đồng Lá |
| 28 | Trạm Thu phí Đồng Đăng |
| 29 | Trạm Thu phí Đức Hoà |
| 30 | Trạm thu phí BOT Biên Cương |
| 31 | Trạm thu phí cao tốc Hà Nội - Hải Phòng - Văn Giang |
| 32 | Trạm thu phí cao tốc Liên Khương - Prenn |
| 33 | Trạm thu phí hầm Hải Vân |
| 34 | Trạm thu phí Đông Xuân |

**Đề xuất xử lý:** không loại bỏ nhóm này ngay. Cần kiểm tra lại nguồn gốc từng điểm trong B, vì nhiều điểm có thể đúng nhưng không có trong file đồng nghiệp.

## Khớp theo tên nhưng cần review tọa độ

| STT | Tên bên A | Tên bên B | Khoảng cách | Điểm giống tên | Nhận xét |
|---:|---|---|---:|---:|---|
| 1 | Trạm thu phí Hòa Lạc – Hòa Bình | Trạm thu phí đường Hòa Lạc - Hòa Bình | 267.4 m | 0.865 | Đã kiểm tra: đây là cùng một trạm. Tên đúng nên dùng là `Trạm thu phí đường Hòa Lạc - Hòa Bình` |
| 2 | Trạm Thu phí Km 237 Cao tốc Hà Nội - Lào Cai | Trạm Thu phí Km 6 Cao tốc Hà Nội - Lào Cai | 211248.77 m | 0.929 | Đã kiểm tra: đây là hai trạm khác nhau, không merge. Tên giống do cùng tuyến cao tốc nhưng khác vị trí/km |

## So sánh thuộc tính dữ liệu

### Thuộc tính bên A

| Thuộc tính | Mức đầy đủ | Nhận xét |
|---|---:|---|
| `name` | 105/105 | Có đầy đủ tên trạm |
| `lat` | 105/105 | Có đầy đủ vĩ độ |
| `lng` | 105/105 | Có đầy đủ kinh độ |
| `address` | 105/105 | Có đầy đủ địa chỉ Google Maps |
| `google_maps_url` | 105/105 | Có đầy đủ link Google Maps |
| `place_id` | 43/105 | Chỉ có một phần |
| `cid` | 105/105 | Có đầy đủ CID |
| `google_name` | 105/105 | Có đầy đủ tên Google |
| `status` | 105/105 | Có đầy đủ trạng thái |

### Thuộc tính bên B

| Thuộc tính | Mức đầy đủ | Nhận xét |
|---|---:|---|
| `id` | 99/99 | Có ID nội bộ |
| `name` | 99/99 | Có tên final |
| `province` | 61/99 | Có một phần tỉnh/thành |
| `road` | 28/99 | Có một phần tuyến đường |
| `km_marker` | 0/99 | Chưa có mốc km |
| `type` | 99/99 | Có loại object |
| `operator` | 0/99 | Chưa có đơn vị vận hành |
| `status` | 99/99 | Có trạng thái |
| `lat` | 99/99 | Có đầy đủ vĩ độ |
| `lon` | 99/99 | Có đầy đủ kinh độ |
| `source` | 99/99 | Có nguồn dữ liệu |
| `confidence` | 99/99 | Có điểm tin cậy |
| `tags` | 99/99 | Có tag phục vụ OSM/Map |

## Khác biệt cột chính

| Nhóm | Cột |
|---|---|
| A có riêng | `address`, `google_maps_url`, `place_id`, `cid`, `google_name`, `lng` |
| B có riêng | `id`, `province`, `road`, `km_marker`, `type`, `operator`, `source`, `source_url`, `confidence`, `google_place_id`, `google_cid`, `category`, `formatted_address`, `osm_id`, `osm_name`, `osm_lat`, `osm_lon`, `osm_distance_m`, `final_status`, `review_action`, `review_comment`, `tags` |
| Cột tương đương | A.`lng` tương đương B.`lon`; A.`google_maps_url` tương đương B.`source_url`; A.`address` tương đương B.`formatted_address`; A.`cid` tương đương B.`google_cid`; A.`place_id` tương đương B.`google_place_id` |

## Kết luận đề xuất

1. Ưu tiên kiểm tra **31 trạm A có nhưng B chưa có** để xem có nên bổ sung vào dataset final không.
2. Giữ lại **34 trạm B có nhưng A chưa có** cho đến khi xác minh nguồn, không nên xóa vội.
3. Trường hợp Hòa Lạc - Hòa Bình được xác nhận là cùng một trạm, nên chuẩn hóa về tên `Trạm thu phí đường Hòa Lạc - Hòa Bình`.
4. Trường hợp Km237/Km6 cao tốc Hà Nội - Lào Cai được xác nhận là hai trạm khác nhau, không merge.
5. Nếu cần merge hai nguồn, nên lấy tọa độ/link Google từ A, nhưng giữ metadata pipeline/OSM/tags từ B.

## Nhận định áp dụng thực tế

Nếu xét riêng độ đầy đủ dữ liệu Google Maps, file **A** của đồng nghiệp có lợi thế hơn vì có đầy đủ `address`, `google_maps_url`, `cid`, `google_name` và tọa độ cho toàn bộ 105 trạm. File này phù hợp để xác minh vị trí trạm trên Google Maps và bổ sung thông tin tham chiếu.

Tuy nhiên, nếu xét để đưa vào hệ thống bản đồ thực tế, file **B** của mình phù hợp hơn làm dataset nền vì đã có cấu trúc phục vụ pipeline: `id`, `source`, `confidence`, `osm_id`, `osm_name`, `osm_distance_m`, `final_status` và `tags`. Các trường này cần thiết để lưu DB, hiển thị MapLibre, đối soát OSM và chuẩn bị merge vào PBF/MBTiles.

Hướng đề xuất là không chọn một bên rồi bỏ bên còn lại, mà nên:

1. Lấy **B** làm dataset nền vì đã phù hợp với pipeline bản đồ.
2. Dùng **A** để bổ sung các trạm còn thiếu, đặc biệt nhóm **31 trạm A có nhưng B chưa có**.
3. Dùng thông tin Google Maps từ **A** để làm giàu dữ liệu trong **B**, như địa chỉ, link Google Maps, CID và tên Google.
4. Sau khi review các điểm bổ sung từ A, sinh lại dataset final rồi lưu DB/GeoJSON/MapLibre.

Kết luận ngắn: **B nên là bộ dữ liệu chính để triển khai thực tế, A nên là nguồn bổ sung và xác minh.**
