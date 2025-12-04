"""
Test Model CAN Bus Attack Detection - IMPROVED VERSION
So sánh dễ dàng với Verilog implementation
Input: 3 features gốc (arbitration_id, data_field, timestamp)
Output: Prediction + Chi tiết features để debug
"""

import pickle
import numpy as np
import pandas as pd
from typing import Union, Dict, Tuple
import json

class CANAttackDetector:
    def __init__(self, model_path='decision_tree_model.pkl'):
        """Load trained model"""
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        print(f"✅ Đã load model từ {model_path}")
        
        # Lưu timestamp trước để tính time_delta
        self.last_timestamp = None
        
    def extract_features(self, arbitration_id: str, data_field: str, timestamp: float = None) -> Dict:
        """
        Chuyển đổi 3 features gốc thành 6 features cho model
        ĐỒNG BỘ 100% với logic Verilog
        
        Args:
            arbitration_id: Hex string (vd: "0x123" hoặc "123")
            data_field: Hex string data (vd: "0102030405060708")
            timestamp: Unix timestamp (seconds)
            
        Returns:
            dict: 6 features + metadata để so sánh
        """
        features = {}
        
        # 1. arb_id_dec: Convert hex arbitration ID to decimal
        if isinstance(arbitration_id, str):
            arb_id_clean = arbitration_id.replace('0x', '').replace('0X', '').strip()
            features['arb_id_dec'] = int(arb_id_clean, 16)
        else:
            features['arb_id_dec'] = int(arbitration_id)
        
        # 2. data_length: Độ dài data field (ký tự hex, không phải bytes)
        data_str = str(data_field).replace('0x', '').replace('0X', '').replace(' ', '').strip()
        features['data_length'] = len(data_str)
        
        # 3. first_byte: Byte đầu tiên (2 ký tự hex đầu)
        if len(data_str) >= 2:
            features['first_byte'] = int(data_str[:2], 16)
        else:
            features['first_byte'] = 0
        
        # 4. last_byte: Byte cuối cùng (2 ký tự hex cuối)
        if len(data_str) >= 2:
            features['last_byte'] = int(data_str[-2:], 16)
        else:
            features['last_byte'] = 0
        
        # 5. byte_sum: Tổng tất cả bytes (checksum đơn giản)
        byte_sum = 0
        try:
            for i in range(0, len(data_str), 2):
                if i+2 <= len(data_str):
                    byte_sum += int(data_str[i:i+2], 16)
        except:
            byte_sum = 0
        features['byte_sum'] = byte_sum
        
        # 6. time_delta: Thời gian từ message trước (giây)
        # CRITICAL: Phải đảm bảo >= 0 để tránh lỗi Verilog syntax
        if timestamp is not None:
            if self.last_timestamp is not None:
                time_delta = timestamp - self.last_timestamp
                # Đảm bảo không âm (timestamps có thể không sorted)
                time_delta = max(time_delta, 0.0)
                # Cap at 1 second
                features['time_delta'] = min(time_delta, 1.0)
            else:
                features['time_delta'] = 0.0
            self.last_timestamp = timestamp
        else:
            features['time_delta'] = 0.0
        
        # Thêm metadata để debug/compare
        features['_metadata'] = {
            'raw_arb_id': arbitration_id,
            'raw_data': data_field,
            'raw_timestamp': timestamp,
            'data_str_length': len(data_str),
            'data_hex': data_str
        }
        
        return features
    
    def predict_single(self, arbitration_id: str, data_field: str, timestamp: float = None):
        """
        Dự đoán một message CAN
        
        Returns:
            tuple: (prediction, probability, features_dict)
        """
        # Extract features
        features = self.extract_features(arbitration_id, data_field, timestamp)
        
        # Tách metadata
        metadata = features.pop('_metadata', {})
        
        # Tạo DataFrame với đúng thứ tự columns
        feature_order = ['arb_id_dec', 'data_length', 'first_byte', 'last_byte', 'byte_sum', 'time_delta']
        X = pd.DataFrame([features])[feature_order]
        
        # Predict
        prediction = self.model.predict(X)[0]
        probability = self.model.predict_proba(X)[0]
        
        # Restore metadata
        features['_metadata'] = metadata
        
        return prediction, probability, features
    
    def predict_batch(self, messages: list):
        """
        Dự đoán nhiều messages
        
        Args:
            messages: List of tuples [(arb_id, data_field, timestamp), ...]
            
        Returns:
            list: Predictions
        """
        results = []
        for msg in messages:
            arb_id, data_field = msg[0], msg[1]
            timestamp = msg[2] if len(msg) > 2 else None
            
            pred, prob, features = self.predict_single(arb_id, data_field, timestamp)
            results.append({
                'arbitration_id': arb_id,
                'data_field': data_field,
                'prediction': int(pred),
                'label': 'Attack' if pred == 1 else 'Normal',
                'confidence': float(prob[int(pred)]),
                'features': features
            })
        
        return results
    
    def reset_timestamp(self):
        """Reset timestamp tracking"""
        self.last_timestamp = None


def print_comparison_table(results: list):
    """
    In bảng so sánh dạng table, dễ compare với Verilog testbench output
    """
    print("\n" + "=" * 120)
    print("📊 COMPARISON TABLE - SO SÁNH VỚI VERILOG OUTPUT")
    print("=" * 120)
    
    # Header
    header = f"{'No':<4} {'Arb_ID':>7} {'Data_Field':<18} {'Timestamp':<18} " \
             f"{'arb_id':>6} {'len':>4} {'1st':>4} {'last':>4} {'sum':>5} " \
             f"{'t_delta':>10} {'Pred':>6} {'Conf':>7}"
    print(header)
    print("-" * 120)
    
    # Rows
    for i, r in enumerate(results, 1):
        feat = r['features']
        meta = feat.get('_metadata', {})
        
        row = f"{i:<4} {r['arbitration_id']:>7} {r['data_field']:<18} {meta.get('raw_timestamp', 0):<18.7f} " \
              f"{feat['arb_id_dec']:>6} {feat['data_length']:>4} " \
              f"{feat['first_byte']:>4} {feat['last_byte']:>4} {feat['byte_sum']:>5} " \
              f"{feat['time_delta']:>10.6f} {r['label']:>6} {r['confidence']:>6.1%}"
        print(row)
    
    print("=" * 120)


def print_verilog_testbench_format(results: list, random_delay: bool = True, 
                                  delay_range: tuple = (50, 200),
                                  time_unit: str = 'clk'):
    """
    In ra format giống Verilog testbench để dễ copy-paste
    
    Args:
        results: List of test results
        random_delay: Nếu True, thêm delay ngẫu nhiên giữa các test
        delay_range: (min, max) delay range
        time_unit: 'clk' (clock cycles) hoặc 'ns' (nanoseconds)
    """
    import random
    
    print("\n" + "=" * 100)
    print("🔧 VERILOG TESTBENCH FORMAT")
    if random_delay:
        print(f"    (với delay ngẫu nhiên {delay_range[0]}-{delay_range[1]} {time_unit} giữa các test)")
    print("=" * 100)
    print("// Test cases - Copy to Verilog testbench")
    print()
    
    for i, r in enumerate(results, 1):
        feat = r['features']
        meta = feat.get('_metadata', {})
        
        print(f"// ========== Test case {i}: {r['label']} ==========")
        print(f"arb_id_dec  = 11'd{feat['arb_id_dec']};")
        print(f"data_length = 4'd{feat['data_length']};")
        print(f"first_byte  = 8'd{feat['first_byte']};")
        print(f"last_byte   = 8'd{feat['last_byte']};")
        print(f"byte_sum    = 11'd{feat['byte_sum']};")
        
        # Convert time_delta to microseconds for Verilog
        time_us = int(abs(feat['time_delta']) * 1_000_000)
        time_us = min(time_us, 1_000_000)  # Cap at 1 second = 1,000,000 us
        print(f"time_delta  = 32'd{time_us}; // {feat['time_delta']:.6f} seconds")
        print(f"start = 1;")
        print(f"@(posedge clk);")
        print(f"start = 0;")
        print(f"wait(done);")
        print(f"// Expected: {r['label']} (confidence: {r['confidence']:.1%})")
        print(f"// Check: is_attack should be {1 if r['label']=='Attack' else 0}")
        print(f"$display(\"Test {i}: Node=%d, Attack=%b (Expected: {r['label']})\", final_node, is_attack);")
        
        # Thêm delay ngẫu nhiên (trừ test cuối cùng)
        if random_delay and i < len(results):
            delay = random.randint(delay_range[0], delay_range[1])
            
            if time_unit == 'clk':
                # Delay theo clock cycles
                print(f"repeat({delay}) @(posedge clk); // Random delay: {delay} clock cycles")
            elif time_unit == 'ns':
                # Delay theo nanoseconds
                print(f"#{delay}; // Random delay: {delay} ns")
            else:
                # Default: absolute time delay
                print(f"#{delay}; // Random delay: {delay} time units")
        
        print()
    
    print("=" * 100)
    
    # Thêm hướng dẫn sử dụng
    print("\n💡 USAGE INSTRUCTIONS:")
    print("   1. Copy toàn bộ code trên")
    print("   2. Paste vào initial block của testbench")
    print("   3. Chạy simulation: vsim -do \"run -all\"")
    print("   4. So sánh output với Python predictions")
    if random_delay:
        print(f"   5. Delay ngẫu nhiên {delay_range[0]}-{delay_range[1]} {time_unit} giữa mỗi test")
        print("      → Giúp test timing robustness của design")


def export_to_json(results: list, filename: str = "test_results.json"):
    """Export kết quả ra JSON để compare"""
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Đã export kết quả ra {filename}")


def test_standard_cases():
    """Test với các test cases chuẩn từ dataset"""
    print("=" * 100)
    print("TEST CAN BUS ATTACK DETECTION MODEL - STANDARD TEST CASES")
    print("=" * 100)
    
    detector = CANAttackDetector('decision_tree_model.pkl')
    
    # Test cases từ dataset thực tế
    test_messages = [
        # (arbitration_id, data_field, timestamp, expected_label)
        ("34C", "F2820F5003EA0FA0", 1672531205.7830172, "Normal"),
        ("000", "0000000000000000", 1672531205.783651, "Attack"),
        ("000", "0000000000000000", 1672531205.785138, "Attack"),
        ("0C7", "039B3777", 1672531205.7851431, "Normal"),
        ("000", "0000000000000000", 1672531205.785746, "Attack"),
        ("1FE", "067E7F0200008154", 1672531205.7862232, "Normal"),
        ("362", "00000000", 1672531205.786227, "Normal"),
        ("000", "0000000000000000", 1672531205.786359, "Attack"),
        ("0F1", "000500400000", 1672531205.787298, "Normal"),
        ("0AA", "2BDE2BFB42540400", 1672531205.787308, "Normal"),
    ]
    
    results = []
    correct = 0
    total = len(test_messages)
    
    print("\n📝 Đang xử lý test cases...")
    
    for arb_id, data, ts, expected in test_messages:
        pred, prob, features = detector.predict_single(arb_id, data, ts)
        
        predicted_label = 'Attack' if pred == 1 else 'Normal'
        is_correct = (predicted_label == expected)
        if is_correct:
            correct += 1
        
        results.append({
            'arbitration_id': arb_id,
            'data_field': data,
            'prediction': int(pred),
            'label': predicted_label,
            'confidence': float(prob[int(pred)]),
            'expected': expected,
            'correct': is_correct,
            'features': features
        })
    
    # Print results
    print_comparison_table(results)
    
    # Accuracy
    accuracy = correct / total
    print(f"\n📈 ACCURACY: {correct}/{total} = {accuracy:.1%}")
    
    # Print Verilog format with options
    print("\n" + "="*100)
    print("📋 VERILOG TESTBENCH OPTIONS")
    print("="*100)
    print("Chọn format output:")
    print("  1. Random delay (clock cycles) - Default")
    print("  2. Random delay (nanoseconds)")
    print("  3. Fixed delay")
    print("  4. No delay")
    
    # Option 1: Random delay với clock cycles (recommended)
    print("\n" + "="*100)
    print("📌 OPTION 1: RANDOM DELAY (CLOCK CYCLES) - RECOMMENDED")
    print("="*100)
    print_verilog_testbench_format(results, random_delay=True, 
                                  delay_range=(50, 200), time_unit='clk')
    
    # Option 2: Random delay với nanoseconds
    print("\n" + "="*100)
    print("📌 OPTION 2: RANDOM DELAY (NANOSECONDS)")
    print("="*100)
    print_verilog_testbench_format(results, random_delay=True, 
                                  delay_range=(100, 500), time_unit='ns')
    
    # Option 3: No delay (nhanh nhất)
    print("\n" + "="*100)
    print("📌 OPTION 3: NO DELAY (FASTEST)")
    print("="*100)
    print_verilog_testbench_format(results, random_delay=False)
    
    # Export to JSON
    export_to_json(results)
    
    return detector, results


def detailed_feature_inspection(detector, arb_id, data_field, timestamp=None):
    """
    Kiểm tra chi tiết từng feature - để debug so sánh với Verilog
    """
    print("\n" + "=" * 100)
    print("🔍 DETAILED FEATURE INSPECTION")
    print("=" * 100)
    
    pred, prob, features = detector.predict_single(arb_id, data_field, timestamp)
    meta = features.get('_metadata', {})
    
    print(f"\n📥 INPUT:")
    print(f"   Arbitration ID : {arb_id}")
    print(f"   Data Field     : {data_field}")
    print(f"   Timestamp      : {timestamp}")
    
    print(f"\n🔄 FEATURE EXTRACTION:")
    print(f"   1. arb_id_dec  = {features['arb_id_dec']:<6} (0x{features['arb_id_dec']:03X} = decimal {features['arb_id_dec']})")
    print(f"   2. data_length = {features['data_length']:<6} (hex string length)")
    print(f"   3. first_byte  = {features['first_byte']:<6} (0x{features['first_byte']:02X} = decimal {features['first_byte']})")
    print(f"   4. last_byte   = {features['last_byte']:<6} (0x{features['last_byte']:02X} = decimal {features['last_byte']})")
    print(f"   5. byte_sum    = {features['byte_sum']:<6} (sum of all bytes)")
    print(f"   6. time_delta  = {features['time_delta']:.9f} seconds")
    
    print(f"\n📊 PREDICTION:")
    print(f"   Result         : {'🚨 ATTACK' if pred == 1 else '✅ NORMAL'}")
    print(f"   Confidence     : {prob[int(pred)]:.4f} ({prob[int(pred)]:.2%})")
    print(f"   Probabilities  : [Normal: {prob[0]:.4f}, Attack: {prob[1]:.4f}]")
    
    # Verilog equivalent
    print(f"\n🔧 VERILOG EQUIVALENT:")
    time_us = int(features['time_delta'] * 1_000_000)
    print(f"   arb_id_dec  = 11'd{features['arb_id_dec']};")
    print(f"   data_length = 4'd{features['data_length']};")
    print(f"   first_byte  = 8'd{features['first_byte']};")
    print(f"   last_byte   = 8'd{features['last_byte']};")
    print(f"   byte_sum    = 11'd{features['byte_sum']};")
    print(f"   time_delta  = 32'd{time_us}; // microseconds")
    
    print("=" * 100)


def compare_with_verilog_output(python_results: list, verilog_output_file: str):
    """
    So sánh kết quả Python với Verilog output
    
    Args:
        python_results: List of dicts from test_standard_cases()
        verilog_output_file: Path to Verilog simulation output
    """
    print("\n" + "=" * 100)
    print("⚖️  PYTHON vs VERILOG COMPARISON")
    print("=" * 100)
    
    # TODO: Parse verilog output file and compare
    # Format expected: Test X: Node=Y, Attack=Z
    
    print("\n📝 Python results ready for comparison")
    print("💡 Copy Verilog testbench output here to compare")
    print("\nPython predictions:")
    for i, r in enumerate(python_results, 1):
        print(f"Test {i}: Prediction={r['label']}, Confidence={r['confidence']:.2%}")


if __name__ == "__main__":
    import random
    
    # Run standard tests
    print("\n🚀 Starting tests...\n")
    detector, results = test_standard_cases()
    
    # Random inspection: Chọn ngẫu nhiên 1 trong 10 test cases
    print("\n" + "="*100)
    print("📋 RANDOM DETAILED INSPECTION")
    print("="*100)
    
    # Lấy random 1 result từ 10 test cases
    random_result = random.choice(results)
    random_features = random_result['features']
    random_meta = random_features.get('_metadata', {})
    
    print(f"\n🎲 Đã chọn ngẫu nhiên: Test case với Arb_ID = {random_result['arbitration_id']}")
    
    detailed_feature_inspection(
        detector,
        arb_id=random_meta.get('raw_arb_id', random_result['arbitration_id']),
        data_field=random_meta.get('raw_data', random_result['data_field']),
        timestamp=random_meta.get('raw_timestamp')
    )
    
    print("\n✅ All tests completed!")
    print("\n💡 TIP: So sánh bảng trên với Verilog testbench output")
    print("    - Copy các số từ 'VERILOG TESTBENCH FORMAT' vào testbench")
    print("    - Chạy simulation và so sánh prediction")
    print("    - Mỗi lần chạy sẽ inspect ngẫu nhiên 1 test case khác nhau 🎲")