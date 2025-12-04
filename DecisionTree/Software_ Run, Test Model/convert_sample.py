"""
CAN Bus Feature Converter: 3 Features → 6 Features
Chuyển đổi dữ liệu CAN thô thành features cho ML model hoặc FPGA

Input:  3 features (arbitration_id, data_field, timestamp)
Output: 6 features (arb_id_dec, data_length, first_byte, last_byte, byte_sum, time_delta)

Sử dụng:
    python feature_converter.py input.csv output.csv
    hoặc import trong Python code
"""

import pandas as pd
import numpy as np
import sys
from typing import Union, List, Dict


class CANFeatureConverter:
    """
    Chuyển đổi CAN bus raw data thành engineered features
    Đồng bộ 100% với Verilog logic
    """
    
    def __init__(self):
        self.last_timestamp = None
        
    def convert_single(self, arbitration_id: Union[str, int], 
                      data_field: str, 
                      timestamp: float = None) -> Dict:
        """
        Convert 1 CAN message: 3 features → 6 features
        
        Args:
            arbitration_id: Hex string ("0x123" hoặc "123") hoặc integer
            data_field: Hex data string ("0102030405060708")
            timestamp: Unix timestamp (seconds) - optional
            
        Returns:
            dict với 6 features
        """
        features = {}
        
        # ====================================================================
        # FEATURE 1: arb_id_dec
        # Chuyển arbitration ID từ hex sang decimal
        # ====================================================================
        if isinstance(arbitration_id, str):
            # Remove "0x" prefix nếu có
            arb_id_clean = arbitration_id.replace('0x', '').replace('0X', '').strip()
            features['arb_id_dec'] = int(arb_id_clean, 16)
        else:
            features['arb_id_dec'] = int(arbitration_id)
        
        # ====================================================================
        # FEATURE 2: data_length
        # Độ dài của data field (số ký tự hex, không phải số bytes)
        # ====================================================================
        data_str = str(data_field).replace('0x', '').replace('0X', '').replace(' ', '').strip()
        features['data_length'] = len(data_str)
        
        # ====================================================================
        # FEATURE 3: first_byte
        # Byte đầu tiên (2 ký tự hex đầu tiên)
        # ====================================================================
        if len(data_str) >= 2:
            features['first_byte'] = int(data_str[:2], 16)
        else:
            features['first_byte'] = 0
        
        # ====================================================================
        # FEATURE 4: last_byte
        # Byte cuối cùng (2 ký tự hex cuối cùng)
        # ====================================================================
        if len(data_str) >= 2:
            features['last_byte'] = int(data_str[-2:], 16)
        else:
            features['last_byte'] = 0
        
        # ====================================================================
        # FEATURE 5: byte_sum
        # Tổng tất cả các bytes (checksum đơn giản)
        # Ví dụ: "0102" → 0x01 + 0x02 = 1 + 2 = 3
        # ====================================================================
        byte_sum = 0
        try:
            # Duyệt qua từng cặp ký tự hex (1 byte = 2 hex chars)
            for i in range(0, len(data_str), 2):
                if i + 2 <= len(data_str):
                    byte_val = int(data_str[i:i+2], 16)
                    byte_sum += byte_val
        except ValueError:
            byte_sum = 0  # Nếu không parse được, set = 0
        
        features['byte_sum'] = byte_sum
        
        # ====================================================================
        # FEATURE 6: time_delta
        # Khoảng thời gian giữa message hiện tại và message trước (giây)
        # IMPORTANT: Phải đảm bảo >= 0 để tránh lỗi trong Verilog
        # Cap tối đa ở 1 giây để tránh outlier
        # ====================================================================
        if timestamp is not None:
            if self.last_timestamp is not None:
                time_delta = timestamp - self.last_timestamp
                # Đảm bảo không âm (có thể xảy ra nếu timestamps không sorted)
                time_delta = max(time_delta, 0.0)
                # Cap at 1 second
                features['time_delta'] = min(time_delta, 1.0)
            else:
                features['time_delta'] = 0.0  # First message
            
            self.last_timestamp = timestamp
        else:
            features['time_delta'] = 0.0
        
        return features
    
    def convert_dataframe(self, df: pd.DataFrame, 
                         arb_id_col: str = 'arbitration_id',
                         data_col: str = 'data_field', 
                         timestamp_col: str = 'timestamp') -> pd.DataFrame:
        """
        Convert toàn bộ DataFrame
        
        Args:
            df: Input DataFrame với 3 columns gốc
            arb_id_col: Tên column chứa arbitration_id
            data_col: Tên column chứa data_field
            timestamp_col: Tên column chứa timestamp (optional)
            
        Returns:
            DataFrame mới với 6 features được thêm vào
        """
        df_result = df.copy()
        
        # Reset timestamp tracking
        self.last_timestamp = None
        
        # Check if columns exist
        required_cols = [arb_id_col, data_col]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in DataFrame")
        
        has_timestamp = timestamp_col in df.columns
        
        # Convert từng row
        features_list = []
        for idx, row in df.iterrows():
            arb_id = row[arb_id_col]
            data = row[data_col]
            ts = row[timestamp_col] if has_timestamp else None
            
            features = self.convert_single(arb_id, data, ts)
            features_list.append(features)
        
        # Thêm 6 features vào DataFrame
        features_df = pd.DataFrame(features_list)
        for col in features_df.columns:
            df_result[col] = features_df[col]
        
        return df_result
    
    def reset(self):
        """Reset internal state (timestamp tracking)"""
        self.last_timestamp = None
    
    def validate_features(self, features: Dict) -> bool:
        """
        Validate features ranges (để đảm bảo phù hợp với FPGA constraints)
        
        Returns:
            True nếu valid, False nếu out of range
        """
        checks = [
            ('arb_id_dec', 0, 2047, 11),      # 11-bit CAN ID
            ('data_length', 0, 16, 4),         # Max 16 hex chars = 8 bytes
            ('first_byte', 0, 255, 8),         # 8-bit byte
            ('last_byte', 0, 255, 8),          # 8-bit byte
            ('byte_sum', 0, 2047, 11),         # Tối đa 8 bytes * 255 = 2040
            ('time_delta', 0, 1.0, 32),        # Cap at 1.0 second
        ]
        
        for feat_name, min_val, max_val, bits in checks:
            val = features.get(feat_name, 0)
            if not (min_val <= val <= max_val):
                print(f"⚠️  Warning: {feat_name} = {val} out of range [{min_val}, {max_val}]")
                return False
        
        return True


def convert_csv_file(input_file: str, output_file: str, 
                    arb_id_col: str = 'arbitration_id',
                    data_col: str = 'data_field',
                    timestamp_col: str = 'timestamp'):
    """
    Convert CSV file: thêm 6 features vào file gốc
    
    Args:
        input_file: Path to input CSV (có 3 columns gốc)
        output_file: Path to output CSV (sẽ có thêm 6 columns)
        arb_id_col: Column name for arbitration_id
        data_col: Column name for data_field
        timestamp_col: Column name for timestamp
    """
    print(f"📂 Đang đọc file: {input_file}")
    
    # Read CSV
    df = pd.read_csv(input_file)
    print(f"✅ Đã load {len(df)} rows")
    print(f"📋 Columns: {list(df.columns)}")
    
    # Convert
    converter = CANFeatureConverter()
    df_converted = converter.convert_dataframe(df, arb_id_col, data_col, timestamp_col)
    
    print(f"\n✅ Đã convert xong! Thêm 6 features:")
    new_cols = ['arb_id_dec', 'data_length', 'first_byte', 'last_byte', 'byte_sum', 'time_delta']
    for col in new_cols:
        print(f"   - {col}")
    
    # Save
    df_converted.to_csv(output_file, index=False)
    print(f"\n💾 Đã save kết quả vào: {output_file}")
    
    # Show sample
    print(f"\n📊 Mẫu dữ liệu (5 rows đầu):")
    display_cols = [arb_id_col, data_col] + new_cols
    if 'attack' in df_converted.columns:
        display_cols.append('attack')
    print(df_converted[display_cols].head())
    
    return df_converted


def print_usage():
    """Print usage instructions"""
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                   CAN BUS FEATURE CONVERTER                              ║
║                   3 Features → 6 Features                                ║
╚══════════════════════════════════════════════════════════════════════════╝

USAGE:
    python feature_converter.py <input.csv> <output.csv>

INPUT CSV FORMAT:
    Required columns:
    - arbitration_id  : CAN arbitration ID (hex string, e.g., "0x123" or "123")
    - data_field      : Data payload (hex string, e.g., "0102030405060708")
    - timestamp       : Unix timestamp in seconds (optional)

OUTPUT:
    CSV file with 6 additional columns:
    1. arb_id_dec   : Decimal arbitration ID
    2. data_length  : Length of data field
    3. first_byte   : First byte value
    4. last_byte    : Last byte value
    5. byte_sum     : Sum of all bytes
    6. time_delta   : Time since previous message

EXAMPLES:
    # Basic usage
    python feature_converter.py raw_data.csv features.csv
    
    # With custom column names
    from feature_converter import convert_csv_file
    convert_csv_file('data.csv', 'out.csv', 
                     arb_id_col='can_id', 
                     data_col='payload')

PYTHON API:
    from feature_converter import CANFeatureConverter
    
    converter = CANFeatureConverter()
    
    # Convert single message
    features = converter.convert_single("0x123", "0102030405060708", 1234567890.5)
    print(features)
    
    # Convert DataFrame
    df_features = converter.convert_dataframe(df)
    """)


def demo():
    """Demo usage của converter"""
    print("=" * 80)
    print("DEMO: CAN Feature Converter")
    print("=" * 80)
    
    converter = CANFeatureConverter()
    
    # Example messages
    test_cases = [
        ("34C", "F2820F5003EA0FA0", 1672531205.7830172),
        ("000", "0000000000000000", 1672531205.783651),
        ("0C7", "039B3777", 1672531205.7851431),
        ("1FE", "067E7F0200008154", 1672531205.7862232),
        ("0AA", "2BDE2BFB42540400", 1672531205.787308),
    ]
    
    print("\n📝 Converting test messages...\n")
    
    results = []
    for arb_id, data, ts in test_cases:
        features = converter.convert_single(arb_id, data, ts)
        
        # Validate
        is_valid = converter.validate_features(features)
        
        results.append({
            'input_arb_id': arb_id,
            'input_data': data,
            'input_ts': ts,
            **features,
            'valid': is_valid
        })
        
        print(f"🔹 Input:  arb_id={arb_id:>4}, data={data}")
        print(f"   Output: arb_id_dec={features['arb_id_dec']:<5} data_length={features['data_length']:<3} "
              f"first={features['first_byte']:<4} last={features['last_byte']:<4} "
              f"sum={features['byte_sum']:<5} delta={features['time_delta']:.6f}")
        print()
    
    # Convert to DataFrame
    df_results = pd.DataFrame(results)
    print("\n📊 Results DataFrame:")
    print(df_results[['input_arb_id', 'arb_id_dec', 'data_length', 'first_byte', 
                     'last_byte', 'byte_sum', 'time_delta', 'valid']])
    
    print("\n" + "=" * 80)
    print("✅ Demo completed!")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments - run demo
        demo()
        print("\n💡 For CSV conversion, use:")
        print("   python feature_converter.py input.csv output.csv")
        
    elif len(sys.argv) == 2 and sys.argv[1] in ['-h', '--help', 'help']:
        print_usage()
        
    elif len(sys.argv) == 3:
        # CSV conversion mode
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        
        try:
            convert_csv_file(input_file, output_file)
            print("\n✅ Conversion completed successfully!")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    else:
        print("❌ Invalid arguments!")
        print_usage()
        sys.exit(1)