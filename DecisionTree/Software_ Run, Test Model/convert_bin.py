"""
Convert Decision Tree CSV to Binary MEM format for FPGA
Chuyển đổi cấu trúc cây từ CSV sang file .mem (binary format) để nạp vào FPGA

Format Binary cho mỗi node (64-bit = 8 bytes):
Cấu trúc: Node_ID + Feature_ID + Threshold + Right_Child + Left_Child + Node_Type

- Bits [63:56]: Node ID (8-bit) - 0-255
- Bits [55:53]: Feature ID (3-bit) - 0-5
- Bits [52:26]: Threshold value (27-bit fixed-point)
- Bits [25:18]: Right child index (8-bit) - 0-255
- Bits [17:10]: Left child index (8-bit) - 0-255  
- Bits [9:2]:   Node type (8-bit) - 00=internal, 01=leaf
- Bits [1:0]:   Reserved (2-bit)
"""

import pandas as pd
import numpy as np
import struct

class TreeToBinaryMemConverter:
    def __init__(self, csv_file):
        """Load tree structure from CSV"""
        self.df = pd.read_csv(csv_file)
        print(f"✅ Loaded tree with {len(self.df)} nodes from {csv_file}")
        
        # Mapping features to IDs
        self.feature_map = {
            '00': 0,  # arb_id_dec
            '01': 1,  # data_length
            '02': 2,  # first_byte
            '03': 3,  # last_byte
            '04': 4,  # byte_sum
            '05': 5   # time_delta
        }
        
    def float_to_fixed_point(self, value, feature_id, int_bits=12, frac_bits=15):
        """
        Convert float to fixed-point representation với format khác nhau cho từng feature
        Total 27 bits: phân bổ integer và fractional bits tùy feature
        
        Feature-specific formats:
        - Feature 0 (arb_id_dec): Q11.16 (max ~2047, precision ~0.000015)
        - Feature 1 (data_length): Q4.23 (max ~15, precision ~0.00000012)
        - Feature 2 (first_byte): Q8.19 (max ~255, precision ~0.0000019)
        - Feature 3 (last_byte): Q8.19 (max ~255, precision ~0.0000019)
        - Feature 4 (byte_sum): Q11.16 (max ~2047, precision ~0.000015)
        - Feature 5 (time_delta): Q0.27 (max ~1, precision ~0.0000000075) - SỐ THẬP PHÂN NHỎ
        """
        
        # Chọn format dựa trên feature_id
        if feature_id == 0:  # arb_id_dec (max ~1328)
            int_bits, frac_bits = 11, 16  # Range: 0-2047, precision: 1/65536
        elif feature_id == 1:  # data_length (max ~15)
            int_bits, frac_bits = 4, 23   # Range: 0-15, precision: 1/8388608
        elif feature_id == 2:  # first_byte (max ~251)
            int_bits, frac_bits = 8, 19   # Range: 0-255, precision: 1/524288
        elif feature_id == 3:  # last_byte (max ~251)
            int_bits, frac_bits = 8, 19   # Range: 0-255, precision: 1/524288
        elif feature_id == 4:  # byte_sum (max ~1044)
            int_bits, frac_bits = 11, 16  # Range: 0-2047, precision: 1/65536
        elif feature_id == 5:  # time_delta (max ~0.0014, min ~8.3e-07)
            int_bits, frac_bits = 0, 27   # Range: 0-1, precision: 1/134217728 (BEST FOR SMALL DECIMALS)
        else:
            # Default: balanced format
            int_bits, frac_bits = 14, 13
        
        # Scale and convert
        scaled = int(round(value * (2 ** frac_bits)))
        
        # Clamp to 27-bit range (unsigned)
        max_val = (2 ** 27) - 1
        min_val = 0
        scaled = max(min_val, min(max_val, scaled))
        
        # Keep only 27 bits
        return scaled & 0x7FFFFFF
    
    def node_to_binary(self, node_row):
        """
        Convert one node to 64-bit binary value
        Format: [Node_ID(8)][Feature_ID(3)][Threshold(27)][Right(8)][Left(8)][Type(8)][Reserved(2)]
        
        Returns:
            int: 64-bit integer representation
        """
        node_id = int(node_row['Node'])
        feature = str(node_row['Feature'])
        threshold = float(node_row['Threshold'])
        left_child = int(node_row['Left_Child'])
        right_child = int(node_row['Right_Child'])
        prediction = int(node_row['Prediction'])
        
        # Check if leaf node
        is_leaf = (feature == '-1' or (left_child == 0 and right_child == 0))
        
        if is_leaf:
            # Leaf node
            node_type = 0x01  # Leaf indicator (8-bit)
            feature_id = 0
            threshold_fixed = 0
            # For leaf, encode prediction in node_type (1=Attack, 0=Normal)
            if prediction == 1:
                node_type = 0x01  # Attack
            else:
                node_type = 0x00  # Normal
        else:
            # Internal node
            node_type = 0x00  # Internal node (8-bit)
            feature_id = self.feature_map.get(feature, 0)
            # Pass feature_id to fixed-point conversion for optimal format
            threshold_fixed = self.float_to_fixed_point(threshold, feature_id)
        
        # Pack binary value
        node_value = (
            ((node_id & 0xFF) << 56) |              # Bits [63:56]: Node ID (8-bit)
            ((feature_id & 0x7) << 53) |            # Bits [55:53]: Feature ID (3-bit)
            ((threshold_fixed & 0x7FFFFFF) << 26) | # Bits [52:26]: Threshold (27-bit)
            ((right_child & 0xFF) << 18) |          # Bits [25:18]: Right child (8-bit)
            ((left_child & 0xFF) << 10) |           # Bits [17:10]: Left child (8-bit)
            ((node_type & 0xFF) << 2)               # Bits [9:2]: Node type (8-bit)
            # Bits [1:0]: Reserved (always 0)
        )
        
        return node_value
    
    def decode_node(self, node_value):
        """Decode 64-bit node value back to components (for verification)"""
        node_id = (node_value >> 56) & 0xFF
        feature_id = (node_value >> 53) & 0x7
        threshold = (node_value >> 26) & 0x7FFFFFF
        right_child = (node_value >> 18) & 0xFF
        left_child = (node_value >> 10) & 0xFF
        node_type = (node_value >> 2) & 0xFF
        reserved = node_value & 0x3
        
        # Determine if leaf based on node_type and children
        is_leaf = (node_type == 1) or (left_child == 0 and right_child == 0)
        
        return {
            'node_id': node_id,
            'feature_id': feature_id,
            'threshold_raw': threshold,
            'right_child': right_child,
            'left_child': left_child,
            'node_type_value': node_type,
            'node_type': 'Leaf' if is_leaf else 'Internal',
            'prediction': node_type if is_leaf else None,
            'reserved': reserved
        }
    
    def generate_binary_mem_file(self, output_file='tree.mem'):
        """
        Generate Binary MEM file for FPGA
        Format: Pure binary values (64 bits of 0s and 1s per line)
        """
        print(f"\n🔄 Converting tree to Pure Binary MEM format...")
        
        binary_values = []
        for idx, row in self.df.iterrows():
            node_binary = self.node_to_binary(row)
            binary_values.append(node_binary)
        
        print(f"✅ Converted {len(binary_values)} nodes")
        
        # Write MEM file with pure binary format (0s and 1s only)
        with open(output_file, 'w') as f:
            # Write header
            f.write("// Pure Binary Memory Initialization File for FPGA\n")
            f.write("// Decision Tree Nodes (64-bit pure binary format)\n")
            f.write(f"// Total Nodes: {len(binary_values)}\n")
            f.write("// Format: [NodeID][FeatureID][Threshold][Right][Left][Type][Reserved]\n")
            f.write("// Each line: 64 binary digits (0 or 1)\n")
            f.write("//\n")
            f.write("// Node Structure:\n")
            f.write("//   [63:56] Node ID (8-bit)\n")
            f.write("//   [55:53] Feature ID (3-bit)\n")
            f.write("//   [52:26] Threshold (27-bit fixed-point)\n")
            f.write("//   [25:18] Right Child (8-bit)\n")
            f.write("//   [17:10] Left Child (8-bit)\n")
            f.write("//   [9:2]   Node Type (8-bit: 0x00=Internal, 0x01=Leaf)\n")
            f.write("//   [1:0]   Reserved (2-bit)\n")
            f.write("//\n\n")
            
            # Write binary data in pure binary format (0s and 1s)
            for idx, binary_val in enumerate(binary_values):
                # Decode for comment
                decoded = self.decode_node(binary_val)
                
                # Convert to 64-bit binary string
                binary_str = f"{binary_val:064b}"
                
                # Add comment
                if decoded['node_type'] == 'Leaf':
                    pred_label = 'Attack' if decoded['prediction'] == 1 else 'Normal'
                    comment = f"Node {decoded['node_id']:3d}: LEAF -> {pred_label}"
                else:
                    comment = f"Node {decoded['node_id']:3d}: Feature[{decoded['feature_id']}] L={decoded['left_child']:3d} R={decoded['right_child']:3d}"
                
                # Write binary string with comment
                f.write(f"{binary_str}  // {comment}\n")
        
        print(f"✅ Pure Binary MEM file saved: {output_file}")
        
        # Generate metadata
        self._write_metadata(binary_values, output_file.replace('.mem', '_metadata.txt'))
        
        return binary_values
    
    def _write_metadata(self, binary_values, metadata_file):
        """Write metadata about the tree"""
        with open(metadata_file, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("DECISION TREE BINARY MEM METADATA FOR FPGA\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Total Nodes: {len(binary_values)}\n")
            
            # Count leaf vs internal nodes
            leaf_count = 0
            internal_count = 0
            for binary_val in binary_values:
                node_type = (binary_val >> 2) & 0xFF
                left = (binary_val >> 10) & 0xFF
                right = (binary_val >> 18) & 0xFF
                if node_type == 1 or (left == 0 and right == 0):
                    leaf_count += 1
                else:
                    internal_count += 1
            
            f.write(f"Internal Nodes: {internal_count}\n")
            f.write(f"Leaf Nodes: {leaf_count}\n")
            
            # Calculate memory size
            total_bits = len(binary_values) * 64
            total_bytes = total_bits // 8
            f.write(f"\nMemory Requirements:\n")
            f.write(f"  Total bits: {total_bits:,}\n")
            f.write(f"  Total bytes: {total_bytes:,}\n")
            f.write(f"  Total KB: {total_bytes / 1024:.2f}\n")
            
            # Feature mapping
            f.write(f"\nFeature ID Mapping:\n")
            feature_names = {
                0: 'arb_id_dec',
                1: 'data_length',
                2: 'first_byte',
                3: 'last_byte',
                4: 'byte_sum',
                5: 'time_delta'
            }
            for fid in range(6):
                f.write(f"  {fid}: {feature_names[fid]}\n")
            
            f.write(f"\nNode Binary Format (64-bit):\n")
            f.write(f"  Bits [63:56]: Node ID (8-bit) - 0 to 255\n")
            f.write(f"  Bits [55:53]: Feature ID (3-bit) - 0 to 5\n")
            f.write(f"  Bits [52:26]: Threshold (27-bit fixed-point, format depends on feature)\n")
            f.write(f"    • Feature 0 (arb_id): Q11.16 format\n")
            f.write(f"    • Feature 1 (data_length): Q4.23 format\n")
            f.write(f"    • Feature 2 (first_byte): Q8.19 format\n")
            f.write(f"    • Feature 3 (last_byte): Q8.19 format\n")
            f.write(f"    • Feature 4 (byte_sum): Q11.16 format\n")
            f.write(f"    • Feature 5 (time_delta): Q0.27 format (pure fractional)\n")
            f.write(f"  Bits [25:18]: Right Child Index (8-bit)\n")
            f.write(f"  Bits [17:10]: Left Child Index (8-bit)\n")
            f.write(f"  Bits [9:2]:   Node Type (8-bit: 0x00=Internal, 0x01=Leaf)\n")
            f.write(f"  Bits [1:0]:   Reserved (2-bit)\n")
            
            # Sample nodes
            f.write(f"\nSample Node Decoding:\n")
            for i in [0, 1, 2]:
                if i < len(binary_values):
                    decoded = self.decode_node(binary_values[i])
                    f.write(f"\n  Node {i}:\n")
                    f.write(f"    Binary (HEX): 0x{binary_values[i]:016X}\n")
                    f.write(f"    Binary (BIN): {binary_values[i]:064b}\n")
                    f.write(f"    Node ID: {decoded['node_id']}\n")
                    f.write(f"    Feature ID: {decoded['feature_id']}\n")
                    f.write(f"    Type: {decoded['node_type']}\n")
                    if decoded['node_type'] == 'Internal':
                        f.write(f"    Left Child: {decoded['left_child']}\n")
                        f.write(f"    Right Child: {decoded['right_child']}\n")
                    else:
                        pred_label = 'Attack' if decoded['prediction'] == 1 else 'Normal'
                        f.write(f"    Prediction: {pred_label}\n")
            
            f.write(f"\n\nHow to use in FPGA:\n")
            f.write(f"  Verilog: $readmemb(\"tree.mem\", memory_array);  // Use $readmemb for binary\n")
            f.write(f"  VHDL: Use text I/O to read binary strings\n")
            f.write(f"\n  Memory array should be:\n")
            f.write(f"    - Width: 64 bits\n")
            f.write(f"    - Depth: {len(binary_values)} locations\n")
            f.write(f"    - Address width: {(len(binary_values)-1).bit_length()} bits\n")
        
        print(f"✅ Metadata saved: {metadata_file}")
    
    def generate_verilog_example(self, output_file='tree_mem_example.v'):
        """Generate Verilog example code to use the MEM file"""
        
        num_nodes = len(self.df)
        addr_width = (num_nodes - 1).bit_length()
        
        with open(output_file, 'w') as f:
            f.write("// Example Verilog module to load pure binary MEM file\n")
            f.write("// This shows how to use the tree.mem file in your FPGA design\n\n")
            
            f.write("module tree_memory (\n")
            f.write("    input  wire clk,\n")
            f.write(f"    input  wire [{addr_width-1}:0] addr,\n")
            f.write("    output reg  [63:0] data\n")
            f.write(");\n\n")
            
            f.write(f"    // Memory array: {num_nodes} nodes × 64 bits\n")
            f.write(f"    reg [63:0] tree_mem [0:{num_nodes-1}];\n\n")
            
            f.write("    // Load pure binary data from MEM file\n")
            f.write("    initial begin\n")
            f.write("        $readmemb(\"tree.mem\", tree_mem);  // Use $readmemb for binary format\n")
            f.write("    end\n\n")
            
            f.write("    // Read operation\n")
            f.write("    always @(posedge clk) begin\n")
            f.write("        data <= tree_mem[addr];\n")
            f.write("    end\n\n")
            
            f.write("    // Node field extraction\n")
            f.write("    wire [7:0]  node_id       = data[63:56];\n")
            f.write("    wire [2:0]  feature_id    = data[55:53];\n")
            f.write("    wire [26:0] threshold     = data[52:26];\n")
            f.write("    wire [7:0]  right_child   = data[25:18];\n")
            f.write("    wire [7:0]  left_child    = data[17:10];\n")
            f.write("    wire [7:0]  node_type     = data[9:2];\n")
            f.write("    wire        is_leaf       = (node_type == 8'h01) || \n")
            f.write("                                (left_child == 0 && right_child == 0);\n\n")
            
            f.write("endmodule\n")
        
        print(f"✅ Verilog example saved: {output_file}")
    
    def generate_threshold_decoder_verilog(self, output_file='threshold_decoder.v'):
        """Generate Verilog module for threshold comparison with proper scaling"""
        
        with open(output_file, 'w') as f:
            f.write("// Threshold Decoder and Comparator for Decision Tree\n")
            f.write("// Handles different fixed-point formats for each feature\n\n")
            
            f.write("module threshold_decoder (\n")
            f.write("    input  wire [2:0]  feature_id,      // 0-5\n")
            f.write("    input  wire [26:0] threshold_raw,   // Raw 27-bit threshold from memory\n")
            f.write("    input  wire [31:0] feature_value,   // Input feature value (scaled)\n")
            f.write("    output reg         comparison_result // 1 if feature_value <= threshold\n")
            f.write(");\n\n")
            
            f.write("    // Feature-specific fixed-point formats:\n")
            f.write("    // Feature 0 (arb_id_dec):   Q11.16 - 11 int bits, 16 frac bits\n")
            f.write("    // Feature 1 (data_length):  Q4.23  - 4 int bits,  23 frac bits\n")
            f.write("    // Feature 2 (first_byte):   Q8.19  - 8 int bits,  19 frac bits\n")
            f.write("    // Feature 3 (last_byte):    Q8.19  - 8 int bits,  19 frac bits\n")
            f.write("    // Feature 4 (byte_sum):     Q11.16 - 11 int bits, 16 frac bits\n")
            f.write("    // Feature 5 (time_delta):   Q0.27  - 0 int bits,  27 frac bits (pure fractional)\n\n")
            
            f.write("    reg [31:0] scaled_threshold;\n")
            f.write("    reg [4:0]  shift_amount;\n\n")
            
            f.write("    always @(*) begin\n")
            f.write("        // Determine shift amount based on feature\n")
            f.write("        case (feature_id)\n")
            f.write("            3'd0: shift_amount = 5'd16;  // arb_id: shift by 16 (Q11.16)\n")
            f.write("            3'd1: shift_amount = 5'd23;  // data_length: shift by 23 (Q4.23)\n")
            f.write("            3'd2: shift_amount = 5'd19;  // first_byte: shift by 19 (Q8.19)\n")
            f.write("            3'd3: shift_amount = 5'd19;  // last_byte: shift by 19 (Q8.19)\n")
            f.write("            3'd4: shift_amount = 5'd16;  // byte_sum: shift by 16 (Q11.16)\n")
            f.write("            3'd5: shift_amount = 5'd27;  // time_delta: shift by 27 (Q0.27)\n")
            f.write("            default: shift_amount = 5'd16;\n")
            f.write("        endcase\n\n")
            
            f.write("        // Scale threshold to match feature_value format\n")
            f.write("        // Assume feature_value is already scaled appropriately\n")
            f.write("        scaled_threshold = {5'b0, threshold_raw};\n\n")
            
            f.write("        // Compare: Go RIGHT if feature_value > threshold\n")
            f.write("        comparison_result = (feature_value <= scaled_threshold);\n")
            f.write("    end\n\n")
            
            f.write("endmodule\n\n")
            
            f.write("// Example usage in tree traversal:\n")
            f.write("//\n")
            f.write("// wire [63:0] node_data;\n")
            f.write("// wire [2:0]  feature_id = node_data[55:53];\n")
            f.write("// wire [26:0] threshold = node_data[52:26];\n")
            f.write("// wire [7:0]  left_child = node_data[17:10];\n")
            f.write("// wire [7:0]  right_child = node_data[25:18];\n")
            f.write("//\n")
            f.write("// threshold_decoder decoder (\n")
            f.write("//     .feature_id(feature_id),\n")
            f.write("//     .threshold_raw(threshold),\n")
            f.write("//     .feature_value(input_features[feature_id]),\n")
            f.write("//     .comparison_result(go_left)\n")
            f.write("// );\n")
            f.write("//\n")
            f.write("// assign next_node = go_left ? left_child : right_child;\n")
        
        print(f"✅ Threshold decoder module saved: {output_file}")


def verify_conversion(csv_file, binary_values, converter):
    """Verify the binary conversion by decoding"""
    print("\n" + "=" * 70)
    print("🔍 VERIFYING BINARY CONVERSION")
    print("=" * 70)
    
    # Read original CSV
    df_original = pd.read_csv(csv_file)
    
    print(f"\n✅ CSV nodes: {len(df_original)}")
    print(f"✅ Binary nodes: {len(binary_values)}")
    
    if len(df_original) != len(binary_values):
        print("❌ WARNING: Node count mismatch!")
        return False
    
    # Verify sample nodes
    print("\n📋 Sample Nodes Verification:")
    errors = 0
    
    for i in [0, 1, 2, 10, 50, -1]:
        if i >= len(df_original):
            continue
            
        node_row = df_original.iloc[i]
        binary_val = binary_values[i]
        decoded = converter.decode_node(binary_val)
        
        print(f"\n  Node {node_row['Node']}:")
        print(f"    Original CSV:")
        print(f"      Feature: {node_row['Feature']}")
        print(f"      Left: {node_row['Left_Child']}, Right: {node_row['Right_Child']}")
        print(f"      Prediction: {node_row['Prediction']}")
        print(f"    Decoded from Binary:")
        print(f"      HEX: 0x{binary_val:016X}")
        print(f"      BIN: {binary_val:064b}")
        print(f"      Node ID: {decoded['node_id']}")
        print(f"      Feature ID: {decoded['feature_id']}")
        print(f"      Type: {decoded['node_type']}")
        print(f"      Left: {decoded['left_child']}, Right: {decoded['right_child']}")
        print(f"      Prediction: {decoded['prediction']}")
        
        # Verify correctness
        if decoded['node_id'] != node_row['Node']:
            print(f"    ❌ ERROR: Node ID mismatch!")
            errors += 1
        elif decoded['left_child'] != node_row['Left_Child']:
            print(f"    ❌ ERROR: Left child mismatch!")
            errors += 1
        elif decoded['right_child'] != node_row['Right_Child']:
            print(f"    ❌ ERROR: Right child mismatch!")
            errors += 1
        else:
            print(f"    ✅ Verification PASSED")
    
    if errors == 0:
        print("\n✅ All verifications PASSED!")
        return True
    else:
        print(f"\n❌ Found {errors} errors!")
        return False


def main():
    """Main conversion workflow"""
    print("=" * 70)
    print("DECISION TREE TO BINARY MEM CONVERTER FOR FPGA")
    print("Format: Binary data in hexadecimal text (.mem file)")
    print("=" * 70)
    
    # Input file
    csv_file = 'LUT/tree_0_v.csv'
    
    # Create converter
    converter = TreeToBinaryMemConverter(csv_file)
    
    # Generate binary MEM file
    print("\n🔄 Generating Binary MEM file...")
    binary_values = converter.generate_binary_mem_file('tree.mem')
    
    # Generate Verilog example
    converter.generate_verilog_example('tree_mem_example.v')
    
    # Generate threshold decoder
    converter.generate_threshold_decoder_verilog('threshold_decoder.v')
    
    # Verify
    verify_conversion(csv_file, binary_values, converter)
    
    print("\n" + "=" * 70)
    print("✅ BINARY MEM FILE GENERATED SUCCESSFULLY!")
    print("=" * 70)
    print("\n📦 Output files:")
    print("  1. tree.mem                - Binary MEM file (MAIN FILE FOR FPGA)")
    print("  2. tree_metadata.txt       - Detailed documentation")
    print("  3. tree_mem_example.v      - Verilog usage example")
    print("  4. threshold_decoder.v     - Threshold comparison module")
    
    print("\n💡 64-bit Binary Node Structure:")
    print("  ┌────────────┬────────────┬──────────────┬───────┬──────┬──────┬──────┐")
    print("  │  [63:56]   │  [55:53]   │   [52:26]    │[25:18]│[17:10]│ [9:2]│ [1:0]│")
    print("  │  Node ID   │ Feature ID │  Threshold   │ Right │ Left │ Type │ Rsvd │")
    print("  │  (8-bit)   │  (3-bit)   │  (27-bit)    │(8-bit)│(8-bit)│(8bit)│(2bit)│")
    print("  └────────────┴────────────┴──────────────┴───────┴──────┴──────┴──────┘")
    
    print("\n🎯 FPGA Implementation Guide:")
    print(f"  - Memory required: ~{len(binary_values) * 8 / 1024:.2f} KB")
    print(f"  - Total nodes: {len(binary_values)}")
    print(f"  - Address width: {(len(binary_values)-1).bit_length()} bits")
    print(f"  - Data width: 64 bits")
    print("\n  How to use in Verilog:")
    print("    reg [63:0] tree_mem [0:NUM_NODES-1];")
    print("    initial $readmemb(\"tree.mem\", tree_mem);  // Use $readmemb for binary")
    print("\n  Node Type encoding:")
    print("    - 0x00 = Internal node (check feature & threshold)")
    print("    - 0x01 = Leaf node → Attack")
    print("    - 0x00 + no children = Leaf node → Normal")


if __name__ == "__main__":
    main()