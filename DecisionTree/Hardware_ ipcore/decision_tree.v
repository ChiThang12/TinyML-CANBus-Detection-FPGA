// ============================================================================
// ============================================================================

// ============================================================================
// MODULE 1: INPUT FEATURE SCALER (IMPROVED)
// ============================================================================
module feature_scaler (
    input  wire        clk,              // Thêm clock để pipeline
    input  wire        rst_n,
    input  wire        valid_in,         // Input valid signal
    input  wire [10:0] arb_id_dec,
    input  wire [3:0]  data_length,
    input  wire [7:0]  first_byte,
    input  wire [7:0]  last_byte,
    input  wire [10:0] byte_sum,
    input  wire [31:0] time_delta,
    
    output reg  [31:0] feature_0_scaled,
    output reg  [31:0] feature_1_scaled,
    output reg  [31:0] feature_2_scaled,
    output reg  [31:0] feature_3_scaled,
    output reg  [31:0] feature_4_scaled,
    output reg  [31:0] feature_5_scaled,
    output reg         valid_out         // Output valid signal
);

    // Pipeline registers để tránh timing violations
    reg [31:0] f0_comb, f1_comb, f2_comb, f3_comb, f4_comb, f5_comb;
    
    // Combinational scaling
    always @(*) begin
        // Feature 0: arb_id_dec - Q11.16
        f0_comb = {21'b0, arb_id_dec} << 16;
        
        // Feature 1: data_length - Q4.23
        f1_comb = {28'b0, data_length} << 23;
        
        // Feature 2: first_byte - Q8.19
        f2_comb = {24'b0, first_byte} << 19;
        
        // Feature 3: last_byte - Q8.19
        f3_comb = {24'b0, last_byte} << 19;
        
        // Feature 4: byte_sum - Q11.16
        f4_comb = {21'b0, byte_sum} << 16;
        
        // Feature 5: time_delta - Q0.27
        // Sử dụng phép nhân thay vì chia để tránh latency cao
        // time_delta (us) * 2^27 / 1000000 ≈ time_delta * 134
        f5_comb = (time_delta * 134);  // Approximate scaling
    end
    
    // Sequential output để đồng bộ timing
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            feature_0_scaled <= 32'b0;
            feature_1_scaled <= 32'b0;
            feature_2_scaled <= 32'b0;
            feature_3_scaled <= 32'b0;
            feature_4_scaled <= 32'b0;
            feature_5_scaled <= 32'b0;
            valid_out <= 1'b0;
        end else if (valid_in) begin
            feature_0_scaled <= f0_comb;
            feature_1_scaled <= f1_comb;
            feature_2_scaled <= f2_comb;
            feature_3_scaled <= f3_comb;
            feature_4_scaled <= f4_comb;
            feature_5_scaled <= f5_comb;
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule


// ============================================================================
// MODULE 2: FEATURE SELECTOR (IMPROVED)
// ============================================================================
module feature_selector (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [2:0]  feature_id,
    input  wire [31:0] feature_0_scaled,
    input  wire [31:0] feature_1_scaled,
    input  wire [31:0] feature_2_scaled,
    input  wire [31:0] feature_3_scaled,
    input  wire [31:0] feature_4_scaled,
    input  wire [31:0] feature_5_scaled,
    output reg  [31:0] selected_feature,
    output reg         valid_out,
    output reg         error             // Invalid feature_id
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            selected_feature <= 32'b0;
            valid_out <= 1'b0;
            error <= 1'b0;
        end else if (valid_in) begin
            error <= 1'b0;
            valid_out <= 1'b1;
            case (feature_id)
                3'd0: selected_feature <= feature_0_scaled;
                3'd1: selected_feature <= feature_1_scaled;
                3'd2: selected_feature <= feature_2_scaled;
                3'd3: selected_feature <= feature_3_scaled;
                3'd4: selected_feature <= feature_4_scaled;
                3'd5: selected_feature <= feature_5_scaled;
                default: begin
                    selected_feature <= 32'b0;
                    error <= 1'b1;  // Invalid feature ID
                end
            endcase
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule


// ============================================================================
// MODULE 3: THRESHOLD COMPARATOR (IMPROVED)
// ============================================================================
module threshold_comparator (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [31:0] feature_value,
    input  wire [26:0] threshold_raw,
    output reg         go_left,
    output reg         valid_out
);

    wire [31:0] threshold_extended;
    assign threshold_extended = {5'b0, threshold_raw};
    
    // Pipeline comparison để cải thiện timing
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            go_left <= 1'b0;
            valid_out <= 1'b0;
        end else if (valid_in) begin
            go_left <= (feature_value <= threshold_extended);
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule


// ============================================================================
// MODULE 4: NODE DECODER (IMPROVED - Combinational, no changes needed)
// ============================================================================
module node_decoder (
    input  wire [63:0] node_data,
    output wire [7:0]  node_id,
    output wire [2:0]  feature_id,
    output wire [26:0] threshold,
    output wire [7:0]  right_child,
    output wire [7:0]  left_child,
    output wire [7:0]  node_type,
    output wire        is_leaf
);

    assign node_id     = node_data[63:56];
    assign feature_id  = node_data[55:53];
    assign threshold   = node_data[52:26];
    assign right_child = node_data[25:18];
    assign left_child  = node_data[17:10];
    assign node_type   = node_data[9:2];
    
    assign is_leaf = (node_type == 8'h01) || 
                     ((left_child == 8'h00) && (right_child == 8'h00));

endmodule


// ============================================================================
// MODULE 5: DECISION TREE TRAVERSAL (IMPROVED)
// ============================================================================
module decision_tree_classifier (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    
    // Input: Raw CAN message data
    input  wire [10:0] arb_id_dec,
    input  wire [3:0]  data_length,
    input  wire [7:0]  first_byte,
    input  wire [7:0]  last_byte,
    input  wire [10:0] byte_sum,
    input  wire [31:0] time_delta,
    
    // Output: Classification result
    output reg         done,
    output reg         is_attack,
    output reg  [7:0]  final_node,
    output reg         error,            // Error flag
    output reg  [7:0]  tree_depth        // Độ sâu của cây (debug)
);

    // ========================================================================
    // STATE MACHINE - Cải thiện với thêm states
    // ========================================================================
    localparam IDLE         = 3'd0;
    localparam SCALE        = 3'd1;
    localparam DECODE       = 3'd2;
    localparam COMPARE      = 3'd3;
    localparam NEXT_NODE    = 3'd4;
    localparam CLASSIFY     = 3'd5;
    localparam ERROR_STATE  = 3'd6;
    
    reg [2:0] state, next_state;
    reg [7:0] current_node_addr;
    reg [7:0] depth_counter;
    
    // Max depth protection (tránh infinite loop)
    localparam MAX_DEPTH = 8'd50;
    
    // ========================================================================
    // TREE MEMORY
    // ========================================================================
    reg [63:0] tree_mem [0:172];
    
    initial begin
        $readmemb("tree.mem", tree_mem);
    end
    
    wire [63:0] current_node_data;
    assign current_node_data = tree_mem[current_node_addr];
    
    // ========================================================================
    // PIPELINE CONTROL SIGNALS
    // ========================================================================
    reg        scale_valid;
    wire       scale_done;
    reg        selector_valid;
    wire       selector_done;
    wire       selector_error;
    reg        compare_valid;
    wire       compare_done;
    
    // ========================================================================
    // FEATURE SCALING - Pipelined
    // ========================================================================
    wire [31:0] feature_0_scaled, feature_1_scaled, feature_2_scaled;
    wire [31:0] feature_3_scaled, feature_4_scaled, feature_5_scaled;
    
    feature_scaler scaler (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(scale_valid),
        .arb_id_dec(arb_id_dec),
        .data_length(data_length),
        .first_byte(first_byte),
        .last_byte(last_byte),
        .byte_sum(byte_sum),
        .time_delta(time_delta),
        .feature_0_scaled(feature_0_scaled),
        .feature_1_scaled(feature_1_scaled),
        .feature_2_scaled(feature_2_scaled),
        .feature_3_scaled(feature_3_scaled),
        .feature_4_scaled(feature_4_scaled),
        .feature_5_scaled(feature_5_scaled),
        .valid_out(scale_done)
    );
    
    // ========================================================================
    // NODE DECODING
    // ========================================================================
    wire [7:0]  node_id;
    wire [2:0]  feature_id;
    wire [26:0] threshold;
    wire [7:0]  right_child, left_child;
    wire [7:0]  node_type;
    wire        is_leaf;
    
    node_decoder decoder (
        .node_data(current_node_data),
        .node_id(node_id),
        .feature_id(feature_id),
        .threshold(threshold),
        .right_child(right_child),
        .left_child(left_child),
        .node_type(node_type),
        .is_leaf(is_leaf)
    );
    
    // ========================================================================
    // FEATURE SELECTION - Pipelined
    // ========================================================================
    wire [31:0] selected_feature;
    
    feature_selector selector (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(selector_valid),
        .feature_id(feature_id),
        .feature_0_scaled(feature_0_scaled),
        .feature_1_scaled(feature_1_scaled),
        .feature_2_scaled(feature_2_scaled),
        .feature_3_scaled(feature_3_scaled),
        .feature_4_scaled(feature_4_scaled),
        .feature_5_scaled(feature_5_scaled),
        .selected_feature(selected_feature),
        .valid_out(selector_done),
        .error(selector_error)
    );
    
    // ========================================================================
    // THRESHOLD COMPARISON - Pipelined
    // ========================================================================
    wire go_left;
    
    threshold_comparator comparator (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(compare_valid),
        .feature_value(selected_feature),
        .threshold_raw(threshold),
        .go_left(go_left),
        .valid_out(compare_done)
    );
    
    // ========================================================================
    // NEXT NODE SELECTION
    // ========================================================================
    wire [7:0] next_node;
    assign next_node = go_left ? left_child : right_child;
    
    // ========================================================================
    // STATE MACHINE LOGIC - Improved
    // ========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_node_addr <= 8'd0;
            depth_counter <= 8'd0;
            done <= 1'b0;
            is_attack <= 1'b0;
            final_node <= 8'd0;
            error <= 1'b0;
            tree_depth <= 8'd0;
            scale_valid <= 1'b0;
            selector_valid <= 1'b0;
            compare_valid <= 1'b0;
        end
        else begin
            // Default: clear one-cycle pulses
            scale_valid <= 1'b0;
            selector_valid <= 1'b0;
            compare_valid <= 1'b0;
            
            case (state)
                IDLE: begin
                    done <= 1'b0;
                    error <= 1'b0;
                    if (start) begin
                        current_node_addr <= 8'd0;
                        depth_counter <= 8'd0;
                        scale_valid <= 1'b1;  // Bắt đầu scaling
                        state <= SCALE;
                    end
                end
                
                SCALE: begin
                    if (scale_done) begin
                        state <= DECODE;
                    end
                end
                
                DECODE: begin
                    // Check if leaf node
                    if (is_leaf) begin
                        state <= CLASSIFY;
                        final_node <= current_node_addr;
                        tree_depth <= depth_counter;
                        is_attack <= (node_type == 8'h01);
                    end
                    else begin
                        // Check max depth
                        if (depth_counter >= MAX_DEPTH) begin
                            state <= ERROR_STATE;
                            error <= 1'b1;
                        end
                        else begin
                            selector_valid <= 1'b1;
                            state <= COMPARE;
                        end
                    end
                end
                
                COMPARE: begin
                    if (selector_done) begin
                        if (selector_error) begin
                            state <= ERROR_STATE;
                            error <= 1'b1;
                        end
                        else begin
                            compare_valid <= 1'b1;
                            state <= NEXT_NODE;
                        end
                    end
                end
                
                NEXT_NODE: begin
                    if (compare_done) begin
                        current_node_addr <= next_node;
                        depth_counter <= depth_counter + 1'b1;
                        state <= DECODE;
                    end
                end
                
                CLASSIFY: begin
                    done <= 1'b1;
                    state <= IDLE;
                end
                
                ERROR_STATE: begin
                    done <= 1'b1;
                    error <= 1'b1;
                    state <= IDLE;
                end
                
                default: state <= IDLE;
            endcase
        end
    end

endmodule


// ============================================================================
// TESTBENCH - IMPROVED
// ============================================================================
module tb_decision_tree;

    reg clk, rst_n, start;
    reg [10:0] arb_id_dec;
    reg [3:0]  data_length;
    reg [7:0]  first_byte, last_byte;
    reg [10:0] byte_sum;
    reg [31:0] time_delta;
    
    wire done, is_attack, error;
    wire [7:0] final_node, tree_depth;
    
    decision_tree_classifier dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .arb_id_dec(arb_id_dec),
        .data_length(data_length),
        .first_byte(first_byte),
        .last_byte(last_byte),
        .byte_sum(byte_sum),
        .time_delta(time_delta),
        .done(done),
        .is_attack(is_attack),
        .final_node(final_node),
        .error(error),
        .tree_depth(tree_depth)
    );
    
    // Clock generation: 10ns period (100MHz)
    initial clk = 0;
    always #5 clk = ~clk;
    
    // Timeout watchdog
    initial begin
        #100000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end
    
    // Test stimulus
    initial begin
        $dumpfile("dt_classifier.vcd");
        $dumpvars(0, tb_decision_tree);
        
        // Initialize
        rst_n = 0;
        start = 0;
        arb_id_dec = 0;
        data_length = 0;
        first_byte = 0;
        last_byte = 0;
        byte_sum = 0;
        time_delta = 0;
        
        #20 rst_n = 1;
        #10;
        
        // Test case 1: Normal message
        $display("\n=== Test 1: Normal Message ===");
        @(posedge clk);
   arb_id_dec  = 11'd0;
   data_length = 5'd16;
   first_byte  = 8'd0;
   last_byte   = 8'd0;
   byte_sum    = 11'd0;
   time_delta  = 32'd0; // microseconds
        start = 1;
        @(posedge clk);
        start = 0;
        
        wait(done);
        if (!error)
            $display("Result: Node=%d, Attack=%b, Depth=%d", 
                     final_node, is_attack, tree_depth);
        else
            $display("ERROR in classification!");
        
        #100;
        $display("\n=== All tests completed ===");
        $finish;
    end
    
    // Monitor signals
    always @(posedge clk) begin
        if (done && !error) begin
            $display("  [%0t] Classification complete", $time);
        end
        if (error) begin
            $display("  [%0t] ERROR detected!", $time);
        end
    end

endmodule