"""
Test Random Forest CAN Bus Attack Detection - WITH HARDWARE TIMING COMPARISON
So sánh performance giữa Python software và Verilog hardware
"""

import pickle
import numpy as np
import pandas as pd
from typing import Union, Dict, Tuple, List
import json
import time
from statistics import mean, stdev, median

class CANAttackDetectorRF:
    def __init__(self, model_path='random_forest_model.pkl'):
        """Load trained Random Forest model"""
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        self.n_trees = len(self.model.estimators_)
        print(f"✅ Đã load Random Forest model từ {model_path}")
        print(f"   - Số lượng trees: {self.n_trees}")
        print(f"   - Model type: {type(self.model).__name__}")
        
        self.last_timestamp = None
        
        # Timing statistics
        self.timing_stats = {
            'feature_extraction': [],
            'prediction': [],
            'total': []
        }
        
    def extract_features(self, arbitration_id: str, data_field: str, timestamp: float = None) -> Dict:
        """Extract features với timing measurement"""
        features = {}
        
        # 1. arb_id_dec
        if isinstance(arbitration_id, str):
            arb_id_clean = arbitration_id.replace('0x', '').replace('0X', '').strip()
            features['arb_id_dec'] = int(arb_id_clean, 16)
        else:
            features['arb_id_dec'] = int(arbitration_id)
        
        # 2. data_length
        data_str = str(data_field).replace('0x', '').replace('0X', '').replace(' ', '').strip()
        features['data_length'] = len(data_str)
        
        # 3. first_byte
        if len(data_str) >= 2:
            features['first_byte'] = int(data_str[:2], 16)
        else:
            features['first_byte'] = 0
        
        # 4. last_byte
        if len(data_str) >= 2:
            features['last_byte'] = int(data_str[-2:], 16)
        else:
            features['last_byte'] = 0
        
        # 5. byte_sum
        byte_sum = 0
        try:
            for i in range(0, len(data_str), 2):
                if i+2 <= len(data_str):
                    byte_sum += int(data_str[i:i+2], 16)
        except:
            byte_sum = 0
        features['byte_sum'] = byte_sum
        
        # 6. time_delta
        if timestamp is not None:
            if self.last_timestamp is not None:
                time_delta = timestamp - self.last_timestamp
                time_delta = max(time_delta, 0.0)
                features['time_delta'] = min(time_delta, 1.0)
            else:
                features['time_delta'] = 0.0
            self.last_timestamp = timestamp
        else:
            features['time_delta'] = 0.0
        
        features['_metadata'] = {
            'raw_arb_id': arbitration_id,
            'raw_data': data_field,
            'raw_timestamp': timestamp,
            'data_str_length': len(data_str),
            'data_hex': data_str
        }
        
        return features
    
    def get_tree_predictions(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Lấy prediction từ từng cây"""
        tree_predictions = np.array([tree.predict(X)[0] for tree in self.model.estimators_])
        tree_probas = np.array([tree.predict_proba(X)[0] for tree in self.model.estimators_])
        return tree_predictions, tree_probas
    
    def predict_single(self, arbitration_id: str, data_field: str, timestamp: float = None):
        """Dự đoán với timing measurement"""
        
        # ⏱️ Timing: Feature extraction
        t_start_extract = time.perf_counter()
        features = self.extract_features(arbitration_id, data_field, timestamp)
        t_extract = time.perf_counter() - t_start_extract
        
        metadata = features.pop('_metadata', {})
        feature_order = ['arb_id_dec', 'data_length', 'first_byte', 'last_byte', 'byte_sum', 'time_delta']
        X = pd.DataFrame([features])[feature_order]
        
        # ⏱️ Timing: Prediction
        t_start_pred = time.perf_counter()
        prediction = self.model.predict(X)[0]
        probability = self.model.predict_proba(X)[0]
        tree_predictions, tree_probas = self.get_tree_predictions(X)
        t_pred = time.perf_counter() - t_start_pred
        
        # Total time
        t_total = t_extract + t_pred
        
        # Save timing stats
        self.timing_stats['feature_extraction'].append(t_extract)
        self.timing_stats['prediction'].append(t_pred)
        self.timing_stats['total'].append(t_total)
        
        # Vote breakdown
        attack_votes = int(np.sum(tree_predictions == 1))
        normal_votes = int(np.sum(tree_predictions == 0))
        
        vote_breakdown = {
            'attack_votes': attack_votes,
            'normal_votes': normal_votes,
            'total_trees': self.n_trees,
            'tree_predictions': tree_predictions.tolist(),
            'tree_probas': tree_probas.tolist(),
            'agreement_rate': max(attack_votes, normal_votes) / self.n_trees
        }
        
        features['_metadata'] = metadata
        
        # Thêm timing info
        timing_info = {
            'feature_extraction_us': t_extract * 1e6,
            'prediction_us': t_pred * 1e6,
            'total_us': t_total * 1e6
        }
        
        return prediction, probability, features, vote_breakdown, timing_info
    
    def predict_batch(self, messages: list):
        """Dự đoán nhiều messages với timing"""
        results = []
        
        # ⏱️ Batch timing
        t_batch_start = time.perf_counter()
        
        for msg in messages:
            arb_id, data_field = msg[0], msg[1]
            timestamp = msg[2] if len(msg) > 2 else None
            
            pred, prob, features, votes, timing = self.predict_single(arb_id, data_field, timestamp)
            results.append({
                'arbitration_id': arb_id,
                'data_field': data_field,
                'prediction': int(pred),
                'label': 'Attack' if pred == 1 else 'Normal',
                'confidence': float(prob[int(pred)]),
                'features': features,
                'votes': votes,
                'timing': timing
            })
        
        t_batch_total = time.perf_counter() - t_batch_start
        
        # Add batch timing stats
        batch_timing = {
            'total_messages': len(messages),
            'total_time_us': t_batch_total * 1e6,
            'avg_time_per_msg_us': (t_batch_total / len(messages)) * 1e6 if messages else 0
        }
        
        return results, batch_timing
    
    def get_timing_summary(self):
        """Lấy tổng kết timing statistics"""
        if not self.timing_stats['total']:
            return None
        
        summary = {}
        for stage in ['feature_extraction', 'prediction', 'total']:
            times = self.timing_stats[stage]
            summary[stage] = {
                'mean_us': mean(times) * 1e6,
                'median_us': median(times) * 1e6,
                'min_us': min(times) * 1e6,
                'max_us': max(times) * 1e6,
                'std_us': stdev(times) * 1e6 if len(times) > 1 else 0
            }
        
        return summary
    
    def reset_timestamp(self):
        """Reset timestamp tracking"""
        self.last_timestamp = None
    
    def reset_timing_stats(self):
        """Reset timing statistics"""
        self.timing_stats = {
            'feature_extraction': [],
            'prediction': [],
            'total': []
        }


def print_timing_comparison(results: list, batch_timing: dict, clock_freq_mhz: float = 100.0):
    """
    In bảng so sánh timing giữa Software (Python) và Hardware (Verilog)
    
    Args:
        clock_freq_mhz: Tần số clock của hardware (MHz)
    """
    print("\n" + "=" * 140)
    print("⏱️  SOFTWARE vs HARDWARE TIMING COMPARISON")
    print("=" * 140)
    
    # Hardware specs
    clock_period_ns = 1000.0 / clock_freq_mhz  # ns per clock
    hw_latency_cycles = 200  # Typical worst-case from your design
    hw_latency_us = (hw_latency_cycles * clock_period_ns) / 1000.0
    
    print(f"\n🔧 HARDWARE SPECIFICATION:")
    print(f"   Clock Frequency    : {clock_freq_mhz:.1f} MHz")
    print(f"   Clock Period       : {clock_period_ns:.2f} ns")
    print(f"   Typical Latency    : {hw_latency_cycles} cycles = {hw_latency_us:.3f} µs")
    
    # Software timing
    sw_times = [r['timing']['total_us'] for r in results]
    sw_mean = mean(sw_times)
    sw_median = median(sw_times)
    sw_min = min(sw_times)
    sw_max = max(sw_times)
    sw_std = stdev(sw_times) if len(sw_times) > 1 else 0
    
    print(f"\n💻 SOFTWARE TIMING (Python/NumPy):")
    print(f"   Mean Time          : {sw_mean:.3f} µs")
    print(f"   Median Time        : {sw_median:.3f} µs")
    print(f"   Min Time           : {sw_min:.3f} µs")
    print(f"   Max Time           : {sw_max:.3f} µs")
    print(f"   Std Dev            : {sw_std:.3f} µs")
    print(f"   Total Batch Time   : {batch_timing['total_time_us']:.3f} µs ({batch_timing['total_messages']} messages)")
    
    # Comparison
    speedup = sw_mean / hw_latency_us
    
    print(f"\n📊 PERFORMANCE COMPARISON:")
    print(f"   {'Metric':<30} {'Software':<20} {'Hardware':<20} {'Speedup':<15}")
    print(f"   {'-'*85}")
    print(f"   {'Latency (µs)':<30} {sw_mean:>15.3f}     {hw_latency_us:>15.3f}     {speedup:>10.1f}x")
    print(f"   {'Throughput (msg/sec)':<30} {1e6/sw_mean:>15.0f}     {1e6/hw_latency_us:>15.0f}     {(1e6/hw_latency_us)/(1e6/sw_mean):>10.1f}x")
    print(f"   {'Deterministic':<30} {'No':>20} {'Yes':>20} {'✓':>15}")
    print(f"   {'Real-time capable':<30} {'Limited':>20} {'Yes':>20} {'✓':>15}")
    
    # Detailed timing breakdown
    print(f"\n⚙️  SOFTWARE TIMING BREAKDOWN:")
    feature_times = [r['timing']['feature_extraction_us'] for r in results]
    pred_times = [r['timing']['prediction_us'] for r in results]
    
    print(f"   Feature Extraction : {mean(feature_times):.3f} µs (avg) | {min(feature_times):.3f} - {max(feature_times):.3f} µs")
    print(f"   RF Prediction      : {mean(pred_times):.3f} µs (avg) | {min(pred_times):.3f} - {max(pred_times):.3f} µs")
    
    # Hardware breakdown (estimated from your FSM)
    hw_scale_cycles = 2
    hw_tree_cycles = hw_latency_cycles - hw_scale_cycles - 2  # subtract SCALE and VOTE
    hw_scale_us = (hw_scale_cycles * clock_period_ns) / 1000.0
    hw_tree_us = (hw_tree_cycles * clock_period_ns) / 1000.0
    hw_vote_us = (2 * clock_period_ns) / 1000.0
    
    print(f"\n⚙️  HARDWARE TIMING BREAKDOWN:")
    print(f"   Feature Scaling    : ~{hw_scale_cycles} cycles = {hw_scale_us:.3f} µs")
    print(f"   21 Trees (parallel): ~{hw_tree_cycles} cycles = {hw_tree_us:.3f} µs")
    print(f"   Voting             : ~2 cycles = {hw_vote_us:.3f} µs")
    
    print("\n" + "=" * 140)
    
    # Visualization
    print(f"\n📈 LATENCY VISUALIZATION (µs):")
    print(f"   Software: [{'█' * int(sw_mean/10)}] {sw_mean:.1f} µs")
    print(f"   Hardware: [{'█' * max(1, int(hw_latency_us/10))}] {hw_latency_us:.1f} µs")
    print(f"   Speedup : {speedup:.1f}x faster in hardware")
    
    return {
        'software_mean_us': sw_mean,
        'hardware_latency_us': hw_latency_us,
        'speedup': speedup,
        'hw_throughput': 1e6 / hw_latency_us,
        'sw_throughput': 1e6 / sw_mean
    }


def print_comparison_table_with_timing(results: list):
    """In bảng so sánh với timing info"""
    print("\n" + "=" * 160)
    print("📊 RANDOM FOREST RESULTS WITH TIMING")
    print("=" * 160)
    
    header = f"{'No':<4} {'Arb_ID':>7} {'Data_Field':<18} " \
             f"{'A_Votes':>8} {'N_Votes':>8} {'Pred':>6} {'Conf':>7} " \
             f"{'Extract(µs)':>12} {'Predict(µs)':>12} {'Total(µs)':>11}"
    print(header)
    print("-" * 160)
    
    for i, r in enumerate(results, 1):
        votes = r['votes']
        timing = r['timing']
        
        row = f"{i:<4} {r['arbitration_id']:>7} {r['data_field']:<18} " \
              f"{votes['attack_votes']:>8} {votes['normal_votes']:>8} " \
              f"{r['label']:>6} {r['confidence']:>6.1%} " \
              f"{timing['feature_extraction_us']:>12.3f} " \
              f"{timing['prediction_us']:>12.3f} " \
              f"{timing['total_us']:>11.3f}"
        print(row)
    
    print("=" * 160)


def benchmark_repeated_tests(detector, test_messages, n_repeats=100):
    """
    Chạy benchmark với nhiều lần lặp để có thống kê chính xác
    """
    print("\n" + "=" * 100)
    print(f"🏃 RUNNING BENCHMARK - {n_repeats} REPETITIONS")
    print("=" * 100)
    
    all_times = []
    
    print(f"\nProcessing {len(test_messages)} test cases × {n_repeats} repetitions...")
    
    for rep in range(n_repeats):
        detector.reset_timing_stats()
        detector.reset_timestamp()
        
        for arb_id, data, ts, _ in test_messages:
            detector.predict_single(arb_id, data, ts)
        
        summary = detector.get_timing_summary()
        all_times.append(summary['total']['mean_us'])
        
        if (rep + 1) % 20 == 0:
            print(f"  Progress: {rep + 1}/{n_repeats} repetitions completed")
    
    # Statistics
    bench_mean = mean(all_times)
    bench_median = median(all_times)
    bench_min = min(all_times)
    bench_max = max(all_times)
    bench_std = stdev(all_times)
    
    print(f"\n📊 BENCHMARK RESULTS ({n_repeats} runs):")
    print(f"   Mean Time    : {bench_mean:.3f} µs")
    print(f"   Median Time  : {bench_median:.3f} µs")
    print(f"   Min Time     : {bench_min:.3f} µs")
    print(f"   Max Time     : {bench_max:.3f} µs")
    print(f"   Std Dev      : {bench_std:.3f} µs")
    print(f"   CV (%)       : {(bench_std/bench_mean)*100:.2f}%")
    
    print("\n" + "=" * 100)
    
    return {
        'mean': bench_mean,
        'median': bench_median,
        'min': bench_min,
        'max': bench_max,
        'std': bench_std
    }


def test_with_timing():
    """Main test với timing comparison"""
    print("=" * 100)
    print("TEST RANDOM FOREST WITH HARDWARE TIMING COMPARISON")
    print("=" * 100)
    
    detector = CANAttackDetectorRF('./SW/random_forest_model.pkl')
    
    test_messages = [
        ("34C", "F2820F5003EA0FA0", 1672531205.7830172, "Normal"),
        ("000", "0000000000000000", 1672531205.783651, "Attack"),
        ("000", "0000000000000000", 1672531205.785138, "Attack"),
        ("0C7", "039B3777", 1672531205.7851431, "Normal"),
        ("000", "0000000000000000", 1672531205.785746, "Attack"),
        ("1FE", "067E7F0200008154", 1672531205.7862232, "Normal"),
        ("362", "00000000", 1672531205.786227, "Normal"),
        ("000", "0000000000000000", 1672531205.786359, "Attack"),
        ("0F1", "000500400000", 1672531205.787298, "Normal"),
        ("0AA", "0000000000000000", 1672531275.675515, "Attack"),
    ]
    
    # Run predictions with timing
    print("\n📝 Running predictions with timing measurement...\n")
    
    messages_only = [(arb, data, ts) for arb, data, ts, _ in test_messages]
    results, batch_timing = detector.predict_batch(messages_only)
    
    # Add expected labels
    for i, r in enumerate(results):
        r['expected'] = test_messages[i][3]
        r['correct'] = r['label'] == r['expected']
    
    # Print results with timing
    print_comparison_table_with_timing(results)
    
    # Accuracy
    correct = sum(1 for r in results if r['correct'])
    accuracy = correct / len(results)
    print(f"\n✅ ACCURACY: {correct}/{len(results)} = {accuracy:.1%}")
    
    # Timing comparison với hardware
    print("\n" + "=" * 100)
    hw_clock_freq = float(input("Enter hardware clock frequency in MHz (default 100): ") or "100")
    
    timing_comparison = print_timing_comparison(results, batch_timing, hw_clock_freq)
    
    # Benchmark option
    do_benchmark = input("\n🏃 Run detailed benchmark (100 repetitions)? (y/n): ").lower() == 'y'
    if do_benchmark:
        benchmark_stats = benchmark_repeated_tests(detector, test_messages, n_repeats=100)
        
        # Compare with hardware
        hw_latency = (200 * 1000.0 / hw_clock_freq) / 1000.0  # µs
        print(f"\n📊 BENCHMARK vs HARDWARE:")
        print(f"   Software (benchmark): {benchmark_stats['mean']:.3f} µs")
        print(f"   Hardware (estimated): {hw_latency:.3f} µs")
        print(f"   Hardware speedup    : {benchmark_stats['mean']/hw_latency:.1f}x")
    
    return detector, results, timing_comparison


if __name__ == "__main__":
    print("\n🚀 Starting Random Forest tests with timing analysis...\n")
    detector, results, timing_comp = test_with_timing()
    
    print("\n✅ All tests completed!")
    print("\n💡 KEY TAKEAWAYS:")
    print(f"   • Software latency : {timing_comp['software_mean_us']:.1f} µs (variable)")
    print(f"   • Hardware latency : {timing_comp['hardware_latency_us']:.1f} µs (fixed)")
    print(f"   • Hardware speedup : {timing_comp['speedup']:.1f}x faster")
    print(f"   • HW throughput    : {timing_comp['hw_throughput']:.0f} messages/sec")
    print(f"   • SW throughput    : {timing_comp['sw_throughput']:.0f} messages/sec")