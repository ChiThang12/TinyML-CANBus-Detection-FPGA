// Threshold Decoder and Comparator for Decision Tree
// Handles different fixed-point formats for each feature

module threshold_decoder (
    input  wire [2:0]  feature_id,      // 0-5
    input  wire [26:0] threshold_raw,   // Raw 27-bit threshold from memory
    input  wire [31:0] feature_value,   // Input feature value (scaled)
    output reg         comparison_result // 1 if feature_value <= threshold
);

    // Feature-specific fixed-point formats:
    // Feature 0 (arb_id_dec):   Q11.16 - 11 int bits, 16 frac bits
    // Feature 1 (data_length):  Q4.23  - 4 int bits,  23 frac bits
    // Feature 2 (first_byte):   Q8.19  - 8 int bits,  19 frac bits
    // Feature 3 (last_byte):    Q8.19  - 8 int bits,  19 frac bits
    // Feature 4 (byte_sum):     Q11.16 - 11 int bits, 16 frac bits
    // Feature 5 (time_delta):   Q0.27  - 0 int bits,  27 frac bits (pure fractional)

    reg [31:0] scaled_threshold;
    reg [4:0]  shift_amount;

    always @(*) begin
        // Determine shift amount based on feature
        case (feature_id)
            3'd0: shift_amount = 5'd16;  // arb_id: shift by 16 (Q11.16)
            3'd1: shift_amount = 5'd23;  // data_length: shift by 23 (Q4.23)
            3'd2: shift_amount = 5'd19;  // first_byte: shift by 19 (Q8.19)
            3'd3: shift_amount = 5'd19;  // last_byte: shift by 19 (Q8.19)
            3'd4: shift_amount = 5'd16;  // byte_sum: shift by 16 (Q11.16)
            3'd5: shift_amount = 5'd27;  // time_delta: shift by 27 (Q0.27)
            default: shift_amount = 5'd16;
        endcase

        // Scale threshold to match feature_value format
        // Assume feature_value is already scaled appropriately
        scaled_threshold = {5'b0, threshold_raw};

        // Compare: Go RIGHT if feature_value > threshold
        comparison_result = (feature_value <= scaled_threshold);
    end

endmodule

// Example usage in tree traversal:
//
// wire [63:0] node_data;
// wire [2:0]  feature_id = node_data[55:53];
// wire [26:0] threshold = node_data[52:26];
// wire [7:0]  left_child = node_data[17:10];
// wire [7:0]  right_child = node_data[25:18];
//
// threshold_decoder decoder (
//     .feature_id(feature_id),
//     .threshold_raw(threshold),
//     .feature_value(input_features[feature_id]),
//     .comparison_result(go_left)
// );
//
// assign next_node = go_left ? left_child : right_child;
