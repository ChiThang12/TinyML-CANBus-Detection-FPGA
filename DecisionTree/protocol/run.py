import serial
import time

# ============================================================================
# NHẬP GIÁ TRỊ CỦA BẠN TẠI ĐÂY
# ============================================================================
arb_id_dec  = 0    # 11-bit: 0 đến 2047
data_length = 16   # 5-bit:  0 đến 31 (CHANGED from 4-bit)
first_byte  = 0    # 8-bit:  0 đến 255
last_byte   = 0   # 8-bit:  0 đến 255
byte_sum    = 0    # 11-bit: 0 đến 2047
time_delta  = 0      # 32-bit: microseconds

COM_PORT    = 'COM6'
BAUD_RATE   = 115200

def pack_features(arb_id, data_len, first, last, sum_bytes, time_us):
    """
    Đóng gói 6 features thành 11 bytes
    Format:
      [0]    : arb_id[10:8]  (3 bits, padded to byte)
      [1]    : arb_id[7:0]   (8 bits)
      [2]    : data_len[4:0] (5 bits, padded to byte) - CHANGED
      [3]    : first_byte    (8 bits)
      [4]    : last_byte     (8 bits)
      [5]    : sum[10:8]     (3 bits, padded to byte)
      [6]    : sum[7:0]      (8 bits)
      [7-10] : time_delta    (32 bits, big-endian)
    """
    # Validate inputs
    assert 0 <= arb_id <= 2047, "arb_id must be 11-bit (0-2047)"
    assert 0 <= data_len <= 31, "data_length must be 5-bit (0-31)"  # CHANGED
    assert 0 <= first <= 255, "first_byte must be 8-bit (0-255)"
    assert 0 <= last <= 255, "last_byte must be 8-bit (0-255)"
    assert 0 <= sum_bytes <= 2047, "byte_sum must be 11-bit (0-2047)"
    assert 0 <= time_us <= 0xFFFFFFFF, "time_delta must be 32-bit"
    
    data = bytearray(11)
    
    # Bytes 0-1: arb_id_dec (11-bit)
    data[0] = (arb_id >> 8) & 0x07  # Only 3 bits: [10:8]
    data[1] = arb_id & 0xFF         # 8 bits: [7:0]
    
    # Byte 2: data_length (5-bit) - CHANGED
    data[2] = data_len & 0x1F       # Only 5 bits: [4:0]
    
    # Byte 3: first_byte (8-bit)
    data[3] = first & 0xFF
    
    # Byte 4: last_byte (8-bit)
    data[4] = last & 0xFF
    
    # Bytes 5-6: byte_sum (11-bit)
    data[5] = (sum_bytes >> 8) & 0x07  # Only 3 bits: [10:8]
    data[6] = sum_bytes & 0xFF         # 8 bits: [7:0]
    
    # Bytes 7-10: time_delta (32-bit, big-endian)
    data[7] = (time_us >> 24) & 0xFF
    data[8] = (time_us >> 16) & 0xFF
    data[9] = (time_us >> 8) & 0xFF
    data[10] = time_us & 0xFF
    
    return bytes(data)

# ============================================================================
# ĐÓNG GÓI DỮ LIỆU
# ============================================================================
try:
    data_bytes = pack_features(arb_id_dec, data_length, first_byte, 
                               last_byte, byte_sum, time_delta)
except AssertionError as e:
    print(f"\n❌ LỖI VALIDATION: {e}\n")
    exit(1)

# ============================================================================
# HIỂN THỊ THÔNG TIN
# ============================================================================
print("\n" + "="*70)
print(" UART FEATURE SENDER - 11 Bytes (5-bit data_length)")
print("="*70)
print("\n📊 Giá trị đầu vào:")
print(f"  arb_id_dec  = {arb_id_dec:4d}  (0x{arb_id_dec:03X})  [11-bit]")
print(f"  data_length = {data_length:4d}  (0x{data_length:02X})  [5-bit]")  # CHANGED
print(f"  first_byte  = {first_byte:4d}  (0x{first_byte:02X})  [8-bit]")
print(f"  last_byte   = {last_byte:4d}  (0x{last_byte:02X})  [8-bit]")
print(f"  byte_sum    = {byte_sum:4d}  (0x{byte_sum:03X})  [11-bit]")
print(f"  time_delta  = {time_delta:4d}  (0x{time_delta:08X}) [32-bit]")

print("\n📦 Dữ liệu gửi đi (Hex):")
print("  " + " ".join(f"{b:02X}" for b in data_bytes))

print("\n🔍 Chi tiết từng byte:")
descriptions = [
    "arb_id[10:8] (3-bit)",
    "arb_id[7:0]",
    "data_length[4:0] (5-bit)",  # CHANGED
    "first_byte",
    "last_byte",
    "byte_sum[10:8] (3-bit)",
    "byte_sum[7:0]",
    "time_delta[31:24]",
    "time_delta[23:16]",
    "time_delta[15:8]",
    "time_delta[7:0]"
]

for i, b in enumerate(data_bytes):
    print(f"  Byte[{i:2d}] = 0x{b:02X}  ({descriptions[i]})")

# ============================================================================
# GỬI QUA UART
# ============================================================================
try:
    print(f"\n{'='*70}")
    print(f"🔌 Đang mở {COM_PORT} @ {BAUD_RATE} baud...")
    
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
    time.sleep(0.1)
    
    print("\n[STEP 1] 📤 Gửi START marker...")
    ser.write(b'START\n')
    time.sleep(0.05)
    
    print(f"[STEP 2] 📤 Gửi {len(data_bytes)} bytes dữ liệu...")
    ser.write(data_bytes)
    time.sleep(0.1)
    
    print("\n✅ GỬI THÀNH CÔNG!")
    print(f"⏱️  Tổng thời gian truyền ≈ {len(data_bytes) * 10 * 1000 / BAUD_RATE:.2f}ms")
    print("="*70 + "\n")
    
    ser.close()

except serial.SerialException as e:
    print(f"\n❌ LỖI SERIAL: {e}")
    print(f"💡 Kiểm tra: {COM_PORT} có đúng không? Port có đang mở không?\n")

except Exception as e:
    print(f"\n❌ LỖI: {e}\n")