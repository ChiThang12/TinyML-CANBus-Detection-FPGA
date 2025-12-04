// ============================================================================
// RANDOM FOREST CLASSIFIER - 21 DECISION TREES (với Clock Cycle Counter)
// ============================================================================

// ============================================================================
// MODULE 1: INPUT FEATURE SCALER
// ============================================================================
module feature_scaler (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
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
    output reg         valid_out
);

    reg [31:0] f0_comb, f1_comb, f2_comb, f3_comb, f4_comb, f5_comb;
    
    always @(*) begin
        f0_comb = {21'b0, arb_id_dec} << 16;
        f1_comb = {28'b0, data_length} << 23;
        f2_comb = {24'b0, first_byte} << 19;
        f3_comb = {24'b0, last_byte} << 19;
        f4_comb = {21'b0, byte_sum} << 16;
        f5_comb = (time_delta * 134);
    end
    
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
// MODULE 2: FEATURE SELECTOR
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
    output reg         error
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
                    error <= 1'b1;
                end
            endcase
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule


// ============================================================================
// MODULE 3: THRESHOLD COMPARATOR
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
// MODULE 4: NODE DECODER
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
// MODULE 5: SINGLE DECISION TREE
// ============================================================================
module single_decision_tree (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [4:0]  tree_id,
    
    input  wire [31:0] feature_0_scaled,
    input  wire [31:0] feature_1_scaled,
    input  wire [31:0] feature_2_scaled,
    input  wire [31:0] feature_3_scaled,
    input  wire [31:0] feature_4_scaled,
    input  wire [31:0] feature_5_scaled,
    
    output reg         done,
    output reg         vote_attack,
    output reg         error
);

    localparam IDLE      = 3'd0;
    localparam DECODE    = 3'd1;
    localparam SELECT    = 3'd2;
    localparam COMPARE   = 3'd3;
    localparam NEXT_NODE = 3'd4;
    localparam CLASSIFY  = 3'd5;
    localparam ERROR_ST  = 3'd6;
    
    reg [2:0] state;
    reg [7:0] current_node_addr;
    reg [7:0] depth_counter;
    
    localparam MAX_DEPTH = 8'd50;
    
    reg [63:0] tree_mem [0:198];
    
    integer k;
    initial begin
        for (k = 0; k < 256; k = k + 1) begin
            tree_mem[k] = 64'h0000000000000000;
        end
        
        case (tree_id)
            5'd0:  $readmemb("tree_0.mem", tree_mem);
            5'd1:  $readmemb("tree_1.mem", tree_mem);
            5'd2:  $readmemb("tree_2.mem", tree_mem);
            5'd3:  $readmemb("tree_3.mem", tree_mem);
            5'd4:  $readmemb("tree_4.mem", tree_mem);
            5'd5:  $readmemb("tree_5.mem", tree_mem);
            5'd6:  $readmemb("tree_6.mem", tree_mem);
            5'd7:  $readmemb("tree_7.mem", tree_mem);
            5'd8:  $readmemb("tree_8.mem", tree_mem);
            5'd9:  $readmemb("tree_9.mem", tree_mem);
            5'd10: $readmemb("tree_10.mem", tree_mem);
            5'd11: $readmemb("tree_11.mem", tree_mem);
            5'd12: $readmemb("tree_12.mem", tree_mem);
            5'd13: $readmemb("tree_13.mem", tree_mem);
            5'd14: $readmemb("tree_14.mem", tree_mem);
            5'd15: $readmemb("tree_15.mem", tree_mem);
            5'd16: $readmemb("tree_16.mem", tree_mem);
            5'd17: $readmemb("tree_17.mem", tree_mem);
            5'd18: $readmemb("tree_18.mem", tree_mem);
            5'd19: $readmemb("tree_19.mem", tree_mem);
            5'd20: $readmemb("tree_20.mem", tree_mem);
            default: $readmemb("tree_0.mem", tree_mem);
        endcase
    end
    
    wire [63:0] current_node_data;
    assign current_node_data = tree_mem[current_node_addr];
    
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
    
    reg        selector_valid;
    wire       selector_done;
    wire       selector_error;
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
    
    reg  compare_valid;
    wire compare_done;
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
    
    wire [7:0] next_node;
    assign next_node = go_left ? left_child : right_child;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_node_addr <= 8'd0;
            depth_counter <= 8'd0;
            done <= 1'b0;
            vote_attack <= 1'b0;
            error <= 1'b0;
            selector_valid <= 1'b0;
            compare_valid <= 1'b0;
        end
        else begin
            selector_valid <= 1'b0;
            compare_valid <= 1'b0;
            
            case (state)
                IDLE: begin
                    if (start) begin
                        done <= 1'b0;
                        error <= 1'b0;
                        current_node_addr <= 8'd0;
                        depth_counter <= 8'd0;
                        state <= DECODE;
                    end
                end
                
                DECODE: begin
                    if (is_leaf) begin
                        state <= CLASSIFY;
                        vote_attack <= (node_type == 8'h01);
                    end
                    else begin
                        if (depth_counter >= MAX_DEPTH) begin
                            state <= ERROR_ST;
                            error <= 1'b1;
                        end
                        else begin
                            selector_valid <= 1'b1;
                            state <= SELECT;
                        end
                    end
                end
                
                SELECT: begin
                    if (selector_done) begin
                        if (selector_error) begin
                            state <= ERROR_ST;
                            error <= 1'b1;
                        end
                        else begin
                            compare_valid <= 1'b1;
                            state <= COMPARE;
                        end
                    end
                end
                
                COMPARE: begin
                    if (compare_done) begin
                        state <= NEXT_NODE;
                    end
                end
                
                NEXT_NODE: begin
                    current_node_addr <= next_node;
                    depth_counter <= depth_counter + 1;
                    state <= DECODE;
                end
                
                CLASSIFY: begin
                    done <= 1'b1;
                    state <= IDLE;
                end
                
                ERROR_ST: begin
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
// MODULE 6: RANDOM FOREST CLASSIFIER (TOP MODULE với Clock Counter)
// ============================================================================
module random_forest_classifier (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    
    input  wire [10:0] arb_id_dec,
    input  wire [3:0]  data_length,
    input  wire [7:0]  first_byte,
    input  wire [7:0]  last_byte,
    input  wire [10:0] byte_sum,
    input  wire [31:0] time_delta,
    
    output reg         done,
    output reg         is_attack,
    output reg  [4:0]  attack_votes,
    output reg  [4:0]  normal_votes,
    output reg         error,
    output reg  [31:0] cycle_count  // ✅ Tổng số chu kỳ clock
);

    localparam NUM_TREES = 21;
    
    localparam IDLE     = 2'd0;
    localparam SCALE    = 2'd1;
    localparam CLASSIFY = 2'd2;
    localparam VOTE     = 2'd3;
    
    reg [1:0] state;
    reg counting_active;  // Flag để kiểm soát đếm chu kỳ
    
    reg        scale_valid;
    wire       scale_done;
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
    
    reg  [20:0] tree_start;
    wire [20:0] tree_done;
    wire [20:0] tree_vote_attack;
    wire [20:0] tree_error;
    
    genvar i;
    generate
        for (i = 0; i < NUM_TREES; i = i + 1) begin : tree_array
            single_decision_tree tree (
                .clk(clk),
                .rst_n(rst_n),
                .start(tree_start[i]),
                .tree_id(i[4:0]),
                .feature_0_scaled(feature_0_scaled),
                .feature_1_scaled(feature_1_scaled),
                .feature_2_scaled(feature_2_scaled),
                .feature_3_scaled(feature_3_scaled),
                .feature_4_scaled(feature_4_scaled),
                .feature_5_scaled(feature_5_scaled),
                .done(tree_done[i]),
                .vote_attack(tree_vote_attack[i]),
                .error(tree_error[i])
            );
        end
    endgenerate
    
    reg [4:0] attack_count;
    wire all_trees_done;
    assign all_trees_done = &tree_done;
    
    integer j;
    always @(*) begin
        attack_count = 5'd0;
        for (j = 0; j < NUM_TREES; j = j + 1) begin
            if (tree_vote_attack[j])
                attack_count = attack_count + 1;
        end
    end
    
    // ✅ STATE MACHINE với Clock Cycle Counter
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            done <= 1'b0;
            is_attack <= 1'b0;
            attack_votes <= 5'd0;
            normal_votes <= 5'd0;
            error <= 1'b0;
            scale_valid <= 1'b0;
            tree_start <= 21'd0;
            cycle_count <= 32'd0;
            counting_active <= 1'b0;
        end
        else begin
            scale_valid <= 1'b0;
            tree_start <= 21'd0;
            
            // ✅ Đếm chu kỳ clock khi đang xử lý
            if (counting_active)
                cycle_count <= cycle_count + 1;
            
            case (state)
                IDLE: begin
                    done <= 1'b0;
                    error <= 1'b0;
                    if (start) begin
                        $display("\n=== Starting Random Forest at t=%0t ===", $time);
                        scale_valid <= 1'b1;
                        state <= SCALE;
                        cycle_count <= 32'd0;      // ✅ Reset counter
                        counting_active <= 1'b1;   // ✅ Bắt đầu đếm
                    end
                end
                
                SCALE: begin
                    if (scale_done) begin
                        $display("Scaling complete, starting trees at t=%0t", $time);
                        tree_start <= 21'h1FFFFF;
                        state <= CLASSIFY;
                    end
                end
                
                CLASSIFY: begin
                    if (all_trees_done) begin
                        $display("All trees done at t=%0t, tree_done=%b", $time, tree_done);
                        state <= VOTE;
                    end
                end
                
                VOTE: begin
                    attack_votes <= attack_count;
                    normal_votes <= NUM_TREES - attack_count;
                    is_attack <= (attack_count > (NUM_TREES / 2));
                    error <= |tree_error;
                    done <= 1'b1;
                    counting_active <= 1'b0;  // ✅ Dừng đếm
                    $display("=== Voting complete: Attack=%0d, Normal=%0d ===", 
                             attack_count, NUM_TREES - attack_count);
                    $display("=== Total Clock Cycles: %0d ===\n", cycle_count);
                    state <= IDLE;
                end
                
                default: state <= IDLE;
            endcase
        end
    end

endmodule

// ============================================================================
// TESTBENCH với Clock Cycle Display - Icarus Verilog Compatible
// ============================================================================
`timescale 1ns/1ps

module tb_random_forest;

    reg clk, rst_n, start;
    reg [10:0] arb_id_dec;
    reg [3:0]  data_length;
    reg [7:0]  first_byte, last_byte;
    reg [10:0] byte_sum;
    reg [31:0] time_delta;
    
    wire done, is_attack, error;
    wire [4:0] attack_votes, normal_votes;
    wire [31:0] cycle_count;  // Clock cycle counter
    
    // Instantiate DUT
    random_forest_classifier dut (
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
        .attack_votes(attack_votes),
        .normal_votes(normal_votes),
        .error(error),
        .cycle_count(cycle_count)
    );
    
    // Clock generation
    initial begin
        clk = 0;
        forever #5 clk = ~clk;  // Clock period = 10ns
    end
    
    // Timeout monitor
    initial begin
        #5000000;  // Increased timeout for Icarus
        $display("\nERROR: Simulation timeout at t=%0t!", $time);
        $display("State: done=%b, error=%b", done, error);
        $finish;
    end
    
    // Main test sequence
    initial begin
        // Initialize VCD dump for Icarus
        $dumpfile("rf_classifier.vcd");
        $dumpvars(0, tb_random_forest);
        
        // Initial reset
        rst_n = 0;
        start = 0;
        arb_id_dec = 0;
        data_length = 0;
        first_byte = 0;
        last_byte = 0;
        byte_sum = 0;
        time_delta = 0;
        
        // Apply reset
        repeat(4) @(posedge clk);
        rst_n = 1;
        repeat(2) @(posedge clk);
        
        $display("\n========================================================");
        $display("       RANDOM FOREST CLASSIFIER TEST");
        $display("========================================================");
        
        // Test case 1: Normal traffic
        $display("\n[TEST 1] Normal traffic classification");
        arb_id_dec  = 11'd241;
        data_length = 4'd12;
        first_byte  = 8'd0;
        last_byte   = 8'd0;
        byte_sum    = 11'd69;
        time_delta  = 32'd0;
        
        start = 1;
        @(posedge clk);
        start = 0;
        
        wait(done || error);
        @(posedge clk);
        
        if (!error) begin
            $display("\n--------------------------------------------------------");
            $display("RESULTS");
            $display("--------------------------------------------------------");
            $display("Classification: %s", is_attack ? "ATTACK DETECTED" : "NORMAL TRAFFIC");
            $display("Attack votes:   %2d/21", attack_votes);
            $display("Normal votes:   %2d/21", normal_votes);
            $display("--------------------------------------------------------");
            $display("Total clock cycles: %d", cycle_count);
            $display("Execution time:     %d ns", cycle_count * 10);
            $display("Throughput:         %.2f MHz", 1000.0 / (cycle_count * 10.0));
            $display("--------------------------------------------------------");
        end else begin
            $display("\nERROR: Classification failed!");
            $display("Total clock cycles before error: %0d", cycle_count);
        end
        
        // Additional test cases can be added here
        
        repeat(10) @(posedge clk);
        $display("\nTEST COMPLETED at t=%0t ns", $time);
        $finish;
    end

    // Monitor process
    initial begin
        $display("Time\tCycle\tState");
        $display("-----\t-----\t-----");
        forever begin
            @(posedge clk);
            if (start) begin
                $display("%0t\t%0d\tSTART", $time, cycle_count);
            end
            if (done) begin
                $display("%0t\t%0d\tDONE", $time, cycle_count);
            end
            if (error) begin
                $display("%0t\t%0d\tERROR", $time, cycle_count);
            end
        end
    end

endmodule